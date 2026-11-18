"""Cutout: Bernard cut out of his own footage, standing on black at the bottom of the frame, with the picture that
explains his words up top, a new picture on a spoken word every two to four seconds and his corner switching on it.

Frame one carries the claim over one of his screens (a small typewriter kicker, the figure in the kit serif italic with
the red brush under it, a short trail of his words). Then, each on its word: a picture of his screen, a figure card on
black (the figure pops in red, its small label types on as he says it, an older figure can sit above it, struck), one
shot of his own room with him full frame, and a picture that builds in under a figure as the figure lifts away and
turns white. Captions in phrases on the lower line, one red word only where no card carries red. Film grade, grain, a
minor pad that changes chord on the beats, air whooshes, low hits under the figures, typewriter keys on the label, all
made in code. The cutout is BiRefNet HR on every frame of the passage (the matte add-on), under the heavy lock.
"""
import json
import math
import os
import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from studio_engine import brand, heavy
from studio_engine import film as L
from studio_engine import sound as snd
from studio_engine.errors import StudioError
from studio_engine.layout import resolve_at, text_box
from studio_engine.render import IN709, Encoder, Reader, mux


KIND = "reel"
SEP = "  ·  "
KICKERS = [f"FIELD NOTES{SEP}NO. {n:02d}" for n in range(1, 100)]
LABELS = list(KICKERS)

# the frame, as Bernard picked it
SIDE = 80
CAP_Y = 1498                    # the caption baseline: the lower line (78 percent), clear of his chin
CAP_SIZE = 58
KICKER_Y = 245                  # the kicker's baseline (its letters start at the safe line, 220)
CLAIM_Y, CLAIM_SIZE = 430, 200  # the claim figure's baseline and size
TRAIL_GAP = 125                 # claim baseline to the trail's baseline
OPEN_Y = 330                    # the opening picture's top edge
PIC_Y = 330                     # a picture beat's top edge
UNDER_Y = 400                   # a picture that builds in under a lifted figure
PIC_W, PIC_H = 1080, 768        # every picture up top is this size, its bottom 150 rows fading to black
FIG_SIZE, FIG_Y, FIG_Y_OLD = 285, 660, 700   # figure size and the centre of its row (lower when an old figure sits above)
OLD_SIZE, OLD_Y = 104, 330      # the struck older figure (top of its sprite)
UNIT_K, GAP_K = 96 / 330, 120 / 330   # the unit's size and its tuck under the figure, both by the figure's size
LABEL_SIZE, LABEL_Y = 44, 905
TYPE_STEP = 0.05                # a typed label part: one letter every 0.05 s
LIFT = 0.32                     # the figure lifts and shrinks to 55 percent over this long
GRAIN = 0.03
TAIL = 0.8
CORNERS = {"left": 300, "right": 780, "centre": 540}
CROP_ASPECT = PIC_W / PIC_H

# levels as he heard them (dB under his voice at the effect's loudest; the bed under his voice before it ducks)
BED = {"name": "cutout", "under_db": 16}
FX = {"whoosh": 30, "hit": 27, "key": 31}

LEADING = {"a", "an", "the", "i", "to", "of", "and", "for", "in", "on", "at", "my", "your", "our", "with", "from", "but",
           "or", "it", "is", "was", "we", "you", "he", "she", "they", "this", "that", "so", "by"}


# ----------------------------------------------------------------------------------------------- the plan
def _t(x, words, duration, field):
    return resolve_at(x, words, duration, field=field)


def plan(spec, words, duration):
    """The sections in time order: [(t0, beat dict, index)], the opening first (index -1)."""
    beats = spec.get("beats") or []
    out = [(0.0, {"kind": "opening", **(spec.get("opening") or {})}, -1)]
    last = 0.0
    for k, b in enumerate(beats):
        t = _t(b["at"], words, duration, f"beats[{k}].at")
        if t <= last + 1e-3:
            raise StudioError(f"The pictures must come one after another: beats[{k}] starts at or before the one "
                              "before it. Put the beats in the order he says their words.")
        last = t
        out.append((t, b, k))
    return out


def fig_font(b):
    return brand.font("display", int(FIG_SIZE * float(b.get("size", 1.0))))


def validate(spec, words, duration):
    secs = plan(spec, words, duration)
    if secs[1:] and secs[1][0] > duration:
        raise StudioError("The first picture starts after his last word.")
    prev = None
    for t, b, k in secs[1:]:
        kind = b["kind"]
        if kind == "picture" and b.get("keep_figure") and (prev is None or prev["kind"] != "figure"):
            raise StudioError(f"beats[{k}] keeps the figure, so the beat right before it must be a figure card.")
        if kind == "figure":
            f = fig_font(b)
            w = L.tw(b["text"], f)
            if b.get("unit"):
                fu = brand.font("display_soft", int(f.size * UNIT_K))       # the unit's ink ends here (see fig_sprite)
                w += int(f.size * 0.35) - int(f.size * GAP_K) + int(fu.size * 0.35) + fu.getlength(b["unit"])
            if w > 1080 - 2 * SIDE:
                raise StudioError(f'The figure "{b["text"]}" in beats[{k}] is too wide for the frame at this size. Use '
                                  "a smaller size or a shorter figure.")
            for j, part in enumerate(b.get("label") or []):
                _t(part["at"], words, duration, f"beats[{k}].label[{j}].at")
            lab = SEP.join(p["text"].upper() for p in b.get("label") or [])
            if lab and L.tw(lab, brand.font("archive", LABEL_SIZE), 0.14) > 1080 - 2 * SIDE:
                raise StudioError(f"The label in beats[{k}] is too long for the frame. Use fewer of his words.")
        prev = b
    op = spec.get("opening") or {}
    f = brand.font("display", int(CLAIM_SIZE * float(op.get("scale", 1.0))))
    if f.getlength(op.get("figure", "")) > 1080 - 2 * SIDE - 60:
        raise StudioError("The opening figure is too wide for the frame at this size. Use a smaller scale or a shorter "
                          "figure.")
    for k, c in enumerate(spec.get("captions") or []):
        _t(c["at"], words, duration, f"captions[{k}].at")
        if c.get("red") and c["red"].upper() not in c["text"].upper():
            raise StudioError(f'captions[{k}]: the red word "{c["red"]}" is not in that caption.')


# ----------------------------------------------------------------------------------------------- his cutout
class Matte:
    """The matte run for the passage picture: every frame and its alpha, made once and kept in the project."""

    def __init__(self, ctx):
        from studio_engine import matte
        from studio_engine.util import nice_fps, probe
        if not matte.available():
            raise StudioError("The cutout style needs the cutout model. Type /studio-setup and say yes to the cutout "
                              "model.")
        pic = ctx.picture()
        meta = probe(pic)
        fps = min(nice_fps(meta["video"]["fps"]), ctx.fps)   # never more frames than the reel shows
        t1 = meta["duration"]
        run = ctx.project.path("matte", f"passage-{0.0:.2f}-{t1:.2f}-{fps:g}")
        stamp = {"source": ctx.passage.get("source"), "segments": ctx.passage.get("segments")}
        sf = run / "passage-stamp.json"
        if sf.exists() and json.loads(sf.read_text()) != stamp:
            shutil.rmtree(run)              # a new passage with the same length: never reuse the old frames
        ctx.say("Cutting him out of every frame (this takes a few minutes the first time).")
        info = matte.matte_clip(ctx.project, None, 0.0, t1, fps)
        run.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(stamp))
        self.info = info
        self.run, self.fps = run, fps
        self.frames = sorted((run / "frames").glob("f*.jpg"))
        if not self.frames:
            raise StudioError("I could not take any frames out of his video to cut him out of.")
        self.n = len(self.frames)
        self.coverage = {}
        self.holds = self.find_holds(ctx.passage.get("segments") or [])

    def _small(self, n):
        im = Image.open(self.frames[min(self.n, max(1, n)) - 1]).convert("L").resize((96, 54))
        return np.asarray(im, np.float32)

    def find_holds(self, segments):
        """Old videos often cut to another camera right at the end (or start) of a range, a frame or two inside the
        words. Where the picture jumps within 0.2 s of a range's edge, hold the last (or first) good frame over the
        jump: [(t0, t1, t_hold)]."""
        holds = []
        edge = int(round(0.2 * self.fps)) + 1
        for sg in segments:
            a = int(round(sg["at"] * self.fps)) + 1
            z = int(round((sg["at"] + sg["out"] - sg["in"]) * self.fps))
            if z - a < 4 * edge:
                continue
            for lo, hi, end in ((z - edge, z, True), (a, a + edge, False)):
                prev = self._small(lo - 1 if end else hi + 1)
                fr = range(lo, hi + 1) if end else range(hi, lo - 1, -1)
                for n in fr:
                    cur = self._small(n)
                    if np.abs(cur - prev).mean() > 30:         # a camera change, not a hand moving
                        if end:
                            holds.append(((n - 1.5) / self.fps, (z + 0.5) / self.fps, (n - 2) / self.fps))
                        else:
                            holds.append(((a - 1.5) / self.fps, (n - 0.5) / self.fps, n / self.fps))
                        break
                    prev = cur
        return holds

    def hold(self, t):
        """Passage time t, moved off a camera change at a range's edge."""
        for t0, t1, th in self.holds:
            if t0 <= t < t1:
                return th
        return t

    def get(self, t):
        """(frame RGB uint8, alpha float) at passage time t."""
        n = min(self.n, int(round(self.hold(t) * self.fps)) + 1)
        n = max(1, n)
        rgb = np.asarray(Image.open(self.run / "frames" / f"f{n:05d}.jpg").convert("RGB"))
        a = np.asarray(Image.open(self.run / "alpha" / f"a{n:05d}.png"), np.float32) / 255
        self.coverage[n] = float((a > 0.5).mean())
        return rgb, a


def clean_alpha(a):
    """Keep his body: the largest solid part of the matte and whatever lies within 31 px of it (a stray object the
    model also picked up, a lamp or a screen at the side, is dropped)."""
    import cv2
    hard = (a > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hard)
    if n <= 2:
        return a
    body = (lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    near = cv2.dilate(body, np.ones((31, 31), np.uint8)).astype(bool)
    return np.where(near, a, 0)


# ----------------------------------------------------------------------------------------------- the renderer
class Piece:
    def __init__(self, ctx):
        self.ctx = ctx
        sp = ctx.spec
        self.W, self.H, self.fps = ctx.w, ctx.h, ctx.fps
        self.tail = float(sp.get("tail", TAIL))
        self.total_s = ctx.duration + self.tail
        self.N = int(math.ceil(self.total_s * self.fps))
        self.secs = plan(sp, ctx.words, ctx.duration)
        self.starts = [s[0] for s in self.secs]
        self.op = sp.get("opening") or {}
        self.cut = dict({"x": 0.5, "width": 0.6875, "scale": 0.86, "band": 0, "brighten": 1.0},
                        **(sp.get("cutout") or {}))
        c = ctx.brand["colors"]
        self.col = {k: brand.rgb_of(v) for k, v in c.items()}
        self.sides = self.plan_sides()
        self.labels_at = {}
        for t, b, k in self.secs:
            if b["kind"] == "figure":
                self.labels_at[k] = [ctx.at(p["at"], f"beats[{k}].label[{j}].at")
                                     for j, p in enumerate(b.get("label") or [])]
        self.captions = self.plan_captions()

    # ---------------------------------------------------------------- sections
    def sec_index(self, t):
        i = 0
        for j, s in enumerate(self.starts):
            if t >= s:
                i = j
        return i

    def plan_sides(self):
        """His corner per section: the spec's `side`, else switching on every picture (never three in a row on one
        side); the room shot has none."""
        out, prev, run = [], None, 0
        for t, b, k in self.secs:
            if b["kind"] == "room":
                out.append("room")
                continue
            if b["kind"] == "picture" and b.get("keep_figure") and "side" not in b and prev:
                s = prev
            elif "side" in b:
                s = b["side"]
            elif prev is None:
                s = "right"
            else:
                s = "left" if prev == "right" else "right" if prev == "left" else ("left" if run % 2 else "right")
            run = run + 1 if s == prev else 1
            prev = s
            out.append(s)
        return out

    def red_figure_at(self, t):
        """True while a figure card shows its figure in red (a lifted figure is white)."""
        i = self.sec_index(t)
        return self.secs[i][1]["kind"] == "figure" and self.secs[i][1].get("red", True)

    def plan_captions(self):
        """[(t0, t1, text, red word or None)]. From the spec's captions, else phrases of his words broken at full stops
        and commas, at a picture change, at a pause, and at four words, never ending on a small leading word."""
        ctx = self.ctx
        end = ctx.duration + 0.5
        spec_caps = ctx.spec.get("captions")
        out = []
        if spec_caps:
            starts = [ctx.at(c["at"], f"captions[{k}].at") for k, c in enumerate(spec_caps)]
            for k, c in enumerate(spec_caps):
                t1 = starts[k + 1] if k + 1 < len(starts) else end
                if "until" in c:
                    t1 = min(t1, ctx.at(c["until"], f"captions[{k}].until"))
                if t1 > starts[k]:
                    out.append((starts[k], t1, c["text"].upper(), (c.get("red") or "").upper() or None))
            return out
        groups, cur = [], []
        beat_t = set(round(s, 3) for s in self.starts[1:])
        for j, w in enumerate(ctx.words):
            if cur and (any(abs(w["t0"] - s) < 0.06 for s in beat_t) or w["t0"] - cur[-1]["t1"] >= 0.3):
                groups.append(cur)
                cur = []
            cur.append(w)
            if w["w"][-1:] in ".,?!;:" or len(cur) >= 4:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        k = 0
        while k < len(groups) - 1:              # never end a phrase on "the", "a", "and": carry it to the next
            g = groups[k]
            if g[-1]["w"].lower() in LEADING:
                groups[k + 1] = [g[-1]] + groups[k + 1]
                if len(g) == 1:                 # a lone small word joins the next phrase whole
                    del groups[k]
                else:
                    groups[k] = g[:-1]
                continue                        # "with my": check the new last word too
            k += 1
        for k, g in enumerate(groups):
            t0 = 0.0 if k == 0 else g[0]["t0"]
            t1 = groups[k + 1][0]["t0"] if k + 1 < len(groups) else end
            out.append((t0, t1, " ".join(w["w"] for w in g).upper().rstrip(",;:"), None))
        return out

    def caption_at(self, t):
        for t0, t1, txt, red in self.captions:
            if t0 <= t < t1:
                return txt, (red if red and not self.red_figure_at(t) else None)
        return None

    # ---------------------------------------------------------------- pictures
    def open_readers(self):
        ctx = self.ctx
        W, H = self.W, self.H
        self.pics = {}
        for t, b, k in self.secs:
            pic = b.get("picture") if b["kind"] == "opening" else b if b["kind"] == "picture" else None
            if pic and pic.get("source"):
                self.pics[k] = self.picture_source(pic, k)
        rm = ctx.spec.get("room") or {}
        size = ctx.passage.get("size") or [1920, 1080]
        sw, sh = float(size[0]), float(size[1])
        zoom = float(rm.get("zoom", 1.4))
        s = max(zoom * 1080 / sh, W / sw)
        pw, ph = int(round(sw * s / 2) * 2), int(round(sh * s / 2) * 2)
        self.room_top = int(rm.get("top", 440))
        vis = max(2, min(ph, H - self.room_top))
        x = int(round(min(max(0.0, float(rm.get("x", self.cut["x"])) * pw - W / 2), pw - W)))
        self.room_h = vis
        self.room = None
        if any(b["kind"] == "room" for _, b, _ in self.secs):
            self.room = Reader(ctx.picture(), (W, vis), self.fps,
                               vf=f"scale={pw}:{ph}:flags=lanczos,crop={W}:{vis}:{x}:0,{IN709}")
        self.room_ramp = np.clip(np.arange(vis) / 140.0, 0, 1)[:, None, None].astype(np.float32)
        self.fade = np.clip(np.arange(PIC_H)[::-1] / 150.0, 0, 1)[:, None, None].astype(np.float32)

    def picture_source(self, pic, k):
        """A video (from `in` seconds) or a still, cropped to the box `crop` (fractions of its width and height; the
        box keeps the picture's 1080 x 768 shape) and scaled to 1080 x 768."""
        src = self.ctx.source(pic["source"])
        cr = pic.get("crop") or {}
        where = "the opening picture" if k < 0 else f"beats[{k}]"
        if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".heic"):
            im = Image.open(src).convert("RGB")
            sw, sh = im.size
            x, y, w, h = self.crop_box(cr, sw, sh, where)
            im = im.crop((x, y, x + w, y + h)).resize((PIC_W, PIC_H), Image.LANCZOS)
            return {"still": L.to_f(np.asarray(im))}
        from studio_engine.util import probe
        v = probe(src)["video"]
        if not v:
            raise StudioError(f"The source for {where} has no picture.")
        x, y, w, h = self.crop_box(cr, v["w"], v["h"], where)
        rd = Reader(src, (PIC_W, PIC_H), self.fps, vf=f"crop={w}:{h}:{x}:{y},scale={PIC_W}:{PIC_H}:flags=lanczos,{IN709}")
        return {"reader": rd, "in": float(pic.get("in", 0.0))}

    @staticmethod
    def crop_box(cr, sw, sh, where):
        w = int(round(float(cr.get("w", 1.0)) * sw))
        h = int(round(w / CROP_ASPECT))
        if h > sh + 2:                      # taller than the source: narrow the box instead, never squash
            h = sh
            w = int(round(h * CROP_ASPECT))
        h = min(h, sh)
        x = int(round(float(cr.get("x", 0.0)) * sw))
        y = int(round(float(cr.get("y", 0.0)) * sh))
        x, y = min(max(0, x), max(0, sw - w)), min(max(0, y), max(0, sh - h))
        if w < 64 or h < 64:
            raise StudioError(f"The crop of {where} is too small.")
        return x - x % 2, y - y % 2, w - w % 2, h - h % 2

    def pic_frame(self, k, t, t0):
        p = self.pics[k]
        if "still" in p:
            return p["still"]
        return L.to_f(p["reader"].get(int(round((p["in"] + max(0.0, t - t0)) * self.fps))))

    def put_picture(self, base, pic, t, t0, y):
        s, op = L.pop(t, t0)
        pic = pic * self.fade
        if s < 0.999:
            import cv2
            M = np.float32([[s, 0, (1 - s) * PIC_W / 2], [0, s, (1 - s) * PIC_H / 2]])
            pic = cv2.warpAffine(pic, M, (PIC_W, PIC_H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        reg = base[y:y + PIC_H]
        base[y:y + PIC_H] = reg * (1 - op) + np.maximum(reg, pic) * op if op < 1 else np.maximum(reg, pic)
        return base

    @staticmethod
    def claim_ground(pic):
        """The top of the opening picture defocused and darkened so the claim reads over it."""
        import cv2
        m = np.clip(1 - (np.arange(PIC_H) - 150) / 170.0, 0, 1)[:, None, None].astype(np.float32)
        m = m * m * (3 - 2 * m)
        return pic * (1 - m) + cv2.GaussianBlur(pic, (0, 0), 12) * 0.2 * m

    def room_frame(self, t):
        W, H = self.W, self.H
        tt = min(t, self.ctx.duration - 0.5 / self.fps)
        src = L.to_f(self.room.get(int(round(self.matte.hold(tt) * self.fps))))
        f = np.full((H, W, 3), 0.012, np.float32)
        f[self.room_top:self.room_top + self.room_h] = src * self.room_ramp + 0.012 * (1 - self.room_ramp)
        f = L.grade_film(f, lift_amt=0.03, contrast=1.06, sat=0.9, warm=0.05)
        return L.halation(f, 0.7, 16, 0.28) * L.vignette(W, H, 0.28)

    # ---------------------------------------------------------------- his cutout
    def place_cutout(self, base, t, side):
        """His cutout, bottom flush, his centre on the corner's x. With a `band`, a feathered ring of his own frame
        around the matte shows too: on a dark room that brings back dark hair the model drops, and over a picture it
        reads as shadow. It only works where his room is dark behind him."""
        import cv2
        c = self.cut
        rgb, a = self.matte.get(min(t, self.ctx.duration - 0.5 / self.fps))
        sh, sw = a.shape
        cw = int(round(float(c["width"]) * sw))
        cx_src = float(c["x"]) * sw
        x0s = int(round(cx_src - cw / 2))
        lo, hi = max(0, x0s), min(sw, x0s + cw)
        rgb_c = np.zeros((sh, cw, 3), np.float32)
        a_c = np.zeros((sh, cw), np.float32)
        rgb_c[:, lo - x0s:hi - x0s] = L.to_f(rgb[:, lo:hi])
        a_c[:, lo - x0s:hi - x0s] = clean_alpha(a[:, lo:hi])
        rgb_c = L.grade_film(np.clip(rgb_c * float(c["brighten"]), 0, 1), lift_amt=0.02, contrast=1.08, sat=0.9,
                             warm=0.05)
        scale = float(c["scale"]) * (1.5 if side == "centre" else 1.0)
        unit = 1080 / sh                                # his picture is `scale` x 1080 px tall whatever the source
        h, w_ = int(sh * unit * scale), int(cw * unit * scale)
        interp = cv2.INTER_AREA if unit * scale < 1 else cv2.INTER_CUBIC
        full = cv2.resize(rgb_c, (w_, h), interpolation=interp)
        a2 = cv2.resize(a_c, (w_, h), interpolation=interp).clip(0, 1)
        cx = CORNERS[side]
        x0 = int(round(cx - w_ / 2))
        y0 = self.H - h
        band = int(c["band"])
        if band > 0:
            halo = cv2.GaussianBlur(cv2.dilate(a2, np.ones((band, band), np.uint8)), (0, 0), band / 2 + 0.5)
            k = np.maximum(a2, halo.clip(0, 1) * 0.97)[..., None]
        else:
            k = a2[..., None]
        sx0, sx1 = max(0, -x0), min(w_, self.W - x0)
        dx0, dx1 = max(0, x0), min(self.W, x0 + w_)
        ys0 = max(0, -y0)
        reg = base[y0 + ys0:self.H, dx0:dx1]
        kk = k[ys0:, sx0:sx1]
        base[y0 + ys0:self.H, dx0:dx1] = reg * (1 - kk) + full[ys0:, sx0:sx1] * kk
        return base

    # ---------------------------------------------------------------- layers
    def fig_sprite(self, b, white=False):
        """The figure (and its unit) as one sprite; its row's centre sits at FIG_Y (FIG_Y_OLD under an old figure)."""
        col = self.col["warm_white"] if white or not b.get("red", True) else self.col["red"]
        f = fig_font(b)
        big, _ = L.text_img(b["text"], f, col)
        if not b.get("unit"):
            return big
        mo, _ = L.text_img(b["unit"], brand.font("display_soft", int(f.size * UNIT_K)), self.col["zen"])
        gap = int(f.size * GAP_K)
        canvas = Image.new("RGBA", (big.width + mo.width - gap + 40, big.height), (0, 0, 0, 0))
        canvas.alpha_composite(big, (0, 0))
        canvas.alpha_composite(mo, (big.width - gap, int(big.height * 0.62 - mo.height * 0.62)))
        return canvas

    def fig_centre(self, b):
        return FIG_Y_OLD if b.get("old") else FIG_Y

    @lru_cache(maxsize=None)
    def old_layer(self, k):
        b = self.secs[k + 1][1]
        lay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        old, _ = L.text_img(b["old"], brand.font("display_soft", OLD_SIZE), (120, 120, 120))
        lay.alpha_composite(old, (int((self.W - old.width) / 2), OLD_Y))
        ImageDraw.Draw(lay).line([(self.W / 2 - 200, 404), (self.W / 2 + 200, 384)], fill=(150, 150, 150, 255), width=6)
        return lay

    def label_text(self, k, t):
        """(the label as shown at time t, the full label). The first part appears whole on its word with the
        separator after it; each later part types on letter by letter from its word."""
        b = self.secs[k + 1][1]
        parts = [p["text"].upper() for p in b.get("label") or []]
        ats = self.labels_at.get(k, [])
        shown = ""
        for j, (p, a) in enumerate(zip(parts, ats)):
            if t < a:
                break
            n = len(p) if j == 0 else min(len(p), int((t - a) / TYPE_STEP) + 1)
            shown += p[:n]
            if j + 1 < len(parts) and n == len(p):
                shown += SEP
        return shown, SEP.join(parts)

    def figure_layer(self, k, t):
        """A figure card on black at time t: the old figure (struck) above, the figure popping in, the label typed."""
        t0, b, _ = self.secs[k + 1]
        lay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if b.get("old"):
            lay.alpha_composite(self.old_layer(k))
        s, op = L.pop(t, t0, 0.28)
        sp = self.fig_sprite(b)
        sp = sp.resize((int(sp.width * s), int(sp.height * s)), Image.LANCZOS)
        lay.alpha_composite(L.set_alpha(sp, op), (int((self.W - sp.width) / 2), int(self.fig_centre(b) - sp.height / 2)))
        shown, full = self.label_text(k, t)
        if shown:
            f = brand.font("archive", LABEL_SIZE)
            L.draw_text(ImageDraw.Draw(lay), (self.W / 2 - L.tw(full, f, 0.14) / 2, LABEL_Y + self.label_drop(b)), shown,
                        f, self.col["zen"] + (255,), 0.14)
        return lay

    @staticmethod
    def label_drop(b):
        return max(0.0, float(b.get("size", 1.0)) - 1.0) * 150

    def lifted_layer(self, k, t, t0):
        """The figure of card k lifting away as the picture builds in under it: the old figure fades, the figure turns
        white, shrinks to 55 percent and rises."""
        fb = self.secs[k + 1][1]
        kk = L.ease_out(L.clamp((t - t0) / LIFT), 3)
        lay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        if fb.get("old"):
            lay.alpha_composite(L.set_alpha(self.old_layer(k), 1 - kk))
        sp = self.fig_sprite(fb, white=True)
        sc = 1 - 0.45 * kk
        sp = sp.resize((max(1, int(sp.width * sc)), max(1, int(sp.height * sc))), Image.LANCZOS)
        cy = self.fig_centre(fb) - 420 * kk
        lay.alpha_composite(sp, (int((self.W - sp.width) / 2), int(cy - sp.height / 2)))
        return lay

    @lru_cache(maxsize=None)
    def claim_layer(self):
        """The claim on frame one: kicker, the figure with the red brush under it, the trail."""
        W, H = self.W, self.H
        lay, d = L.text_layer((W, H))
        if self.kicker():
            L.draw_text(d, (W / 2, KICKER_Y), self.kicker(), brand.font("archive", 34), self.col["zen"] + (210,), 0.22,
                        "ms")
        f, fig, x0, base = self.claim_geom()
        if fig:
            d.text((x0, base), fig, font=f, fill=self.col["warm_white"] + (255,), anchor="ls")
        if self.op.get("trail"):
            L.draw_text(d, (W / 2, base + TRAIL_GAP), self.op["trail"], brand.font("body", 54), self.col["zen"] + (255,),
                        0.0, "ms")
        lay = L.shadow_of(L.shadow_of(lay, 26, 0.5, 0), 8, 0.7, 3)
        if fig:
            lay.alpha_composite(L.brush_draw("red-a", f.getlength(fig) * 1.08, 0.5, -1.2), (int(x0 - 22), int(base + 8)))
        return lay

    def kicker(self):
        k = self.op.get("kicker", 1)
        if k is False or k is None:
            return None
        return KICKERS[(int(k) if k is not True else 1) - 1]

    def claim_geom(self):
        s = float(self.op.get("scale", 1.0))
        size = int(CLAIM_SIZE * s)
        base = CLAIM_Y + (size - CLAIM_SIZE) * 0.7
        f = brand.font("display", size)
        fig = self.op.get("figure", "")
        return f, fig, (self.W - f.getlength(fig)) / 2, base

    def caption_geom(self, txt, red):
        f = L.fit("caption", brand.caption_px(CAP_SIZE, self.ctx.brand), txt, self.W - 2 * SIDE - 40, 0.02)
        if red and red in txt:
            lead, rest = txt[: txt.index(red)], txt[txt.index(red) + len(red):]
            fr = brand.font("display", int(f.size * 1.32))
            wl, wr, wrest = L.tw(lead, f, 0.02), fr.getlength(red), L.tw(rest, f, 0.02)
            x = (self.W - wl - wr - wrest) / 2
            return f, fr, [(lead, x, f, False), (red, x + wl, fr, True), (rest, x + wl + wr, f, False)]
        return f, None, [(txt, (self.W - L.tw(txt, f, 0.02)) / 2, f, False)]

    @lru_cache(maxsize=None)
    def caption_layer(self, txt, red):
        lay, d = L.text_layer((self.W, self.H))
        _, _, parts = self.caption_geom(txt, red)
        for s, x, f, is_red in parts:
            if not s:
                continue
            if is_red:
                d.text((x, CAP_Y + 4), s, font=f, fill=self.col["red_on_footage"] + (255,), anchor="ls")
            else:
                L.draw_text(d, (x, CAP_Y), s, f, self.col["zen"] + (255,), 0.02)
        return L.shadow_of(L.shadow_of(lay, 22, 0.5, 0), 6, 0.8, 3)

    # ---------------------------------------------------------------- one frame
    def frame(self, i):
        t = i / self.fps
        j = self.sec_index(t)
        t0, b, k = self.secs[j]
        side = self.sides[j]
        if b["kind"] == "room":
            f = self.room_frame(t)
        else:
            f = np.full((self.H, self.W, 3), 0.008, np.float32)
            lay = None
            if b["kind"] == "opening":
                if k in self.pics:
                    f = self.put_picture(f, self.claim_ground(self.pic_frame(k, t, 0.0)) * 0.92, t, -1.0, OPEN_Y)
                lay = self.claim_layer()
            elif b["kind"] == "figure":
                lay = self.figure_layer(k, t)
            elif b["kind"] == "picture":
                if b.get("keep_figure"):
                    lay = self.lifted_layer(k - 1, t, t0)
                    pic = self.pic_frame(k, t, t0)
                    _, op = L.pop(t, t0 + 0.18)
                    reg = f[UNDER_Y:UNDER_Y + PIC_H]
                    f[UNDER_Y:UNDER_Y + PIC_H] = reg * (1 - op) + np.maximum(reg, pic * self.fade) * op
                else:
                    f = self.put_picture(f, self.pic_frame(k, t, t0), t, t0, PIC_Y)
            if lay is not None:
                f = L.over(f, lay)
            f = self.place_cutout(f, t, side)
            f = f * L.vignette(self.W, self.H, 0.25)
        c = self.caption_at(t)
        if c:
            f = L.over(f, self.caption_layer(*c))
        grain = float((self.ctx.spec.get("finish") or {}).get("grain", GRAIN))
        return L.to_u8(L.grain(f, i, grain))

    # ---------------------------------------------------------------- the layout record
    def record(self):
        lay = self.ctx.layout
        W = self.W
        hexs = self.ctx.brand["colors"]
        ends = self.starts[1:] + [self.total_s]
        for j, ((t0, b, k), t1) in enumerate(zip(self.secs, ends)):
            beat = lay.beat(b["kind"] if b["kind"] != "picture" else "picture", t0, t1)
            if b["kind"] == "opening":
                if self.kicker():
                    f = brand.font("archive", 34)
                    lay.text(beat, self.kicker(), text_box(f, self.kicker(), W / 2, KICKER_Y, "ms", 0.22), role="label",
                             color=hexs["zen"])
                f, fig, x0, base = self.claim_geom()
                if fig:
                    lay.text(beat, fig, text_box(f, fig, x0, base, "ls"), color=hexs["warm_white"])
                    br = L.brush_draw("red-a", f.getlength(fig) * 1.08, 0.5, -1.2)
                    lay.mark(beat, "brush under the figure", (x0 - 22, base + 8, br.width, br.height), red=True,
                             color=hexs["red"])
                if self.op.get("trail"):
                    ft = brand.font("body", 54)
                    lay.text(beat, self.op["trail"], text_box(ft, self.op["trail"], W / 2, base + TRAIL_GAP, "ms"),
                             color=hexs["zen"])
            elif b["kind"] == "figure":
                self.record_figure(beat, b, k, red=b.get("red", True))
            elif b["kind"] == "picture" and b.get("keep_figure"):
                fb = self.secs[j - 1][1]
                f = fig_font(fb)
                sc = 0.55
                cy = self.fig_centre(fb) - 420
                sp = self.fig_sprite(fb, white=True)
                wd, ht = sp.width * sc, sp.height * sc
                x = (W - wd) / 2 + int(f.size * 0.35) * sc
                asc = f.getmetrics()[0]
                base = cy - ht / 2 + (int(f.size * 0.35) + asc) * sc
                fs = brand.font("display", max(8, int(f.size * sc)))
                lay.text(beat, fb["text"], text_box(fs, fb["text"], x, base, "ls"), color=hexs["warm_white"])
        for t0, t1, txt, red in self.captions:
            # a caption's red word stays white while a red figure is up; split the caption where that changes
            cuts = [t0] + [s for s in self.starts if t0 < s < t1] + [t1]
            for a, z in zip(cuts, cuts[1:]):
                r = red if red and not self.red_figure_at(a + 1e-4) else None
                cb = lay.beat("caption", a, z)
                f, fr, parts = self.caption_geom(txt, r)
                for s, x, ff, is_red in parts:
                    if not s.strip():
                        continue
                    y = CAP_Y + 4 if is_red else CAP_Y
                    lay.text(cb, s.strip(), text_box(ff, s, x, y, "ls", 0 if is_red else 0.02),
                             color=hexs["red_on_footage"] if is_red else hexs["zen"])

    def record_figure(self, beat, b, k, red=True):
        hexs = self.ctx.brand["colors"]
        W = self.W
        f = fig_font(b)
        sp = self.fig_sprite(b)
        pad = int(f.size * 0.35)
        x = (W - sp.width) / 2 + pad
        y = self.fig_centre(b) - sp.height / 2 + pad + f.getmetrics()[0]
        lay = self.ctx.layout
        lay.text(beat, b["text"], text_box(f, b["text"], x, y, "ls"), color=hexs["red"] if red else hexs["warm_white"])
        if b.get("unit"):
            fu = brand.font("display_soft", int(f.size * UNIT_K))
            big_w = L.text_img(b["text"], f, (0, 0, 0))[0].width
            mo, (mx, my) = L.text_img(b["unit"], fu, (0, 0, 0))
            ux = (W - sp.width) / 2 + big_w - int(f.size * GAP_K) + mx
            uy = self.fig_centre(b) - sp.height / 2 + int(sp.height * 0.62 - mo.height * 0.62) + my
            lay.text(beat, b["unit"], text_box(fu, b["unit"], ux, uy, "ls"), color=hexs["zen"])
        if b.get("old"):
            fo = brand.font("display_soft", OLD_SIZE)
            old, (ox, oy) = L.text_img(b["old"], fo, (0, 0, 0))
            lay.text(beat, b["old"], text_box(fo, b["old"], (W - old.width) / 2 + ox, OLD_Y + oy, "ls"), color="#787878")
            lay.mark(beat, "the old figure struck through", (W / 2 - 200, 384, 400, 20), red=False)
        _, full = self.label_text(k, 1e9)
        if full:
            fa = brand.font("archive", LABEL_SIZE)
            lay.text(beat, full, text_box(fa, full, W / 2 - L.tw(full, fa, 0.14) / 2, LABEL_Y + self.label_drop(b), "ls",
                                          0.14), color=hexs["zen"])

    # ---------------------------------------------------------------- sound
    def effects(self):
        spec_fx = self.ctx.spec.get("effects", True)
        if spec_fx is False:
            return []
        softer = float(spec_fx.get("softer_db", 0)) if isinstance(spec_fx, dict) else 0.0
        out = []
        figs = 0
        for t0, b, k in self.secs[1:]:
            if b["kind"] == "room":
                continue
            out.append({"array": snd.whoosh_air(0.7, seed=k), "t": max(0.0, t0 - 0.12), "under_db": FX["whoosh"] + softer})
            if b["kind"] == "figure":
                out.append({"array": snd.sub_hit(46 + 6 * figs), "t": t0,
                            "under_db": FX["hit"] + min(figs, 1) + softer})
                figs += 1
                for j, a in enumerate(self.labels_at.get(k, [])):
                    if j == 0:
                        continue
                    for n in range(min(4, len(b["label"][j]["text"]))):
                        out.append({"name": "key", "t": a + n * TYPE_STEP, "under_db": FX["key"] + softer})
        return out

    def bed(self):
        """The cutout pad: A minor, F on the second beat, C on the third (or the spec's own `sound.bed`)."""
        ch = [s for s in self.starts[2:4]]
        return dict(BED, changes=ch)


def render(ctx):
    pc = Piece(ctx)
    pc.matte = Matte(ctx)
    pc.open_readers()
    ctx.say("Drawing the cutout reel.")
    pic = ctx.work / "picture.mp4"
    import time
    t_start = time.time()
    with heavy.lock("cutout frames"):
        enc = Encoder(pic, ctx.w, ctx.h, ctx.fps, crf=15)
        for i in range(pc.N):
            enc.write(pc.frame(i))
        enc.close()
    frames_s = time.time() - t_start
    if pc.room is not None:
        pc.room.close()
    for p in pc.pics.values():
        if "reader" in p:
            p["reader"].close()

    ctx.say("Mixing the sound.")
    sound = dict(ctx.spec.get("sound") or {})
    if "bed" not in sound:
        sound["bed"] = {**pc.bed(), "changes": [{"t": x} for x in pc.bed()["changes"]]}
    ctx.spec = dict(ctx.spec, sound=sound)
    levels = ctx.sound(extra_sfx=pc.effects(), duration=pc.total_s)
    pc.record()
    mux(pic, ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    cov = list(pc.matte.coverage.values())
    (ctx.out / "cutout.json").write_text(json.dumps({
        "matte": {k: pc.matte.info.get(k) for k in ("run", "frames", "matted_now", "seconds", "s_per_frame", "device")},
        "frames_drawn": pc.N, "frames_seconds": round(frames_s, 1), "s_per_frame_drawn": round(frames_s / pc.N, 3),
        "his_area": {"min": round(min(cov), 4) if cov else 0, "median": round(float(np.median(cov)), 4) if cov else 0},
        "lost_frames": [n for n, v in sorted(pc.matte.coverage.items()) if v < 0.02],
        "held_over_camera_changes": [[round(x, 3) for x in h] for h in pc.matte.holds]}, indent=1))
    return {"output": "final.mp4", "levels": levels, "keep_work": bool(os.environ.get("STUDIO_KEEP_WORK"))}


def qa_extra(project, version_dir, layout):
    """His cutout was found in every frame (the matte kept at least 2 percent of the picture), and the picture pace."""
    out = {}
    f = Path(version_dir) / "cutout.json"
    if f.exists():
        c = json.loads(f.read_text())
        out["cutout_found"] = {"pass": not c["lost_frames"], "lost_frames": c["lost_frames"][:20],
                               "his_area": c["his_area"]}
    beats = [b for b in layout["beats"] if b["kind"] in ("opening", "picture", "figure", "room")]
    holds = [round(b["t1"] - b["t0"], 2) for b in beats]
    rooms = sum(1 for b in beats if b["kind"] == "room")
    out["picture_pace"] = {"pass": rooms <= 2, "holds_s": holds, "room_shots": rooms,
                           "warn": any(h > 4.5 for h in holds),
                           "note": "a new picture every 2 to 4 seconds; one or two room shots at most"}
    return out
