"""Your feed: his real posts among anonymous grey posts, until his own post lifts out of the feed.

The picture is drawn by the shared Remotion project (engine/remotion/src/your-feed/). This module turns the spec into
props for it: his two posts as card pictures (cut from a screen recording of his own feed, or made from a photo of his),
and every moment of the four scenes resolved from his words. Then the sound and the deliverable.

Scenes: scroll (the feed flicks down and lands on his post, the cursor clicks it), back (the camera pulls back to his
post between the post above and the post below; "YOUR POST"; optional pulses on the neighbours, optional collapse of his
post into the same grey post, optional caption of his words), zoom (his post comes back in colour, the camera moves into
its picture, optional title of his words, optional frame drawn on a detail), lift (a second post of his sits in the
feed; its picture is pulled out of the card and settles straight on; one short red rule).
"""
import math
import os
from pathlib import Path

import numpy as np

from studio_engine import brand, remotion
from studio_engine import sound as snd
from studio_engine.errors import StudioError
from studio_engine.layout import resolve_at, text_box
from studio_engine.media import safe_input
from studio_engine.render import mux
from studio_engine.util import fps_str, probe, run

KIND = "animated"
LABELS = ["YOUR POST"]

CW, CH = 554, 878                   # a post card in card units (the pixels of a 1080p screen recording); mirrors the tsx
FEED_COUNT, MID = 7, 5              # posts in the column; his is the sixth
LEAD, TAIL = 0.35, 1.25             # seconds of picture before his first word and after his last
GRAIN = 0.06
STILLS = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".tif", ".tiff"}
PIC_CARD = (0, 96, CW, 788)         # where a photo sits on a card made from a photo (4:5, like a feed post)
LIFT_MAX_W, LIFT_MAX_H = 880, 1000  # the lifted picture's largest size on screen


# ----------------------------------------------------------------------------------------------- checks
def _anchors(spec):
    out = []
    for scene, keys in (("scroll", ("at", "land", "click")), ("back", ("at", "label", "above", "below", "same")),
                        ("zoom", ("at",)), ("lift", ("at", "pull", "red"))):
        for k in keys:
            if k in (spec.get(scene) or {}):
                out.append((f"{scene}.{k}", spec[scene][k]))
    cap = (spec.get("back") or {}).get("caption")
    if cap:
        out.append(("back.caption.at", cap.get("at")))
    fr = (spec.get("zoom") or {}).get("frame")
    if fr:
        out.append(("zoom.frame.at", fr.get("at")))
    return out


def validate(spec, words, duration):
    for scene, need in (("back", "at"), ("zoom", "at"), ("lift", "at"), ("lift", "pull")):
        if need not in (spec.get(scene) or {}):
            raise StudioError(f'This style needs "{scene}": {{"{need}": ...}} in the spec (the word where it happens).')
    for name, a in _anchors(spec):
        resolve_at(a, words, duration, field=name)
    t = lambda s, k: resolve_at(spec[s][k], words, duration)  # noqa: E731
    order = [("back.at", t("back", "at")), ("zoom.at", t("zoom", "at")), ("lift.at", t("lift", "at")),
             ("lift.pull", t("lift", "pull"))]
    for (a, ta), (b, tb) in zip(order, order[1:]):
        if tb <= ta:
            raise StudioError(f"The spec's {b} comes before {a}. The scenes run in order: scroll, back, zoom, lift.")
    if t("zoom", "at") - t("back", "at") < 1.2:
        raise StudioError("The pull back needs at least 1.2 seconds before the zoom. Start the zoom a few words later.")
    if t("lift", "at") - t("zoom", "at") < 1.2:
        raise StudioError("The zoom needs at least 1.2 seconds before the lift. Start the lift a few words later.")
    posts = spec.get("posts") or {}
    for k in ("first", "second"):
        p = posts.get(k)
        if not p or "source" not in p:
            raise StudioError(f'This style needs two of his posts: add "posts": {{"{k}": {{"source": ...}}}}.')
        pic = p.get("picture")
        if pic is not None and not (len(pic) == 4 and 0 <= pic[0] < pic[2] <= 1 and 0 <= pic[1] < pic[3] <= 1):
            raise StudioError(f"posts.{k}.picture must be four fractions [left, top, right, bottom] of the post.")
    cap = (spec.get("back") or {}).get("caption")
    if cap and len(cap.get("text", "")) > 22:
        raise StudioError("The caption under the posts is longer than 22 characters. Use two or three of his words.")


# ----------------------------------------------------------------------------------------------- his posts
def find_card(grey, px, py, run_frac=0.6):
    """The post card around the point (px, py) of a screen frame: (x0, y0, x1, y1) of its thin border, or None.

    A border is a thin line a little darker than the white page, with white page outside it and the card inside it
    (a picture that starts right at the border also counts). The side borders are followed from corner to corner to
    get the card's height; the top and bottom are the nearest lines across the card at those ends. Measured on his
    LinkedIn activity page: a post card is 554 x 878 pixels in a 1080p recording."""
    g = grey.astype(np.int16)
    H, W = g.shape
    px, py = int(min(max(px, 4), W - 5)), int(min(max(py, 4), H - 5))

    def edge(c, o, i):
        return (c < 246) & (c > 170) & (o >= 247) & ((np.abs(i - c) >= 6) | (i >= 247))

    def col(x, side):
        return edge(g[:, x], g[:, min(W - 1, max(0, x + 3 * side))], g[:, min(W - 1, max(0, x - 3 * side))])

    def row(y, x0, x1, side):
        return edge(g[y, x0:x1], g[min(H - 1, max(0, y + 3 * side)), x0:x1], g[min(H - 1, max(0, y - 3 * side)), x0:x1])

    ya, yb = max(0, py - 200), min(H, py + 200)
    left = next((x for x in range(px, 3, -1) if col(x, -1)[ya:yb].mean() > run_frac), None)
    right = next((x for x in range(px, W - 4) if col(x, 1)[ya:yb].mean() > run_frac), None)
    if left is None or right is None or right - left < 200:
        return None
    sides = (col(left, -1) | col(left + 1, -1)) & (col(right, 1) | col(right - 1, 1))
    m = np.convolve(sides.astype(float), np.ones(9) / 9, "same") > 0.3
    y0 = y1 = py
    while y0 > 0 and m[y0 - 1]:
        y0 -= 1
    while y1 < H - 1 and m[y1 + 1]:
        y1 += 1
    xa, xb = left + 20, right - 20
    top = next((y for y in range(min(H - 4, y0 + 6), max(3, y0 - 30), -1) if row(y, xa, xb, -1).mean() > run_frac), None)
    bot = next((y for y in range(max(3, y1 - 6), min(H - 4, y1 + 30)) if row(y, xa, xb, 1).mean() > run_frac), None)
    if top is None or bot is None or bot - top < 200:
        return None
    return left, top, right, bot


def grab_frame(src, t, work, log=None):
    import cv2
    out = Path(work) / f"frame-{t:.3f}.png"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", *safe_input(src), "-frames:v", "1",
         "-vf", "scale=in_color_matrix=bt709:in_range=tv", str(out)], log=log)
    im = cv2.imread(str(out))
    out.unlink(missing_ok=True)
    if im is None:
        raise StudioError(f"Could not read a frame at {t:.1f} seconds of the screen recording.")
    return im


def picture_band(card_bgr):
    """The picture of a cut-out post: the longest run of rows that are not white page (fractions of the card)."""
    g = card_bgr.mean(axis=2).mean(axis=1)
    busy = g < 238
    best, cur, start = (0, 0), 0, 0
    for y, b in enumerate(busy):
        if b:
            if cur == 0:
                start = y
            cur += 1
            if cur > best[1] - best[0]:
                best = (start, y + 1)
        else:
            cur = 0
    if best[1] - best[0] < 80:
        return (0.0, 0.27, 1.0, 0.74)
    return (0.0, best[0] / card_bgr.shape[0], 1.0, best[1] / card_bgr.shape[0])


def screen_card(ctx, src, p, field, out_png):
    """Cut his post out of a frame of the screen recording, at card size."""
    import cv2
    if "at" not in p or "point" not in p:
        raise StudioError(f'{field} comes from a screen recording: give "at" (the second where the whole post is on '
                          'screen) and "point" ([x, y], a point inside the post, in the recording\'s pixels).')
    dur = probe(src)["duration"]
    t = float(p["at"])
    if not 0 <= t < dur:
        raise StudioError(f"{field}.at is {t:.1f} seconds, but the screen recording is {dur:.1f} seconds long.")
    im = grab_frame(src, t, ctx.work, ctx.log)
    box = find_card(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), *p["point"])
    if box is None:
        raise StudioError(f"Could not find the edges of the post at {field}.point at {t:.1f} seconds. Pick a moment "
                          "where the whole post is on screen, still (no scrolling), and a point inside it.")
    x0, y0, x1, y1 = box
    crop = im[max(0, y0 - 2):y1 + 1, max(0, x0 - 1):x1 + 2]
    h, w = crop.shape[:2]
    if (w, h) != (CW, CH):
        s = CW / w
        crop = cv2.resize(crop, (CW, max(1, round(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        if crop.shape[0] >= CH:
            crop = crop[:CH]
        else:
            pad = np.full((CH - crop.shape[0], CW, 3), crop[-1].mean(axis=0), np.uint8)
            crop = np.vstack([crop, pad])
    cv2.imwrite(str(out_png), crop)
    pic = p.get("picture") or picture_band(crop)
    return {"box": [int(v) for v in box], "pic": pic}


def photo_card(ctx, src, p, out_png):
    """A post made from a photo of his: a warm-white card with the photo in it (4:5, like a feed post), grey lines
    where the post's text would be. No words are written on it."""
    from PIL import Image, ImageDraw, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    x0, y0, x1, y1 = PIC_CARD
    pw, ph = x1 - x0, y1 - y0
    cy = float(p.get("crop_y", 0.4))
    im = ImageOps.fit(im, (pw, ph), Image.LANCZOS, centering=(0.5, min(max(cy, 0.0), 1.0)))
    card = Image.new("RGB", (CW, CH), tuple(brand.rgb_of(brand.hex("warm_white"))))
    d = ImageDraw.Draw(card)
    bar = (208, 202, 192)
    d.ellipse((16, 20, 70, 74), fill=bar)
    d.rounded_rectangle((84, 26, 250, 40), 7, fill=bar)
    d.rounded_rectangle((84, 50, 200, 60), 5, fill=(222, 217, 208))
    card.paste(im, (x0, y0))
    for x in (50, 180, 310, 440):
        d.ellipse((x, 820, x + 30, 850), fill=(222, 217, 208))
    card.save(out_png)
    pic = p.get("picture") or (x0 / CW, y0 / CH, x1 / CW, y1 / CH)
    return {"box": None, "pic": pic}


def make_post(ctx, key, public):
    p = ctx.spec["posts"][key]
    src = ctx.source(p["source"])
    out = public / f"post-{key}.png"
    if Path(src).suffix.lower() in STILLS:
        r = photo_card(ctx, src, p, out)
    else:
        r = screen_card(ctx, src, p, f"posts.{key}", out)
    x0, y0, x1, y1 = r["pic"]
    pic = [round(x0 * CW, 2), round(y0 * CH, 2), round(x1 * CW, 2), round(y1 * CH, 2)]
    return {"src": out.name, "w": CW, "h": CH, "pic": pic}, r


# ----------------------------------------------------------------------------------------------- timing
class Clock:
    """Word anchors -> seconds of the film (his voice starts `lead` seconds in) and frames."""

    def __init__(self, ctx, lead):
        self.ctx, self.lead, self.fps = ctx, lead, ctx.fps

    def t(self, a, field):
        return self.ctx.at(a, field) + self.lead

    def f(self, sec):
        return int(round(sec * self.fps))


def plan(ctx, clock, total_s):
    sp = ctx.spec
    sc, bk, zm, lf = (dict(sp.get(k) or {}) for k in ("scroll", "back", "zoom", "lift"))
    T = clock.t
    back_at = T(bk["at"], "back.at")
    zoom_at = T(zm["at"], "zoom.at")
    lift_at = T(lf["at"], "lift.at")
    pull = T(lf["pull"], "lift.pull")
    s_at = T(sc.get("at", {"t": 0.05}), "scroll.at")
    if "click" in sc:
        click = T(sc["click"], "scroll.click")
    else:
        click = (T(sc["land"], "scroll.land") + 0.15) if "land" in sc else back_at - 0.1
    land = T(sc["land"], "scroll.land") if "land" in sc else click - 0.15
    if land <= s_at + 0.3:
        raise StudioError("The scroll is too short: the post it lands on needs about a second. Start the pull back "
                          "a few words later.")
    m = {"scroll": {"at": s_at, "land": land, "click": click},
         # the label waits until the pull back has mostly happened, or it runs into the post as it shrinks
         "back": {"at": back_at, "label": max(T(bk["label"], "back.label"), back_at + 0.55) if "label" in bk
                  else back_at + 0.65}}
    for k in ("above", "below", "same"):
        m["back"][k] = T(bk[k], f"back.{k}") if k in bk else None
    cap = bk.get("caption")
    m["back"]["caption"] = ({"text": cap["text"], "at": T(cap["at"], "back.caption.at")} if cap else None)
    fr = zm.get("frame")
    m["zoom"] = {"at": zoom_at, "title": zm.get("title"), "frame": fr,
                 "frame_at": T(fr["at"], "zoom.frame.at") if fr else None}
    m["lift"] = {"at": lift_at, "pull": pull, "red": T(lf["red"], "lift.red") if "red" in lf else pull + 0.57,
                 "rule_y": float(lf.get("rule_y", 0.12))}
    return m


ZOOM_Y = 930          # the screen line the zoom centres on (mirrors the tsx)
TITLE_CLEAR = 400     # with a title, the zoomed picture starts below this line


def zoom_focus(spec_zoom, pic):
    """Where the camera goes in the zoom: the picture's centre, scaled to about 560 x 790 on screen. With a title and
    a big zoom, the camera aims a little higher on the picture so its top edge stays clear of the title."""
    x0, y0, x1, y1 = pic
    zs = spec_zoom or {}
    f = zs.get("focus") or {}
    scale = float(f.get("scale", min(560 / (x1 - x0), 790 / (y1 - y0), 3.0)))
    x = float(f["x"]) * CW if "x" in f else (x0 + x1) / 2
    if "y" in f:
        y = float(f["y"]) * CH
    else:
        y = (y0 + y1) / 2 + 8
        if zs.get("title"):
            y = min(y, y0 + (ZOOM_Y - TITLE_CLEAR) / scale)
    return x, y, scale


# ----------------------------------------------------------------------------------------------- layout for QA
def record_layout(ctx, m, second_pic, total_s):
    cream, red = ctx.brand["colors"]["cream"], ctx.brand["colors"]["red_on_footage"]
    bk, zm, lf = m["back"], m["zoom"], m["lift"]
    b = ctx.layout.beat("scroll", 0.0, bk["at"], i=0)
    b = ctx.layout.beat("back", bk["label"], zm["at"], i=1)
    lab = brand.font("archive", 40)
    ctx.layout.text(b, "YOUR POST", text_box(lab, "YOUR POST", 140, 850, "lm", 3 / 40), role="label",
                    color=red if bk["same"] is not None else cream, red=bk["same"] is not None)
    if bk["caption"]:
        f = brand.font("display_soft", 64)
        ctx.layout.text(b, bk["caption"]["text"], text_box(f, bk["caption"]["text"], 140, 1510 + 64 * 0.8, "ls"),
                        role="words", color=cream)
    b = ctx.layout.beat("zoom", zm["at"] + 0.55, lf["at"], i=2)
    if zm["title"]:
        small, big = zm["title"].get("small", ""), zm["title"].get("big", "")
        if small:
            ctx.layout.text(b, small, text_box(brand.font("archive", 30), small, 540, 236 + 18, "mm", 6 / 30),
                            role="words", color=cream)
        if big:
            ctx.layout.text(b, big, text_box(brand.font("display_soft", 92), big, 540, 236 + 36 + 6 + 46, "mm"),
                            role="words", color=cream)
    b = ctx.layout.beat("lift", lf["red"], total_s, i=3)
    x0, y0, x1, y1 = second_pic
    iw, ih = x1 - x0, y1 - y0
    w = min(LIFT_MAX_W, LIFT_MAX_H * iw / ih)
    h = w * ih / iw
    u = w / 880
    top = 820 - 10 - h / 2
    ctx.layout.mark(b, "red rule", (540 - 45 * u, top + lf["rule_y"] * h, 90 * u, 6 * u), red=True,
                    color=ctx.brand["colors"]["red"])


# ----------------------------------------------------------------------------------------------- sound
SR = snd.SR


def _sig():
    from scipy import signal
    return signal


def fx_whoosh(d, rng):
    n = int(d * SR)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    for i in range(0, n, 512):
        fc = 300 + 2600 * np.sin(np.pi * i / n) ** 1.5
        out[i:i + 512] = snd.bp(x[i:i + 512], fc * 0.6, fc * 1.4)
    return snd.lp(out * np.sin(np.pi * np.linspace(0, 1, n)) ** 2, 6000)


def fx_tick(rng, d=0.06):
    tt = np.arange(int(d * SR)) / SR
    return snd.bp(rng.standard_normal(len(tt)), 2500, 7000) * np.exp(-tt * 120) + \
        0.4 * np.sin(2 * np.pi * 1800 * tt) * np.exp(-tt * 90)


def fx_click(rng):
    a = fx_tick(rng, 0.052) * 0.8
    b = np.concatenate([np.zeros(int(0.012 * SR)), fx_tick(rng, 0.04)])[:len(a)]
    return a + 0.5 * np.pad(b, (0, len(a) - len(b)))


def fx_thud(f0, d, weight, rng):
    tt = np.arange(int(d * SR)) / SR
    f = f0 * (1 + 1.6 * np.exp(-tt * 30))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 5)
    return body * weight + snd.lp(rng.standard_normal(len(tt)), 2500) * np.exp(-tt * 60) * 0.5


def fx_swell(d, rng):
    n = int(d * SR)
    x = snd.bp(rng.standard_normal(n), 2000, 9000) * np.linspace(0, 1, n) ** 2
    return x * np.concatenate([np.ones(n - 400), np.linspace(1, 0, 400)])


def bed_feed(dur, rng):
    """A glassy pad over a soft pulse at 100 beats a minute, with a light tick on the off-beats."""
    sig = _sig()

    def mtof(mn):
        return 440 * 2 ** ((mn - 69) / 12)

    chords = [[57, 64, 69, 71], [55, 62, 67, 69], [53, 60, 65, 69], [55, 62, 67, 71]]
    y = np.zeros(int(dur * SR) + SR)
    bar = int(2.4 * SR)
    for i in range(0, len(y), bar):
        ch = chords[(i // bar) % len(chords)]
        seg = np.zeros(bar + SR)
        tt = np.arange(len(seg)) / SR
        for mn in ch:
            for det in (-0.08, 0.0, 0.07):
                seg += sig.sawtooth(2 * np.pi * mtof(mn + det) * tt + rng.random() * 6) * 0.2
        seg = snd.lp(seg, 1600)
        e = np.minimum(1, tt / 0.9) * np.minimum(1, np.maximum(0, (len(seg) / SR - tt) / 1.0))
        y[i:i + len(seg)] += (seg * e)[:len(y) - i]
    y = y[:int(dur * SR)] * 0.35
    pulse = np.zeros_like(y)
    step = 60 / 100
    for kk in range(int(dur / step) + 1):
        s0 = int(kk * step * SR)
        hit = fx_thud(mtof(33), 0.5, 1.0, rng) * 0.6
        pulse[s0:s0 + len(hit)] += hit[:max(0, len(y) - s0)]
    y += snd.lp(pulse, 200) * 0.9
    for kk in range(int(dur / (step / 2))):
        if kk % 2:
            s0 = int(kk * step / 2 * SR)
            h = fx_tick(rng, 0.04) * 0.08
            y[s0:s0 + len(h)] += h[:max(0, len(y) - s0)]
    n = len(y)
    fade = np.minimum(1, np.arange(n) / (0.4 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.9 * SR))
    return y * fade


def effects(m, rng):
    """The style's own effects, placed on the scene moments: [(t, array, under_db)]."""
    sc, bk, zm, lf = m["scroll"], m["back"], m["zoom"], m["lift"]
    ev = [(sc["at"] - 0.30, fx_whoosh(0.9, rng), 25), (sc["click"] + 0.02, fx_click(rng), 27),
          (bk["at"], fx_whoosh(0.8, rng), 30), (bk["label"], fx_tick(rng), 27)]
    for k in ("above", "below"):
        if bk[k] is not None:
            ev.append((bk[k], fx_tick(rng), 27))
    if bk["same"] is not None:
        ev.append((bk["same"], fx_swell(0.4, rng), 30))
    ev.append((zm["at"], fx_whoosh(0.9, rng), 30))
    if zm["frame_at"] is not None:
        ev += [(zm["frame_at"] - 0.03, fx_click(rng), 27), (zm["frame_at"] + 0.65, fx_tick(rng), 29)]
    ev += [(lf["at"] - 0.1, fx_whoosh(0.3, rng), 29), (lf["pull"] - 0.08, fx_swell(0.75, rng), 27),
           (lf["red"] + 0.17, fx_thud(140, 0.35, 0.6, rng) * 0.7, 29)]
    return ev


def make_sound(ctx, m, lead, total_s):
    rng = np.random.default_rng(7)
    v = snd.decode(ctx.voice())
    voice = np.zeros((int(round(total_s * SR)), 2))
    snd.place(voice, v, lead)
    sp = ctx.spec.get("sound") or {}
    bed_name = sp.get("bed", "feed")
    under = float(sp.get("under_db", ctx.brand["sound"]["music_under_db"]))
    if bed_name == "feed":
        bed = snd.stereo(bed_feed(total_s, rng))
    elif bed_name in ("none", "", None):
        bed = None
    else:
        bed = bed_name
    sfx = []
    if sp.get("effects", True):
        lo, hi = ctx.brand["sound"]["sfx_under_db_min"], ctx.brand["sound"]["sfx_under_db_max"]
        for t, x, u in effects(m, rng):
            if t < 0:
                x, t = x[int(-t * SR):], 0.0
            sfx.append({"array": snd.stereo(x), "t": t, "under_db": min(max(u, lo), hi)})
    return snd.mix(voice, total_s, ctx.out / "mix.wav", bed=bed, sfx=sfx, music_under=under, work=ctx.work)


# ----------------------------------------------------------------------------------------------- render
def render(ctx):
    fps = ctx.fps
    lead = float(ctx.spec.get("lead", LEAD))
    total_s = lead + ctx.duration + float(ctx.spec.get("tail", TAIL))
    total = int(math.ceil(total_s * fps - 1e-6))
    total_s = total / fps
    clock = Clock(ctx, lead)
    public = ctx.work / "public"
    public.mkdir(parents=True, exist_ok=True)
    remotion.place(brand.font_path("title"), public / "fonts" / "serif.ttf")
    remotion.place(brand.font_path("display"), public / "fonts" / "serif-italic.ttf")
    remotion.place(brand.font_path("archive"), public / "fonts" / "label.ttf")

    ctx.say("Cutting his posts out.")
    first, r1 = make_post(ctx, "first", public)
    second, r2 = make_post(ctx, "second", public)
    posts_dir = ctx.out / "posts"
    posts_dir.mkdir(exist_ok=True)
    for k in ("first", "second"):
        remotion.place(public / f"post-{k}.png", posts_dir / f"{k}.png")

    m = plan(ctx, clock, total_s)
    F = clock.f
    zx, zy, zs = zoom_focus(ctx.spec.get("zoom"), first["pic"])
    fr = m["zoom"]["frame"]
    box = None
    if fr:
        bx0, by0, bx1, by1 = fr["box"]
        px0, py0, px1, py1 = first["pic"]
        box = {"x0": px0 + bx0 * (px1 - px0), "y0": py0 + by0 * (py1 - py0), "x1": px0 + bx1 * (px1 - px0),
               "y1": py0 + by1 * (py1 - py0), "at": F(m["zoom"]["frame_at"])}
    bk = m["back"]
    c = ctx.brand["colors"]
    props = {
        "w": ctx.w, "h": ctx.h, "fps": fps, "frames": total,
        "colors": {"obsidian": "#0B0B0C", "cream": c["cream"], "red": c["red"], "redOver": c["red_on_footage"]},
        "fonts": {"serif": "fonts/serif.ttf", "serifItalic": "fonts/serif-italic.ttf", "label": "fonts/label.ttf"},
        "first": first, "second": second, "feedCount": FEED_COUNT, "mid": MID,
        "scroll": {k: F(v) for k, v in m["scroll"].items()},
        "back": {"at": F(bk["at"]), "label": F(bk["label"]),
                 **{k: (None if bk[k] is None else F(bk[k])) for k in ("above", "below", "same")},
                 "caption": None if not bk["caption"] else {"text": bk["caption"]["text"], "at": F(bk["caption"]["at"])}},
        "zoom": {"at": F(m["zoom"]["at"]), "x": zx, "y": zy, "scale": zs, "title": m["zoom"]["title"], "box": box},
        "lift": {"at": F(m["lift"]["at"]), "pull": F(m["lift"]["pull"]), "red": F(m["lift"]["red"]),
                 "ruleY": m["lift"]["rule_y"], "maxW": LIFT_MAX_W, "maxH": LIFT_MAX_H},
        "grain": float((ctx.spec.get("finish") or {}).get("grain", GRAIN)),
    }
    motion = remotion.render("your-feed", props, public, ctx.work / "motion.mp4", log=ctx.log)

    pic = ctx.work / "picture.mp4"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(motion), "-vf",
         "format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
         "-frames:v", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-r", fps_str(fps), "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart", "-an", pic], log=ctx.log)

    ctx.say("Mixing the sound.")
    levels = make_sound(ctx, m, lead, total_s)
    record_layout(ctx, m, second["pic"], total_s)
    mux(pic, ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels, "posts": {"first": r1, "second": r2},
            "keep_work": bool(os.environ.get("STUDIO_KEEP_WORK"))}
