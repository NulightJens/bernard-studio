"""studio finish <project> --version N [--anyway]

Copies the final into Finished/: "<date> <title>.mp4" for a video, or a "<date> <title>" folder of slides, plus
"<date> <title> caption.txt": a caption draft made only from his words: the passage he picked, or, for a carousel made
from lines he typed (no passage), those lines word for word, one paragraph each. It never posts anything.
"""
import datetime as _dt
import re
import shutil

from . import passage as passage_mod
from . import paths
from .errors import StudioError
from .project import safe_name
from .util import say


def caption_from(text):
    """His passage as a caption draft: his sentences, tidied (spacing, a capital to start, a full stop to end)."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return ""
    t = t[0].upper() + t[1:]
    if t[-1] not in ".!?":
        t += "."
    sentences = re.split(r"(?<=[.!?])\s+", t)
    return "\n\n".join(s.strip() for s in sentences if s.strip())


def caption_for(project):
    """The passage as a caption draft; with no passage, his typed lines exactly as he typed them."""
    try:
        return caption_from(passage_mod.load(project)["text"])
    except StudioError:
        pass
    from . import lines
    return "\n\n".join(e["text"].strip("\n") for e in lines.entries(project) if e["text"].strip())


def finish(project, n, anyway=False):
    entry = project.version(n)
    qa = entry.get("qa") or {}
    if not qa:
        raise StudioError(f"Version {n} has not been checked yet. Run studio qa first.")
    if not qa.get("pass") and not anyway:
        raise StudioError(f"Version {n} does not pass every check yet. Fix it, or finish it anyway with --anyway.")
    src = project.resolve(entry["output"])
    paths.finished_folder().mkdir(parents=True, exist_ok=True)
    base = f"{_dt.date.today().isoformat()} {safe_name(project.title)}"
    stem, k = base, 2
    while any(paths.finished_folder().glob(f"{stem}*")) and k < 100:
        stem, k = f"{base} ({k})", k + 1
    if src.is_dir():
        dst = paths.finished_folder() / stem
        shutil.copytree(src, dst)
    else:
        dst = paths.finished_folder() / f"{stem}{src.suffix.lower()}"
        shutil.copy2(src, dst)
    cap = paths.finished_folder() / f"{stem} caption.txt"
    cap.write_text(caption_for(project) + "\n")
    entry["finished"] = str(dst)
    project.data["status"] = "finished"
    project.data["finished"] = {"version": int(n), "file": str(dst), "caption": str(cap)}
    project.set_version(entry)
    say(f'Done. "{dst.name}" and its caption draft are in your Finished folder.')
    return {"file": str(dst), "caption": str(cap)}
