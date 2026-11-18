"""Two ways for the wizard to look at things without writing code or knowing where the folders are.

    studio transcript "<project>" [--source <name>] [--find "<words>"]
        What he said in each video of the project, one sentence per line with its start and end time. With --find, only
        the places where those words are said (case and punctuation do not matter), each with its sentence.
    studio open drop|photos|projects|finished|folder|gallery
    studio open project "<project>"
    studio open version "<project>" [<n>]
    studio open file "<path>"
        Opens one of his folders in Finder, the examples page in his browser, a version (the video in QuickTime, the
        slides folder in Finder), or one of his own files (a cutout, a frame sheet). The folders come from STUDIO_USER,
        so nothing needs a fixed path. Everything goes through safe_to_open, the one place the open rules live.
"""
import os
import re
import subprocess
from pathlib import Path

from . import paths
from .errors import StudioError
from .project import Project, read_json
from .util import say

SENTENCE_END = re.compile(r"[.!?]['\")\]]*$")
PAUSE_S = 0.8          # a pause this long also ends a line
MAX_LINE_WORDS = 40    # a very long run with no full stop is split so each line stays readable


def _norm(w):
    return re.sub(r"[^\w']+", "", str(w).lower().replace("’", "'"))


def _sources(project, name=None):
    srcs = [s for s in project.data.get("sources") or [] if s.get("ingest") or s.get("kind") in ("video", "audio")]
    if name:
        srcs = [project.source(name)]
    if not srcs:
        raise StudioError("This project has no videos with words yet. Bring one in with studio ingest first.")
    out = []
    for s in srcs:
        f = project.path(s.get("ingest") or f"ingest/{s['name']}.json")
        if not f.exists():
            raise StudioError(f'"{s["name"]}" has not been read yet. Run studio ingest on it first.')
        out.append((s["name"], read_json(f)))
    return out


def sentences(words):
    """His words grouped into lines: a line ends at a full stop, question or exclamation mark, or a long pause."""
    lines, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        gap = (nxt["t0"] - w["t1"]) if nxt else 0
        if nxt is None or SENTENCE_END.search(w["w"]) or gap >= PAUSE_S or len(cur) >= MAX_LINE_WORDS:
            lines.append({"t0": round(cur[0]["t0"], 2), "t1": round(cur[-1]["t1"], 2),
                          "text": " ".join(x["w"] for x in cur)})
            cur = []
    return lines


def find(words, phrase):
    """Every place the phrase is said: [{t0, t1, i0, i1, words}] (word indexes are inclusive)."""
    want = [x for x in (_norm(p) for p in str(phrase).split()) if x]
    if not want:
        raise StudioError("Tell me which words to look for.")
    have = [_norm(w["w"]) for w in words]
    hits = []
    for i in range(len(have) - len(want) + 1):
        if have[i:i + len(want)] == want:
            j = i + len(want) - 1
            hits.append({"t0": round(words[i]["t0"], 2), "t1": round(words[j]["t1"], 2), "i0": i, "i1": j,
                         "words": " ".join(w["w"] for w in words[i:j + 1])})
    return hits


def _clock(s):
    m, sec = divmod(float(s), 60)
    return f"{int(m)}:{sec:04.1f}"


def transcript(project, source=None, phrase=None):
    out = []
    for name, rec in _sources(project, source):
        words = rec.get("words") or []
        lines = sentences(words)
        entry = {"source": name, "duration": rec.get("duration"), "words": len(words)}
        say(f'"{name}" ({_clock(rec.get("duration") or 0)} long):')
        if phrase is None:
            entry["lines"] = lines
            for ln in lines:
                say(f"  {_clock(ln['t0'])} to {_clock(ln['t1'])}  {ln['text']}")
            if not lines:
                say("  No words were heard in this one.")
        else:
            hits = find(words, phrase)
            for h in hits:
                h["sentence"] = next((ln["text"] for ln in lines if ln["t0"] <= h["t0"] <= ln["t1"]), h["words"])
                say(f"  {_clock(h['t0'])} to {_clock(h['t1'])}  {h['sentence']}")
            if not hits:
                say(f'  "{phrase}" is not said in this one.')
            entry["find"] = phrase
            entry["hits"] = hits
        out.append(entry)
    return {"project": project.dir.name, "sources": out}


# ----------------------------------------------------------------------------------------------- open
FOLDERS = {"drop": paths.drop_folder, "photos": paths.photos_folder, "projects": paths.projects_folder,
           "finished": paths.finished_folder, "folder": paths.user}
TARGETS = tuple(FOLDERS) + ("gallery", "project", "version", "file")


def open_rules():
    """The open rules the hook reads too (hooks/open-rules.json), so the two checks cannot drift."""
    import json
    try:
        return json.loads((paths.root() / "hooks" / "open-rules.json").read_text())
    except (OSError, ValueError):
        raise StudioError("This copy of the studio is missing a file it needs to open things. Reinstall it.")


def _within(p, root):
    return p == root or p.startswith(root.rstrip("/") + "/")


def _is_package(path):
    """True when macOS treats the folder as one item (an app, a library, any package), as Finder does. Unknown counts
    as a package, so nothing unclear is opened."""
    r = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e",
                        "function run(a){ObjC.import('AppKit');"
                        "return $.NSWorkspace.sharedWorkspace.isFilePackageAtPath(a[0]) ? 'yes' : 'no'}", str(path)],
                       capture_output=True, text=True)
    return r.returncode != 0 or r.stdout.strip() != "no"


def safe_to_open(path):
    """The real path to open, or a plain error. Only his own folders, project folders, his pictures, videos, PDFs and
    text files, and the examples page: never an app, a script or anything a double-click would run. The same rules
    as the hook (hooks/auto-allow.js), read from the same file, and never looser: an absolute path with no .. and no
    part starting with ~, inside his folder or the examples, after following every symlink."""
    refuse = StudioError("I can only open your studio folders, your projects and their videos, pictures and text.")
    raw = str(path)
    if not raw.startswith("/") or any(part == ".." or part.startswith("~") for part in raw.split("/")):
        raise refuse
    rules = open_rules()
    real = os.path.realpath(raw)
    user = os.path.realpath(str(paths.user()))
    examples = os.path.realpath(str(paths.examples_dir()))
    projects = os.path.realpath(str(paths.projects_folder()))
    if not (_within(real, user) or _within(real, examples)):
        raise refuse
    ext = os.path.splitext(os.path.basename(real).lower())[1].lstrip(".")
    if os.path.isdir(real):
        own = {user} | {os.path.join(user, f) for f in rules["studio_folders"]}
        if not (real in own or _within(real, projects) or _within(real, examples)):
            raise refuse
        if ext in rules["bundle_types"] or os.path.exists(os.path.join(real, "Contents", "Info.plist")):
            raise refuse
        if _is_package(real):
            raise refuse
        return real
    if os.path.isfile(real):
        if ext in rules["file_types"] or (ext in rules["examples_only_types"] and _within(real, examples)):
            return real
    raise refuse


def launch(path):
    """Open a file or folder the way a double-click would, after the safety check. Tests replace _run."""
    _run(["open", safe_to_open(path)])


def _run(cmd):
    subprocess.run(cmd, check=False)


def resolve_target(what, project=None, version=None):
    """The file or folder `studio open` shows, without opening it."""
    if what in FOLDERS:
        p = FOLDERS[what]()
        if what != "projects":
            p.mkdir(parents=True, exist_ok=True)
        return p
    if what == "gallery":
        g = paths.examples_dir() / "gallery.html"
        if not g.exists():
            raise StudioError("The examples page is missing from this copy of the studio.")
        return g
    if what == "file":
        if not project:
            raise StudioError('Say which file, for example: studio open file "<the file>".')
        return Path(safe_to_open(project))
    if what in ("project", "version"):
        if not project:
            raise StudioError(f'Say which project, for example: studio open {what} "<project>".')
        p = Project.find(project)
        if what == "project":
            return p.dir
        versions = p.data.get("versions") or []
        if not versions:
            raise StudioError("This project has no version yet.")
        entry = p.version(version) if version is not None else versions[-1]
        out = p.resolve(entry["output"])
        if not out.exists():
            raise StudioError(f"Version {entry['n']} is missing its file. Make it again with studio render.")
        return out
    raise StudioError(f'I can open: {", ".join(TARGETS)}. Not "{what}".')


def open_target(what, project=None, version=None):
    p = resolve_target(what, project, version)
    launch(p)
    names = {"drop": "your Drop footage here folder", "photos": "your My photos folder",
             "projects": "your Projects folder", "finished": "your Finished folder", "folder": "your studio folder",
             "gallery": "the examples page", "project": "the project folder", "file": f'"{p.name}"'}
    say(f"Opened {names.get(what, 'the version')}.")
    return {"opened": str(p), "what": what}


# ----------------------------------------------------------------------------------------------- list
def _size(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024.0


LIST_DEPTH = 2     # a folder and one level of folders inside it
LIST_MAX = 200


def list_target(what, project=None, version=None):
    """studio list <same targets as open> | studio list style <slug>: the files there, without opening anything.
    Only inside his studio folder, or a style's own guide folder and its examples; symlinks that lead out are skipped."""
    refuse = StudioError("I can only list your studio folders, your projects and the styles' own files.")
    if what == "style":
        slug = str(project or "")
        if not re.fullmatch(r"[a-z0-9-]+", slug) or slug not in paths.known_styles():
            raise StudioError(f'There is no style called "{slug}". Type studio styles to see them.')
        pairs = [(paths.root() / "skills" / f"style-{slug}", paths.root() / "skills"),
                 (paths.examples_dir() / slug, paths.examples_dir())]
    else:
        target = resolve_target(what, project, version)
        folder = target if target.is_dir() else target.parent
        pairs = [(folder, paths.examples_dir() if what == "gallery" else paths.user())]
    rows, more = [], 0
    for folder, root in pairs:
        root_real = os.path.realpath(str(root))
        real = os.path.realpath(str(folder))
        if not os.path.isdir(real):
            continue
        if not _within(real, root_real):
            raise refuse
        say(f"{folder}:")
        for f in sorted(folder.rglob("*")):
            rel = f.relative_to(folder)
            if any(part.startswith(".") for part in rel.parts) or len(rel.parts) > LIST_DEPTH:
                continue
            fr = os.path.realpath(str(f))
            if not _within(fr, real) or not os.path.isfile(fr):
                continue
            if len(rows) >= LIST_MAX:
                more += 1
                continue
            rows.append({"file": str(f), "name": str(rel), "size": os.path.getsize(fr)})
            say(f"  {rel}  ({_size(rows[-1]['size'])})")
    if more:
        say(f"  ... and {more} more files.")
    if not rows:
        say("Nothing in there yet.")
    return {"what": what, "files": rows, "more": more}


def frame(project, source, at):
    """One full-size still of a source at a moment, saved in the project folder, so Claude can look at the footage
    before choosing a style (no other tools needed)."""
    from .media import check_source, safe_input
    src = project.resolve(project.source(source)["file"])
    check_source(src)
    at = max(0.0, float(at))
    out = project.path(f"look-{source}-{at:.1f}s.png")
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{at:.3f}", *safe_input(str(src)),
                        "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:in_range=tv", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise StudioError(f'I could not take a still from "{source}" at {at:.1f} seconds.')
    say(f"Saved a still from {source} at {at:.1f} seconds.")
    return {"frame": str(out), "source": source, "at": at}

