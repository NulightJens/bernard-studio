"""Lines he typed himself (for carousels), kept exactly as he typed them.

    studio lines "<project>" --add "<his text>"     one entry per call, never edited
    studio lines "<project>"                        prints every entry

Each entry is saved in project.json ("lines": [{"at", "text"}]) and in <project>/his-lines.txt (every entry, a blank
line between them), which the "his words" check reads. A carousel with no recording renders from these lines: its
words are his typed lines plus any transcripts in the project (see words_passage).
"""
from .errors import StudioError
from .project import now


def add(project, text):
    text = str(text)
    if not text.strip():
        raise StudioError("There is nothing to save: the line is empty.")
    project.data.setdefault("lines", []).append({"at": now(), "text": text})
    project.save()
    write_file(project)
    return len(project.data["lines"]) - 1


def entries(project):
    return list(project.data.get("lines") or [])


def write_file(project):
    project.path("his-lines.txt").write_text("\n\n".join(e["text"] for e in entries(project)) + "\n")


def all_words(project):
    """His words available to a carousel without a passage: every typed line, then every ingested transcript."""
    import json
    words = []
    for e in entries(project):
        words += e["text"].split()
    for f in sorted(project.path("ingest").glob("*.json")):
        try:
            words += [w["w"] for w in json.loads(f.read_text()).get("words") or []]
        except Exception:
            continue
    return words


def words_passage(project):
    """A stand-in passage for a carousel with no recording picked: his words with no times, no voice, no picture."""
    ws = all_words(project)
    if not ws:
        raise StudioError("This carousel has no words of his yet. Save the lines he typed with studio lines --add, "
                          "or bring in one of his videos.")
    return {"source": None, "segments": [], "duration": 0.0, "text": " ".join(ws), "voice": None, "picture": None,
            "words": [{"i": i, "w": w, "t0": 0.0, "t1": 0.0} for i, w in enumerate(ws)], "typed": True}
