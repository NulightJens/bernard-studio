"""Moving type: one camera glides over a typeset board in his kit and lands on each phrase as he says it.

Serif lines rise in, labels spread in small caps, numbers slam with a spring, a camera shake and a pass of light, a
typewriter line types itself. Lines the camera has left dim and go soft. To close, the camera pulls back to a poster
where one red brush strikes a line (the only red in the film).

The spec lists camera stops ("beats", kind "stop"), each with its lines. Everything else (where the lines sit, when the
camera moves, the sound effects) follows from his words; the optional fields only fine-tune. See SPEC.md.
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from studio_engine import brand, heavy
from studio_engine import sound as snd
from studio_engine.errors import StudioError
from studio_engine.render import Encoder, draw_frames, mux, poster
from studio_engine.words import find_phrase, plain

KIND = "animated"
LABELS = []                     # every word on screen is his

SS = 2.5                        # glyph masks drawn at 2.5x board scale, then mip-mapped
CAM_Y = 0.465                   # the camera centre sits a little above the middle of the frame
BG = np.array([0x0B, 0x0A, 0x09]) / 255.0          # obsidian ground
MUTED = np.array([0x8E, 0x87, 0x7C]) / 255.0       # label grey
TYPE_DIM = 0.82                 # the typed line sits a little darker than the warm white

# look -> font kind in the kit, weight, letter spacing, colour key, entrance, default size (board px)
LOOKS = {
    "strong": dict(font="display", wt=600, track=0.0, col="cream", ent="rise", size=220),
    "italic": dict(font="display", wt=500, track=0.0, col="cream", ent="rise", size=130),
    "serif": dict(font="title", wt=500, track=0.0, col="cream", ent="rise", size=120),
    "label": dict(font="caption", wt=800, track=0.24, col="muted", ent="label", size=40),
    "number": dict(font="caption", wt=800, track=-0.02, col="cream", ent="slam", size=240),
    "typed": dict(font="archive", wt=None, track=0.0, col="typed", ent="type", size=70),
}
NUMBER_EARLY = 0.03             # a number lands a hair before he says it
MOVE_LEAD = 0.36                # the camera leaves for the next stop this long before its first word
MOVE_LAND = -0.04               # and lands this long before it (negative: before)
POSTER_AFTER = 0.40             # the pull back starts this long after the last word begins
POSTER_MOVE = 0.95              # and takes this long
POSTER_HOLD = 1.75              # the poster holds this long before the film ends
STRIKE_AFTER = 0.08             # the brush strikes this long after the poster lands
MAX_LINE_W = 900                # a line left at its default size is made smaller until it is this wide at most
                                # (the example piece's lines run 290 to 918 board px; wider lines make the camera pull far out)


# ----------------------------------------------------------------------------------------------- easing
def ease(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def ease_io(t, p=3.0):
    t = float(np.clip(t, 0, 1))
    return 0.5 * (2 * t) ** p if t < 0.5 else 1 - 0.5 * (2 * (1 - t)) ** p


def ease_out(t, p=3.0):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** p


def spring(t, f=2.2, z=0.55):
    t = max(t, 0.0)
    w = 2 * np.pi * f
    return 1 - np.exp(-z * w * t) * np.cos(w * np.sqrt(1 - z * z) * t)


# ----------------------------------------------------------------------------------------------- checking the spec
def _stops(spec):
    return [b for b in spec.get("beats") or [] if b.get("kind", "stop") == "stop"]


def _tokens(text):
    out = []
    for p in str(text).split():
        out += plain(p)
    return out


def validate(spec, words, duration):
    stops = _stops(spec)
    if len(stops) < 2:
        raise StudioError("Moving type needs at least two camera stops in beats (one for each phrase group).")
    have = set()
    for w in words:
        have.update(plain(w["w"]))
    texts = []
    for k, st in enumerate(stops):
        lines = st.get("lines") or []
        if not lines:
            raise StudioError(f"beats[{k}] has no lines. Each stop needs at least one line of his words.")
        for j, ln in enumerate(lines):
            look = ln.get("look", "serif")
            if look not in LOOKS:
                raise StudioError(f'beats[{k}].lines[{j}].look is "{look}". Looks: {", ".join(LOOKS)}.')
            extra = [t for t in _tokens(ln.get("text", "")) if t not in have]
            if not _tokens(ln.get("text", "")):
                raise StudioError(f"beats[{k}].lines[{j}] has no words in it.")
            if extra:
                raise StudioError(f'beats[{k}].lines[{j}] says "{ln["text"]}", but he never says '
                                  f'"{" ".join(extra)}" in this passage. Use only his words.')
            texts.append(ln["text"])
    pst = spec.get("poster") or {}
    if pst.get("strike") and pst.get("underline"):
        raise StudioError("The poster can strike one line or underline one line, not both (one red per frame).")
    for key in ("strike", "underline"):
        if pst.get(key) and pst[key] not in texts:
            raise StudioError(f'poster.{key} is "{pst[key]}", which is not one of the lines. Copy the line exactly.')
    p = spec.get("poster") or {}
    if "from" in p and not (0 <= int(p["from"]) < len(stops)):
        raise StudioError(f"poster.from must be a stop number from 0 to {len(stops) - 1}.")


# ----------------------------------------------------------------------------------------------- the plan
class Board:
    """Everything the frames need, worked out once from the spec: lines, their times, the camera keys."""

    def __init__(self, ctx_at, spec, words, duration, W, H, fps, colors):
        self.W, self.H, self.fps = W, H, fps
        self.spec = spec
        cream = np.array(brand.rgb_of(colors["cream"])) / 255.0
        warm = np.array(brand.rgb_of(colors["warm_white"])) / 255.0
        self.red = np.array(brand.rgb_of(colors["red"]), np.float32) / 255.0
        self.red_hex = colors["red"]
        cols = {"cream": cream, "muted": MUTED, "typed": warm * TYPE_DIM}
        self.stops = []
        items = []
        after = 0
        for k, st in enumerate(_stops(spec)):
            ids = []
            for j, ln in enumerate(st["lines"]):
                look = LOOKS[ln.get("look", "serif")]
                txt = str(ln["text"])
                if ln.get("look") == "label":
                    txt = txt.upper()
                if "at" in ln:
                    t = ctx_at(ln["at"], f"beats[{k}].lines[{j}].at")
                else:
                    i0, i1 = find_phrase(words, ln["text"], after)
                    after = i1 + 1
                    t = words[i0]["t0"]
                if look["ent"] == "slam":
                    t -= NUMBER_EARLY
                it = dict(id=f"{k}.{j}", txt=txt, look=ln.get("look", "serif"), f=look["font"], wt=look["wt"],
                          track=look["track"], size=float(ln.get("size", look["size"])), col=cols[look["col"]],
                          col_key=look["col"], ent=look["ent"], t=t, stop=k, x=ln.get("x"), y=ln.get("y"),
                          auto_size="size" not in ln)
                items.append(it)
                ids.append(it["id"])
            self.stops.append(dict(k=k, ids=ids, keep=bool(st.get("keep", False)), camera=st.get("camera") or {}))
        # the opening stop is fully set on the first frame: the film opens on words, not on black
        for it in items:
            if it["stop"] == 0:
                it["t"] = -1.0
        self.items = items
        self.by = {it["id"]: it for it in items}
        marked = (spec.get("poster") or {}).get("underline")
        for it in items:
            it["underlined"] = bool(marked) and it["txt"] in (marked, str(marked).upper())
            self._glyphs(it)
            if it["auto_size"] and it["ent"] != "label" and it["w"] > MAX_LINE_W:
                it["size"] = round(it["size"] * MAX_LINE_W / it["w"], 1)
                self._glyphs(it)
        self._place()
        self._times(ctx_at, words)
        self._camera(ctx_at)
        self._alphas()
        self._strike_it = self._find_strike()

    # ------------------------------------------------------------------ glyphs
    def _font(self, it, size):
        f = ImageFont.truetype(str(brand.font_path(it["f"])), int(size))
        if it["wt"] is not None:
            try:
                f.set_variation_by_axes([it["wt"]])
            except Exception:
                pass
        return f

    def _glyphs(self, it):
        """Per-character masks at SS x size, with their offsets from the line's origin."""
        fnt = self._font(it, it["size"] * SS)
        track = it["track"]
        asc, desc = fnt.getmetrics()
        x = 0.0
        chars = []
        for ch in it["txt"]:
            w = fnt.getlength(ch)
            if ch != " ":
                pad = int(fnt.size * 0.3)
                img = Image.new("L", (int(w + 2 * pad), int(asc + desc + 2 * pad)), 0)
                ImageDraw.Draw(img).text((pad, pad), ch, font=fnt, fill=255)
                a = np.asarray(img).astype(np.float32) / 255
                ys, xs = np.nonzero(a > 0.002)
                if len(xs):
                    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
                    m = a[max(0, y0):y1, max(0, x0):x1]
                    mips = [m]
                    for _ in range(3):
                        m = cv2.resize(m, (max(1, m.shape[1] // 2), max(1, m.shape[0] // 2)),
                                       interpolation=cv2.INTER_AREA)
                        mips.append(m)
                    chars.append(dict(mips=mips, ox=(x + max(0, x0) - pad) / SS, oy=(max(0, y0) - pad) / SS))
            x += w + track * fnt.size
        hb = fnt.getbbox("H")
        it["w"] = (x - track * fnt.size) / SS
        it["cap"] = (hb[1] / SS, hb[3] / SS)
        it["chars"] = chars

    def _place(self):
        """Lines without x and y are stacked down the board: closer inside a stop, a wider gap between stops."""
        prev = None
        for it in self.items:
            if it["y"] is None:
                if prev is None:
                    it["y"] = 0.0
                else:
                    d = 0.75 * (prev["size"] + it["size"]) / 2 + 75
                    if prev.get("underlined"):
                        d += prev["size"] * 0.18          # room for the red brush under it
                    if it["stop"] != prev["stop"]:
                        d += 80
                    it["y"] = prev["y"] + d
            it["x"] = float(it["x"] or 0.0)
            it["y"] = float(it["y"])
            prev = it
        for it in self.items:
            cap_top, cap_bot = it["cap"]
            it["ox"] = it["x"] - it["w"] / 2
            it["oy"] = it["y"] - (cap_top + cap_bot) / 2

    # ------------------------------------------------------------------ timing
    def _times(self, ctx_at, words):
        last_word = words[-1]
        p = self.spec.get("poster") or {}
        for k, st in enumerate(self.stops):
            cam = st["camera"]
            first = min(self.by[i]["t"] for i in st["ids"])
            if self.by[st["ids"][0]]["ent"] == "slam":
                first += NUMBER_EARLY                 # moves follow the word, not the early slam
            st["first"] = first
            st["move"] = 0.0 if k == 0 else first - float(cam.get("lead", MOVE_LEAD))
            st["land"] = 0.0 if k == 0 else first + float(cam.get("arrive", MOVE_LAND))
        self.p_start = ctx_at(p["at"], "poster.at") if "at" in p else last_word["t0"] + POSTER_AFTER
        self.p_land = self.p_start + POSTER_MOVE
        self.strike_t = self.p_land + STRIKE_AFTER
        self.dur = max(self.p_land + float(p.get("hold", POSTER_HOLD)), last_word["t1"] + 0.6)
        self.strike = p.get("strike") or p.get("underline")
        self.mark = "underline" if p.get("underline") else "strike"
        # which lines each stop frames, and which stay lit: its own, plus the last stop's (labels aside) when it keeps
        for k, st in enumerate(self.stops):
            frame = list(st["ids"])
            if st["keep"] and k > 0:
                kept = [i for i in self.stops[k - 1]["frame"] if self.by[i]["ent"] != "label"]
                frame = kept + frame
            st["frame"] = frame
        for it in self.items:
            # a line dims when the camera leaves for a stop that does not keep it
            it["dim_at"] = None
            for st in self.stops[it["stop"] + 1:]:
                if it["id"] not in st["frame"]:
                    it["dim_at"] = st["move"]
                    break

    # ------------------------------------------------------------------ camera
    def bbox(self, ids, pad=0):
        xs0, xs1, ys0, ys1 = [], [], [], []
        for i in ids:
            it = self.by[i]
            xs0.append(it["ox"]); xs1.append(it["ox"] + it["w"])
            ys0.append(it["oy"] + it["cap"][0] - it["size"] * 0.12)
            ys1.append(it["oy"] + it["cap"][1] + it["size"] * 0.12)
        return min(xs0) - pad, min(ys0) - pad, max(xs1) + pad, max(ys1) + pad

    def frame_for(self, ids, width=820, maxs=1.35):
        x0, y0, x1, y1 = self.bbox(ids)
        s = min(maxs, width / (x1 - x0), 1300 / (y1 - y0))
        return np.array([(x0 + x1) / 2, (y0 + y1) / 2, s])

    def _view(self, base, v):
        return (base[0], base[1] + float(v.get("dy", 0.0)), base[2] * float(v.get("zoom", 1.0)), float(v.get("roll", 0.0)))

    def _camera(self, ctx_at):
        keys = []
        sign = -1.0
        for k, st in enumerate(self.stops):
            cam = st["camera"]
            has_num = any(self.by[i]["ent"] == "slam" for i in st["ids"])
            base = self.frame_for(st["frame"], width=float(cam.get("width", 800 if has_num else 820)))
            num_later = [self.by[i] for i in st["ids"][1:] if self.by[i]["ent"] == "slam"]
            if st["keep"] and k > 0:
                land_d = {"zoom": 1.0, "dy": 0.0, "roll": 0.0}
            elif num_later:
                land_d = {"zoom": 1.06, "dy": -30.0, "roll": -sign * 0.7}
            else:
                land_d = {"zoom": 1.0, "dy": 0.0, "roll": sign * 0.6}
            if not (st["keep"] and k > 0):
                sign = -sign
            land = dict(land_d, **(cam.get("land") or {}))
            leave_d = {"zoom": land["zoom"] * 0.97, "dy": land["dy"] * 0.3, "roll": land["roll"] * 0.4}
            leave = dict(leave_d, **(cam.get("leave") or {}))
            keys.append((st["land"], *self._view(base, land)))
            if "keys" in cam:
                for j, kk in enumerate(cam["keys"]):
                    keys.append((ctx_at(kk["at"], f"beats[{k}].camera.keys[{j}].at"), *self._view(base, kk)))
            elif num_later:
                n0 = num_later[0]["t"] + NUMBER_EARLY - 0.05
                keys.append((n0, *self._view(base, {"zoom": land["zoom"] - 0.06, "dy": land["dy"] / 3,
                                                    "roll": land["roll"] / 2})))
            end = self.stops[k + 1]["move"] if k + 1 < len(self.stops) else self.p_start
            keys.append((end, *self._view(base, leave)))
        # the poster: the camera pulls back over the board from the first story stop to the end
        p = self.spec.get("poster") or {}
        self.p_from = int(p["from"]) if "from" in p else self._poster_from()
        marked = p.get("strike") or p.get("underline")
        for it in self.items:                      # the red line is always on the poster
            if marked and (it["txt"] == marked or it["txt"] == str(marked).upper()):
                self.p_from = min(self.p_from, it["stop"])
        ids = [it["id"] for it in self.items if it["stop"] >= self.p_from]
        fin = self.frame_for(ids, width=780)
        fin[1] += 40
        keys.append((self.p_land, fin[0], fin[1], fin[2], 0.0))
        keys.append((self.dur, fin[0], fin[1], fin[2] * 0.975, 0.0))
        keys.sort(key=lambda k: k[0])
        self.keys = [(t, np.array(v, float)) for t, *v in keys]

    def _poster_from(self):
        """The opening stop (and any stop that keeps it) is left out of the poster; a very tall board starts later."""
        k = 1
        while k < len(self.stops) and self.stops[k]["keep"]:
            k += 1
        k = min(k, len(self.stops) - 1)
        while k < len(self.stops) - 1:
            ids = [it["id"] for it in self.items if it["stop"] >= k]
            x0, y0, x1, y1 = self.bbox(ids)
            if y1 - y0 <= 2400:
                break
            k += 1
        return k

    def cam_at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1].copy()
        for (t0, a), (t1, b) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / max(1e-6, t1 - t0)
                dist = abs(b[0] - a[0]) + abs(b[1] - a[1]) + 400 * abs(np.log(b[2] / a[2]))
                e = ease_io(u, 3.2) if dist > 120 else u      # big moves ease hard, holds drift linearly
                c = a + (b - a) * e
                c[2] = np.exp(np.log(a[2]) + (np.log(b[2]) - np.log(a[2])) * e)
                return c
        return ks[-1][1].copy()

    def shake(self, t):
        s = np.zeros(2)
        for it in self.items:
            if it["ent"] != "slam":
                continue
            d = t - (it["t"] + 0.06)
            if 0 <= d < 0.6:
                s += 9 * np.exp(-d * 9) * np.array([np.sin(d * 71), np.cos(d * 53)])
        return s

    def speed(self, t):
        a, b = self.cam_at(t - 0.5 / self.fps), self.cam_at(t + 0.5 / self.fps)
        v = np.hypot(a[0] - b[0], a[1] - b[1]) * a[2] + 1000 * abs(np.log(b[2] / a[2])) + 20 * abs(b[3] - a[3])
        return v + np.linalg.norm(self.shake(t) - self.shake(t + 1 / self.fps))

    # ------------------------------------------------------------------ opacity per line
    def _alphas(self):
        last = len(self.stops) - 1
        kept_by_last = set(self.stops[last]["frame"]) - set(self.stops[last]["ids"])
        for it in self.items:
            if it["stop"] < self.p_from:
                tgt = 0.0
            elif it["ent"] == "slam" or it["stop"] == last:
                tgt = 1.0
            elif it["id"] in kept_by_last:
                tgt = 0.9
            elif it["ent"] == "label":
                tgt = 0.45
            else:
                tgt = 0.16
            it["poster"] = tgt

    def item_alpha(self, it, t):
        a = 1.0
        if it["dim_at"] is not None:
            a = 1 - 0.74 * float(ease((t - it["dim_at"]) / 0.55))
        pull = float(ease((t - self.p_start) / 0.9))
        a = a + (it["poster"] - a) * pull
        if it is self._strike_it and self.mark == "strike":
            a *= 1 - 0.5 * float(ease((t - self.strike_t - 0.12) / 0.35))
        return a

    def strike_item(self):
        return self._strike_it

    def _find_strike(self):
        if not self.strike:
            return None
        hits = [it for it in self.items if it["txt"] == self.strike or it["txt"] == str(self.strike).upper()]
        return hits[-1] if hits else None

    def glyph_state(self, it, j, t):
        """(opacity, dy, scale) for glyph j at time t, in board px."""
        t0, e = it["t"], it["ent"]
        if e == "rise":
            u = (t - (t0 + j * 0.022)) / 0.42
            return float(ease(u * 1.6)), it["size"] * 0.32 * (1 - float(ease_out(u, 3.5))), 1.0
        if e == "label":
            u = (t - (t0 + j * 0.016)) / 0.35
            return float(ease(u * 1.4)), 0.0, 1.0
        if e == "slam":
            u = t - (t0 + j * 0.028)
            o = float(ease(u / 0.06))
            s = 1.0 + 0.35 * (1 - spring(u, 3.2, 0.62)) if u > 0 else 1.35
            return o, 0.0, s
        if e == "type":
            return (1.0 if t >= t0 + j * 0.05 else 0.0), 0.0, 1.0
        return 1.0, 0.0, 1.0

    def spread(self, it, t):
        if it["ent"] != "label":
            return 1.0
        return 1 + 0.35 * (1 - float(ease_out((t - it["t"]) / 0.9, 3)))


# ----------------------------------------------------------------------------------------------- drawing
class Painter:
    """Draws frames of a Board. Safe to call from several threads at once."""

    def __init__(self, board):
        self.b = board
        W, H = board.W, board.H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
        self.vig = (1 - 0.62 * np.clip(r, 0, 1.4) ** 2.0)[..., None].astype(np.float32)
        pool = np.exp(-(((xx - W * 0.5) / (W * 0.75)) ** 2 + ((yy - H * 0.42) / (H * 0.5)) ** 2))[..., None]
        self.base = (BG * 0.9 + (np.array([0.075, 0.062, 0.050]) - BG) * pool).astype(np.float32)
        d = ((xx - W * 0.15) * 0.80 + (yy + 200) * 0.6)
        p = (xx - W * 0.15) * 0.6 - (yy + 200) * 0.80
        self.shaft = (np.exp(-(p / 260) ** 2) * np.clip(1 - d / 2600, 0, 1)).astype(np.float32)[..., None] * \
            np.array([1.0, 0.9, 0.75], np.float32)
        rng = np.random.default_rng(11)
        self.dust = [(float(rng.uniform(-1500, 1500)), float(rng.uniform(-2400, 2400)), float(rng.uniform(5, 26)),
                      float(rng.uniform(0.012, 0.05)), float(rng.uniform(0.15, 0.45))) for _ in range(46)]
        g = np.random.default_rng(7)
        self.grain = [g.standard_normal((H // 2, W // 2)).astype(np.float32) for _ in range(12)]
        if board.strike:
            br = cv2.imread(str(brand.brush("red-a")), cv2.IMREAD_UNCHANGED)
            self.brush_a = br[..., 3].astype(np.float32) / 255

    # ------------------------------------------------------------------ glyph warps
    @staticmethod
    def _corners(m, M):
        h, w = m.shape
        pts = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], np.float32) @ M.T
        return pts

    def _pick(self, mips, M_full):
        sx = math.sqrt(M_full[0, 0] ** 2 + M_full[1, 0] ** 2)
        lvl = 0
        while lvl < len(mips) - 1 and sx * (2 ** lvl) < 0.55:
            lvl += 1
        M = M_full.copy()
        M[:, :2] *= 2 ** lvl
        return mips[lvl], M

    def _draw(self, jobs):
        """jobs: [(mips, M, opacity)] -> (alpha array, [y0, y1, x0, x1]) covering them, clipped to the frame."""
        W, H = self.b.W, self.b.H
        prepared, bb = [], None
        for mips, M_full, op in jobs:
            m, M = self._pick(mips, M_full)
            pts = self._corners(m, M)
            x0, y0 = np.floor(pts.min(0)).astype(int) - 2
            x1, y1 = np.ceil(pts.max(0)).astype(int) + 2
            X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
            if X1 <= X0 or Y1 <= Y0:
                continue
            prepared.append((m, M, op, X0, Y0, X1, Y1))
            bb = [Y0, Y1, X0, X1] if bb is None else [min(bb[0], Y0), max(bb[1], Y1), min(bb[2], X0), max(bb[3], X1)]
        if bb is None:
            return None, None
        return prepared, bb

    def _blit_all(self, prepared, bb, pad=0):
        H, W = self.b.H, self.b.W
        bb = [max(0, bb[0] - pad), min(H, bb[1] + pad), max(0, bb[2] - pad), min(W, bb[3] + pad)]
        a = np.zeros((bb[1] - bb[0], bb[3] - bb[2]), np.float32)
        for m, M, op, X0, Y0, X1, Y1 in prepared:
            M2 = M.copy()
            M2[0, 2] -= X0
            M2[1, 2] -= Y0
            out = cv2.warpAffine(m, M2.astype(np.float32), (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            roi = a[Y0 - bb[0]:Y1 - bb[0], X0 - bb[2]:X1 - bb[2]]
            np.maximum(roi, out * op, out=roi)
        return a, bb

    def _board_to_screen(self, cam, sh):
        cx, cy, s, roll = cam
        th = np.radians(roll)
        R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]) * s
        off = -R @ np.array([cx, cy]) + np.array([self.b.W / 2, self.b.H * CAM_Y]) + sh
        return R, off

    def layers(self, t, cam):
        b = self.b
        sh = b.shake(t)
        R, off = self._board_to_screen(cam, sh)
        out = []
        for it in b.items:
            if t < it["t"] - 0.05:
                continue
            ia = b.item_alpha(it, t)
            if ia <= 0.003:
                continue
            spread = b.spread(it, t)
            jobs = []
            for j, g in enumerate(it["chars"]):
                o, dy, gs = b.glyph_state(it, j, t)
                if o <= 0.002:
                    continue
                gm = g["mips"][0]
                gw, gh = gm.shape[1] / SS, gm.shape[0] / SS
                bx = it["ox"] + g["ox"] + gw / 2
                by = it["oy"] + g["oy"] + gh / 2 + dy
                bx = it["x"] + (bx - it["x"]) * spread
                if it["ent"] == "slam":
                    bx = it["x"] + (bx - it["x"]) * gs
                    by = it["y"] + (by - it["y"]) * gs
                sc = gs / SS
                A = np.array([[sc, 0], [0, sc]])
                At = np.array([bx - gw / 2 * gs, by - gh / 2 * gs])
                M = R @ A
                Mt = R @ At + off
                jobs.append((g["mips"], np.hstack([M, Mt[:, None]]), o))
            prepared, bb = self._draw(jobs)
            if prepared is None:
                continue
            dimmed = t > it["t"] + 0.8 and ia < 0.9
            sig = 1.0 + 5.0 * float(np.clip((0.9 - ia) / 0.7, 0, 1)) * cam[2] if dimmed else 0
            a, bb = self._blit_all(prepared, bb, pad=int(3 * sig) + 2 if dimmed else 0)
            if dimmed:
                a = cv2.GaussianBlur(a, (0, 0), sig)
            col = it["col"].astype(np.float32)
            if it["ent"] == "slam":
                u = (t - it["t"] - 0.12) / 0.7
                if 0 < u < 1:
                    yy = np.arange(bb[0], bb[1], dtype=np.float32)[:, None]
                    xx = np.arange(bb[2], bb[3], dtype=np.float32)[None, :]
                    pos = -300 + u * (b.W + 600)
                    band = np.exp(-(((xx + 0.45 * yy - 0.45 * b.H * CAM_Y) - pos) / 90) ** 2)
                    col = (it["col"][None, None, :] * (1 + 0.55 * band[..., None])).astype(np.float32)
            out.append((a * np.float32(ia), col, bb))
            if b.strike and it is b.strike_item() and t > b.strike_t:
                lay = self._strike(it, t, R, off)
                if lay is not None:
                    out.append(lay)
        return out

    def _strike(self, it, t, R, off):
        """The red brush through the line (strike) or under it (underline), painted left to right."""
        u = float(ease_out((t - self.b.strike_t) / 0.34, 2.2))
        BA = self.brush_a
        bw = it["w"] * 1.12
        sc = bw / BA.shape[1]
        bh = BA.shape[0] * sc
        cut = int(BA.shape[1] * u)
        ramp = np.clip((cut - np.arange(BA.shape[1])) / 40, 0, 1).astype(np.float32)
        wipe = BA * ramp[None, :]
        A = np.array([[sc, 0], [0, sc * 0.62]])
        At = np.array([it["x"] - bw / 2, it["y"] - bh * 0.31 + 6])
        if self.b.mark == "underline":            # a band about a fifth of the type size, just under the baseline
            A[1, 1] = it["size"] * 0.24 / BA.shape[0]
            At[1] = it["y"] + (it["cap"][1] - it["cap"][0]) / 2 + it["size"] * 0.06
        M = np.hstack([R @ A, (R @ At + off)[:, None]])
        mips = [wipe, cv2.resize(wipe, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA),
                cv2.resize(wipe, None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)]
        prepared, bb = self._draw([(mips, M, 1.0)])
        if prepared is None:
            return None
        a, bb = self._blit_all(prepared, bb)
        return a * np.float32(0.97), self.b.red, bb

    def background(self, t, cam):
        W, H = self.b.W, self.b.H
        img = np.broadcast_to(self.base, (H, W, 3)).copy()
        cx, cy, s, roll = cam
        dl = np.zeros((H, W), np.float32)
        for (x, y, r, br, par) in self.dust:
            px = W / 2 + (x - cx * par) * (0.6 + 0.4 * s) + 18 * np.sin(t * 0.3 + x)
            py = H / 2 + (y - cy * par) * (0.6 + 0.4 * s) - t * 9 * par * 3
            py = (py + 400) % (H + 800) - 400
            if -60 < px < W + 60 and -60 < py < H + 60:
                cv2.circle(dl, (int(px * 4), int(py * 4)), int(r * 4), br, -1, lineType=cv2.LINE_AA, shift=2)
        dl = cv2.GaussianBlur(dl, (0, 0), 6)
        img += dl[..., None] * np.array([1.0, 0.92, 0.8], np.float32)
        img += self.shaft * np.float32(0.022 + 0.006 * np.sin(t * 0.7))
        return img

    def compose(self, t, n_sub):
        b = self.b
        acc, bg = None, None
        for k in range(n_sub):
            ts = t + (k / n_sub - 0.5) * (1 / b.fps) * 0.5          # 180-degree shutter
            cam = b.cam_at(ts)
            if bg is None:
                bg = self.background(ts, cam)
            img = bg.copy()
            for a, col, bb in self.layers(ts, cam):
                roi = img[bb[0]:bb[1], bb[2]:bb[3]]
                roi *= (1 - a[..., None])
                roi += col * a[..., None]
            acc = img if acc is None else acc + img
        img = acc / n_sub
        lum = img.max(axis=2)
        glow = cv2.GaussianBlur(np.clip(lum - 0.35, 0, 1), (0, 0), 14)       # soft halation on bright type
        img += glow[..., None] * np.array([0.30, 0.22, 0.16], np.float32)
        img *= self.vig
        return img

    def to8(self, img, i):
        W, H = self.b.W, self.b.H
        g = cv2.resize(self.grain[i % len(self.grain)], (W, H), interpolation=cv2.INTER_LINEAR)
        lum = img.mean(axis=2, keepdims=True)
        img = img + g[..., None] * (0.022 * (0.35 + 0.65 * np.sqrt(np.clip(lum, 0, 1))))
        x = np.clip(img, 0, None)
        x = np.where(x > 0.85, 0.85 + 0.15 * np.tanh((x - 0.85) / 0.15), x)
        dither = np.random.default_rng(1000 + i).uniform(-0.5, 0.5, (H, W, 1)).astype(np.float32)
        return np.clip(x * 255 + dither, 0, 255).astype(np.uint8)

    def frame(self, i):
        t = i / self.b.fps
        sub = int(np.clip(1 + self.b.speed(t) / 3.5, 1, 14))
        return self.to8(self.compose(t, sub), i)


# ----------------------------------------------------------------------------------------------- sound effects
def effects(board):
    """The style's own effects bus: air on every camera move, a low hit under each number, typewriter keys, a long
    whoosh on the pull back and a brush swish on the strike."""
    n = int((board.dur + 1.0) * snd.SR)
    bus = np.zeros((n, 2))
    for k, st in enumerate(board.stops[1:]):
        snd.place(bus, snd.lp(snd.whoosh_air(0.55, k, 250, 2400, 0.6), 5000), st["move"] - 0.05, -4)
    snd.place(bus, snd.whoosh_air(1.3, 9, 150, 1500, 0.5), board.p_start - 0.05, -2)
    for it in board.items:
        if it["ent"] == "slam" and it["t"] >= 0:
            snd.place(bus, snd.low_hit(1.4, 46, 1), it["t"] + 0.02, 2)
            snd.place(bus, snd.reverb(snd.tick(3, 1800, 0.08), 1.2, 0.5), it["t"] + 0.02, -10)
        if it["ent"] == "type":
            for j, ch in enumerate(it["txt"]):
                if ch != " ":
                    snd.place(bus, snd.tick(j, 2600 + 300 * (j % 3), 0.04), max(0.0, it["t"]) + j * 0.05, -6)
    if board.strike_item():
        snd.place(bus, snd.hp(snd.whoosh_air(0.38, 21, 1500, 7000, 0.3), 1200), board.strike_t - 0.02, -2)
    return snd.reverb(bus, 1.6, 0.18)[: int(board.dur * snd.SR)]


def music(ctx, board):
    """The spec's bed (default: the moving-type bed, minor until the last three stops, opening to major on the last),
    with the room it had in the example piece."""
    s = ctx.spec.get("sound") or {}
    bed = s.get("bed")
    if bed in (None, "type") or (isinstance(bed, dict) and bed.get("name") == "type"):
        opts = dict(bed) if isinstance(bed, dict) else {"name": "type"}
        if "changes" in opts:
            opts["changes"] = [ctx.at(c, "sound.bed.changes") for c in opts["changes"]]
        else:
            firsts = [st["first"] for st in board.stops]
            opts["changes"] = firsts[-3:] if len(firsts) >= 4 else None
        for key in ("pulse_until", "swell_at"):
            if key in opts:
                opts[key] = ctx.at(opts[key], f"sound.bed.{key}")
        under = opts.pop("under_db", None)
        opts.pop("name")
        arr = snd.reverb(snd.make_bed("type", board.dur, **opts), 3.0, 0.3)
        return arr, under
    if isinstance(bed, dict):
        bed = dict(bed)
        for key in ("changes",):
            if key in bed:
                bed[key] = [ctx.at(c, f"sound.bed.{key}") for c in bed[key]]
        for key in ("rise", "pulse_until", "swell_at"):
            if key in bed:
                bed[key] = ctx.at(bed[key], f"sound.bed.{key}")
    return bed, None


# ----------------------------------------------------------------------------------------------- layout record
def _screen_box(board, it, cam):
    x0 = it["ox"]
    x1 = it["ox"] + it["w"]
    y0 = it["oy"] + it["cap"][0] - it["size"] * 0.12
    y1 = it["oy"] + it["cap"][1] + it["size"] * 0.12
    cx, cy, s, roll = cam
    th = np.radians(roll)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]) * s
    off = -R @ np.array([cx, cy]) + np.array([board.W / 2, board.H * CAM_Y])
    pts = np.array([[x0, y0], [x1, y0], [x0, y1], [x1, y1]]) @ R.T + off
    lo, hi = pts.min(0), pts.max(0)
    return (lo[0], lo[1], hi[0] - lo[0], hi[1] - lo[1])


def _hex(c):
    return "#" + "".join(f"{int(round(v * 255)):02X}" for v in np.clip(c, 0, 1))


def record(ctx, board):
    """layout.json: for each stop, the lines the camera frames where it lands; the poster with its red strike."""
    for k, st in enumerate(board.stops):
        end = board.stops[k + 1]["move"] if k + 1 < len(board.stops) else board.p_start
        t = min(st["land"] + 0.5, (st["land"] + end) / 2)
        cam = board.cam_at(t)
        bt = ctx.layout.beat("stop", st["land"], end, i=k)
        for i in st["frame"]:
            it = board.by[i]
            ctx.layout.text(bt, it["txt"], _screen_box(board, it, cam), role="words", color=_hex(it["col"]),
                            red=False, size=int(it["size"]))
    cam = board.cam_at(board.p_land + 0.3)
    bt = ctx.layout.beat("poster", board.p_land, board.dur, i=len(board.stops))
    for it in board.items:
        if it["poster"] > 0.1:
            ctx.layout.text(bt, it["txt"], _screen_box(board, it, cam), role="words", color=_hex(it["col"]),
                            red=False, size=int(it["size"]))
    sit = board.strike_item()
    if sit:
        x, y, w, h = _screen_box(board, sit, cam)
        if board.mark == "underline":
            y += h * 0.75
        ctx.layout.mark(bt, f"brush {board.mark}", (x - 0.06 * w, y, w * 1.12, h), red=True, color=board.red_hex)


# ----------------------------------------------------------------------------------------------- the render
def render(ctx):
    spec = ctx.spec
    board = Board(ctx.at, spec, ctx.words, ctx.duration, ctx.w, ctx.h, ctx.fps, ctx.brand["colors"])
    painter = Painter(board)
    n = int(board.dur * ctx.fps)
    silent = ctx.work / "picture.mp4"
    ctx.say(f"Drawing {n} frames of moving type.")
    import time
    t0 = time.time()
    with heavy.lock("moving-type frames"):
        enc = Encoder(silent, ctx.w, ctx.h, ctx.fps, tune="grain")
        draw_frames(enc, painter.frame, n, ctx.say)
        enc.close()
    secs = time.time() - t0
    ctx.say("Mixing the sound.")
    bed, under = music(ctx, board)
    sfx = [{"array": effects(board), "t": 0.0, "under_db": 25}]
    for k, e in enumerate((spec.get("sound") or {}).get("sfx") or []):
        e = dict(e)
        e["t"] = ctx.at(e.get("at", e.get("t")), f"sound.sfx[{k}].at")
        sfx.append(e)
    kw = {"music_under": under} if under is not None else {}
    levels = snd.mix(ctx.voice(), board.dur, ctx.out / "mix.wav", bed=bed, sfx=sfx, work=ctx.work, **kw)
    mux(silent, ctx.out / "mix.wav", ctx.out / "final.mp4")
    poster(ctx.out / "final.mp4", min(board.dur - 0.1, board.strike_t + 0.8), ctx.out / "poster.png")
    record(ctx, board)
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels, "frames": n, "draw_seconds": round(secs, 1),
            "frames_per_second": round(n / max(secs, 1e-6), 2)}


def stills(ctx_at, spec, words, duration, W, H, fps, colors, times):
    """Single frames at given times (seconds), for previews and the regression test."""
    board = Board(ctx_at, spec, words, duration, W, H, fps, colors)
    painter = Painter(board)
    out = []
    for t in times:
        i = int(round(t * fps))
        out.append(painter.to8(painter.compose(t, 1), i))
    return out, board
