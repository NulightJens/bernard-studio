"""Pictures for slides from his own videos: full-size frames, sharp-frame picks and crops clear of burned-in captions.

    from slides import pictures
    img = pictures.frame(project, "my-tiktok", 12.5)                 # RGB array at the video's own size
    box = pictures.clear_crop(project, "my-tiktok", img, 1080 / 1350)  # (x0, y0, x1, y1) with no caption inside
    pic = pictures.picture(project, {"source": "my-tiktok", "t": 12.5}, 1080, 1350)   # crop + resize in one go

A picture spec is {"source": <name>, "t": <seconds>} (a frame of his video) or {"source": <name>} for a photo he
added, plus optional "zoom" (1 = the widest clear crop), "x" and "y" (0..1, where the crop sits: 0 flush left or top,
1 flush right or bottom, like CSS object-position).
"""
import json
import re
import subprocess

import numpy as np

from studio_engine.errors import StudioError
from studio_engine.media import safe_input

MARGIN = 0.02          # extra room kept around a caption band (share of the frame height)


def _ingest(project, source):
    f = project.path("ingest", f"{source}.json")
    return json.loads(f.read_text()) if f.exists() else {}


def source_file(project, source):
    try:
        return project.resolve(project.source(source)["file"])
    except Exception as e:
        raise StudioError(f'The source "{source}" is not in this project.') from e


def frame(project, source, t=None):
    """A frame of a video (or the photo itself) at full size, RGB."""
    from PIL import Image, ImageOps
    f = source_file(project, source)
    rec = project.source(source)
    if rec.get("kind") == "image":
        return np.asarray(ImageOps.exif_transpose(Image.open(f)).convert("RGB"))
    if t is None:
        raise StudioError(f'Say which moment of "{source}" to use (its "t" in seconds).')
    import io
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{float(t):.3f}", *safe_input(str(f)),
                        "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:in_range=tv", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise StudioError(f'I could not take the frame at {t} seconds from "{source}".')
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"))


def caption_band(project, source):
    """The burned-in caption band the ingest found (0..1 of the frame, top-left origin), or None."""
    return ((_ingest(project, source).get("captions") or {}).get("band"))


def text_boxes(img, level="fast"):
    """Apple Vision text boxes on one picture, in pixels: [{"x", "y", "w", "h", "text", "conf"}]."""
    try:
        from ocrmac import ocrmac
        from PIL import Image
    except Exception:
        return None
    H, W = img.shape[:2]
    try:
        res = ocrmac.OCR(Image.fromarray(img), recognition_level=level).recognize()
    except Exception:
        return None
    return [{"x": x * W, "y": (1 - y - h) * H, "w": w * W, "h": h * H, "text": t, "conf": float(c)}
            for t, c, (x, y, w, h) in res]


TOK = re.compile(r"[a-z0-9$%']+")


def tokens(s):
    return TOK.findall(s.lower().replace("\u2019", "'"))


def said_pairs(project, source, t=None, window=3.0):
    """The two-word pairs and the words he says in this source (burned-in captions repeat what he says), or only
    around moment t (seconds) when it is given: captions show the words of that moment."""
    ws = _ingest(project, source).get("words") or []
    if t is not None:
        ws = [x for x in ws if t - window <= x.get("t0", 0) <= t + window]
    w = tokens(" ".join(x["w"] for x in ws))
    return set(zip(w, w[1:])), set(w)


def said_run(project, source, t, window=3.0):
    """What he says around moment t, letters and digits only, no spaces (burned-in captions often lose their spaces
    when read back: "Captureideas")."""
    ws = _ingest(project, source).get("words") or []
    tk = tokens(" ".join(x["w"] for x in ws if t - window <= x.get("t0", 0) <= t + window))
    return "".join(tk) + "|" + "".join(NUMBERS.get(x, x) for x in tk)      # also with "three" read as "3"


NUMBERS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
NEAR_BAND = 0.10       # caption graphics (a big keyword, a list number) sit just above or below the caption band


def caption_like(project, source, boxes, H, band=None, said=None, t=None):
    """The text boxes on a frame of this source that are burned-in captions: inside the caption band the ingest
    found; or, for a video with no fixed band (captions that move around), text that spells out what he says around
    moment t (spaces ignored; short words only when big), or without a moment two words in a row from anything he
    says in the source (one of four letters or more)."""
    band = band if band is not None else caption_band(project, source)
    if t is None:
        pairs, _ = said if said is not None else said_pairs(project, source)
    else:
        run = said_run(project, source, t)
    out = []
    for b in boxes or []:
        tk = tokens(b["text"])
        if b["conf"] < 0.3 or not tk:
            continue
        cy = (b["y"] + b["h"] / 2) / H
        in_band = bool(band) and band["y"] - MARGIN <= cy <= band["y"] + band["h"] + MARGIN
        if t is None:
            said_it = any(p in pairs and max(len(x) for x in p) >= 4 for p in zip(tk, tk[1:]))
        else:
            letters = "".join(tk)
            said_it = letters in run and (len(letters) >= 5 or b["h"] >= 0.035 * H)
        near_band = bool(band) and band["y"] - NEAR_BAND <= cy <= band["y"] + band["h"] + NEAR_BAND
        if in_band or (said_it and (not band or near_band)):   # far from a known band (a book cover): not a caption
            out.append(b)
    return out


def blocked(project, source, img, t=None):
    """Boxes (x0, y0, x1, y1) in pixels a crop of this frame (at moment t) must keep out: the caption band and every
    caption on this very frame."""
    H, W = img.shape[:2]
    pad = MARGIN * H
    out = []
    band = caption_band(project, source)
    if band:
        out.append((0.0, (band["y"] - MARGIN) * H, float(W), (band["y"] + band["h"] + MARGIN) * H))
    padx = max(pad, 0.03 * W)       # read-back boxes run short on tight, stylised caption fonts
    for b in caption_like(project, source, text_boxes(img, "accurate"), H, band, t=t):
        out.append((b["x"] - padx, b["y"] - pad, b["x"] + b["w"] + padx, b["y"] + b["h"] + pad))
    return out


def clear_crop(project, source, img, aspect, zoom=1.0, x=0.5, y=0.5, t=None):
    """The crop (x0, y0, x1, y1) at width/height `aspect` that keeps every caption out: the biggest clear crop
    (made smaller only as far as captions demand), as close as it can sit to where (x, y) asks: 0 = flush left or
    top, 1 = flush right or bottom, 0.5 = centred (like CSS object-position)."""
    H, W = img.shape[:2]
    rects = blocked(project, source, img, t)
    full_h = min(float(H), W / aspect)
    z = max(1.0, float(zoom or 1.0))
    for k in range(0, 31):
        ch = full_h / z * (1 - k * 0.025)
        cw = ch * aspect
        fx, fy = x * (W - cw) + cw / 2, y * (H - ch) + ch / 2      # x, y work like CSS object-position
        best = None
        for i in range(41):
            for j in range(41):
                x0 = (W - cw) * i / 40
                y0 = (H - ch) * j / 40
                if any(x0 < r[2] and x0 + cw > r[0] and y0 < r[3] and y0 + ch > r[1] for r in rects):
                    continue
                d = (x0 + cw / 2 - fx) ** 2 + (y0 + ch / 2 - fy) ** 2
                if best is None or d < best[0]:
                    best = (d, x0, y0)
        if best:
            _, x0, y0 = best
            return (int(round(x0)), int(round(y0)), int(round(x0 + cw)), int(round(y0 + ch)))
    raise StudioError(f'Captions cover too much of "{source}" at that moment to cut a clean picture. Pick another moment.')


def best_moment(project, source, t0, t1, step=0.25):
    """The best still moment of a video between t0 and t1: sharp (Laplacian variance) and not mid-move (small
    difference from the frames either side, so a scrolling screen is caught while it pauses, never ghosted), with
    burned-in caption rows masked out of the measure."""
    import cv2
    f = source_file(project, source)
    band = caption_band(project, source)
    ts = list(np.arange(max(0.0, t0 - step), t1 + step + 1e-6, step))
    grays = []
    for t in ts:
        g = cv2.cvtColor(frame(project, source, float(t)), cv2.COLOR_RGB2GRAY)
        g = cv2.resize(g, (640, int(round(g.shape[0] * 640 / g.shape[1]))), interpolation=cv2.INTER_AREA)
        if band:
            g[int(band["y"] * g.shape[0]):int((band["y"] + band["h"]) * g.shape[0])] = int(np.median(g))
        grays.append(g.astype(np.float32))
    best, score = None, None
    for k in range(1, len(ts) - 1):
        if not t0 <= ts[k] <= t1:
            continue
        sharp = float(cv2.Laplacian(grays[k], cv2.CV_32F).var())
        move = float(np.abs(grays[k] - grays[k - 1]).mean() + np.abs(grays[k + 1] - grays[k]).mean()) / 2
        sc = sharp / (1.0 + move)
        if score is None or sc > score:
            best, score = float(ts[k]), sc
    if best is None:
        raise StudioError(f'The stretch {t0} to {t1} seconds of "{source}" is too short to pick a still from.')
    return round(best, 3)


def picture(project, spec, w, h):
    """A picture spec -> a PIL image of exactly w x h, cut clear of captions. A spec with "from" and "to" (seconds)
    instead of "t" takes the best still moment in that stretch; the moment used is written back into spec["t"]."""
    from PIL import Image
    if spec.get("t") is None and "from" in spec and "to" in spec:
        spec["t"] = best_moment(project, spec["source"], float(spec["from"]), float(spec["to"]))
    img = frame(project, spec["source"], spec.get("t"))
    box = clear_crop(project, spec["source"], img, w / h, spec.get("zoom", 1.0), spec.get("x", 0.5), spec.get("y", 0.5),
                     spec.get("t"))
    return Image.fromarray(img).crop(box).resize((w, h), Image.LANCZOS), box


def note(layout, slide, box, spec, crop):
    """Record where a picture from his footage sits on a slide (QA checks that area for caption text he said)."""
    layout.data.setdefault("pictures", []).append({"slide": slide, "box": [round(float(v), 1) for v in box],
                                                   "source": spec["source"], "t": spec.get("t"), "crop": list(crop)})
