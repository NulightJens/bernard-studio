"""The leftover-caption check every carousel style runs in its QA: text detection (Apple Vision) on every finished
slide. Text the style set itself is fine; text inside a picture is fine (a screen, a template on a phone, a book cover);
text that matches the burned-in captions of one of his source videos fails, and so does any caption found on the
source frame itself inside the part of it the slide shows. An overlay of every detected box is saved next to
qa.json as evidence: green = the slide's own text, grey = text inside a picture, red = leftover caption text.

    from slides import captions
    checks = {"no_old_captions": captions.check(project, version_dir, layout, slide_files)}
"""
import json
import re

import numpy as np

from slides.pictures import caption_band, said_run, text_boxes

TOK = re.compile(r"[a-z0-9$%']+")


def tokens(s):
    return TOK.findall(s.lower().replace("’", "'"))


def caption_texts(project):
    """Every line of burned-in caption the ingest read (once a second), per video source: text in the caption band
    or text that repeats what he says at that moment. Returns ({source: [token lists]}, {video source names})."""
    from slides.pictures import caption_like
    lines, said = {}, {}
    for f in sorted(project.path("ingest").glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except Exception:
            continue
        cap = rec.get("captions") or {}
        if not cap.get("samples") or not rec.get("video"):
            continue
        name = rec["name"]
        said[name] = name
        H = 1000.0
        for smp in cap["samples"]:
            boxes = [dict(b, y=b["y"] * H, h=b["h"] * H) for b in smp["boxes"]]
            band = cap.get("band")
            found = ([b for b in boxes if band["y"] - 0.02 <= (b["y"] + b["h"] / 2) / H <= band["y"] + band["h"] + 0.02]
                     if band else caption_like(project, name, boxes, H, None, t=smp["t"]))
            for b in found:
                lines.setdefault(name, []).append(tokens(b["text"]))
    return lines, said


def _grams(toks, n):
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def is_caption(text, caps, cap2=None):
    """True when a detected line looks like one of the caption lines: the same line, or two words in a row from one
    (with at least one word of four letters or more)."""
    t = tokens(text)
    if not t:
        return False
    joined = " ".join(t)
    for c in caps:
        if len(joined) >= 6 and joined in " ".join(c):
            return True
    if len(t) >= 2:
        cap2 = cap2 if cap2 is not None else set().union(*[_grams(c, 2) for c in caps]) if caps else set()
        for g in _grams(t, 2):
            if g in cap2 and max(len(x) for x in g) >= 4:
                return True
    return False


def _inside(b, boxes, pad=10):
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    return any(x - pad <= cx <= x + w + pad and y - pad <= cy <= y + h + pad for x, y, w, h in boxes)


def _frame_h(project, source):
    try:
        return float(json.loads(project.path("ingest", f"{source}.json").read_text())["video"]["h"])
    except Exception:
        return None


def source_captions_shown(project, p):
    """Captions detected on the source frame itself (at the moment the picture was taken) that fall inside the part
    of the frame the slide shows: [(text, slide box)]. Independent of how the slide's own text detection reads them."""
    from slides.pictures import caption_like, frame
    if p.get("t") is None or not p.get("crop"):
        return []
    try:
        img = frame(project, p["source"], p["t"])
    except Exception:
        return []
    H = img.shape[0]
    x0, y0, x1, y1 = p["crop"]
    bx, by, bw, bh = p["box"]
    sx, sy = bw / max(1, x1 - x0), bh / max(1, y1 - y0)
    out = []
    for c in caption_like(project, p["source"], text_boxes(img, "accurate"), H, t=p["t"]):
        ix0, iy0 = max(x0, c["x"]), max(y0, c["y"])
        ix1, iy1 = min(x1, c["x"] + c["w"]), min(y1, c["y"] + c["h"])
        if ix1 - ix0 > 2 and iy1 - iy0 > 2:
            out.append((c["text"], [bx + (ix0 - x0) * sx, by + (iy0 - y0) * sy, bx + (ix1 - x0) * sx, by + (iy1 - y0) * sy]))
    return out


def _in_picture(b, pics):
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    return [p for p in pics if p["box"][0] <= cx <= p["box"][0] + p["box"][2] and p["box"][1] <= cy <= p["box"][1] + p["box"][3]]


def check(project, vdir, layout, slide_files):
    from PIL import Image, ImageDraw
    lines, said = caption_texts(project)
    caps = [c for v in lines.values() for c in v]
    cap2 = set().union(*[_grams(c, 2) for c in caps]) if caps else set()
    own, pics = {}, {}
    for b in layout["beats"]:
        own.setdefault(b.get("slide"), []).extend(t["box"] for t in b["texts"])
    for p in layout.get("pictures", []):
        pics.setdefault(p["slide"], []).append(p)
    out_dir = vdir / "qa" / "captions"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, bad = [], []
    for f in slide_files:
        img = np.asarray(Image.open(f).convert("RGB"))
        found = text_boxes(img, "accurate")
        if found is None:
            return {"pass": True, "warn": True, "note": "Text detection is not available on this Mac, so slides were "
                                                        "not checked for old captions."}
        ov = Image.fromarray(img).convert("RGB")
        d = ImageDraw.Draw(ov)
        left, pic = [], 0
        for b in found:
            t = tokens(b["text"])
            if b["conf"] < 0.3 or not t:
                continue
            box = [b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]]
            if _inside(b, own.get(f.name, [])):
                d.rectangle(box, outline=(40, 170, 80), width=3)
                continue
            inside = _in_picture(b, pics.get(f.name, []))
            banded = [p for p in inside if caption_band(project, p["source"])]
            # inside a picture from a video with a fixed band, where the text sits decides (a book cover can carry the
            # same words as the caption); anywhere else, the words decide
            hit = (not banded) and bool(caps) and is_caption(b["text"], caps, cap2)
            for p in inside:                                       # his own words, burned into his own footage
                band = caption_band(project, p["source"])
                if band and p.get("crop"):                          # a fixed band: is this text inside it?
                    x0, y0, x1, y1 = p["crop"]
                    sy = y0 + (b["y"] + b["h"] / 2 - p["box"][1]) / p["box"][3] * (y1 - y0)
                    fh = _frame_h(project, p["source"])
                    rel = sy / fh if fh else -1
                    hit = hit or band["y"] - 0.02 <= rel <= band["y"] + band["h"] + 0.02
                    continue
                if p["source"] in said and p.get("t") is not None:
                    run = said_run(project, p["source"], p["t"])
                    letters = "".join(t)
                    hit = hit or (len(letters) >= 2 and letters in run and (len(letters) >= 5 or b["h"] >= 18))
            if hit:
                d.rectangle(box, outline=(220, 30, 30), width=5)
                left.append(b["text"])
            else:
                d.rectangle(box, outline=(130, 130, 130), width=2)
                pic += 1
        for p in pics.get(f.name, []):
            for cb in source_captions_shown(project, p):
                d.rectangle(cb[1], outline=(220, 30, 30), width=5)
                left.append(f"caption on the source frame at {p['t']} s shown in the picture: {cb[0]}")
        ov.save(out_dir / f.name)
        rows.append({"slide": f.name, "leftover_captions": left, "text_in_pictures": pic})
        bad += [f"{f.name}: {t}" for t in left]
    return {"pass": not bad, "leftover": bad, "slides": rows, "caption_lines_known": len(caps),
            "overlays": f"{vdir.name}/qa/captions"}
