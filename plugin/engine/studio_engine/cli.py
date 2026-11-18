"""The `studio` command (Python side). bin/studio handles doctor, install and needs in bash and sends the rest here.

Every command prints short plain progress lines; with --json the last line of stdout is one JSON object for Claude
({"ok": true, ...} or {"ok": false, "error": "..."}). Errors are one plain sentence and a non-zero exit code; details go
to the project's logs folder (or STUDIO_HOME/logs).
"""
import argparse
import json
import subprocess
import sys
import traceback

from . import paths
from .errors import StudioError
from .util import say, set_json

USAGE = """studio <command> ...
  new "<title>" [--kind reel|carousel|animated]
  projects
  ingest <project> <file-or-link>... [--link] [--no-scan]
  passage <project> --source <name> --from "<first words>" --to "<last words>" [--from .. --to ..] [--gap s]
  passage <project> --source <name> --t0 <s> --t1 <s> [--t0 .. --t1 ..]
  fix-word <project> "<heard>" "<said>" [--source <name>] [--at <seconds>] [--all]
  voice <project> [--method auto|ffmpeg|auphonic]
  matte <project> [--source <name>] [--t0 s] [--t1 s] [--fps n] [--frames n] [--cutouts]
  matte-photo <file> [--name <pose name>] [--cut-y px] [--grade none|bright|warm|kit|dark-room]
  render <project> --spec <spec.json> [--version N] [--notes 0,2] [--no-qa]
  qa <project> --version N
  finish <project> --version N [--anyway]
  note <project> "<his note>"
  lines <project> [--add "<lines he typed>"]
  transcript <project> [--source <name>] [--find "<words>"]
  open drop|photos|projects|finished|folder|gallery | open project <project> | open version <project> [N]
  open file "<path>"      (one of his own pictures, videos, PDFs or text files)
  list <the same as open> | list style <slug>      (the files there, nothing opened)
  styles | gallery | sounds
  brand get [<key>] | brand set <key> <value>
  doctor | install <component> | needs <slug> | needs --all     (handled by the setup scripts)
Add --json for one JSON object on the last line."""


def _project(ref):
    from .project import Project
    return Project.find(ref)


def cmd_new(a):
    from .project import Project
    p = Project.new(a.title, a.kind)
    say(f'Made the project "{p.dir.name}".')
    return {"project": p.dir.name, "folder": str(p.dir)}


def cmd_projects(a):
    from .project import Project
    rows = [p.summary() for p in Project.all()]
    unfinished = sorted([r for r in rows if r["status"] != "finished"], key=lambda r: r["updated"] or "", reverse=True)
    finished = sorted([r for r in rows if r["status"] == "finished"], key=lambda r: r["updated"] or "", reverse=True)
    rows = unfinished + finished
    if not rows:
        say("No projects yet.")
    for r in rows:
        v = f"version {r['last_version']}" if r["last_version"] else "no version yet"
        say(f"{r['name']}: {r['style'] or 'no style yet'}, {v}, {r['status']}")
    return {"projects": rows}


def cmd_ingest(a):
    from .ingest import ingest
    p = _project(a.project)
    recs = ingest(p, a.items, link=a.link, scan=not a.no_scan)
    return {"project": p.dir.name, "sources": [{"name": r["name"], "kind": r["kind"], "duration": r.get("duration"),
                                                 "words": len(r.get("words") or []),
                                                 "caption_band": (r.get("captions") or {}).get("band"),
                                                 "text": (r.get("text") or "")[:4000]} for r in recs]}


def cmd_passage(a):
    from .passage import build
    p = _project(a.project)
    froms, tos, t0s, t1s = a.frm or [], a.to or [], a.t0 or [], a.t1 or []
    if len(froms) != len(tos):
        raise StudioError("Every --from needs a --to.")
    if len(t0s) != len(t1s):
        raise StudioError("Every --t0 needs a --t1.")
    d = build(p, a.source, list(zip(froms, tos)), list(zip(t0s, t1s)), gap=a.gap)
    return {"project": p.dir.name, "passage": "passage/passage.json", "duration": d["duration"], "text": d["text"],
            "words": len(d["words"]), "segments": d["segments"], "align": d["align"]}


def cmd_fix_word(a):
    from .fixword import fix_word
    p = _project(a.project)
    return dict(fix_word(p, a.heard, a.said, a.source, a.at, a.all), project=p.dir.name)


def cmd_voice(a):
    from .voice import clean
    p = _project(a.project)
    return dict(clean(p, a.method), project=p.dir.name)


def cmd_matte(a):
    from .matte import matte_clip
    p = _project(a.project)
    return matte_clip(p, a.source, a.t0, a.t1, a.fps, a.frames, True if a.cutouts else None)


def cmd_matte_photo(a):
    from .matte import matte_photo
    return matte_photo(a.file, a.name, a.cut_y, a.grade)


def cmd_render(a):
    from .render import render
    p = _project(a.project)
    notes = [int(x) for x in a.notes.split(",") if x.strip()] if a.notes is not None else None
    e = render(p, a.spec, a.version, notes, run_qa=not a.no_qa)
    return {"project": p.dir.name, "version": e["n"], "output": str(p.resolve(e["output"])),
            "qa": e.get("qa"), "sheet": str(p.resolve(f"v{e['n']}/sheet.png"))}


def cmd_qa(a):
    from .qa import run
    p = _project(a.project)
    rep = run(p, a.version)
    return {"project": p.dir.name, "version": a.version, "pass": rep["pass"],
            "failed": [k for k, c in rep["checks"].items() if not c.get("pass", True)],
            "warnings": rep["warnings"], "qa": str(p.resolve(f"v{a.version}/qa.json")),
            "sheet": str(p.resolve(f"v{a.version}/sheet.png"))}


def cmd_finish(a):
    from .finish import finish
    p = _project(a.project)
    return dict(finish(p, a.version, a.anyway), project=p.dir.name)


def cmd_note(a):
    p = _project(a.project)
    k = p.add_note(a.text)
    say("Noted. The next version will carry it.")
    return {"project": p.dir.name, "note": k, "open_notes": p.open_notes()}


def cmd_lines(a):
    from . import lines
    p = _project(a.project)
    if a.add is not None:
        lines.add(p, a.add)
        say("Saved his lines exactly as he typed them.")
    rows = lines.entries(p)
    if a.add is None:
        for i, e in enumerate(rows):
            say(f"{i + 1}. {e['text']}")
        if not rows:
            say("No typed lines in this project yet.")
    return {"project": p.dir.name, "lines": rows}


def cmd_frame(a):
    from .browse import frame
    return frame(_project(a.project), a.source, a.at)


def cmd_transcript(a):
    from .browse import transcript
    return transcript(_project(a.project), a.source, a.find)


def _target_args(a):
    rest = list(a.rest or [])
    project = rest[0] if rest else None
    version = None
    if len(rest) > 1:
        try:
            version = int(rest[1])
        except ValueError:
            raise StudioError(f'"{rest[1]}" is not a version number.')
    return project, version


def cmd_open(a):
    from .browse import open_target
    return open_target(a.what, *_target_args(a))


def cmd_list(a):
    from .browse import list_target
    if a.what == "style":
        return list_target("style", (a.rest or [None])[0])
    return list_target(a.what, *_target_args(a))


def styles_list():
    f = paths.styles_json()
    rows = []
    if f.exists():
        data = json.loads(f.read_text())
        rows = data.get("styles", data) if isinstance(data, dict) else data
    else:
        rows = [{"slug": d.name} for d in sorted(paths.styles_dir().glob("*")) if (d / "render.py").exists()]
    out = []
    for r in rows:
        if str(r.get("slug", "")).startswith("_"):
            continue
        r = dict(r)
        r["ready"] = (paths.style_dir(r["slug"]) / "render.py").exists()
        out.append(r)
    return out


def cmd_styles(a):
    rows = styles_list()
    for r in rows:
        say(f"{r.get('name', r['slug'])} ({r.get('kind', '')}): {r.get('what', '')}".rstrip(": "))
    return {"styles": rows}


def cmd_gallery(a):
    g = paths.examples_dir() / "gallery.html"
    if not g.exists():
        raise StudioError("The examples page is missing from this copy of the studio.")
    subprocess.run(["open", str(g)])
    say("Opened the examples page.")
    return {"gallery": str(g)}


def cmd_sounds(a):
    from .sound import names
    n = names()
    say("Effects: " + ", ".join(n["effects"]))
    say("Music beds: " + ", ".join(n["beds"]))
    return n


def cmd_brand(a):
    from . import brand
    if a.action == "get":
        v = brand.get(a.key)
        if not a.json:
            print(json.dumps(v, indent=1) if isinstance(v, (dict, list)) else v)
        return {"key": a.key, "value": v}
    if a.key is None or a.value is None:
        raise StudioError('Say which setting and its new value, for example: studio brand set captions.size 70')
    v = brand.set_value(a.key, a.value)
    say(f"Saved {a.key} = {v}.")
    return {"key": a.key, "value": v}


def parser():
    ap = argparse.ArgumentParser(prog="studio", usage=USAGE, add_help=False)
    ap.add_argument("-h", "--help", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("new")
    s.add_argument("title")
    s.add_argument("--kind", default="reel")
    sub.add_parser("projects")
    s = sub.add_parser("ingest")
    s.add_argument("project")
    s.add_argument("items", nargs="+")
    s.add_argument("--link", action="store_true", help="link the file instead of copying it")
    s.add_argument("--no-scan", action="store_true")
    s = sub.add_parser("passage")
    s.add_argument("project")
    s.add_argument("--source", required=True)
    s.add_argument("--from", dest="frm", action="append")
    s.add_argument("--to", action="append")
    s.add_argument("--t0", action="append", type=float)
    s.add_argument("--t1", action="append", type=float)
    s.add_argument("--gap", type=float, default=0.30)
    s = sub.add_parser("fix-word")
    s.add_argument("project")
    s.add_argument("heard")
    s.add_argument("said")
    s.add_argument("--source")
    s.add_argument("--at", type=float)
    s.add_argument("--all", action="store_true")
    s = sub.add_parser("voice")
    s.add_argument("project")
    s.add_argument("--method", default="auto", choices=["auto", "ffmpeg", "auphonic"])
    s = sub.add_parser("matte")
    s.add_argument("project")
    s.add_argument("--source")
    s.add_argument("--t0", type=float)
    s.add_argument("--t1", type=float)
    s.add_argument("--fps", type=float)
    s.add_argument("--frames", type=int)
    s.add_argument("--cutouts", action="store_true")      # also keep full-colour cutouts (rgba/p*.png)
    s = sub.add_parser("matte-photo")
    s.add_argument("file")
    s.add_argument("--name")
    s.add_argument("--cut-y", type=int)
    s.add_argument("--grade", default="none")
    s = sub.add_parser("render")
    s.add_argument("project")
    s.add_argument("--spec", required=True)
    s.add_argument("--version", type=int)
    s.add_argument("--notes")
    s.add_argument("--no-qa", action="store_true")
    s = sub.add_parser("qa")
    s.add_argument("project")
    s.add_argument("--version", type=int, required=True)
    s = sub.add_parser("finish")
    s.add_argument("project")
    s.add_argument("--version", type=int, required=True)
    s.add_argument("--anyway", action="store_true")
    s = sub.add_parser("note")
    s.add_argument("project")
    s.add_argument("text")
    s = sub.add_parser("lines")
    s.add_argument("project")
    s.add_argument("--add")
    s = sub.add_parser("frame")
    s.add_argument("project")
    s.add_argument("--source", required=True)
    s.add_argument("--at", type=float, required=True)
    s = sub.add_parser("transcript")
    s.add_argument("project")
    s.add_argument("--source")
    s.add_argument("--find")
    for name in ("open", "list"):
        s = sub.add_parser(name)
        s.add_argument("what")
        s.add_argument("rest", nargs="*")
    sub.add_parser("styles")
    sub.add_parser("gallery")
    sub.add_parser("sounds")
    s = sub.add_parser("brand")
    s.add_argument("action", choices=["get", "set"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    return ap


COMMANDS = {"new": cmd_new, "projects": cmd_projects, "ingest": cmd_ingest, "passage": cmd_passage,
            "fix-word": cmd_fix_word,
            "voice": cmd_voice, "matte": cmd_matte, "matte-photo": cmd_matte_photo, "render": cmd_render,
            "qa": cmd_qa, "finish": cmd_finish, "note": cmd_note, "lines": cmd_lines,
            "transcript": cmd_transcript, "frame": cmd_frame, "open": cmd_open, "list": cmd_list, "styles": cmd_styles, "gallery": cmd_gallery,
            "sounds": cmd_sounds, "brand": cmd_brand}


def _log_error(a, exc):
    """Write the traceback where the plain message says it is."""
    try:
        if getattr(a, "project", None):
            p = _project(a.project)
            f = p.log_file("errors.log")
        else:
            paths.home_logs().mkdir(parents=True, exist_ok=True)
            f = paths.home_logs() / "studio.log"
        with open(f, "a") as h:
            h.write(f"$ studio {' '.join(sys.argv[1:])}\n")
            traceback.print_exception(exc, file=h)
            if exc.__cause__ is not None:
                h.write(f"cause: {exc.__cause__!r}\n")
        return f
    except Exception:
        return None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [x for x in argv if x != "--json"]
    set_json(as_json)
    paths.configure_env()
    ap = parser()
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if argv[0] in ("doctor", "install", "needs"):
        print("Setup commands run through the studio launcher (bin/studio), not the engine.")
        return 2
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        print(f"I did not understand that. {USAGE.splitlines()[0]}")
        return 2
    a.json = as_json
    try:
        res = COMMANDS[a.cmd](a) or {}
        if as_json:
            print(json.dumps(dict({"ok": True}, **res), default=str))
        return 0
    except StudioError as e:
        _log_error(a, e)
        print(str(e))
        if as_json:
            print(json.dumps({"ok": False, "error": str(e)}))
        return e.code or 1
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except Exception as e:
        f = _log_error(a, e)
        msg = "Something went wrong inside the studio." + (f" The details are in {f}." if f else "")
        print(msg)
        if as_json:
            print(json.dumps({"ok": False, "error": msg}))
        return 1
