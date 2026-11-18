"""Screen and Face: his real screen on top, him below, and a black seam between them where the number lands.

The picture is drawn by the shared Remotion project (engine/remotion/src/screen-and-face/). This module turns the spec
into frames for it: the screen shots cut from his screen recording, his face panel from the passage picture, and every
figure's moments resolved from his words. Then film grain, the finished sound and the deliverable.
"""
import math
import os
from pathlib import Path

from studio_engine import brand, remotion
from studio_engine.errors import StudioError
from studio_engine.layout import text_box
from studio_engine.media import safe_input
from studio_engine.render import mux
from studio_engine.util import fps_str, probe, run

KIND = "reel"
LABELS = []

# the frame, as Bernard picked it (mirrors ScreenAndFace.tsx)
BAND_Y, BAND_H = 820, 190
BOT_Y = BAND_Y + BAND_H
SIDE = 80
NUM_SIZE, LINE_SIZE, LINE_H = 168, 50, 54
SCALE_MIN, SCALE_MAX = 0.7, 1.4   # a figure's `scale` (his "make the number bigger"): 168 px times this
STRIKE_H = 132               # the red brush across a figure at scale 1
PUNCH = 1.06                 # every second take is pushed in 6 percent to soften the jump cut
GRAIN = 7                    # film grain strength (ffmpeg noise)
OPEN_WITHIN = 0.25           # a figure anchored this close to the start is on screen from the first frame
LINE_COLOR = "#3A3631"       # the seam's hairlines
STILLS = (".png", ".jpg", ".jpeg", ".heic", ".webp")
JOIN_SOUND = {"name": "whoosh", "under_db": 29, "len": 0.9, "offset": -0.08}


# ----------------------------------------------------------------------------------------------- checks
def _anchors(b):
    out = [("at", b.get("at"))]
    for k in ("rule", "strike", "underline", "until"):
        if k in b:
            out.append((k, b[k]))
    for j, ln in enumerate(b.get("lines") or []):
        if "at" in ln:
            out.append((f"lines[{j}].at", ln["at"]))
    return out


def validate(spec, words, duration):
    from studio_engine.layout import resolve_at
    beats = spec.get("beats") or []
    if not beats:
        raise StudioError("This style needs at least one figure in the spec's beats (the number in the seam).")
    last = -1.0
    for k, b in enumerate(beats):
        for name, a in _anchors(b):
            resolve_at(a, words, duration, field=f"beats[{k}].{name}")
        t = resolve_at(b["at"], words, duration)
        if t < last:
            raise StudioError(f"The spec's beats[{k}] comes before the figure above it. Put the figures in the order "
                              "he says them.")
        last = t
        sc = float(b.get("scale", 1.0))
        if not SCALE_MIN <= sc <= SCALE_MAX:
            raise StudioError(f"The spec's beats[{k}].scale is {sc}; it must be between {SCALE_MIN} and {SCALE_MAX}.")
        if sc != 1.0:
            lines = [ln["text"] for ln in b.get("lines") or []]
            w = int((spec.get("format") or {}).get("w", 1080))
            why = fits_seam(str(b.get("text", "")), sc, lines, w)
            if why:
                most = max_scale(str(b.get("text", "")), lines, w)
                raise StudioError(f"The spec's beats[{k}] figure \"{b.get('text')}\" at scale {sc} is {why}; "
                                  + (f"the most it can take is {most:.2f}." if most else "use scale 1."))
        if "strike" in b and "underline" in b:
            raise StudioError(f"The spec's beats[{k}] has both a strike and an underline. Each figure gets one red at "
                              "most: pick one.")
    shots = spec.get("screens") or []
    if not shots:
        raise StudioError('This style needs his screen: add at least one entry to the spec\'s "screens".')
    prev = -1.0
    for k, s in enumerate(shots):
        t = resolve_at(s.get("from", {"t": 0.0}), words, duration, field=f"screens[{k}].from")
        if t < prev:
            raise StudioError(f"The spec's screens[{k}] starts before the shot above it. Put the shots in order.")
        prev = t


# The composition draws lining figures ("lnum"), which PIL cannot select, so digits and the dollar sign use their
# measured size in the browser (em fractions, from rendered frames): ink top above the baseline, ink bottom below it,
# advance. Other characters are measured with PIL. The baseline sits 0.315 em under the seam's centre line.
LINING = {"digit": (0.643, 0.0, 0.491), "$": (0.732, 0.101, 0.5)}
BASELINE = 0.315
TAILS = set(",.;gjpqy")      # tails (commas, descenders) may reach a little past the seam's edge, as at scale 1
TAIL_PAST = 8                # how far, in px
BODY_IN = 3                  # everything else stays this far inside the seam's hairlines


def figure_box(text, scale=1.0):
    """(box, body_box) of a figure as the composition draws it: x, y, w, h on the frame. `box` holds every ink and
    the full advance; `body_box` leaves out the tails."""
    size = NUM_SIZE * scale
    f = kit_font("title", size, 600)
    base = BAND_Y + BAND_H / 2 + BASELINE * size
    x, tops, bots, btops, bbots = float(SIDE), [], [], [], []
    for ch in text:
        if ch.isdigit() or ch == "$":
            up, down, adv = LINING["digit" if ch.isdigit() else "$"]
            top, bot, adv = base - up * size, base + down * size, adv * size
        elif ch.isspace():
            x += f.getlength(ch)
            continue
        else:
            _, t, _, bt = f.getbbox(ch, anchor="ls")
            top, bot, adv = base + t, base + bt, f.getlength(ch)
        tops.append(top)
        bots.append(bot)
        if ch not in TAILS:
            btops.append(top)
            bbots.append(bot)
        x += adv
    if not tops:
        return (SIDE, base, 0, 0), (SIDE, base, 0, 0)
    box = (SIDE, min(tops), x - SIDE, max(bots) - min(tops))
    body = (SIDE, min(btops or tops), x - SIDE, max(bbots or bots) - min(btops or tops))
    return box, body


def fits_seam(text, scale, lines=(), w=1080):
    """None when the figure fits at this scale, else the reason in a few plain words."""
    box, body = figure_box(text, scale)
    if body[1] < BAND_Y + BODY_IN or body[1] + body[3] > BAND_Y + BAND_H - BODY_IN:
        return "too tall for the seam"
    if box[1] < BAND_Y - TAIL_PAST or box[1] + box[3] > BAND_Y + BAND_H + TAIL_PAST:
        return "its tail runs out of the seam"
    line_f = kit_font("display", LINE_SIZE, 500)
    room = w - SIDE - (max(line_f.getlength(t) for t in lines) + 24 if lines else 0)
    if box[0] + box[2] > room:
        return "too wide next to its lines" if lines else "too wide for the frame"
    return None


def max_scale(text, lines=(), w=1080):
    """The biggest `scale` (in steps of 0.01) at which the figure fits the seam: top to bottom inside its hairlines,
    and 24 px clear of its lines on the right."""
    best = None
    for k in range(int(SCALE_MIN * 100), int(SCALE_MAX * 100) + 1):
        if fits_seam(text, k / 100, lines, w) is None:
            best = k / 100
    return best


# ----------------------------------------------------------------------------------------------- pieces
def frame_of(ctx, a, field):
    return int(round(ctx.at(a, field) * ctx.fps))


def plan_figures(ctx, total):
    fps = ctx.fps
    beats = ctx.spec["beats"]
    figs = []
    starts = [ctx.at(b["at"], f"beats[{k}].at") for k, b in enumerate(beats)]
    for k, b in enumerate(beats):
        open_ = starts[k] <= OPEN_WITHIN and k == 0
        in_at = 0 if open_ else int(round(starts[k] * fps))
        if "until" in b:
            out_at = frame_of(ctx, b["until"], f"beats[{k}].until")
        elif k + 1 < len(beats):
            out_at = int(round(starts[k + 1] * fps)) - 6
        else:
            out_at = None
        strike = frame_of(ctx, b["strike"], f"beats[{k}].strike") if "strike" in b else None
        lines = []
        for j, ln in enumerate(b.get("lines") or []):
            at = frame_of(ctx, ln["at"], f"beats[{k}].lines[{j}].at") if "at" in ln else in_at
            lines.append({"text": ln["text"], "at": at})
        if strike is not None:
            lines_out = strike + 2
        elif out_at is not None:
            lines_out = out_at - 2
        else:
            lines_out = None
        figs.append({"text": b["text"], "scale": float(b.get("scale", 1.0)), "open": open_, "inAt": in_at,
                     "ruleAt": frame_of(ctx, b["rule"], f"beats[{k}].rule") if "rule" in b else None,
                     "strikeAt": strike, "outAt": out_at, "lines": lines, "linesFrom": 0,
                     "linesOutAt": lines_out, "linesCut": None if lines_out is None else lines_out + 8,
                     "underlineAt": frame_of(ctx, b["underline"], f"beats[{k}].underline") if "underline" in b else None})
    for a, b in zip(figs, figs[1:]):
        b["linesFrom"] = a["linesCut"] if a["linesCut"] is not None else b["inAt"]
    return figs


def face_box(ctx):
    """Where his picture sits in the bottom panel: `zoom` 1 just fills the panel, `x` and `y` are the point of his
    picture (fractions) at the panel's centre line and top edge."""
    size = ctx.passage.get("size") or [1920, 1080]
    W, H = float(size[0]), float(size[1])
    pw, ph = ctx.w, ctx.h - BOT_Y
    f = ctx.spec.get("face") or {}
    zoom = float(f.get("zoom", 1.0))
    s = zoom * max(pw / W, ph / H)
    w, h = W * s, H * s
    left = min(0.0, max(pw - w, pw / 2 - float(f.get("x", 0.5)) * w))
    top = min(0.0, max(ph - h, -float(f.get("y", 0.0)) * h))
    return {"left": round(left, 2), "top": round(top, 2), "width": round(w, 2), "height": round(h, 2)}


def cut_shot(ctx, src, t_in, speed, frames, out, src_dur, t_out=None):
    """One screen shot: from `t_in` on the screen source, `frames` long at the output rate, sped up or slowed by
    `speed`; holds its last frame from `t_out` (or where the recording runs out)."""
    if Path(src).suffix.lower() in STILLS:
        t_in, t_out, speed = 0.0, None, 1.0
    elif t_in < 0 or t_in >= src_dur:
        raise StudioError(f"A screen shot starts at {t_in:.1f} seconds, but the screen recording is {src_dur:.1f} "
                          "seconds long.")
    need = frames / ctx.fps * speed
    if t_out is not None:
        if t_out <= t_in:
            raise StudioError(f"A screen shot ends at {t_out:.1f} seconds, before it starts at {t_in:.1f}.")
        need = min(need, t_out - t_in)
    vf = (f"setpts=(PTS-STARTPTS)/{speed:.6f},fps={fps_str(ctx.fps)},scale='min(1920,iw)':-2,"
          f"tpad=stop_mode=clone:stop_duration={frames / ctx.fps + 1:.3f},format=yuv420p")
    span = need + (0.5 if t_out is None else 0.0)
    if Path(src).suffix.lower() in STILLS:          # a screenshot: held for the whole shot
        head = ["-loop", "1", "-framerate", fps_str(ctx.fps), *safe_input(src)]
    else:
        head = ["-ss", f"{t_in:.4f}", "-t", f"{span:.4f}", *safe_input(src)]
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *head, "-vf", vf, "-frames:v", str(frames + 2), "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "12", out],
        log=ctx.log)


def plan_screens(ctx, total, public):
    shots = ctx.spec["screens"]
    starts = [frame_of(ctx, s.get("from", {"t": 0.0}), f"screens[{k}].from") for k, s in enumerate(shots)]
    starts[0] = 0
    out, durs = [], {}
    for k, s in enumerate(shots):
        end = starts[k + 1] if k + 1 < len(shots) else total
        n = max(1, end - starts[k])
        src = ctx.source(s.get("source", "screen"))
        if str(src) not in durs:
            durs[str(src)] = 0.0 if Path(src).suffix.lower() in STILLS else probe(src)["duration"]
        name = f"screen-{k}.mp4"
        cut_shot(ctx, src, float(s.get("in", 0.0)), float(s.get("speed", 1.0)), n, public / name, durs[str(src)],
                 float(s["out"]) if "out" in s else None)
        out.append({"src": name, "from": starts[k], "dur": n, "push": list(s.get("push", [1.0, 1.05])),
                    "origin": s.get("origin", "50% 50%")})
    return out


def record_layout(ctx, figs, total):
    """Every text box and red element, for QA (boxes measured with the same fonts at the same sizes)."""
    fps = ctx.fps
    line_f = kit_font("display", LINE_SIZE, 500)
    red = ctx.brand["colors"]["red"]
    cream = ctx.brand["colors"]["cream"]
    cy = BAND_Y + BAND_H / 2
    for k, g in enumerate(figs):
        t0 = 0.0 if g["open"] else g["inAt"] / fps
        t1 = (g["outAt"] + 8) / fps if g["outAt"] is not None else total / fps
        b = ctx.layout.beat("figure", t0, min(t1, total / fps), i=k)
        nb = figure_box(g["text"], g["scale"])[0]
        ctx.layout.text(b, g["text"], nb, role="words", color=cream)
        n = len(g["lines"])
        y = cy - (n - 1) * LINE_H / 2
        lboxes = []
        for ln in g["lines"]:
            # the browser right-aligns each line's advance on the margin; its italic ink stays within a pixel of it
            # (measured on rendered frames), while PIL's ink box for italics reaches up to 8 px further. So the box is
            # the line's layout box: its advance width, ending on the margin.
            _, top, _, hh = text_box(line_f, ln["text"], ctx.w - SIDE, y, "rm")
            adv = line_f.getlength(ln["text"])
            bx = (ctx.w - SIDE - adv, top, adv, hh)
            ctx.layout.text(b, ln["text"], bx, role="words", color=cream)
            lboxes.append(bx)
            y += LINE_H
        if g["strikeAt"] is not None:
            x, yy, w, h = nb
            sh = STRIKE_H * g["scale"]
            ctx.layout.mark(b, "brush strike", (x - 40, cy - sh / 2, w + 70, sh), red=True, color=red)
        if g["underlineAt"] is not None and lboxes:
            x0 = min(bx[0] for bx in lboxes)
            ctx.layout.mark(b, "underline", (x0, lboxes[-1][1] + lboxes[-1][3] + 6, ctx.w - SIDE - x0, 3), red=True,
                            color=red)


def kit_font(kind, size, weight):
    """A kit font at the weight the composition draws it (the kit's own weight may differ)."""
    from PIL import ImageFont
    f = ImageFont.truetype(str(brand.font_path(kind)), int(round(size)))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


# ----------------------------------------------------------------------------------------------- render
def render(ctx):
    fps = ctx.fps
    total = int(math.ceil(ctx.duration * fps))
    public = ctx.work / "public"
    public.mkdir(parents=True, exist_ok=True)
    for name, kind in (("serif.ttf", "title"), ("serif-italic.ttf", "display")):
        remotion.place(brand.font_path(kind), public / "fonts" / name)
    remotion.place(brand.brush("red-a"), public / "brush-red.png")
    remotion.place(ctx.picture(), public / "face.mp4")

    ctx.say("Cutting the screen shots.")
    screens = plan_screens(ctx, total, public)
    figs = plan_figures(ctx, total)
    segs = ctx.passage.get("segments") or [{"at": 0.0}]
    face = dict(face_box(ctx), src="face.mp4",
                segments=[{"from": int(round(s["at"] * fps)), "punch": PUNCH if k % 2 else 1.0}
                          for k, s in enumerate(segs)])
    c = ctx.brand["colors"]
    props = {"w": ctx.w, "h": ctx.h, "fps": fps, "frames": total,
             "colors": {"black": c["black"], "cream": c["cream"], "red": c["red"], "line": LINE_COLOR},
             "fonts": {"serif": "fonts/serif.ttf", "serifItalic": "fonts/serif-italic.ttf"},
             "brush": "brush-red.png", "face": face, "screens": screens, "figures": figs}
    motion = remotion.render("screen-and-face", props, public, ctx.work / "motion.mp4", log=ctx.log)

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
    extra = []
    js = ctx.spec.get("join_sound", JOIN_SOUND)
    if js and len(segs) > 1:
        js = dict(JOIN_SOUND, **js) if isinstance(js, dict) else dict(JOIN_SOUND)
        for s in segs[1:]:
            extra.append({"name": js["name"], "t": max(0.0, s["at"] + float(js.get("offset", 0.0))),
                          "under_db": js["under_db"], "len": js.get("len")})
    levels = ctx.sound(extra_sfx=extra)
    record_layout(ctx, figs, total)
    mux(pic, ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels, "keep_work": bool(os.environ.get("STUDIO_KEEP_WORK"))}


def qa_extra(project, version_dir, layout):
    """seam_fit: in every figure the number and its lines keep at least 24 px apart (a long figure and long lines
    would run into each other in the seam)."""
    bad = []
    for b in layout["beats"]:
        texts = b["texts"]
        if not texts:
            continue
        x, _, w, _ = texts[0]["box"]
        right = x + w
        for t in texts[1:]:
            if t["box"][0] < right + 24:
                bad.append({"beat": b["i"], "figure": texts[0]["text"], "line": t["text"]})
    return {"seam_fit": {"pass": not bad, "too_close": bad}}
