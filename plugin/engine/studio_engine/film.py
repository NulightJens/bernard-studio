"""The film look the receipts, documentary and cutout reels were picked in: the kit's cinema grade, halation,
vignettes, moving film grain, the kit's caption shadow and text drawing helpers. Pure functions on float RGB frames
(0..1) and PIL RGBA layers, sized by the frame they are given.
"""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from studio_engine import brand


# ----------------------------------------------------------------------------------------------- type
def tw(txt, f, track=0.0):
    """Advance width of a line with tracking (a fraction of the font size between letters)."""
    return f.getlength(txt) + track * f.size * max(0, len(txt) - 1)


def cap_h(f):
    return -f.getbbox("H", anchor="ls")[1]


def fit(kind, size, txt, max_w, track=0.0, floor=24):
    """The kit font `kind` at `size`, shrunk in 2 px steps until the line fits `max_w`."""
    while size > floor and tw(txt, brand.font(kind, size), track) > max_w:
        size -= 2
    return brand.font(kind, size)


def draw_text(d, xy, txt, f, fill, track=0.0, anchor="ls"):
    x, y = xy
    if not track:
        d.text((x, y), txt, font=f, fill=fill, anchor=anchor)
        return
    wd = tw(txt, f, track)
    x = x - wd / 2 if anchor[0] == "m" else x - wd if anchor[0] == "r" else x
    for ch in txt:
        d.text((x, y), ch, font=f, fill=fill, anchor="l" + anchor[1])
        x += f.getlength(ch) + track * f.size


def tracked_box(f, txt, x, y, anchor="ms", track=0.0):
    """The box a tracked line covers (for the layout record)."""
    l, t, r, b = f.getbbox(txt, anchor="ls")
    wd = tw(txt, f, track)
    x0 = x - wd / 2 if anchor[0] == "m" else x - wd if anchor[0] == "r" else x
    return (x0 + min(0, l), y + t, wd + max(0, r - f.getlength(txt)), b - t)


def shadow_of(layer, blur=10, alpha=0.55, dy=4):
    """The kit's soft shadow under a full-frame RGBA layer."""
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha)))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, dy))
    out.alpha_composite(layer)
    return out


def set_alpha(im, k):
    if k >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel("A").point(lambda v: int(v * max(0.0, k))))
    return im


# ----------------------------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ramp(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out(x, p=3):
    x = clamp(x)
    return 1 - (1 - x) ** p


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def fade(t, a, b, d=0.25):
    """1 between a and b, ramping in and out over d seconds."""
    return clamp((t - a) / d) * (1 - clamp((t - b) / d))


# ----------------------------------------------------------------------------------------------- the grade
def to_f(a):
    return a.astype(np.float32) / 255.0


def to_u8(f):
    return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)


def grade_film(f, lift_amt=0.035, contrast=1.08, sat=0.88, warm=0.04):
    """The kit's cinema grade: ink-blue lift in the shadows, warm highlights, a soft S, a little less colour."""
    lift = np.array(brand.color("ink"), np.float32)
    lum = f.mean(2, keepdims=True)
    f = lum + (f - lum) * sat
    f = 0.5 + (f - 0.5) * contrast
    f = np.clip(f, 0, 1)
    f = f * f * (3 - 2 * f) * 0.35 + f * 0.65
    sh = (1 - lum) ** 3
    f = f + sh * lift_amt * (lift / 255 * 6)
    hi = np.clip((lum - 0.45) / 0.55, 0, 1)
    return f + hi * warm * np.array([1.0, 0.45, -0.3], np.float32)


def halation(f, thresh=0.72, radius=18, amt=0.35):
    """A warm glow around the highlights."""
    import cv2
    lum = f.max(2)
    m = np.clip((lum - thresh) / (1 - thresh), 0, 1)
    if m.max() <= 0:
        return f
    return f + cv2.GaussianBlur(m, (0, 0), radius)[..., None] * amt * np.array([1.0, 0.42, 0.18], np.float32)


@lru_cache(None)
def vignette(w, h, strength=0.35, power=2.2):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 * 0.8 + ((yy - h / 2) / (h / 2)) ** 2)
    return (1 - strength * np.clip(r / 1.25, 0, 1) ** power)[..., None]


@lru_cache(None)
def band_vignette(w, h):
    """The documentary band's own soft vignette (wider than tall)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2 * 0.6)
    return (1 - 0.35 * np.clip(r / 1.3, 0, 1) ** 2.4)[..., None]


@lru_cache(None)
def _grain_bank(w, h, n=12, seed=7):
    rng = np.random.default_rng(seed)
    bank = []
    for _ in range(n):
        g = rng.normal(0, 1, (h // 2 + 2, w // 2 + 2)).astype(np.float32)
        bank.append(np.asarray(Image.fromarray(g).resize((w + 4, h + 4), Image.BICUBIC)))
    return bank


def grain(f, k, strength=0.03, seed=0):
    """Film grain, luma only, moving every frame, a touch stronger in the mids."""
    h, w = f.shape[:2]
    g = _grain_bank(w, h)[(k * 7 + seed) % 12]
    ox, oy = (k * 13) % 4, (k * 29) % 4
    g = g[oy:oy + h, ox:ox + w]
    lum = f.mean(2, keepdims=True)
    return f + g[..., None] * strength * (0.35 + 1.3 * lum * (1 - lum) * 2.5)


# ----------------------------------------------------------------------------------------------- layers
def paste(canvas, im, x, y):
    """Alpha-composite an RGBA sprite at a position, clipped to the canvas."""
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + im.width), min(canvas.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) == (x, y, x + im.width, y + im.height):
        canvas.alpha_composite(im, (x, y))
    else:
        canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def over(base_f, layer):
    """An RGBA PIL layer over a float RGB frame."""
    a = np.asarray(layer, np.float32) / 255.0
    al = a[..., 3:4]
    return base_f * (1 - al) + a[..., :3] * al


@lru_cache(None)
def _brush(name, width, squash):
    src = Image.open(brand.brush(name)).convert("RGBA")
    h = max(1, round(src.height * width / src.width * squash))
    return src.convert("RGBa").resize((int(width), h), Image.LANCZOS).convert("RGBA")


def brush_draw(name, width, squash=0.6, angle=-1.5, progress=1.0):
    """The kit's brush stroke at a width, squashed, drawn on left to right up to `progress`, at a slight angle."""
    b = _brush(name, int(width), squash)
    if progress < 1:
        b = b.copy()
        b.paste((0, 0, 0, 0), (int(b.width * max(0.0, progress)), 0, b.width, b.height))
    return b.rotate(-angle, resample=Image.BICUBIC, expand=True)


def rotate_point(px, py, size, angle, expanded):
    """Where a point of an image lands after PIL's rotate(angle, expand=True) (counter-clockwise, about the centre)."""
    w, h = size
    ew, eh = expanded
    a = math.radians(angle)
    dx, dy = px - w / 2, py - h / 2
    return ew / 2 + dx * math.cos(a) + dy * math.sin(a), eh / 2 - dx * math.sin(a) + dy * math.cos(a)


def text_layer(size):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def text_img(txt, f, fill, track=0.0):
    """A tight RGBA sprite of one line (padding 0.35 of the size on every side) and its baseline-left origin."""
    asc, desc = f.getmetrics()
    pad = int(f.size * 0.35)
    wd = int(math.ceil(tw(txt, f, track))) + 2 * pad
    ht = asc + desc + 2 * pad
    im = Image.new("RGBA", (wd, ht), (0, 0, 0, 0))
    draw_text(ImageDraw.Draw(im), (pad, pad + asc), txt, f, tuple(fill) + (255,), track)
    return im, (pad, pad + asc)


def pop(t, t0, dur=0.3):
    """The cutout entrance: a quick scale-up from 93 percent with a 1.5 percent overshoot that settles, opacity in over
    the first third; still after. Returns (scale, opacity)."""
    k = clamp((t - t0) / dur)
    if k >= 1:
        return 1.0, 1.0
    s = 0.93 + 0.07 * (1 + 0.015 * math.sin(k * math.pi)) * ease_out(k, 3)
    return float(s), clamp(k / 0.35)
