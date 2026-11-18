"""Words in the room: his words set on the wall behind him, with him cut out and laid back in front of them.

The picture is drawn by the shared Remotion project (engine/remotion/src/words-in-the-room/). This module:
  1. checks the camera stays still (the words are fixed to the wall, so a moving camera would slide the room under
     them): a few frames are cut out with the matte and the background alone is lined up against the first frame;
  2. cuts him out of every frame of the passage (BiRefNet HR, alpha used as it is), resumable;
  3. crops room and cutout to what the frame shows, resolves every word anchor and writes the props;
  4. adds film grain, mixes the sound, records every text box for QA.
"""
import io
import json
import math
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from studio_engine import brand, heavy, matte, remotion
from studio_engine.errors import StudioError
from studio_engine.media import safe_input
from studio_engine.render import mux
from studio_engine.util import fps_str, run

KIND = "reel"
LABELS = []

COLOR = "#EFE4CF"            # warm white, nudged toward candlelight
SIZES = {"figure": 236, "line": 64, "type": 36, "title": 76}
TRACK = {"figure": -0.012, "line": 0.0, "type": 0.16, "title": 0.26}
OPEN_WITHIN = 0.25           # a word anchored this close to the start is on the wall from the first frame
GRAIN = 7
END_HOLD = 0.6               # the last frame holds this long under the end fade (seconds)
FADE_TOP = 150               # the room fades in over this many pixels below its top edge
FADE_BOTTOM = (1480, 1672)   # ... and out into the dark under the caption zone
MARGIN = 24                  # room cropped this much wider than the frame (the camera drift)
STILL_LIMIT = 4.0            # most the background may move against the first frame, in pixels of a 1080-line picture
STILL_SAMPLES = 5
ORPHAN, STEADY = 8.0, 3.0   # a patch of wall changing this much at the edge, then holding still: an orphan frame
MATCH_MIN = 0.5              # below this the background no longer lines up at all: a cut to another picture
BRUSH = "red-a"
WALL_GAP = 12               # least space between two blocks on the wall at the same time


# ----------------------------------------------------------------------------------------------- checks
def _anchors(it):
    out = []
    for k in ("at", "warm", "strike", "dim", "until"):
        if k in it:
            out.append((k, it[k]))
    for j, a in enumerate(it.get("stack") or []):
        out.append((f"stack[{j}]", a))
    return out


def validate(spec, words, duration):
    from studio_engine.layout import resolve_at
    wall = spec.get("wall") or []
    if not wall:
        raise StudioError('This style needs at least one line of his words on the wall: add it to the spec\'s "wall".')
    for k, it in enumerate(wall):
        for name, a in _anchors(it):
            resolve_at(a, words, duration, field=f"wall[{k}].{name}")
        kind = it.get("kind")
        if "strike" in it and kind != "figure":
            raise StudioError(f"The spec's wall[{k}] has a strike, but only a figure (a big number) can be struck.")
        if it.get("stack") and kind != "title":
            raise StudioError(f"The spec's wall[{k}] has rules stacked on it, but only a title can carry them.")
        if "until" in it:
            t0 = resolve_at(it["at"], words, duration)
            if resolve_at(it["until"], words, duration) <= t0:
                raise StudioError(f"The spec's wall[{k}] leaves before it arrives: its until must come after its at.")
    if sum(1 for it in wall if "strike" in it) > 1:
        raise StudioError("The spec strikes more than one figure. This style has one red: strike one figure at most.")


# ----------------------------------------------------------------------------------------------- the room
HEAD_X, HEAD_TOP = 0.66, 795      # where the default framing puts his head (as in the example): right of centre, its top here


def room_geometry(ctx, him=None):
    """Where his frame sits in the reel (output pixels): `scale` output pixels per pixel of his frame, `left` and
    `top` the output position of his frame's top-left corner. Left out, they frame him as in the example: a landscape
    video 972 px tall with his head right of centre (x 713) and its top at y 795 (room above it for the words), a
    vertical video filling the width from the top."""
    W, H = (float(x) for x in (ctx.passage.get("size") or [1920, 1080]))
    r = dict(ctx.spec.get("room") or {})
    if "scale" not in r:
        r["scale"] = ctx.w / W if H > W else 0.9 * 1080 / H
    s = float(r["scale"])
    if H > W:
        r.setdefault("left", round((ctx.w - W * s) / 2, 1))
        r.setdefault("top", 0.0)
    elif him:
        r.setdefault("left", round(ctx.w * HEAD_X - him["head_x"] * s, 1))
        r.setdefault("top", round(HEAD_TOP - him["head_top"] * s, 1))
    else:
        r.setdefault("left", round((ctx.w - W * s) / 2, 1))
        r.setdefault("top", 700.0)
    return W, H, s, float(r["left"]), float(r["top"]), r.get("fill")


def find_him(a):
    """His head in a matte (pixels of his frame): the top of the cutout and the middle of its top part."""
    m = a > 128
    rows = np.where(m.sum(1) > max(4, m.shape[1] // 200))[0]
    if not len(rows):
        return None
    top = int(rows[0])
    band = m[top: top + max(8, m.shape[0] // 8)]
    xs = np.where(band.any(0))[0]
    cols = band.sum(0).astype(float)
    cx = float((np.arange(len(cols)) * cols).sum() / max(1.0, cols.sum()))
    return {"head_top": top, "head_x": round(cx, 1), "head_width": int(xs[-1] - xs[0] + 1) if len(xs) else 0}


def crop_box(ctx, W, H, s, left, top):
    """The part of his frame the reel can show (plus the drift margin), in his frame's pixels."""
    x0 = max(0, int(math.floor((-left - MARGIN) / s)))
    x1 = min(int(W), int(math.ceil((ctx.w - left + MARGIN) / s)))
    y0 = max(0, int(math.floor((-top - MARGIN) / s)))
    y1 = min(int(H), int(math.ceil((ctx.h - top + MARGIN) / s)))
    if x1 - x0 < 16 or y1 - y0 < 16:
        raise StudioError("The spec's room puts his video outside the reel. Check room.scale, room.left and room.top.")
    return x0, y0, x1, y1


def grab(src, t):
    from PIL import Image
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0.0, t):.3f}", *safe_input(str(src)),
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise StudioError("I could not read a frame of the picked video.")
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def background_move(ims, alphas):
    """How far the background moves against the first frame: his cutout is masked away, the rest (high-passed so flat
    dark walls do not decide it) is lined up with an affine fit (started from a phase correlation, so a large move is
    still found), and the fit's move is measured at points a quarter in from each corner. Returns (pixels of his frame
    per sample, the background's share of the frame, how well each sample lines up at all)."""
    import cv2
    S = 960

    def prep(im, a):
        g = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2GRAY)
        sc = S / g.shape[1]
        g = cv2.resize(g, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA).astype(np.float32)
        g = g - cv2.GaussianBlur(g, (0, 0), 8)
        a = cv2.resize(a, (g.shape[1], g.shape[0]))
        bg = cv2.dilate((a > 8).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0
        return g, bg, sc

    g0, b0, sc = prep(ims[0], alphas[0])
    h, w = g0.shape
    pts = np.float32([[w * .25, h * .25], [w * .75, h * .25], [w * .75, h * .75], [w * .25, h * .75]])
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    moves, shares, ccs = [], [], []
    for im, a in zip(ims[1:], alphas[1:]):
        g, b, _ = prep(im, a)
        m = (b0 & b).astype(np.uint8)
        shares.append(float(m.mean()))
        (dx, dy), _ = cv2.phaseCorrelate(g0 * m * win, g * m * win)
        warp = np.float32([[1, 0, dx], [0, 1, dy]])
        try:
            cc, warp = cv2.findTransformECC(g0, g, warp, cv2.MOTION_AFFINE,
                                            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), m, 5)
            mv = float(np.max(np.linalg.norm(pts @ warp[:, :2].T + warp[:, 2] - pts, axis=1)) / sc)
        except cv2.error:
            cc, mv = 0.0, None
        moves.append(mv)
        ccs.append(round(float(cc), 3))
    return moves, min(shares) if shares else 0.0, ccs


def difference_picture(im0, a0, im1, a1, out):
    """First frame, the frame that moved most, and the difference of their backgrounds (his cutout greyed out, the
    difference four times brighter): a still camera leaves the wall black; a moving one outlines everything in it."""
    from PIL import Image
    w = 640
    h = int(round(im0.height * w / im0.width))
    g0 = np.asarray(im0.convert("L").resize((w, h))).astype(np.float32)
    g1 = np.asarray(im1.convert("L").resize((w, h))).astype(np.float32)
    him = (np.asarray(Image.fromarray(a0).resize((w, h))) > 8) | (np.asarray(Image.fromarray(a1).resize((w, h))) > 8)
    d = np.clip(np.abs(g1 - g0) * 4, 0, 255)
    d[him] = 64
    sheet = Image.new("RGB", (3 * w + 16, h), (24, 23, 22))
    sheet.paste(im0.resize((w, h)), (0, 0))
    sheet.paste(im1.resize((w, h)), (w + 8, 0))
    sheet.paste(Image.fromarray(d.astype(np.uint8)).convert("RGB"), (2 * w + 16, 0))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return Path(out)


def check_still(ctx):
    """Cut him out of a few frames across the passage and measure the background. Stops with a plain sentence when
    the camera moves (before the long cutout step)."""
    pic = ctx.picture()
    H = float((ctx.passage.get("size") or [1920, 1080])[1])
    W = float((ctx.passage.get("size") or [1920, 1080])[0])
    ts = [ctx.duration * k / (STILL_SAMPLES - 1) for k in range(STILL_SAMPLES)]
    ts[-1] = max(0.0, ctx.duration - 0.1)
    ims = [grab(pic, t) for t in ts]
    with heavy.lock("matte camera check"):
        ctx.say("Checking that the camera stays still.")
        alphas = [matte.alpha(im) for im in ims]
    moves, share, ccs = background_move(ims, alphas)
    limit = STILL_LIMIT * min(W, H) / 1080
    k = 1 + int(np.argmax([-1 if m is None else m for m in moves])) if moves else 0
    pic_f = difference_picture(ims[0], alphas[0], ims[k], alphas[k], ctx.project.path("matte", "camera-check.png"))
    known = [m for m in moves if m is not None]
    worst = max(known) if known else None
    rec = {"samples_s": [round(t, 2) for t in ts], "move_px": [None if m is None else round(m, 2) for m in moves],
           "worst_px": None if worst is None else round(worst, 2), "limit_px": round(limit, 2),
           "background_share": round(share, 2), "picture": ctx.project.rel(pic_f),
           "compared_s": [round(ts[0], 2), round(ts[k], 2)], "match": ccs, "him": find_him(alphas[0])}
    if share < 0.12:
        rec["note"] = "he fills almost the whole frame, so there is little wall to measure or to write on"
    if worst is not None and worst > limit:
        raise StudioError(
            f"The camera moves in this part of the video (the room shifts by about {worst:.0f} pixels), so words "
            "set on the wall would slide against it. Words in the room needs a camera that stays still, on a tripod. "
            "Pick a part where the camera does not move, or use another style for this video (Screen and face, "
            "Documentary or Cutout work with a moving camera).")
    if any(c < MATCH_MIN for c in ccs):
        raise StudioError(
            "The picture cuts away to something else inside these words (another shot, a screen or a different "
            "angle), so there is no one wall to set the words on. Pick words where the picture stays on him in one "
            "shot, or use another style for this video.")
    return rec


def edge_holds(run_dir, frames):
    """A passage cut right at a shot change can carry a frame of the next or the previous shot at its ends, or the last
    frame of an old edit's caption. Such a frame is an orphan: the wall (his cutout masked away) changes between it and
    its neighbour, then stays put. Returns (first, last) 1-based frame numbers to use: frames outside them are replaced
    by the nearest clean one."""
    import cv2
    from PIL import Image
    n = len(frames)

    def small(k):
        f = frames[k - 1]
        g = np.asarray(Image.open(f).convert("L").resize((128, 72), Image.BILINEAR)).astype(np.float32)
        ap = run_dir / "alpha" / f"a{f.stem[1:]}.png"
        a = np.asarray(Image.open(ap).convert("L").resize((128, 72))) if ap.exists() else np.zeros((72, 128), np.uint8)
        return g, cv2.dilate((a > 8).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0

    def d(a, b):
        (ga, ma), (gb, mb) = small(a), small(b)
        x = np.abs(ga - gb)
        x[ma | mb] = 0
        return float(x.reshape(9, 8, 16, 8).mean((1, 3)).max())     # the most changed patch of wall

    first, last = 1, n
    if n >= 6:
        for k in range(n, n - 4, -1):                  # from the end backwards
            if d(k, k - 1) > ORPHAN and d(k - 1, k - 2) < STEADY:
                last = k - 1
                break
        for k in range(1, 4):                          # from the start forwards
            if d(k, k + 1) > ORPHAN and d(k + 1, k + 2) < STEADY:
                first = k + 1
                break
    return first, last


def fill_of(img, rows=8):
    a = np.asarray(img)[:rows].reshape(-1, 3).mean(0)
    return "#%02X%02X%02X" % tuple(int(round(x)) for x in a)


def write_room(ctx, run_dir, n_out, box, public):
    """Room plate (JPEG) and his cutout (PNG) for every reel frame, cropped to `box`."""
    from PIL import Image
    frames = sorted((run_dir / "frames").glob("f*.jpg"))
    if not frames:
        raise StudioError("Cutting him out produced no frames. The details are in the project's logs folder.")
    first, last = edge_holds(run_dir, frames)
    out = public / "room"
    out.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = box

    def one(k):
        src = min(max(k + 1, first), last)
        Image.open(run_dir / "frames" / f"f{src:05d}.jpg").crop(box).save(out / f"f{k + 1:05d}.jpg", quality=95)
        matte.cutout(run_dir, src).crop(box).save(out / f"p{k + 1:05d}.png", compress_level=1)

    n = min(n_out, last)
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
        list(ex.map(one, range(n)))
    first_img = Image.open(run_dir / "frames" / f"f{first:05d}.jpg").convert("RGB").crop((x0, 0, x1, max(1, y1)))
    return n, {"first": first, "last": last, "frames": len(frames)}, first_img


# ----------------------------------------------------------------------------------------------- the words
def font_for(kind, size):
    from PIL import ImageFont
    k = {"figure": ("title", 600), "line": ("display", 500), "type": ("archive", None), "title": ("caption", 800)}[kind]
    f = ImageFont.truetype(str(brand.font_path(k[0])), int(size))
    if k[1]:
        try:
            f.set_variation_by_axes([k[1]])
        except Exception:
            pass
    return f


def text_width(kind, text, size):
    """Width the composition draws: advance plus letter spacing (Chrome adds it after every letter; the title takes
    its last spacing back)."""
    f = font_for(kind, size)
    adv = f.getlength(text) + TRACK[kind] * size * len(text)
    if kind == "title":
        adv -= TRACK[kind] * size
    return adv


def ink_box(kind, text, size, left, y):
    """The text's ink box at a line height of 1 with its top at `y` (what QA checks)."""
    f = font_for(kind, size)
    asc, desc = f.getmetrics()
    base = y + (size - (asc + desc)) / 2 + asc
    x0, t0, x1, t1 = f.getbbox(text, anchor="ls")
    width = text_width(kind, text, size)
    return (left + min(0, x0), base + t0, max(width, x1 - min(0, x0)), t1 - t0)


def plan_wall(ctx, total):
    fps = ctx.fps
    items = []

    def fr(a, field):
        return int(round(ctx.at(a, field) * fps))

    for k, it in enumerate(ctx.spec["wall"]):
        kind = it["kind"]
        size = float(it.get("size", SIZES[kind]))
        t_at = ctx.at(it["at"], f"wall[{k}].at")
        width = text_width(kind, it["text"], size)
        x = it.get("x", "center")
        left = (ctx.w - width) / 2 if x == "center" else float(x)
        brush = None
        if "strike" in it:
            bw = width + 0.8 * size
            brush = {"left": round(left + width / 2 - bw / 2, 1), "width": round(bw, 1)}
        items.append({
            "kind": kind, "text": it["text"], "x": None if x == "center" else float(x), "y": float(it["y"]),
            "size": size, "at": None if t_at <= OPEN_WITHIN else int(round(t_at * fps)),
            "warm": fr(it["warm"], f"wall[{k}].warm") if "warm" in it else None,
            "strike": fr(it["strike"], f"wall[{k}].strike") if "strike" in it else None,
            "dim": fr(it["dim"], f"wall[{k}].dim") if "dim" in it else None,
            "until": fr(it["until"], f"wall[{k}].until") if "until" in it else None,
            "leave": it.get("leave", "lift"),
            "stack": [fr(a, f"wall[{k}].stack[{j}]") for j, a in enumerate(it.get("stack") or [])],
            "cx": round(left + width / 2, 1), "brush": brush, "_left": left, "_width": width,
        })
    return items


def camera_of(ctx):
    c = ctx.spec.get("camera") or {}
    return {"push": float(c.get("push", 0.085)), "drift": float(c.get("drift", -14)),
            "focus": [float(v) for v in c.get("focus", [ctx.w / 2, ctx.h * 0.45])],
            "light": [float(v) for v in c.get("light", [ctx.w / 2, ctx.h * 0.56])]}


def _ease_in_out(x):
    # Bezier(0.65, 0, 0.35, 1), solved for x like Remotion's Easing.bezier
    lo, hi = 0.0, 1.0
    for _ in range(40):
        t = (lo + hi) / 2
        bx = 3 * (1 - t) ** 2 * t * 0.65 + 3 * (1 - t) * t * t * 0.35 + t ** 3
        lo, hi = (t, hi) if bx < x else (lo, t)
    t = (lo + hi) / 2
    return 3 * (1 - t) * t * t + t ** 3


def seen_box(box, cam, f, total):
    p = min(1.0, max(0.0, f / max(1, total)))
    s = 1.0 + cam["push"] * _ease_in_out(p)
    d = cam["drift"] * p
    fx, fy = cam["focus"]
    x, y, w, h = box
    return (fx + (x - fx) * s, fy + d + (y - fy) * s, w * s, h * s)


def union(a, b):
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1))


def record_layout(ctx, items, cam, total, color, red):
    fps = ctx.fps
    for k, it in enumerate(items):
        f0 = 0 if it["at"] is None else it["at"]
        f1 = it["until"] + (16 if it["leave"] == "lift" else 10) if it["until"] is not None else total
        f1 = min(f1, total)
        b = ctx.layout.beat(it["kind"], f0 / fps, f1 / fps, i=k)
        box = ink_box(it["kind"], it["text"], it["size"], it["_left"], it["y"])
        ctx.layout.text(b, it["text"], union(seen_box(box, cam, f0, total), seen_box(box, cam, f1, total)),
                        role="words", color=color)
        if it["brush"] is not None:
            bb = (it["brush"]["left"], it["y"] + 0.19 * it["size"], it["brush"]["width"], 0.72 * it["size"])
            ctx.layout.mark(b, "brush strike", union(seen_box(bb, cam, it["strike"], total),
                                                     seen_box(bb, cam, f1, total)), red=True, color=red)


# ----------------------------------------------------------------------------------------------- render
def render(ctx):
    fps = ctx.fps
    n_pass = int(math.ceil(ctx.duration * fps))
    hold = float(ctx.spec.get("end_hold", END_HOLD))
    total = n_pass + int(round(hold * fps))
    timing = {}

    still = check_still(ctx)
    W, H, s, left, top, fill = room_geometry(ctx, still.get("him"))

    t = time.time()
    info = matte.matte_clip(ctx.project, t0=0.0, t1=ctx.duration, fps=fps)
    timing["matte_s"] = round(time.time() - t, 1)
    timing["matte_s_per_frame"] = info.get("s_per_frame")
    run_dir = ctx.project.resolve(info["run"])

    public = ctx.work / "public"
    public.mkdir(parents=True, exist_ok=True)
    box = crop_box(ctx, W, H, s, left, top)
    x0, y0, x1, y1 = box
    ctx.say("Setting the room.")
    n_room, edges, first_img = write_room(ctx, run_dir, n_pass, box, public)
    if fill is None:
        fill = fill_of(first_img)
    for name, kind in (("serif.ttf", "title"), ("serif-italic.ttf", "display"), ("sans.ttf", "caption"),
                       ("type.ttf", "archive")):
        remotion.place(brand.font_path(kind), public / "fonts" / name)
    remotion.place(brand.brush(BRUSH), public / "brush-red.png")

    room_top = top + y0 * s
    room_bottom = top + H * s
    fb1 = min(FADE_BOTTOM[1], room_bottom)
    room = {"n": n_room, "left": round(left + x0 * s, 2), "top": round(room_top, 2),
            "width": round((x1 - x0) * s, 2), "height": round((y1 - y0) * s, 2),
            "fadeTop": [round(top, 2), round(top + FADE_TOP, 2)] if top > 0 else None,
            "fadeBottom": [round(fb1 - (FADE_BOTTOM[1] - FADE_BOTTOM[0]), 2), round(fb1, 2)]}
    cam = camera_of(ctx)
    items = plan_wall(ctx, total)
    color = ctx.spec.get("color", COLOR)
    props = {"w": ctx.w, "h": ctx.h, "fps": fps, "frames": total, "fill": fill, "color": color,
             "fonts": {"serif": "fonts/serif.ttf", "serifItalic": "fonts/serif-italic.ttf", "sans": "fonts/sans.ttf",
                       "type": "fonts/type.ttf"},
             "brush": "brush-red.png", "room": room, "camera": cam,
             "items": [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]}
    t = time.time()
    motion = remotion.render("words-in-the-room", props, public, ctx.work / "motion.mp4", log=ctx.log)
    timing["motion_s"] = round(time.time() - t, 1)

    ctx.say("Adding film grain.")
    pic = ctx.work / "picture.mp4"
    grain = int((ctx.spec.get("finish") or {}).get("grain", GRAIN))
    vf = (f"noise=c0s={grain}:c0f=t+u:c1s=2:c1f=t+u:c2s=2:c2f=t+u,format=yuv420p,"
          "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(motion), "-vf", vf, "-frames:v", str(total),
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-r", fps_str(fps), "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-color_range", "tv", "-movflags", "+faststart", "-an", pic], log=ctx.log)

    ctx.say("Mixing the sound.")
    levels = ctx.sound(duration=total / fps)
    red = ctx.brand["colors"].get("red_on_footage", ctx.brand["colors"]["red"])
    record_layout(ctx, items, cam, total, color, red)
    mux(pic, ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    rec = {"camera": still, "matte": {"run": info["run"], "frames": info["frames"], "matted_now": info["matted_now"],
                                      "device": info.get("device"), **edges},
           "timing": timing, "fill": fill, "crop": list(box),
           "room": {"scale": round(s, 4), "left": left, "top": top},
           "wall": [{"i": k, "text": it["text"], "box": [round(v, 1) for v in ink_box(it["kind"], it["text"], it["size"],
                                                                                      it["_left"], it["y"])],
                     "t0": round((it["at"] or 0) / fps, 3),
                     "t1": round((it["until"] if it["until"] is not None else total) / fps, 3)}
                    for k, it in enumerate(items)]}
    him = still.get("him")
    if him:
        rec["his_head_in_reel"] = {"top": round(top + him["head_top"] * s), "centre_x": round(left + him["head_x"] * s),
                                  "width": round(him["head_width"] * s)}
    (ctx.out / "room.json").write_text(json.dumps(rec, indent=1))
    return {"output": "final.mp4", "levels": levels, "keep_work": bool(os.environ.get("STUDIO_KEEP_WORK"))}


def wall_fit(wall, gap=WALL_GAP):
    """Blocks on the wall at the same time keep at least `gap` px apart (a bigger figure can grow into the line above
    it). Measured on the wall itself (the camera moves every block together), from when a block is set until it starts
    to leave."""
    bad = []
    for i, a in enumerate(wall):
        for b in wall[i + 1:]:
            if min(a["t1"], b["t1"]) - max(a["t0"], b["t0"]) <= 0:
                continue
            ax, ay, aw, ah = a["box"]
            bx, by, bw, bh = b["box"]
            if ax < bx + bw + gap and bx < ax + aw + gap and ay < by + bh + gap and by < ay + ah + gap:
                bad.append({"blocks": [a["i"], b["i"]], "texts": [a["text"], b["text"]]})
    return {"pass": not bad, "too_close": bad, "gap_px": gap}


def qa_extra(project, version_dir, layout):
    """camera_still: the background moved no more than the limit against the first frame (measured on the cutout's
    background before the render). wall_fit: blocks on the wall at the same time do not run into each other."""
    out = {}
    f = Path(version_dir) / "room.json"
    if f.exists():
        rec = json.loads(f.read_text())
        if "wall" in rec:
            out["wall_fit"] = wall_fit(rec["wall"])
        cam = rec.get("camera") or {}
        worst = cam.get("worst_px")
        out["camera_still"] = {"pass": worst is None or worst <= cam.get("limit_px", STILL_LIMIT), **cam}
    return out
