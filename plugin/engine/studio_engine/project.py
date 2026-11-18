"""One project = one folder under Projects/ with project.json, the record every command updates (CONTRACT section 4).

project.json: {title, kind, style, created, updated, sources:[{name, file, kind}], passage, versions:[{n, spec, output,
qa, notes_applied}], notes:[{at, text, applied_in}], status}. His notes are never deleted.
"""
import datetime as _dt
import json
import os
import re
import tempfile
from pathlib import Path

from . import paths
from .errors import StudioError

KINDS = ("reel", "carousel", "animated")


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def safe_name(title):
    t = re.sub(r"[/:\\\0]", "-", str(title)).strip().strip(".")
    t = re.sub(r"\s+", " ", t)
    return t[:80] or "Untitled"


def write_json(path, data):
    """Write JSON atomically, so a stopped command never leaves half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path):
    return json.loads(Path(path).read_text())


def within(path, folder):
    """True when path's real location (every symlink followed) is the folder or inside it."""
    p, root = os.path.realpath(str(path)), os.path.realpath(str(folder))
    return p == root or p.startswith(root.rstrip("/") + "/")


def in_projects(folder):
    """A project folder sits directly in his Projects folder, after following every symlink."""
    real = os.path.realpath(str(folder))
    return os.path.dirname(real) == os.path.realpath(str(paths.projects_folder()))


class Project:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.file = self.dir / "project.json"
        if not self.file.exists():
            raise StudioError(f'I could not find a project at "{self.dir.name}". Type studio projects to see them.')
        self.data = read_json(self.file)

    # ------------------------------------------------------------------ create and find
    @classmethod
    def new(cls, title, kind="reel", style=None):
        if kind not in KINDS:
            raise StudioError(f'The kind must be one of {", ".join(KINDS)}, not "{kind}".')
        paths.ensure_user_folders()
        day = _dt.date.today().isoformat()
        base = paths.projects_folder() / f"{day} {safe_name(title)}"
        folder, k = base, 2
        while folder.exists():
            folder = base.with_name(f"{base.name} ({k})")
            k += 1
        for sub in paths.PROJECT_DIRS:
            (folder / sub).mkdir(parents=True, exist_ok=True)
        data = {"title": str(title), "kind": kind, "style": style, "created": now(), "updated": now(), "sources": [],
                "passage": None, "versions": [], "notes": [], "status": "new"}
        write_json(folder / "project.json", data)
        return cls(folder)

    @classmethod
    def find(cls, ref):
        """A project from its folder name, a unique part of its name, or a path to its folder. Only folders that sit
        directly in his Projects folder count (real path checked), so a path can never point the studio elsewhere."""
        root = paths.projects_folder()
        ref = str(ref)
        tries = [root / ref]
        if ref.startswith(("/", "~")):
            tries.insert(0, Path(ref).expanduser())
        for d in tries:
            if (d / "project.json").exists():
                if not in_projects(d):
                    raise StudioError("I only work on projects inside your Projects folder. "
                                      "Type studio projects to see them.")
                return cls(d)
        want = ref.lower()
        hits = [d for d in sorted(root.glob("*")) if (d / "project.json").exists() and want in d.name.lower()
                and in_projects(d)]
        if len(hits) == 1:
            return cls(hits[0])
        if len(hits) > 1:
            names = "; ".join(d.name for d in hits[:6])
            raise StudioError(f'More than one project matches "{ref}": {names}. Use the full name.')
        raise StudioError(f'I could not find a project called "{ref}". Type studio projects to see them.')

    @staticmethod
    def all():
        root = paths.projects_folder()
        out = []
        for d in sorted(root.glob("*")):
            if (d / "project.json").exists() and in_projects(d):
                try:
                    out.append(Project(d))
                except Exception:
                    continue
        return out

    # ------------------------------------------------------------------ record
    def save(self):
        self.data["updated"] = now()
        write_json(self.file, self.data)

    @property
    def title(self):
        return self.data["title"]

    @property
    def kind(self):
        return self.data["kind"]

    def path(self, *parts):
        return self.dir.joinpath(*parts)

    def rel(self, p):
        """A path inside the project, written relative to the project folder (what project.json stores)."""
        p = Path(p)
        try:
            return str(p.resolve().relative_to(self.dir.resolve()))
        except ValueError:
            return str(p)

    def resolve(self, rel):
        p = Path(rel)
        return p if p.is_absolute() else self.dir / p

    def source(self, name):
        for s in self.data["sources"]:
            if s["name"] == name:
                return s
        names = ", ".join(s["name"] for s in self.data["sources"]) or "none yet"
        raise StudioError(f'This project has no source called "{name}". Sources: {names}.')

    def add_source(self, entry):
        self.data["sources"] = [s for s in self.data["sources"] if s["name"] != entry["name"]] + [entry]
        if self.data["status"] == "new":
            self.data["status"] = "ingested"
        self.save()

    def version_dir(self, n):
        return self.dir / f"v{int(n)}"

    def next_version(self):
        used = [v["n"] for v in self.data["versions"]]
        k = 1
        while k in used or self.version_dir(k).exists():
            k += 1
        return k

    def version(self, n):
        for v in self.data["versions"]:
            if v["n"] == int(n):
                return v
        raise StudioError(f"Version {n} of this project has not been made yet.")

    def set_version(self, entry):
        self.data["versions"] = [v for v in self.data["versions"] if v["n"] != entry["n"]] + [entry]
        self.data["versions"].sort(key=lambda v: v["n"])
        self.save()

    def add_note(self, text):
        self.data["notes"].append({"at": now(), "text": str(text), "applied_in": None})
        self.save()
        return len(self.data["notes"]) - 1

    def open_notes(self):
        return [i for i, n in enumerate(self.data["notes"]) if n.get("applied_in") is None]

    def log_file(self, name):
        (self.dir / "logs").mkdir(exist_ok=True)
        return self.dir / "logs" / name

    def summary(self):
        last = self.data["versions"][-1] if self.data["versions"] else None
        return {"folder": str(self.dir), "name": self.dir.name, "title": self.title, "kind": self.kind,
                "style": self.data.get("style"), "status": self.data.get("status"),
                "last_version": last["n"] if last else None,
                "last_qa_pass": (last.get("qa") or {}).get("pass") if last else None,
                "open_notes": len(self.open_notes()), "updated": self.data.get("updated")}
