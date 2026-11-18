"""Documentary: a short documentary in the 9:16 frame (see SPEC.md).

A 2:1 picture band (1080 x 540, y 470 to 1010) framed by hairlines, black above and below. Shots cut on his words,
each with one slow push or lateral move, a sub-pixel gate weave, the kit's film grade, halation and grain. Above the
band an archive reel mark and a lower third with his name; in the bottom third the figure (the claim, on screen from
the first frame), its source line, a red brush under it on the word that proves it, then the count down to the new
figure on the word he says it; documentary subtitles under it, and a closing red line that takes their place.
Score: the documentary bed (D minor, B flat, F) with felt mallets on the figure moments, a projector under the open
and clock ticks under the count (both code-made).
"""
import math
import re

import numpy as np

from studio_engine import brand, heavy
from studio_engine import film as L
from studio_engine.errors import StudioError
from studio_engine.layout import resolve_at, text_box
from studio_engine.render import IN709, Encoder, Reader, mux, poster
from studio_engine import sound as snd
from studio_engine.util import probe


KIND = "reel"
NAME = "BERNARD ABLOLA"
MARKS = [f"FIELD NOTES  ·  REEL {n:02d}" for n in range(1, 100)]


def _saved_title():
    try:
        t = brand.style_settings("documentary").get("title")
    except Exception:
        return None
    return t.strip() if isinstance(t, str) and t.strip() else None


LABELS = [NAME] + MARKS + ([_saved_title()] if _saved_title() else [])

# the frame, as Bernard picked it
ASPECT = 2.0                   # the band is 2:1
BY, BH = 470, 540              # band top and height
FIG_Y = 1235                   # the figure's baseline (bottom third)
SUB_Y = 1490                   # the subtitles' baseline, and the closing line's
SUB_SIZE = 42                  # subtitle size at the default caption setting (his setting scales it)
MARK_Y = 250                   # the reel mark's baseline (above the band)
LT_X, LT_NAME_Y, LT_TITLE_Y = 120, 368, 420
FIG_SIZE = 190                 # default figure size
COUNT = 0.55                   # the count runs this long and lands on the new figure's word
LT_HOLD = 2.45                 # the lower third stays this long
AFTER_LAST = 1.38              # the piece ends this long after his last word
FADE_AFTER = 0.63              # the picture fades out from this long after his last word, over 0.6 s
GRAIN = 0.04
STILLS = (".png", ".jpg", ".jpeg", ".heic", ".webp")

# levels as he heard them (dB under his voice: the bed integrated, the effects at their loudest)
BED = {"name": "documentary", "under_db": 16.5}
DUCK_DB = 3.5
PROJECTOR_UNDER, TICK_UNDER, TICKS, TICK_STEP = 31, 33, 6, 0.09

NUM_RE = re.compile(r"^([^\d]*?)(\d[\d,]*(?:\.\d+)?)(.*)$")


# ----------------------------------------------------------------------------------------------- checks
def _num(txt):
    m = NUM_RE.match(txt or "")
    if not m:
        return None
    return m.group(1), float(m.group(2).replace(",", "")), m.group(3), "," in m.group(2)


def max_size(texts):
    """The largest figure size at which every figure line fits between the side margins."""
    W = brand.load()["formats"]["reel"]["w"]
    room = W - 2 * brand.safe()["side"]
    for s in range(300, 99, -2):
        if all(_fig_width(t, u, s) <= room for t, u in texts):
            return s
    return 100


def _fig_width(text, unit, size):
    f = brand.font("display", size)
    w = f.getlength(text)
    if unit:
        w += 18 * size / FIG_SIZE + brand.font("display_soft", round(70 * size / FIG_SIZE)).getlength(unit)
    return w


def validate(spec, words, duration):
    shots = spec.get("shots") or []
    if not shots:
        raise StudioError('This style needs at least one shot in the spec\'s "shots" (what the band shows).')
    prev = -1.0
    for k, s in enumerate(shots):
        t = 0.0 if k == 0 else resolve_at(s.get("from"), words, duration, field=f"shots[{k}].from")
        if t <= prev:
            raise StudioError(f"The spec's shots[{k}] starts before or with the shot above it. Put the shots in order.")
        prev = t
    fig = spec.get("figure")
    if fig:
        to = fig.get("to") or {}
        size = int(fig.get("size", FIG_SIZE))
        texts = [(fig["text"], None)] + ([(to["text"], to.get("unit"))] if to else [])
        if any(_fig_width(t, u, size) > 920 for t, u in texts):
            raise StudioError(f"The figure is too wide for the frame at size {size}. The largest size that fits is "
                              f"{max_size(texts)}; or use a shorter figure.")
        if to:
            t_to = resolve_at(to["at"], words, duration, field="figure.to.at")
            if t_to < COUNT:
                raise StudioError("The figure's count lands too early: the new figure needs its word at least half a "
                                  "second in.")
            if "underline" in fig and resolve_at(fig["underline"], words, duration, "figure.underline") > t_to - COUNT - 0.2:
                raise StudioError("The red underline comes too late: put it on a word before the new figure.")
        for fld in ("at", "underline"):
            if fld in fig:
                resolve_at(fig[fld], words, duration, field=f"figure.{fld}")
    for k, s in enumerate(spec.get("subtitles") or []):
        a, b = s["from"], s["to"]
        if not (0 <= a <= b < len(words)):
            raise StudioError(f"The spec's subtitles[{k}] needs word numbers from 0 to {len(words) - 1}, the first not "
                              "after the last.")
        if k and a <= spec["subtitles"][k - 1]["to"]:
            raise StudioError(f"The spec's subtitles[{k}] overlaps the line above it. Each word goes in one line.")
    if spec.get("close"):
        resolve_at(spec["close"]["at"], words, duration, field="close.at")
    lt = spec.get("lower_third")
    if isinstance(lt, dict):
        if "at" in lt:
            resolve_at(lt["at"], words, duration, field="lower_third.at")
        title = (lt.get("title") or "").strip()
        if title and title != _saved_title():
            raise StudioError(
                f'The title "{title}" under his name has to be his own. Ask him how he titles himself, and on his yes '
                f'save it with: studio brand set style.documentary.title "{title}"')


# ----------------------------------------------------------------------------------------------- pieces
def auto_subtitles(words):
    """His words in short lines: a line ends on a full stop or comma, or at five words or about 26 letters."""
    out, cur = [], []
    for w in words:
        trial = " ".join(x["w"] for x in cur + [w])
        if cur and (len(cur) >= 5 or len(trial) > 26):
            out.append({"from": cur[0]["i"], "to": cur[-1]["i"]})
            cur = []
        cur.append(w)
        if w["w"][-1:] in ".,?!;:":
            out.append({"from": cur[0]["i"], "to": cur[-1]["i"]})
            cur = []
    if cur:
        out.append({"from": cur[0]["i"], "to": cur[-1]["i"]})
    return out


class Shots:
    """Frames for the band: each shot reads his talking picture (on the passage clock) or a named source."""

    def __init__(self, ctx, total):
        self.ctx, self.total = ctx, total
        self.plan = []
        for k, s in enumerate(ctx.spec["shots"]):
            t0 = 0.0 if k == 0 else ctx.at(s["from"], f"shots[{k}].from")
            self.plan.append(dict(s, t0=t0))
        for a, b in zip(self.plan, self.plan[1:]):
            a["t1"] = b["t0"]
        self.plan[-1]["t1"] = total
        self.readers, self.sizes, self.stills = {}, {}, {}

    def _size(self, name):
        if name not in self.sizes:
            if name is None:
                sz = self.ctx.passage.get("size")
                if not sz:
                    v = probe(self.ctx.picture())["video"]
                    sz = [v["w"], v["h"]]
            else:
                p = self.ctx.source(name)
                if p.suffix.lower() in STILLS:
                    from PIL import Image
                    im = Image.open(p).convert("RGB")
                    self.stills[name] = np.asarray(im)
                    sz = list(im.size)
                else:
                    v = probe(p)["video"]
                    if not v:
                        raise StudioError(f'The source "{name}" has no picture.')
                    sz = [v["w"], v["h"]]
            self.sizes[name] = (int(sz[0]), int(sz[1]))
        return self.sizes[name]

    def _frame(self, name, idx):
        size = self._size(name)
        if name in self.stills:
            return self.stills[name]
        if name not in self.readers:
            path = self.ctx.picture() if name is None else self.ctx.source(name)
            self.readers[name] = Reader(path, size, self.ctx.fps, vf=IN709)
        return self.readers[name].get(idx)

    def at(self, t):
        k = 0
        for j, s in enumerate(self.plan):
            if t >= s["t0"]:
                k = j
        return k

    def band(self, t, i):
        import cv2
        s = self.plan[self.at(t)]
        name = s.get("source")
        fps = self.ctx.fps
        if name is None:
            fr = self._frame(None, round(t * fps))
        else:
            fr = self._frame(name, round((float(s.get("in", 0.0)) + (t - s["t0"]) * float(s.get("speed", 1.0))) * fps))
        sw, sh = fr.shape[1], fr.shape[0]
        u = (t - s["t0"]) / max(1e-6, s["t1"] - s["t0"])
        p = L.ease_in_out(u) * 0.85 + 0.15 * L.clamp(u)
        a, b = s.get("start") or {}, s.get("end") or s.get("start") or {}
        cx = (a.get("x", 0.5) + (b.get("x", 0.5) - a.get("x", 0.5)) * p) * sw
        cy = (a.get("y", 0.5) + (b.get("y", 0.5) - a.get("y", 0.5)) * p) * sh
        zoom = a.get("zoom", 1.0) + (b.get("zoom", 1.0) - a.get("zoom", 1.0)) * p
        cw = min(sw / max(zoom, 0.1), sh * ASPECT)          # never taller than the source
        ch = cw / ASPECT
        x0 = float(np.clip(cx - cw / 2, 0, sw - cw))
        y0 = float(np.clip(cy - ch / 2, 0, sh - ch))
        jx, jy = np.random.default_rng(i).normal(0, 0.25, 2)       # gate weave, under half a pixel
        W = self.ctx.w
        sc = W / cw
        M = np.float32([[sc, 0, -(x0 + jx) * sc], [0, sc, -(y0 + jy) * sc]])
        img = cv2.warpAffine(L.to_f(fr), M, (W, BH), flags=cv2.INTER_AREA if sc < 1 else cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REFLECT)
        tone = s.get("tone") or ("face" if name is None else "screen")
        img = np.clip(img * 1.12, 0, 1) if tone == "face" else np.clip(img, 0, 1) ** 1.3 * 0.8
        img = L.grade_film(img, lift_amt=0.045, contrast=1.1, sat=0.82, warm=0.06)
        img = L.halation(img, 0.66, 10, 0.35)
        return img * L.band_vignette(W, BH)

    def close(self):
        for r in self.readers.values():
            r.close()


def money(v, like):
    pre, _, suf, commas = like
    n = int(round(v))
    return f"{pre}{n:,}{suf}" if commas or n >= 10000 else f"{pre}{n}{suf}"


# ----------------------------------------------------------------------------------------------- render
def render(ctx):
    W, H, fps = ctx.w, ctx.h, ctx.fps
    spec = ctx.spec
    words = ctx.words
    side = ctx.brand["safe"]["side"]
    warm = brand.color("warm_white")
    muted = brand.color("muted")
    zen = brand.color("zen")
    iron = np.array(brand.color("iron"), np.float32) / 255
    red_hex = ctx.brand["colors"]["red_on_footage"]
    red = brand.rgb_of(red_hex)

    last_end = words[-1]["t1"] if words else ctx.duration
    total = max(ctx.duration, last_end + AFTER_LAST)
    fade_from = last_end + FADE_AFTER
    n = int(math.ceil(total * fps))
    lay = ctx.layout

    # ---- the plan, resolved from his words
    shots = Shots(ctx, total)
    for k, s in enumerate(shots.plan):
        lay.beat("shot", s["t0"], s["t1"], source=s.get("source") or "his video")

    mark = spec.get("mark", {"reel": 1})
    mark_txt = MARKS[int(mark.get("reel", 1)) - 1] if mark else None
    f_mark = brand.font("archive", 30)
    if mark_txt:
        b = lay.beat("mark", 0.0, total)
        lay.text(b, mark_txt, L.tracked_box(f_mark, mark_txt, W / 2, MARK_Y, "ms", 0.26), role="label",
                 color=brand.hex("muted"))

    lt = spec.get("lower_third", {})
    lt_t0 = None
    if lt is not False:
        lt = lt or {}
        if "at" in lt:
            lt_t0 = ctx.at(lt["at"], "lower_third.at")
        else:
            own = [s["t0"] for s in shots.plan if not s.get("source")]
            lt_t0 = (own[0] if own else 0.0) + 0.15
        title = (lt.get("title") or "").strip() or None
        f_name, f_title = brand.font("label", 30), brand.font("display_soft", 50)
        b = lay.beat("lower-third", lt_t0, lt_t0 + LT_HOLD)
        lay.text(b, NAME, L.tracked_box(f_name, NAME, LT_X, LT_NAME_Y, "ls", 0.18), role="label",
                 color=brand.hex("zen"))
        if title:
            lay.text(b, title, text_box(f_title, title, LT_X, LT_TITLE_Y, "ls"), role="label",
                     color=brand.hex("muted"))

    close = spec.get("close")
    t_close = ctx.at(close["at"], "close.at") if close else None

    fig = spec.get("figure")
    F = None
    if fig:
        size = int(fig.get("size", FIG_SIZE))
        k = size / FIG_SIZE
        to = fig.get("to")
        F = {"text": fig["text"], "line": fig.get("line"), "size": size,
             "t_in": ctx.at(fig["at"], "figure.at") if "at" in fig else 0.0,
             "f": brand.font("display", size), "f_unit": brand.font("display_soft", round(70 * k)),
             "gap": 18 * k, "line_y": FIG_Y + round(92 * k), "f_line": brand.font("archive", 34),
             "under": ctx.at(fig["underline"], "figure.underline") if "underline" in fig else None,
             "to": None}
        if to:
            t_to = ctx.at(to["at"], "figure.to.at")
            F["to"] = {"text": to["text"], "unit": to.get("unit"), "line": to.get("line"), "t": t_to,
                       "t_count": t_to - COUNT, "a": _num(fig["text"]), "b": _num(to["text"])}
        t_end_old = F["to"]["t_count"] if F["to"] else total
        # layout: the claim, the red brush under it, the new figure
        f = F["f"]
        b = lay.beat("figure", F["t_in"], F["under"] if F["under"] is not None else t_end_old)
        lay.text(b, F["text"], text_box(f, F["text"], W / 2, FIG_Y, "ms"), role="words", color=brand.hex("warm_white"))
        if F["line"]:
            lay.text(b, F["line"], L.tracked_box(F["f_line"], F["line"], W / 2, F["line_y"], "ms", 0.2), role="words",
                     color=brand.hex("muted"))
        if F["under"] is not None:
            u_end = min(t_end_old, t_close if t_close is not None else total)
            b = lay.beat("underline", F["under"], u_end)
            lay.text(b, F["text"], text_box(f, F["text"], W / 2, FIG_Y, "ms"), role="words",
                     color=brand.hex("warm_white"))
            wd = f.getlength(F["text"])
            lay.mark(b, "red brush under the figure", ((W - wd) / 2 - 12, FIG_Y + 8 * k, wd * 1.05 + 6, 40 * k), red=True)
            F["u_end"] = u_end
        if F["to"]:
            T = F["to"]
            b = lay.beat("figure", T["t"], total)
            tot = _fig_width(T["text"], T["unit"], size)
            x0 = (W - tot) / 2
            lay.text(b, T["text"], text_box(f, T["text"], x0, FIG_Y, "ls"), role="words", color=brand.hex("warm_white"))
            if T["unit"]:
                ux = x0 + f.getlength(T["text"]) + F["gap"]
                lay.text(b, T["unit"], text_box(F["f_unit"], T["unit"], ux, FIG_Y, "ls"), role="words",
                         color=brand.hex("warm_white"))
            if T["line"]:
                lay.text(b, T["line"], L.tracked_box(F["f_line"], T["line"], W / 2, F["line_y"], "ms", 0.2),
                         role="words", color=brand.hex("muted"))

    subs = []
    groups = spec.get("subtitles") or auto_subtitles(words)
    case_upper = True
    for k, g in enumerate(groups):
        txt = " ".join(words[i]["w"] for i in range(g["from"], g["to"] + 1))
        txt = txt.upper() if case_upper else txt
        s0 = 0.0 if k == 0 else words[g["from"]]["t0"]
        subs.append([s0, None, txt, L.fit("caption", brand.caption_px(SUB_SIZE, ctx.brand), txt, W - 2 * side - 60, 0.06)])
    for a, b in zip(subs, subs[1:]):
        a[1] = b[0]
    if subs:
        subs[-1][1] = last_end + 0.58
    for s0, s1, txt, f in subs:
        end = min(s1, t_close) if t_close is not None else s1
        if end <= s0:
            continue
        b = lay.beat("subtitle", s0, end)
        lay.text(b, txt, L.tracked_box(f, txt, W / 2, SUB_Y, "ms", 0.06), role="words", color=brand.hex("zen"))

    if close:
        f_close = L.fit("display", 96, close["text"], W - 2 * side)
        b = lay.beat("close", t_close, total)
        lay.text(b, close["text"], text_box(f_close, close["text"], W / 2, SUB_Y, "ms"), role="words", color=red_hex)

    # ---- drawing
    TOP0, TOP1 = 0, BY - 2                # the strip above the band
    BOT0 = BY + BH + 2                    # the strip below it

    def top_layer(t):
        im, d = L.text_layer((W, TOP1 - TOP0))
        if mark_txt:
            L.draw_text(d, (W / 2, MARK_Y), mark_txt, f_mark, muted + (255,), 0.26, "ms")
        if lt_t0 is not None:
            a = L.fade(t, lt_t0, lt_t0 + LT_HOLD, 0.35)
            if a > 0:
                L.draw_text(d, (LT_X, LT_NAME_Y), NAME, f_name, zen + (int(255 * a),), 0.18)
                if title:
                    d.text((LT_X, LT_TITLE_Y), title, font=f_title, fill=muted + (int(255 * a),), anchor="ls")
        return im

    def bottom_layer(t):
        im, d = L.text_layer((W, H - BOT0))
        oy = -BOT0
        if F:
            f = F["f"]
            T = F["to"]
            a_in = 1.0 if F["t_in"] <= 0 else L.clamp((t - F["t_in"]) / 0.3)
            counting = T is not None and t >= T["t_count"]
            if not counting:
                txt, unit_a = F["text"], 0.0
                x0 = (W - f.getlength(txt)) / 2
                fig_a = a_in
            else:
                kk = L.ease_out(L.clamp((t - T["t_count"]) / COUNT))
                if T["a"] and T["b"]:
                    va, vb = T["a"][1], T["b"][1]
                    # a price falls (or a count climbs) evenly in ratio; from or to zero it runs straight
                    v = va * (vb / va) ** kk if va > 0 and vb > 0 else va + (vb - va) * kk
                    txt = T["text"] if kk >= 1 else money(v, T["a"] if kk < 0.5 else T["b"])
                    fig_a = 1.0
                else:                         # words, not numbers: the old one gives way to the new
                    txt = T["text"] if kk >= 0.5 else F["text"]
                    fig_a = abs(1 - 2 * kk)
                unit_a = L.clamp((t - T["t"]) / 0.2) if (T["unit"] and t >= T["t"]) else 0.0
                tot = f.getlength(txt) + (F["gap"] + F["f_unit"].getlength(T["unit"]) if unit_a > 0 else 0)
                x0 = (W - tot) / 2
            d.text((x0, FIG_Y + oy), txt, font=f, fill=warm + (int(255 * fig_a),), anchor="ls")
            if unit_a > 0:
                d.text((x0 + f.getlength(txt) + F["gap"], FIG_Y + oy), T["unit"], font=F["f_unit"],
                       fill=warm + (int(255 * unit_a),), anchor="ls")
            # the source line: the old one leaves as the count starts, the new one arrives with the new figure
            if T is None:
                ln, la = F["line"], a_in
            elif t < T["t_count"]:
                ln, la = F["line"], (1 - L.clamp((t - (T["t_count"] - 0.05)) / 0.3)) * a_in
            else:
                ln, la = T["line"], L.clamp((t - T["t"]) / 0.3)
            if ln and la > 0:
                L.draw_text(d, (W / 2, F["line_y"] + oy), ln, F["f_line"], muted + (int(255 * la),), 0.2, "ms")
            # the red brush under the claim, drawn on over 0.4 s
            if F["under"] is not None and F["under"] <= t < F["u_end"]:
                prog = L.ease_in_out(L.clamp((t - F["under"]) / 0.4))
                wd = f.getlength(F["text"])
                br = L.brush_draw("red-b", wd * 1.05, 0.45, -1.0, prog)
                im.alpha_composite(br, (int((W - wd) / 2 - 12), int(FIG_Y + 8 * F["size"] / FIG_SIZE + oy)))
        if t_close is not None and t >= t_close:
            kk = L.ease_out(L.clamp((t - t_close) / 0.5), 2)
            d.text((W / 2, SUB_Y + oy + 14 * (1 - kk)), close["text"], font=f_close, fill=red + (int(255 * kk),),
                   anchor="ms")
        else:
            cur = None
            for j, s in enumerate(subs):
                if t >= s[0]:
                    cur = j
            if cur is not None and t < subs[cur][1]:
                s0, s1, txt, fnt = subs[cur]
                a = (L.clamp((t - s0) / 0.08) if s0 > 0 else 1.0) * (1 - L.clamp((t - (s1 - 0.06)) / 0.06))
                if a > 0:
                    L.draw_text(d, (W / 2, SUB_Y + oy), txt, fnt, zen + (int(235 * a),), 0.06, "ms")
        return im

    silent = ctx.work / "picture.mp4"
    ctx.say("Drawing the frames.")
    with heavy.lock("documentary frames"):
        enc = Encoder(silent, W, H, fps)
        try:
            for i in range(n):
                t = i / fps
                fr = np.full((H, W, 3), 0.006, np.float32)
                k_out = 1 - L.ease_in_out(L.clamp((t - fade_from) / 0.6))
                if k_out > 0:
                    fr[BY:BY + BH] = shots.band(t, i) * k_out
                fr[BY - 2:BY] = np.maximum(fr[BY - 2:BY], iron * 0.9)
                fr[BY + BH:BY + BH + 2] = np.maximum(fr[BY + BH:BY + BH + 2], iron * 0.9)
                fr[TOP0:TOP1] = L.over(fr[TOP0:TOP1], top_layer(t))
                fr[BOT0:] = L.over(fr[BOT0:], bottom_layer(t))
                enc.write(L.to_u8(L.grain(fr, i, float(spec.get("grain", GRAIN)), seed=3)))
                if i and i % 72 == 0:
                    ctx.say(f"Frame {i} of {n}.")
        finally:
            shots.close()
        enc.close()

    ctx.say("Mixing the sound.")
    if not spec.get("sound"):
        spec["sound"] = {"bed": dict(BED)}
    extra = []
    if spec.get("film_sound", True):
        extra.append({"array": snd.projector(), "t": 0.0, "under_db": PROJECTOR_UNDER})
        if F and F["to"]:
            for j in range(TICKS):
                extra.append({"array": snd.clock_tick(j), "t": F["to"]["t_count"] + j * TICK_STEP,
                              "under_db": TICK_UNDER})
    levels = ctx.sound(duration=total, extra_sfx=extra, duck_db=DUCK_DB)
    import json
    (ctx.out / "levels.json").write_text(json.dumps(levels, indent=1))
    mux(silent, ctx.out / "mix.wav", ctx.out / "final.mp4")
    poster(ctx.out / "final.mp4", 0.0, ctx.out / "poster.png")
    lay.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels}
