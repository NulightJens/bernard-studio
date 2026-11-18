"""Receipts: a then-and-now pair of his figures, each landing as a paper receipt on a black card.

The reel opens on his screen (or on him) with the claim already set: a small typewriter kicker, the figure in the kit
serif italic with the red brush under it, a short trail of his words. On the "then" figure a black card FIG. 01
"Then." comes in and a receipt slip lands, its rows typed on as he says them. Between the cards he is on camera with
two-word captions (and an optional red keyword). On the turn ("now", "today", "this year") card FIG. 02 "Now." comes
in: the old slip greyed and struck at the left, the new slip lands with the new figure in red; a handwritten line can
take the red at the end. Film grade, grain, a minor pad that opens on the turn, paper, typewriter keys, a pop and a
marker line, all made in code or from the studio's own library.
"""
import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from studio_engine import brand, heavy
from studio_engine import film as L
from studio_engine.errors import StudioError
from studio_engine.layout import resolve_at, text_box
from studio_engine.render import IN709, Encoder, Reader, mux


KIND = "reel"
ROW_LABELS = ["FROM", "DATE", "FOR", "TIME", "WHO", "PLUS"]
LABELS = ["THE RECEIPTS", "FIG. 01", "FIG. 02", "Then.", "Now.", "RECEIPT", "ITEM", "TOTAL", "* * *"] + ROW_LABELS

# the frame, as Bernard picked it
SIDE = 80
CAP_Y = 1210                    # two-word captions: the top of the caption sits here (the 63 percent slot)
CAP_SIZE = 62                   # caption size at the default setting (his setting scales it)
CARD_CAP_Y = 1530               # captions on the cards, in an ivory box
CARD_CAP_SIZE = 50              # their size at the default caption setting
KICKER_Y = 246                  # the kicker's baseline (its letters start at the safe line, 220)
CLAIM_Y, CLAIM_SIZE = 430, 200  # the claim figure's baseline and size
TRAIL_GAP = 130                 # claim baseline to the trail's baseline
PAPER_W, PAPER_H = 640, 900     # a receipt slip (it widens for a big figure)
PAPER_MAX_W = 860
TOTAL_SIZE, UNIT_SIZE = 178, 64
TOTAL_Y = 520                   # the figure's baseline on the slip
TYPE_STEP = 0.03                # seconds per typed letter
HAND_TIME = 0.55                # the handwritten line writes on over this long
LAND = 0.22                     # a slip lands: drops 26 px and settles from 103 percent, no bounce
GRAIN = 0.03
TAIL = 0.8
KEYWORD_SIZE = 210
# small words that lead into the next word; an automatic two-word caption never ends on one
LEADING = {"a", "an", "the", "i", "to", "of", "and", "for", "in", "on", "at", "my", "your", "our", "with", "from", "but",
           "or", "it", "is", "was", "we", "you", "he", "she", "they", "this", "that", "so", "by"}

# levels as he heard them (dB under his voice at the effect's loudest)
BED = {"name": "pad-minor", "under_db": 16}
FX = {"pop": 30, "paper": 27, "key": 31, "thud": 27, "marker": 28}


# ----------------------------------------------------------------------------------------------- checks
def _t(spec_at, words, duration, field):
    return resolve_at(spec_at, words, duration, field=field)


def plan_times(spec, words, duration):
    """Section edges in seconds: opening end, then card, now card, keyword, and every typed moment."""
    th, nw = spec["then"], spec["now"]
    then_at = _t(th["at"], words, duration, "then.at")
    now_at = _t(nw["at"], words, duration, "now.at")
    op = spec.get("opening") or {}
    open_end = _t(op["until"], words, duration, "opening.until") if "until" in op else then_at
    then_end = _t(th["until"], words, duration, "then.until") if "until" in th else now_at
    if open_end > then_at + 1e-3:
        raise StudioError("The opening must end before the first receipt card comes in (opening.until is after "
                          "then.at).")
    if not then_at < then_end <= now_at + 1e-3:
        raise StudioError("The first card must leave before the second card comes in (then.until must fall between "
                          "then.at and now.at).")
    return open_end, then_at, then_end, now_at


def validate(spec, words, duration):
    open_end, then_at, then_end, now_at = plan_times(spec, words, duration)
    for side in ("then", "now"):
        c = spec[side]
        for j, r in enumerate(c.get("rows") or []):
            if r.get("label", "FROM").upper() not in ROW_LABELS:
                raise StudioError(f'The spec\'s {side}.rows[{j}] label must be one of {", ".join(ROW_LABELS)}.')
            if "at" in r:
                _t(r["at"], words, duration, f"{side}.rows[{j}].at")
        for k in ("total_at",):
            if k in c:
                _t(c[k], words, duration, f"{side}.{k}")
        if c.get("rows") and c.get("hand"):
            raise StudioError(f"The spec's {side} card has both typed rows and a handwritten line. Pick one.")
        slip_width(c)
    if spec["then"].get("hand"):
        raise StudioError("Only the second card (now) can end on a handwritten line.")
    h = spec["now"].get("hand")
    if h:
        t = _t(h["at"], words, duration, "now.hand.at")
        if t < now_at:
            raise StudioError("The handwritten line must come after the second card comes in.")
    kw = spec.get("keyword")
    if kw:
        t = _t(kw["at"], words, duration, "keyword.at")
        if not (then_end - 1e-3 <= t < now_at) and not (open_end - 1e-3 <= t < then_at):
            raise StudioError("The keyword must fall while he is on camera, between the cards (keyword.at).")
    op = spec.get("opening") or {}
    f = brand.font("display", int(CLAIM_SIZE * float(op.get("scale", 1.0))))
    if f.getlength(op.get("figure", "")) > 1080 - 2 * SIDE - 60:
        raise StudioError("The opening figure is too wide for the frame at this size. Use a smaller scale or a "
                          "shorter figure.")
    for k, c in enumerate(spec.get("captions") or []):
        _t(c["at"], words, duration, f"captions[{k}].at")
        if "until" in c:
            _t(c["until"], words, duration, f"captions[{k}].until")


def slip_width(card):
    """The slip is 640 px wide, wider when a big figure needs the room (up to 860)."""
    s = float(card.get("scale", 1.0))
    f = brand.font("display", int(TOTAL_SIZE * s))
    need = f.getlength(card["total"])
    if card.get("unit"):
        need += 16 + brand.font("display_soft", int(UNIT_SIZE * s)).getlength(card["unit"])
    w = max(PAPER_W, int(math.ceil(need + 120)))
    if w > PAPER_MAX_W:
        raise StudioError(f'The figure "{card["total"]}" is too wide for a receipt at this size. Use a smaller scale '
                          "or a shorter figure or unit.")
    return w


# ----------------------------------------------------------------------------------------------- the paper
@lru_cache(None)
def paper(seed, w, h):
    """An ivory paper slip with fine fibre, a soft shade and torn zig-zag top and bottom edges."""
    rng = np.random.default_rng(seed)
    base = np.array(brand.color("cream"), np.float32)
    n = rng.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC))
    fib = rng.normal(0, 1, (h // 40, w // 3)).astype(np.float32)
    fib = np.asarray(Image.fromarray(fib).resize((w, h), Image.BICUBIC))
    yy = np.linspace(-1, 1, h)[:, None]
    shade = 1 - 0.035 * yy ** 2 - 0.02 * np.linspace(-1, 1, w)[None, :] ** 2
    rgb = base[None, None] * shade[..., None] + (n * 3.0 + fib * 2.0)[..., None]
    a = np.full((h, w), 255, np.uint8)
    for edge in ("top", "bot"):
        teeth = 18 * w / PAPER_W
        for x in range(w):
            ph = (x % (w / teeth)) / (w / teeth)
            depth = int(10 * (1 - abs(ph * 2 - 1)) + rng.uniform(0, 2))
            if edge == "top":
                a[:depth, x] = 0
            else:
                a[h - depth:, x] = 0
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), a]), "RGBA")


INK = (28, 26, 24)
LABEL_INK = (110, 104, 96)
GREY_TOTAL = (120, 112, 104)


def typed(d, xy, txt, size, n=None, fill=INK, track=0.08, anchor="ls", seed=0, boxes=None, role="words"):
    """Typewriter letters (the kit's archive face), each strike a touch uneven like a real ribbon. With `boxes`, the
    full line's box is recorded for the layout (paper coordinates)."""
    rng = np.random.default_rng(seed)
    f = brand.font("archive", size)
    show = txt if n is None else txt[: max(0, n)]
    x, y = xy
    wd = L.tw(txt, f, track)
    if anchor[0] == "m":
        x -= wd / 2
    elif anchor[0] == "r":
        x -= wd
    if boxes is not None and txt:
        _, top, _, hh = text_box(f, txt, x, y, "ls")
        boxes.append((txt, (x, top, wd, hh), role, fill))
    for ch in show:
        a = int(255 * rng.uniform(0.78, 1.0))
        d.text((x, y + rng.uniform(-0.8, 0.8)), ch, font=f, fill=tuple(fill) + (a,), anchor="ls")
        x += f.getlength(ch) + track * f.size


def dashed(d, y, x0, x1, col=(120, 114, 104, 255)):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + 10, x1), y)], fill=col, width=2)
        x += 18


def slip(card, seed, state, boxes=None):
    """One receipt in a given state. state: (rows_typed: tuple of letter counts, total shown, total red, struck,
    hand letters). Returns RGBA; with `boxes`, records (text, box, role, colour) in paper coordinates."""
    rows_n, show_total, red, struck, hand_n = state
    pw = slip_width(card)
    im = paper(seed, pw, PAPER_H).copy()
    d = ImageDraw.Draw(im)
    cx = pw / 2
    blood = brand.color("red")
    typed(d, (cx, 92), "RECEIPT", 40, track=0.42, anchor="ms", seed=1, boxes=boxes, role="label")
    dashed(d, 176, 56, pw - 56)
    if card.get("item"):
        typed(d, (60, 236), "ITEM", 26, fill=LABEL_INK, seed=3, boxes=boxes, role="label")
        typed(d, (pw - 60, 236), card["item"].upper(), 30, anchor="rs", seed=4, boxes=boxes)
    dashed(d, 280, 56, pw - 56)
    typed(d, (60, 336), "TOTAL", 26, fill=LABEL_INK, seed=5, boxes=boxes, role="label")
    s = float(card.get("scale", 1.0))
    f = brand.font("display", int(TOTAL_SIZE * s))
    col = blood if red else (GREY_TOTAL if struck else INK)
    if show_total:
        if card.get("unit"):
            f2 = brand.font("display_soft", int(UNIT_SIZE * s))
            wd = f.getlength(card["total"]) + 16 + f2.getlength(card["unit"])
            x0 = cx - wd / 2
            d.text((x0, TOTAL_Y), card["total"], font=f, fill=col + (255,), anchor="ls")
            d.text((x0 + f.getlength(card["total"]) + 16, TOTAL_Y), card["unit"], font=f2, fill=col + (255,),
                   anchor="ls")
            if boxes is not None:
                bb = text_box(f, card["total"], x0, TOTAL_Y, "ls")
                boxes.append((card["total"], bb, "words", col))
                bb2 = text_box(f2, card["unit"], x0 + f.getlength(card["total"]) + 16, TOTAL_Y, "ls")
                boxes.append((card["unit"], bb2, "words", col))
        else:
            d.text((cx, TOTAL_Y), card["total"], font=f, fill=col + (255,), anchor="ms")
            if boxes is not None:
                boxes.append((card["total"], text_box(f, card["total"], cx, TOTAL_Y, "ms"), "words", col))
        if struck:
            d.line([(70, TOTAL_Y - 50), (pw - 70, TOTAL_Y - 68)], fill=INK + (235,), width=9)
    dashed(d, 590, 56, pw - 56)
    rows = card.get("rows") or []
    for j, r in enumerate(rows):
        y = 656 + 56 * j
        typed(d, (60, y), r.get("label", "FROM").upper(), 26, fill=LABEL_INK, seed=6 + 2 * j, boxes=boxes,
              role="label")
        typed(d, (pw - 60, y), r["text"].upper(), 32, n=rows_n[j], anchor="rs", seed=7 + 2 * j, boxes=boxes)
    hand = card.get("hand")
    if hand:
        typed(d, (60, 656), hand.get("label", "PLUS").upper(), 26, fill=LABEL_INK, seed=11, boxes=boxes,
              role="label")
        if hand_n:
            layer = Image.new("RGBA", (pw, 220), (0, 0, 0, 0))
            hf = brand.font("hand", 74)
            ImageDraw.Draw(layer).text((pw / 2, 140), hand["text"][:hand_n], font=hf, fill=blood + (255,),
                                       anchor="ms")
            layer = layer.rotate(3, resample=Image.BICUBIC, center=(pw / 2, 110))
            im.alpha_composite(layer, (0, 610))
            if boxes is not None:
                bb = text_box(hf, hand["text"], pw / 2, 750, "ms")
                boxes.append((hand["text"], (bb[0], bb[1] - 14, bb[2], bb[3] + 28), "words", blood))
        dashed(d, 840, 56, pw - 56)
    else:
        dashed(d, 770, 56, pw - 56)
        typed(d, (cx, 836), "* * *", 26, anchor="ms", fill=(140, 132, 122), seed=10, boxes=boxes, role="label")
    return im


PAD = 60


@lru_cache(maxsize=64)
def sprite(key, card_json, seed, state, angle, scale):
    """The slip rotated and scaled with a soft contact shadow under it (cached by its state)."""
    import json
    rc = slip(json.loads(card_json), seed, state)
    w0, h0 = rc.size
    big = Image.new("RGBA", (w0 + 2 * PAD, h0 + 2 * PAD), (0, 0, 0, 0))
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    a = rc.getchannel("A").point(lambda v: int(v * 0.75))
    sh.paste(Image.new("RGBA", rc.size, (0, 0, 0, 255)), (PAD + 6, PAD + 16), a)
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    big.alpha_composite(sh)
    big.alpha_composite(rc, (PAD, PAD))
    if scale != 1.0:
        big = big.resize((int(big.width * scale), int(big.height * scale)), Image.LANCZOS)
    return big.rotate(angle, resample=Image.BICUBIC, expand=True)


def sprite_boxes(card, seed, state, angle, scale, x, y):
    """The slip's text boxes in frame coordinates (each box's corners through the same pad, scale and rotation)."""
    boxes = []
    rc = slip(card, seed, state, boxes)
    w0, h0 = rc.size
    size = (int((w0 + 2 * PAD) * scale), int((h0 + 2 * PAD) * scale))
    a = math.radians(angle)
    ew = int(math.ceil(abs(size[0] * math.cos(a)) + abs(size[1] * math.sin(a))))
    eh = int(math.ceil(abs(size[0] * math.sin(a)) + abs(size[1] * math.cos(a))))
    out = []
    for txt, (bx, by, bw, bh), role, col in boxes:
        pts = [L.rotate_point((px + PAD) * scale, (py + PAD) * scale, size, angle, (ew, eh))
               for px, py in ((bx, by), (bx + bw, by), (bx, by + bh), (bx + bw, by + bh))]
        xs, ys = [p[0] + x for p in pts], [p[1] + y for p in pts]
        out.append((txt, (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), role, col))
    return out


def land(t, t0):
    k = L.ease_out(L.ramp(t, t0, t0 + LAND), 3)
    return (1 - k) * -26, round(1.03 - 0.03 * k, 3)


# ----------------------------------------------------------------------------------------------- the renderer
class Piece:
    def __init__(self, ctx):
        self.ctx = ctx
        sp = ctx.spec
        self.W, self.H, self.fps = ctx.w, ctx.h, ctx.fps
        self.tail = float(sp.get("tail", TAIL))
        self.total_s = ctx.duration + self.tail
        self.N = int(math.ceil(self.total_s * self.fps))
        self.open_end, self.then_at, self.then_end, self.now_at = plan_times(sp, ctx.words, ctx.duration)
        self.then, self.now = sp["then"], sp["now"]
        self.op = sp.get("opening") or {}
        at = ctx.at
        # a row anchored before its card types on as the card lands
        self.then_rows = [max(self.then_at, at(r["at"], f"then.rows[{j}].at")) if "at" in r else self.then_at
                          for j, r in enumerate(self.then.get("rows") or [])]
        self.now_rows = [max(self.now_at, at(r["at"], f"now.rows[{j}].at")) if "at" in r else self.now_at
                         for j, r in enumerate(self.now.get("rows") or [])]
        self.then_total = at(self.then["total_at"], "then.total_at") if "total_at" in self.then else self.then_at
        self.now_total = at(self.now["total_at"], "now.total_at") if "total_at" in self.now else self.now_at
        h = self.now.get("hand")
        self.hand_at = at(h["at"], "now.hand.at") if h else None
        kw = sp.get("keyword")
        self.kw = kw
        self.kw_at = at(kw["at"], "keyword.at") if kw else None
        self.kw_trail_at = (at(kw["trail_at"], "keyword.trail_at") if kw and "trail_at" in kw else self.kw_at)
        c = ctx.brand["colors"]
        self.col = {k: brand.rgb_of(v) for k, v in c.items()}
        self.captions = self.plan_captions()

    # ---------------------------------------------------------------- sections
    def section(self, t):
        if t < self.open_end:
            return "opening"
        if self.then_at <= t < self.then_end:
            return "then"
        if t >= self.now_at:
            return "now"
        return "face"

    def section_span(self, t):
        s = self.section(t)
        if s == "opening":
            return 0.0, self.open_end
        if s == "then":
            return self.then_at, self.then_end
        if s == "now":
            return self.now_at, self.total_s
        lo = self.then_end if t >= self.then_end else self.open_end
        hi = self.now_at if t >= self.then_end else self.then_at
        return lo, hi

    def caption_stop(self, t0, t1):
        """Captions in a section stop where the keyword (on camera) or the handwritten line (second card) starts."""
        for x in (self.kw_at, self.hand_at):
            if x is not None and t0 <= x < t1:
                t1 = x
        return t1

    def plan_captions(self):
        """[(t0, t1, text, on_card)]. From the spec's captions, else two words at a time from his words."""
        ctx = self.ctx
        out = []
        spec_caps = ctx.spec.get("captions")
        if spec_caps:
            starts = [ctx.at(c["at"], f"captions[{k}].at") for k, c in enumerate(spec_caps)]
            for k, c in enumerate(spec_caps):
                t0 = starts[k]
                lo, hi = self.section_span(t0 + 1e-4)
                t1 = self.caption_stop(lo, hi)
                if k + 1 < len(starts):
                    t1 = min(t1, starts[k + 1])
                if "until" in c:
                    t1 = min(t1, ctx.at(c["until"], f"captions[{k}].until"))
                if t1 > t0:
                    out.append((t0, t1, c["text"].upper(), self.section(t0 + 1e-4) in ("then", "now")))
            return out
        groups, cur = [], []
        for w in ctx.words:
            sec = self.section_span(w["t0"] + 1e-4)
            stop = self.caption_stop(*sec)
            if w["t0"] >= stop:
                if cur:
                    groups.append(cur)
                    cur = []
                continue
            if cur and self.section_span(cur[0]["t0"] + 1e-4) != sec:
                groups.append(cur)
                cur = []
            cur.append(w)
            if w["w"][-1:] in ".,?!;:":
                groups.append(cur)
                cur = []
            elif len(cur) >= 2:
                if cur[-1]["w"].lower() in LEADING:      # "BECAUSE THE" reads badly: carry "the" to the next pair
                    groups.append(cur[:-1])
                    cur = cur[-1:]
                else:
                    groups.append(cur)
                    cur = []
        if cur:
            groups.append(cur)
        span = lambda g: self.section_span(g[0]["t0"] + 1e-4)       # noqa: E731
        k = 0
        while k < len(groups):          # a lone small word left at a section's end joins the pair before it
            g = groups[k]
            last = k + 1 == len(groups) or span(groups[k + 1]) != span(g)
            if last and len(g) == 1 and g[0]["w"].lower().strip(".,?!;:") in LEADING and k > 0 \
                    and span(groups[k - 1]) == span(g) and len(groups[k - 1]) < 3:
                groups[k - 1] = groups[k - 1] + g
                del groups[k]
                continue
            k += 1
        for k, g in enumerate(groups):
            lo, hi = self.section_span(g[0]["t0"] + 1e-4)
            first = k == 0 or span(groups[k - 1]) != (lo, hi)
            t0 = lo if first and g[0]["t0"] - lo < 0.2 else g[0]["t0"]
            t1 = self.caption_stop(lo, hi)
            if k + 1 < len(groups):
                nxt = groups[k + 1][0]["t0"]
                nlo, nhi = self.section_span(nxt + 1e-4)
                t1 = min(t1, nlo if (nlo, nhi) != (lo, hi) else nxt)
            text = " ".join(w["w"] for w in g).upper().rstrip(",;:")
            out.append((t0, t1, text, self.section(t0 + 1e-4) in ("then", "now")))
        return out

    def caption_at(self, t, on_card):
        for t0, t1, txt, card in self.captions:
            if t0 <= t < t1 and card == on_card:
                return txt
        return None

    # ---------------------------------------------------------------- pictures
    def open_readers(self):
        ctx = self.ctx
        W, H = self.W, self.H
        size = ctx.passage.get("size") or [1920, 1080]
        sw, sh = float(size[0]), float(size[1])
        fc = ctx.spec.get("face") or {}
        zoom = float(fc.get("zoom", 1.4))
        s = max(zoom * 1080 / sh, W / sw)
        pw, ph = int(round(sw * s / 2) * 2), int(round(sh * s / 2) * 2)
        self.face_top = int(fc.get("top", 440))
        vis = max(2, min(ph, H - self.face_top))
        x = int(round(min(max(0.0, float(fc.get("x", 0.5)) * pw - W / 2), pw - W)))
        self.face_h = vis
        self.face = Reader(ctx.picture(), (W, vis), self.fps,
                           vf=f"scale={pw}:{ph}:flags=lanczos,crop={W}:{vis}:{x}:0,{IN709}")
        self.ramp = np.clip(np.arange(vis) / 140.0, 0, 1)[:, None, None].astype(np.float32)
        self.screen = None
        scr = self.op.get("screen")
        if scr:
            src = ctx.source(scr.get("source", "screen"))
            if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".heic"):
                im = Image.open(src).convert("RGB")
                self.screen_still = self._fill(im, float(scr.get("x", 0.5)))
            else:
                from studio_engine.util import probe
                v = probe(src)["video"] or {}
                if not v:
                    raise StudioError("The opening screen source has no picture.")
                vw, vh = v["w"], v["h"]
                cw = min(vw, int(round(vh * W / H / 2) * 2))
                cx = int(round(min(max(0.0, float(scr.get("x", 0.5)) * vw - cw / 2), vw - cw)))
                self.screen_in = float(scr.get("in", 0.0))
                self.screen = Reader(src, (W, H), self.fps,
                                     vf=f"crop={cw}:{vh}:{cx}:0,scale={W}:{H}:flags=lanczos,{IN709}")
                self.screen_still = None
        else:
            self.screen_still = None

    def _fill(self, im, xfrac):
        W, H = self.W, self.H
        s = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
        x = int(min(max(0, xfrac * im.width - W / 2), im.width - W))
        return np.asarray(im.crop((x, 0, x + W, H)))

    def face_frame(self, i):
        W, H = self.W, self.H
        t = min(i / self.fps, self.ctx.duration - 0.5 / self.fps)
        src = L.to_f(self.face.get(int(round(t * self.fps))))
        f = np.full((H, W, 3), 0.012, np.float32)
        f[self.face_top:self.face_top + self.face_h] = src * self.ramp + 0.012 * (1 - self.ramp)
        f = L.grade_film(f, lift_amt=0.03, contrast=1.06, sat=0.9, warm=0.05)
        f = L.halation(f, 0.7, 16, 0.28)
        return f * L.vignette(W, H, 0.28)

    def screen_frame(self, i):
        """His screen, full bleed for the opening: a slow 3.5 percent push, graded down, the top dark and defocused so
        the claim reads, a darker band where the captions sit."""
        import cv2
        W, H = self.W, self.H
        t = i / self.fps
        if self.screen_still is not None:
            f = L.to_f(self.screen_still)
        else:
            f = L.to_f(self.screen.get(int(round((self.screen_in + t) * self.fps))))
        k = t / max(self.open_end, 1e-3)
        z = 1.0 + 0.035 * L.ease_in_out(k)
        if z > 1.001:
            M = np.float32([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H * 0.42]])
            f = cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        f = L.grade_film(np.clip(f, 0, 1) ** 1.25 * 0.86, lift_amt=0.02, contrast=1.04, sat=0.85, warm=0.02)
        band = np.exp(-((np.arange(H) - (CAP_Y + 15)) / 170.0) ** 2)[:, None, None].astype(np.float32)
        top = np.clip(1 - (np.arange(H) - 600) / 220.0, 0, 1)[:, None, None].astype(np.float32)
        top = top * top * (3 - 2 * top)
        f = f * (1 - top) + cv2.GaussianBlur(f, (0, 0), 14) * 0.2 * top
        return f * (1 - 0.45 * band) * L.vignette(W, H, 0.4)

    # ---------------------------------------------------------------- layers
    @lru_cache(maxsize=None)
    def ground(self):
        """The kit's dark card: a soft radial ground with paper fibre and corner ticks."""
        W, H = self.W, self.H
        rng = np.random.default_rng(16)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        base = 16.5 - 4.5 * np.clip(r / 1.3, 0, 1) ** 2
        fib = rng.normal(0, 1, (H // 3, W // 48)).astype(np.float32)
        fib = np.asarray(Image.fromarray(fib).resize((W, H), Image.BICUBIC)) * 0.9
        v = np.clip(base + fib, 0, 255)
        g = np.dstack([v, v, v * 1.02]).astype(np.float32) / 255
        im = Image.fromarray(L.to_u8(g)).convert("RGBA")
        d = ImageDraw.Draw(im)
        arm, th, col = 34, 2, (88, 88, 88, 255)
        for x, y, sx, sy in ((60, 120, 1, 1), (W - 60, 120, -1, 1), (60, 1640, 1, -1), (W - 60, 1640, -1, -1)):
            d.rectangle([min(x, x + sx * arm), min(y, y + sy * th), max(x, x + sx * arm), max(y, y + sy * th)], fill=col)
            d.rectangle([min(x, x + sx * th), min(y, y + sy * arm), max(x, x + sx * th), max(y, y + sy * arm)], fill=col)
        return im

    @lru_cache(maxsize=None)
    def card_head(self, fig, title):
        im = self.ground().copy()
        d = ImageDraw.Draw(im)
        L.draw_text(d, (112, 268), fig, brand.font("archive", 34), self.col["muted"] + (255,), 0.16)
        d.text((104, 420), title, font=brand.font("display", 168), fill=self.col["warm_white"] + (255,), anchor="ls")
        return im

    def claim_geom(self):
        s = float(self.op.get("scale", 1.0))
        size = int(CLAIM_SIZE * s)
        base = CLAIM_Y + (size - CLAIM_SIZE) * 0.7
        f = brand.font("display", size)
        fig = self.op.get("figure", "")
        x0 = (self.W - f.getlength(fig)) / 2
        return f, fig, x0, base

    @lru_cache(maxsize=None)
    def claim_layer(self):
        """The claim, there from the first frame: kicker, the figure with the red brush under it, the trail."""
        W, H = self.W, self.H
        lay, d = L.text_layer((W, H))
        if self.op.get("kicker", True):
            L.draw_text(d, (W / 2, KICKER_Y), "THE RECEIPTS", brand.font("archive", 36), self.col["zen"] + (220,),
                        0.3, "ms")
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

    @lru_cache(maxsize=None)
    def caption_layer(self, txt):
        lay, d = L.text_layer((self.W, self.H))
        f = L.fit("caption", brand.caption_px(CAP_SIZE, self.ctx.brand), txt, self.W - 2 * SIDE - 40, 0.02)
        L.draw_text(d, (self.W / 2, CAP_Y + L.cap_h(f) / 2), txt, f, self.col["zen"] + (255,), 0.02, "ms")
        return L.shadow_of(lay, 9, 0.7, 3)

    def caption_box(self, txt):
        f = L.fit("caption", brand.caption_px(CAP_SIZE, self.ctx.brand), txt, self.W - 2 * SIDE - 40, 0.02)
        return text_box(f, txt, self.W / 2, CAP_Y + L.cap_h(f) / 2, "ms", 0.02)

    @lru_cache(maxsize=None)
    def cardcap_layer(self, txt):
        lay, d = L.text_layer((self.W, self.H))
        f, (x0, y0, x1, y1), base = self.cardcap_geom(txt)
        d.rectangle([x0, y0, x1, y1], fill=self.col["cream"] + (255,))
        L.draw_text(d, (self.W / 2, base), txt, f, self.col["obsidian"] + (255,), 0.02, "ms")
        return lay

    def cardcap_geom(self, txt):
        f = L.fit("caption", brand.caption_px(CARD_CAP_SIZE, self.ctx.brand), txt, self.W - 2 * SIDE - 80, 0.02)
        wd, ch = L.tw(txt, f, 0.02), L.cap_h(f)
        y = CARD_CAP_Y
        return f, (self.W / 2 - wd / 2 - 26, y - ch / 2 - 20, self.W / 2 + wd / 2 + 26, y + ch / 2 + 22), y + ch / 2

    @lru_cache(maxsize=None)
    def keyword_layer(self, trail_on):
        lay, d = L.text_layer((self.W, self.H))
        d.text((self.W / 2, 1250), self.kw["text"], font=brand.font("display", KEYWORD_SIZE),
               fill=self.col["red_on_footage"] + (255,), anchor="ms")
        if trail_on and self.kw.get("trail"):
            L.draw_text(d, (self.W / 2, 1340), self.kw["trail"], brand.font("caption", 58), self.col["zen"] + (255,),
                        0.02, "ms")
        return L.shadow_of(L.shadow_of(lay, 28, 0.55, 0), 8, 0.8, 3)

    # ---------------------------------------------------------------- slips over time
    def then_state(self, t, struck=False):
        rows = self.then.get("rows") or []
        n = tuple(min(len(r["text"]), max(0, int((t - a) / TYPE_STEP))) if t >= a else 0
                  for r, a in zip(rows, self.then_rows))
        if struck:
            n = tuple(len(r["text"]) for r in rows)
        show = t >= self.then_total or struck
        return (n, show, show and not struck, struck, 0)

    def now_state(self, t):
        rows = self.now.get("rows") or []
        n = tuple(min(len(r["text"]), max(0, int((t - a) / TYPE_STEP))) if t >= a else 0
                  for r, a in zip(rows, self.now_rows))
        show = t >= self.now_total
        hand_n = 0
        if self.hand_at is not None and t >= self.hand_at:
            k = L.clamp((t - self.hand_at) / HAND_TIME)
            txt = self.now["hand"]["text"]
            hand_n = len(txt) if k >= 1 else int(len(txt) * L.ease_out(k, 2))
        red = show and not (self.hand_at is not None and t >= self.hand_at)
        return (n, show, red, False, hand_n)

    def _card_json(self, card):
        import json
        return json.dumps(card, sort_keys=True)

    def then_pos(self, sp, dy):
        return (self.W - sp.width) / 2, 470 + dy

    def now_pos(self, sp, dy):
        x = (self.W - sp.width) / 2 + 70
        return min(x, self.W - sp.width + 40), 500 + dy

    def card_frame(self, t, i):
        if t < self.then_end:
            im = self.card_head("FIG. 01", "Then.").copy()
            dy, sc = land(t, self.then_at)
            sp = sprite("then", self._card_json(self.then), 11, self.then_state(t), 2.0, sc)
            L.paste(im, sp, *self.then_pos(sp, dy))
        else:
            im = self.card_head("FIG. 02", "Now.").copy()
            old = sprite("then", self._card_json(self.then), 11, self.then_state(t, struck=True), 7.0, 0.74)
            L.paste(im, L.set_alpha(old, 0.72), -40, 610)
            dy, sc = land(t, self.now_at)
            sp = sprite("now", self._card_json(self.now), 23, self.now_state(t), -2.5, sc)
            L.paste(im, sp, *self.now_pos(sp, dy))
        cc = self.caption_at(t, True)
        if cc:
            im.alpha_composite(self.cardcap_layer(cc))
        return L.to_f(np.asarray(im.convert("RGB")))

    def frame(self, i):
        t = i / self.fps
        sec = self.section(t)
        if sec in ("then", "now"):
            f = self.card_frame(t, i)
        else:
            on_screen = sec == "opening" and (self.screen is not None or self.screen_still is not None)
            f = self.screen_frame(i) if on_screen else self.face_frame(i)
            lay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            if sec == "opening":
                lay.alpha_composite(self.claim_layer())
            if self.kw_at is not None and sec == "face" and t >= self.kw_at and \
                    self.section_span(t) == self.section_span(self.kw_at + 1e-4):
                lay.alpha_composite(self.keyword_layer(t >= self.kw_trail_at))
            else:
                c = self.caption_at(t, False)
                if c:
                    lay.alpha_composite(self.caption_layer(c))
            f = L.over(f, lay)
        grain = float((self.ctx.spec.get("finish") or {}).get("grain", GRAIN))
        return L.to_u8(L.grain(f, i, grain))

    # ---------------------------------------------------------------- the layout record
    def record(self):
        lay = self.ctx.layout
        W = self.W
        hexs = self.ctx.brand["colors"]
        b = lay.beat("opening", 0.0, self.open_end)
        if self.op.get("kicker", True):
            f = brand.font("archive", 36)
            lay.text(b, "THE RECEIPTS", text_box(f, "THE RECEIPTS", W / 2, KICKER_Y, "ms", 0.3), role="label",
                     color=hexs["zen"])
        f, fig, x0, base = self.claim_geom()
        if fig:
            lay.text(b, fig, text_box(f, fig, x0, base, "ls"), color=hexs["warm_white"])
            bw = f.getlength(fig) * 1.08
            br = L.brush_draw("red-a", bw, 0.5, -1.2)
            lay.mark(b, "brush under the figure", (x0 - 22, base + 8, br.width, br.height), red=True, color=hexs["red"])
        if self.op.get("trail"):
            ft = brand.font("body", 54)
            lay.text(b, self.op["trail"], text_box(ft, self.op["trail"], W / 2, base + TRAIL_GAP, "ms"),
                     color=hexs["zen"])
        for t0, t1, txt, card in self.captions:
            cb = lay.beat("card caption" if card else "caption", t0, t1)
            if card:
                f, _, basey = self.cardcap_geom(txt)
                lay.text(cb, txt, text_box(f, txt, W / 2, basey, "ms", 0.02), color=hexs["obsidian"])
            else:
                lay.text(cb, txt, self.caption_box(txt), color=hexs["zen"])
        if self.kw:
            lo, hi = self.section_span(self.kw_at + 1e-4)
            kb = lay.beat("keyword", self.kw_at, hi)
            fk = brand.font("display", KEYWORD_SIZE)
            lay.text(kb, self.kw["text"], text_box(fk, self.kw["text"], W / 2, 1250, "ms"), color=hexs["red_on_footage"])
            if self.kw.get("trail"):
                ft = brand.font("caption", 58)
                lay.text(kb, self.kw["trail"], text_box(ft, self.kw["trail"], W / 2, 1340, "ms", 0.02), color=hexs["zen"])

        def head(beat, fig, title):
            fa = brand.font("archive", 34)
            lay.text(beat, fig, text_box(fa, fig, 112, 268, "ls", 0.16), role="label", color=hexs["muted"])
            lay.text(beat, title, text_box(brand.font("display", 168), title, 104, 420, "ls"), role="label",
                     color=hexs["warm_white"])

        def slip_texts(beat, card, seed, state, angle, pos):
            sp = sprite("x", self._card_json(card), seed, state, angle, 1.0)
            x, y = pos(sp, 0)
            for txt, box, role, col in sprite_boxes(card, seed, state, angle, 1.0, x, y):
                hx = "#%02X%02X%02X" % tuple(col)
                lay.text(beat, txt, box, role=role, color=hx)

        b1 = lay.beat("card", self.then_at, self.then_end)
        head(b1, "FIG. 01", "Then.")
        end_t = self.then_end - 1e-3
        slip_texts(b1, self.then, 11, self.then_state(max(end_t, self.then_total)), 2.0, self.then_pos)
        cuts = [self.now_at] + ([self.hand_at] if self.hand_at is not None else []) + [self.total_s]
        for k in range(len(cuts) - 1):
            b2 = lay.beat("card", cuts[k], cuts[k + 1])
            head(b2, "FIG. 02", "Now.")
            lay.mark(b2, "the first receipt, greyed and struck, running off the left edge on purpose",
                     (-40, 610, 600, 760), red=False)
            st = self.now_state(max(cuts[k + 1] - 1e-3, self.now_total) if k == 0 else self.total_s)
            if k == 0 and self.hand_at is not None:
                st = (st[0], st[1], st[1], False, 0)
            slip_texts(b2, self.now, 23, st, -2.5, self.now_pos)

    # ---------------------------------------------------------------- sound
    def effects(self):
        spec_fx = self.ctx.spec.get("effects", True)
        if spec_fx is False:
            return []
        softer = float(spec_fx.get("softer_db", 0)) if isinstance(spec_fx, dict) else 0.0
        out = []

        def add(name, t, extra=None):
            e = {"name": name, "t": max(0.0, t), "under_db": FX[name] + softer}
            e.update(extra or {})
            out.append(e)
        add("pop", 0.0)
        for t in (self.then_at, self.now_at):
            add("paper", t - 0.04, {"len": 0.6})
        for rows, ats in ((self.then.get("rows") or [], self.then_rows), (self.now.get("rows") or [], self.now_rows)):
            for r, a in zip(rows, ats):
                for j in range(3):
                    add("key", a + j * 0.06)
        if self.kw_at is not None:
            add("pop", self.kw_at)
            add("thud", self.kw_at)
        if self.hand_at is not None:
            add("marker", self.hand_at, {"len": 0.5})
        return out


def render(ctx):
    pc = Piece(ctx)
    pc.open_readers()
    ctx.say("Drawing the receipts.")
    pic = ctx.work / "picture.mp4"
    with heavy.lock("receipts frames"):
        enc = Encoder(pic, ctx.w, ctx.h, ctx.fps, crf=15)
        for i in range(pc.N):
            enc.write(pc.frame(i))
        enc.close()
    pc.face.close()
    if pc.screen is not None:
        pc.screen.close()

    ctx.say("Mixing the sound.")
    sound = dict(ctx.spec.get("sound") or {})
    if "bed" not in sound:
        sound["bed"] = dict(BED, changes=[{"t": pc.now_at}])
    ctx.spec = dict(ctx.spec, sound=sound)
    levels = ctx.sound(extra_sfx=pc.effects(), duration=pc.total_s)
    pc.record()
    mux(pic, ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels, "keep_work": bool(os.environ.get("STUDIO_KEEP_WORK"))}
