"""Beats anchored to his words, and the layout record QA reads.

resolve_at(at, words): a spec's "at" -> seconds on the passage clock.
    {"word": 7}                               start of word 7
    {"word": 7, "edge": "end"}                end of word 7
    {"word": 7, "edge": "end", "offset": -0.1}
    {"t": 1.2}                                seconds, last resort
    7  or  1.2                                shorthand for {"word": 7} / {"t": 1.2}

Layout: every renderer writes v<N>/layout.json through this writer, so QA can check safe zones, the one red and his
words without reading pixels.
    lay = Layout(kind="reel", w=1080, h=1920, labels=["THEN", "NOW"])
    b = lay.beat(kind="figure", t0=3.1, t1=5.4, i=0)
    lay.text(b, "$40,000", box=(140, 700, 800, 210), role="figure", color="#F5F5F5")
    lay.text(b, "AGENCY", box=..., role="label", color="#B91C1C", red=True)
    lay.mark(b, "brush underline", box=..., red=True)        # a red element that is not text
    lay.save(version_dir / "layout.json")
Text roles: "words" (his words: captions, figures, quotes) and "label" (the style's fixed labels). Anything not a
label is checked against the passage.
"""
import json
from pathlib import Path

from .errors import StudioError
from .project import write_json

RED_HEX = ("#B91C1C", "#C42727")


def resolve_at(at, words, duration=None, field="at"):
    if at is None:
        raise StudioError(f'A beat is missing its "{field}" time.')
    if isinstance(at, bool):
        raise StudioError(f'"{field}" must be a word number or a time, not true or false.')
    if isinstance(at, int):
        at = {"word": at}
    elif isinstance(at, float):
        at = {"t": at}
    if not isinstance(at, dict):
        raise StudioError(f'"{field}" must look like {{"word": 7}} or {{"t": 1.2}}.')
    off = float(at.get("offset", 0.0))
    if "word" in at:
        i = at["word"]
        if not isinstance(i, int) or i < 0 or i >= len(words):
            raise StudioError(f'"{field}" points at word {i}, but the passage has words 0 to {len(words) - 1}.')
        edge = at.get("edge", "start")
        if edge not in ("start", "end", "mid"):
            raise StudioError(f'"{field}" edge must be "start", "end" or "mid", not "{edge}".')
        w = words[i]
        t = w["t0"] if edge == "start" else w["t1"] if edge == "end" else (w["t0"] + w["t1"]) / 2
    elif "t" in at:
        t = float(at["t"])
    else:
        raise StudioError(f'"{field}" needs a "word" or a "t".')
    t += off
    if duration is not None:
        t = min(max(0.0, t), duration)
    return round(t, 4)


class Layout:
    def __init__(self, kind, w, h, labels=(), fps=None):
        self.data = {"kind": kind, "format": {"w": int(w), "h": int(h), "fps": fps}, "labels": list(labels),
                     "beats": []}

    def beat(self, kind, t0, t1=None, i=None, slide=None, **extra):
        b = {"i": len(self.data["beats"]) if i is None else i, "kind": kind, "t0": round(float(t0), 3),
             "t1": round(float(t1 if t1 is not None else t0), 3), "texts": [], "marks": []}
        if slide is not None:
            b["slide"] = slide
        b.update(extra)
        self.data["beats"].append(b)
        return b

    def text(self, beat, text, box, role="words", color=None, red=None, font=None, size=None):
        x, y, w, h = [round(float(v), 1) for v in box]
        col = (color or "").upper() or None
        beat["texts"].append({"text": str(text), "box": [x, y, w, h], "role": role, "color": col,
                              "red": bool(red) if red is not None else (col in RED_HEX), "font": font, "size": size})

    def mark(self, beat, what, box, red=True, color=None):
        x, y, w, h = [round(float(v), 1) for v in box]
        beat["marks"].append({"what": what, "box": [x, y, w, h], "red": bool(red), "color": (color or "").upper() or None})

    def save(self, path):
        write_json(Path(path), self.data)
        return path


def load(path):
    p = Path(path)
    if not p.exists():
        raise StudioError("This version has no layout record, so its text cannot be checked.")
    return json.loads(p.read_text())


def text_box(draw_font, text, x, y, anchor="ls", tracking=0.0):
    """Box (x, y, w, h) a line of text covers when drawn with PIL at (x, y) with `anchor`; tracking is a fraction of
    the font size added between letters."""
    l, t, r, b = draw_font.getbbox(text, anchor=anchor)
    extra = tracking * draw_font.size * max(0, len(text) - 1)
    if anchor[0] == "m":
        l, r = l - extra / 2, r + extra / 2
    elif anchor[0] == "r":
        l -= extra
    else:
        r += extra
    return (x + l, y + t, r - l, b - t)
