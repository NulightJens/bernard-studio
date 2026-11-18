"""Zen garden: one continuous overhead take over black raked sand under a single low, warm key light.

Three beats, driven by his words:
  feed    the camera flicks down a column of identical ringed stones, like a feed, and rests on one; the light can
          find the stone above it and the stone below it;
  stones  the scroll carries on to a few stones that are each different, and a rake draws rings round each one as he
          names it;
  rise    between them the sand heaves and one red stone comes up through it, sand falling off, and the rake rings it.
          It is the only red in the film.
His lines sit as captions, one phrase at a time, above the bottom of the frame.

The sand is a height field (rake profile, rings that follow each stone's outline) shaded from straight overhead: a
raking key with cast shadows from a horizon march, ambient occlusion, grain albedo and glints, then lens and film.
Everything is code; nothing is generated. See SPEC.md for the settings.
"""
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

from studio_engine import brand, heavy
from studio_engine import sound as snd
from studio_engine.errors import StudioError
from studio_engine.render import Encoder, draw_frames, mux, poster
from studio_engine.words import find_phrase, phrase_tokens, plain

KIND = "animated"
LABELS = []                     # every word on screen is his

RS = 1.25                       # supersampling of the height field
SP = 30.0                       # rake tooth spacing (world px)
DEPTH = 6.5                     # groove depth (world px)
COLLAR = 22.0                   # flat-ish collar round each stone
STEP = 640.0                    # feed spacing
CL = 6 * STEP + 700.0           # centre of the cluster of different stones
CAP_SIZE = 104                  # caption type size (px), the kit's italic serif at weight 700
CAP_MAXW = 1080 - 2 * 110       # captions wrap into balanced lines no wider than this
CAP_BOTTOM = 1585               # the last caption line ends here, above the bottom 300 px
CAP_LINES = 3

FEED_STONE = dict(rx=150, ry=112, rot=0.18, harm=[(2, 0.03, 0.4), (3, 0.02, 1.7), (5, 0.012, 0.2)], h=62, rings=4,
                  seed=0)
_LOVE = [
    dict(x=-250, y=-330, rx=120, ry=70, rot=-0.5, harm=[(2, 0.12, 0.3), (3, 0.08, 2.0)], h=48, rings=5, seed=11),
    dict(x=270, y=-120, rx=92, ry=92, rot=0.0, harm=[(3, 0.10, 0.9), (4, 0.04, 0.1)], h=70, rings=5, seed=12),
    dict(x=-150, y=330, rx=165, ry=58, rot=0.35, harm=[(2, 0.08, 1.1), (5, 0.04, 0.6)], h=40, rings=5, seed=13),
    dict(x=300, y=360, rx=104, ry=76, rot=-0.2, harm=[(2, 0.07, 0.8), (3, 0.05, 2.4)], h=52, rings=5, seed=14),
]
# which of the stones above make the cluster for one to four rings (three is the first piece's garden)
_ARRANGE = {1: [1], 2: [0, 2], 3: [0, 1, 2], 4: [0, 1, 2, 3]}
_RED = dict(x=40.0, y=40.0, rx=86, ry=74, rot=0.6, harm=[(2, 0.05, 0.2), (3, 0.06, 1.3)], h=58, rings=6, seed=21)

# light and lens
ELEV = np.radians(17.0)
TANE = np.tan(ELEV)
LDIR = np.array([0.0, -np.cos(ELEV), np.sin(ELEV)], np.float32)     # towards the light: top of frame, low
HV = (LDIR + np.array([0, 0, 1.0], np.float32)).astype(np.float32)
HV /= np.linalg.norm(HV)


# ----------------------------------------------------------------------------------------------- easing
def ease(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def ease_io(t, p=3.0):
    t = np.clip(t, 0, 1)
    return np.where(t < 0.5, 0.5 * (2 * t) ** p, 1 - 0.5 * (2 * (1 - t)) ** p)


def ease_out(t, p=3.0):
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** p


# ----------------------------------------------------------------------------------------------- textures
def tile_noise(n, k0, k1, seed, power=1.0):
    """periodic band-limited noise (n x n), unit variance"""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    ky = np.fft.fftfreq(n)[:, None] * n
    kx = np.fft.fftfreq(n)[None, :] * n
    k = np.sqrt(kx ** 2 + ky ** 2)
    m = ((k >= k0) & (k <= k1)).astype(np.float64) / np.maximum(k, 1) ** power
    x = np.real(np.fft.ifft2(f * m)).astype(np.float32)
    return x / x.std()


TN = 1024
_TEX = {}
_TEX_LOCK = threading.Lock()


def textures():
    with _TEX_LOCK:
        if not _TEX:
            _TEX["grain"] = tile_noise(TN, 180, 512, 1, 0.0)     # sand grains (~1.5 px)
            _TEX["fine"] = tile_noise(TN, 40, 160, 2, 0.5)       # clumps
            _TEX["mid"] = tile_noise(TN, 4, 24, 3, 1.0)          # slow wander of the rake
            _TEX["rock"] = tile_noise(TN, 10, 90, 4, 1.2)        # stone surface
            r = np.random.default_rng(5)
            spark = (r.random((TN, TN)) > 0.9965).astype(np.float32)
            _TEX["spark"] = cv2.GaussianBlur(spark, (0, 0), 0.6) * 4
    return _TEX


class Sampler:
    """Samples the periodic textures at the world coordinates of one frame. X and Y are axis-aligned grids, so the
    lookup maps are built from their first row and column, once per scale (and x shift) for this frame."""

    def __init__(self, X, Y):
        self.x, self.y, self.shape, self.maps = X[0], Y[:, 0], X.shape, {}

    def __call__(self, name, scale, dx=0):
        key = (scale, dx)
        if key not in self.maps:
            u = (((self.x + dx) / scale) % TN).astype(np.float32)
            v = ((self.y / scale) % TN).astype(np.float32)
            self.maps[key] = (np.ascontiguousarray(np.broadcast_to(u[None, :], self.shape)),
                              np.ascontiguousarray(np.broadcast_to(v[:, None], self.shape)))
        mu, mv = self.maps[key]
        return cv2.remap(_TEX[name], mu, mv, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


# ----------------------------------------------------------------------------------------------- stones
def boundary(st, th):
    """boundary radius of the stone's footprint in direction th (world)"""
    a = th - st["rot"]
    r = 1.0 / np.sqrt((np.cos(a) / st["rx"]) ** 2 + (np.sin(a) / st["ry"]) ** 2)
    m = 1.0
    for k, amp, ph in st["harm"]:
        m = m + amp * np.cos(k * a + ph)
    return r * m


def reach(st):
    return max(st["rx"], st["ry"]) * (1 + sum(a for _, a, _ in st["harm"]))


def stone_fields(st, X, Y, margin=None):
    """(d, u) for the stone over the grid; computed only inside its bounding box"""
    if margin is None:
        margin = COLLAR + st["rings"] * SP + 60
    rmax = reach(st) + margin
    xs, ys = X[0], Y[:, 0]
    c0, c1 = np.searchsorted(xs, st["x"] - rmax), np.searchsorted(xs, st["x"] + rmax)
    r0, r1 = np.searchsorted(ys, st["y"] - rmax), np.searchsorted(ys, st["y"] + rmax)
    d = np.full(X.shape, 1e9, np.float32)
    u = np.ones(X.shape, np.float32)
    if c1 <= c0 or r1 <= r0:
        return d, u
    dx = (xs[c0:c1] - st["x"])[None, :]
    dy = (ys[r0:r1] - st["y"])[:, None]
    r = np.sqrt(dx * dx + dy * dy)
    th = np.arctan2(dy, dx)
    R = boundary(st, th)
    d[r0:r1, c0:c1] = r - R
    u[r0:r1, c0:c1] = np.clip(r / np.maximum(R, 1), 0, 1)
    return d, u


def rake_profile(phase):
    """rounded ridges, slightly flattened tops, sharper troughs (a wooden rake's tooth marks)"""
    c = np.cos(2 * np.pi * phase)
    return 0.5 + 0.5 * np.sign(c) * np.abs(c) ** 0.8


# ----------------------------------------------------------------------------------------------- the plan
_FIELDS = {"feed": {"kind", "flick", "land", "light", "go"}, "stones": {"kind", "arrive", "rings"},
           "rise": {"kind", "at", "up", "ring"}}
_NEEDS = {"feed": ["flick"], "stones": ["rings"], "rise": ["up"]}


def _beats(spec):
    out = {}
    for k, b in enumerate(spec.get("beats") or []):
        kind = b.get("kind")
        if kind not in ("feed", "stones", "rise"):
            raise StudioError(f'beats[{k}].kind is "{kind}". The zen garden has three beats: feed, stones and rise.')
        if kind in out:
            raise StudioError(f'beats[{k}] is a second "{kind}" beat. Each beat can come once.')
        extra = sorted(set(b) - _FIELDS[kind])
        if extra:
            raise StudioError(f'beats[{k}] is a {kind} beat, which has no "{extra[0]}". A {kind} beat takes: '
                              f'{", ".join(sorted(_FIELDS[kind] - {"kind"}))}.')
        for need in _NEEDS[kind]:
            if need not in b:
                raise StudioError(f'beats[{k}] is a {kind} beat and needs "{need}" (a word number).')
        out[kind] = (k, b)
    order = [k for k in ("feed", "stones", "rise") if k in out]
    if [out[k][0] for k in order] != sorted(out[k][0] for k in order):
        raise StudioError("The beats must come in this order: feed (if any), then stones (if any), then rise.")
    if "rise" not in out:
        raise StudioError('The zen garden needs a "rise" beat: the red stone coming up is the end of every piece.')
    return {k: b for k, (_, b) in out.items()}, {k: i for k, (i, _) in out.items()}


def _caption_tokens(text):
    out = []
    for p in str(text).split():
        out += plain(p)
    return out


def validate(spec, words, duration):
    from studio_engine.layout import resolve_at
    beats, idx = _beats(spec)
    have = set()
    for w in words:
        have.update(plain(w["w"]))
    caps = spec.get("captions") or []
    if not caps:
        raise StudioError("The zen garden needs captions: his lines, one phrase each, in the order he says them.")
    after = 0
    for k, c in enumerate(caps):
        txt = c.get("text", "")
        if not _caption_tokens(txt):
            raise StudioError(f"captions[{k}] has no words in it.")
        extra = [t for t in phrase_tokens(txt) if t not in have]
        if extra:
            raise StudioError(f'captions[{k}] says "{txt}", but he never says "{" ".join(extra)}" in this passage. '
                              "Use only his words.")
        if "at" in c:
            resolve_at(c["at"], words, duration, field=f"captions[{k}].at")
            continue
        try:
            i0, i1 = find_phrase(words, txt, after)
        except StudioError:
            raise StudioError(f'captions[{k}] "{txt}" is not found after the caption before it. Captions follow '
                              "his words in order.")
        after = i1 + 1
        if len(_wrap(txt)) > CAP_LINES:
            raise StudioError(f'captions[{k}] "{txt}" is too long for the screen. Split it into two captions.')
    rings = (beats.get("stones") or {}).get("rings") or []
    if "stones" in beats and not 1 <= len(rings) <= 4:
        raise StudioError("The stones beat rings one to four stones: give it one to four words in rings.")
    for b in ("feed",):
        if b in beats:
            for j, ln in enumerate(beats[b].get("light") or []):
                if ln.get("to") not in ("above", "below", "here"):
                    raise StudioError(f'beats[{idx[b]}].light[{j}].to must be "above", "below" or "here".')
    plan = Plan(lambda x, f="at": resolve_at(x, words, duration, f), spec, words, duration, 30.0)
    plan.check()


_CAP_FONT = {}


def cap_size():
    """The caption size after his caption size setting (CAP_SIZE at the default)."""
    return brand.caption_px(CAP_SIZE)


def cap_font():
    size = cap_size()
    if size not in _CAP_FONT:
        _CAP_FONT[size] = brand.font("display", size)
    return _CAP_FONT[size]


def text_layer(txt, fnt, track=0.0, pad=40):
    """Text as a float alpha mask (H, W), tight around the ink."""
    size = fnt.size
    widths = [fnt.getlength(ch) for ch in txt]
    total = sum(widths) + track * size * (len(txt) - 1)
    asc, desc = fnt.getmetrics()
    img = Image.new("L", (int(total + 2 * pad), int(asc + desc + 2 * pad)), 0)
    d = ImageDraw.Draw(img)
    x = pad
    for ch, w in zip(txt, widths):
        d.text((x, pad), ch, font=fnt, fill=255)
        x += w + track * size
    a = np.asarray(img).astype(np.float32) / 255.0
    ys, xs = np.nonzero(a > 0.002)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = 4
    return a[max(0, y0 - m):y1 + m, max(0, x0 - m):x1 + m]


def _wrap(txt):
    """a phrase split into the fewest balanced lines (up to four tried) that each fit CAP_MAXW"""
    words = txt.split()
    f = cap_font()
    for k in range(1, 5):
        lines, cur = [], []
        target = len(txt) / k
        for w in words:
            if cur and len(" ".join(cur + [w])) > target + 3 and len(lines) < k - 1:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                cur.append(w)
        lines.append(" ".join(cur))
        if max(f.getlength(ln) for ln in lines) <= CAP_MAXW - 8:
            masks = [text_layer(ln, f) for ln in lines]
            if max(m.shape[1] for m in masks) <= CAP_MAXW:
                return lines
    return lines + ["", "", "", ""]


def cap_block(txt):
    """the phrase's balanced lines stacked into one mask"""
    f = cap_font()
    masks = [text_layer(ln, f) for ln in _wrap(txt)]
    lh = int(f.size * 1.02)
    H_ = lh * (len(masks) - 1) + max(m.shape[0] for m in masks)
    W_ = max(m.shape[1] for m in masks)
    out = np.zeros((H_, W_), np.float32)
    for i, m in enumerate(masks):
        x = (W_ - m.shape[1]) // 2
        sl = out[i * lh:i * lh + m.shape[0], x:x + m.shape[1]]
        out[i * lh:i * lh + m.shape[0], x:x + m.shape[1]] = np.maximum(sl, m)
    return out


class Plan:
    """Every time and place the frames need, worked out once from the spec and his words."""

    def __init__(self, at, spec, words, duration, fps):
        self.spec, self.words, self.fps = spec, words, fps
        beats, _ = _beats(spec)
        feed, stones, rise = beats.get("feed"), beats.get("stones"), beats["rise"]
        self.has_feed = feed is not None
        last_t1 = max(w["t1"] for w in words) if words else duration
        # the rise: heave starts 0.3 s before its word, the stone is out 0.25 s after `up` starts, rung 0.15 s after
        self.T_UP = at(rise["up"], "rise.up") + 0.25
        self.T_RISE = at(rise["at"], "rise.at") - 0.30 if "at" in rise else self.T_UP - 0.97
        self.T_RRING = at(rise["ring"], "rise.ring") + 0.15 if "ring" in rise else self.T_UP + 0.05
        hold = float(spec.get("hold", 2.0))
        self.DUR = round(max(last_t1 + hold, self.T_RRING + 1.6), 3)
        # the different stones, each rung on its word
        ring_ts = [at(r, f"stones.rings[{k}]") for k, r in enumerate((stones or {}).get("rings") or [])]
        self.ring_ts = ring_ts
        if stones and "arrive" in stones:
            self.T_ARRIVE = at(stones["arrive"], "stones.arrive") + 0.05
        elif ring_ts:
            self.T_ARRIVE = ring_ts[0] - 0.2
        else:
            self.T_ARRIVE = self.T_RISE - 0.6
        # the feed
        self.lights = []
        if feed:
            self.T_FLICK = at(feed["flick"], "feed.flick") - 0.05
            self.T_LAND = at(feed["land"], "feed.land") - 0.05 if "land" in feed else self.T_FLICK + 1.6
            for k, ln in enumerate(feed.get("light") or []):
                self.lights.append((at(ln["at"], f"feed.light[{k}].at") - 0.10, ln["to"]))
            if "go" in feed:
                self.T_GO = at(feed["go"], "feed.go") + 0.25
            else:
                last = max([self.T_LAND + 0.6] + [t + 0.75 for t, _ in self.lights])
                self.T_GO = min(last, self.T_ARRIVE - 0.6)
        # the stones in the world
        self.stones = []
        if feed:
            self.stones += [dict(FEED_STONE, x=0.0, y=k * STEP, id=f"feed{k}") for k in range(0, 6)]
        self.loved = []
        for k, j in enumerate(_ARRANGE.get(len(ring_ts), [])):
            s = dict(_LOVE[j])
            s.update(id=f"love{k}", y=CL + s["y"], ring_t=ring_ts[k])
            self.loved.append(s)
        self.stones += self.loved
        self.red = dict(_RED, id="red", y=CL + _RED["y"])
        self.captions = self._captions(at, words)

    def check(self):
        if self.has_feed:
            seq = [("feed.flick", self.T_FLICK), ("feed.land", self.T_LAND)]
            seq += [(f"feed.light[{k}]", t) for k, (t, _) in enumerate(self.lights)]
            seq += [("feed.go", self.T_GO), ("the arrival at the stones", self.T_ARRIVE)]
            for (a, ta), (b, tb) in zip(seq, seq[1:]):
                if tb <= ta + 0.15:
                    raise StudioError(f"{b} comes before (or right on) {a}. The feed moves in his order: the flick, "
                                      "the landing, the light, then the carry on to the stones.")
            if self.T_ARRIVE - self.T_GO < 0.45:
                raise StudioError("The carry from the feed to the stones is too short. Leave at least half a second "
                                  "of his words between the feed's last word and the first ring.")
        for k, t in enumerate(self.ring_ts):
            if k and t <= self.ring_ts[k - 1] + 0.3:
                raise StudioError("Two rings fall on the same moment. Ring each stone on a different word, in order.")
        if self.T_UP - self.T_RISE < 0.5:
            raise StudioError("The red stone needs half a second or more to come up: put rise.at a word or two "
                              "before rise.up.")
        if self.ring_ts and self.T_RISE < self.ring_ts[0]:
            raise StudioError("The red stone rises before the first ring. The rise comes last.")

    def _captions(self, at, words):
        out, after = [], 0
        for k, c in enumerate(self.spec.get("captions") or []):
            if "at" in c:
                t0 = at(c["at"], f"captions[{k}].at")
                i0, i1 = find_phrase(words, c["text"], after)
            else:
                i0, i1 = find_phrase(words, c["text"], after)
                t0 = words[i0]["t0"]
            after = i1 + 1
            out.append((c["text"], t0, words[i1]["t0"] + 0.35))
        res = []
        for k, (txt, t0, t1) in enumerate(out):
            if k + 1 < len(out):
                res.append((txt, t0 - 0.08, min(out[k + 1][1] - 0.30, t1 + 0.9)))
            else:
                res.append((txt, t0 - 0.08, self.DUR - 0.5))
        return res

    # ------------------------------------------------------------------------------------------- motion
    def scroll_y(self, t):
        """camera centre y in world px: feed flick with inertia, holds, then the long carry to the cluster"""
        if not self.has_feed:
            # no feed: a slow glide down onto the cluster, arriving as the first stone is named
            yl = CL - 40 - 300
            return yl + 300 * float(ease_io(t / max(self.T_ARRIVE, 0.8), 2.6))
        y0 = 0.6 * STEP - 120
        y_land = 3 * STEP
        if t < self.T_FLICK:
            return y0 + 40 * (t / max(self.T_FLICK, 1e-3))
        if t < self.T_GO:
            u = t - self.T_FLICK
            tau = 0.32
            acc = ease(u / 0.12)
            s = (1 - np.exp(-u / tau)) / (1 - np.exp(-(self.T_LAND - self.T_FLICK + 0.35) / tau))
            s = np.clip(s, 0, 1) * acc
            base = y0 + 40
            return base + (y_land - base) * min(1.0, s) + 6 * np.sin(u * 0.8) * ease((u - 1.2) / 1.5)
        yl = y_land + 6 * np.sin((self.T_GO - self.T_FLICK) * 0.8)
        u = (t - self.T_GO) / (self.T_ARRIVE - self.T_GO)
        return yl + (CL - 40 - yl) * ease_io(u, 2.6)

    def cam(self, t):
        y = self.scroll_y(t)
        x = 6 * np.sin(t * 0.21)
        z = 1.0 + 0.012 * t
        if t > self.T_RISE:
            k = ease_io((t - self.T_RISE) / (self.DUR - self.T_RISE), 2)
            z += 0.10 * k
            x += (self.red["x"] - x) * 0.6 * k
            y += (self.red["y"] + 30 - y) * 0.6 * k
        return float(x), float(y), float(z)

    def go_t(self):
        return self.T_GO if self.has_feed else -1.0

    def pool(self, t, SX, SY, W, H):
        """the key light's pool on the frame (screen px). On the feed it tightens on the stone in view and can find
        the one above or below; it opens for the cluster and closes on the red stone."""
        cx, cy = W * 0.5, H * 0.47
        sy = 0.0
        if self.has_feed:
            prev = 0.0
            for tl, to in self.lights:
                o = {"above": -STEP, "below": STEP, "here": 0.0}[to]
                sy += (o - prev) * ease_io((t - tl) / 0.3)
                prev = o
            sy += -prev * ease_io((t - self.T_GO) / 0.45)
            tight = ease((t - self.T_LAND) / 0.5) * (1 - ease((t - self.T_GO) / 0.5))
        else:
            tight = 0.0
        rx, ry = 600 - 190 * tight, 700 - 300 * tight
        go = self.go_t()
        if t > go:
            k = ease((t - go - 0.3) / 1.2)
            rx, ry = rx + 120 * k, ry + 220 * k
        if t > self.T_RISE:
            k = ease((t - self.T_RISE) / 1.5)
            rx, ry = rx - 160 * k, ry - 330 * k
        g = np.exp(-(((SX - cx) / rx) ** 2 + ((SY - (cy + sy)) / ry) ** 2))
        base = 0.08 + 0.92 * g
        return base * (0.45 + 0.55 * ease((t + 0.1) / 0.8))

    def ring_progress(self, st, t):
        if st["id"].startswith("feed"):
            return 1.0
        if st["id"] == "red":
            return float(ease_out((t - self.T_RRING) / 1.3, 1.6))
        return float(ease_out((t - st["ring_t"] + 0.15) / 0.9, 1.6))

    def red_rise(self, t):
        return float(ease_io((t - self.T_RISE - 0.25) / (self.T_UP - self.T_RISE - 0.25), 2.2))

    def caption_box(self, txt, m, W):
        h, w = m.shape
        return ((W - w) // 2, CAP_BOTTOM - h, w, h)

    def red_screen_box(self, t, W, H):
        """the red stone's footprint on screen at time t (x, y, w, h)"""
        cx, cy, z = self.cam(t)
        th = np.linspace(0, 2 * np.pi, 180)
        r = boundary(self.red, th)
        xs = (self.red["x"] + r * np.cos(th) - cx) * z + W / 2
        ys = (self.red["y"] + r * np.sin(th) - cy) * z + H / 2
        return (float(xs.min()), float(ys.min()), float(xs.max() - xs.min()), float(ys.max() - ys.min()))


# ----------------------------------------------------------------------------------------------- the painter
class Garden:
    def __init__(self, plan, W, H, colors):
        textures()
        self.p, self.W, self.H = plan, W, H
        self.GW, self.GH = int(W * RS), int(H * RS)
        self.SX, self.SY = np.meshgrid(np.arange(self.GW, dtype=np.float32) / RS,
                                       np.arange(self.GH, dtype=np.float32) / RS)
        self.SYo = np.arange(H, dtype=np.float32)[:, None] * np.ones((1, W), np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
        self.vig = (1 - 0.5 * np.clip(r, 0, 1.4) ** 2.0)[..., None].astype(np.float32)
        self.focus = np.clip((np.abs(self.SYo - H * 0.47) - 560) / 520, 0, 1)[..., None]
        rng = np.random.default_rng(7)
        self.grain = [rng.standard_normal((H // 2, W // 2)).astype(np.float32) for _ in range(12)]
        self.red = (np.array(brand.rgb_of(colors.get("red", "#B91C1C")), np.float64) / 255.0)
        self.cream = np.array(brand.rgb_of(colors.get("cream", "#F1EBDF")), np.float64) / 255.0
        self.caps = [(txt, t0, t1, cap_block(txt)) for txt, t0, t1 in plan.captions]

    # ------------------------------------------------------------------------------------------- height field
    def heights(self, t, X, Y, smp):
        p = self.p
        mid = smp("mid", 4.0)
        wob = mid * 2.2
        fine = smp("fine", 1.0)
        grain = smp("grain", 0.75)
        dep = DEPTH * (1 + 0.08 * mid)
        lines = dep * rake_profile((Y + wob) / SP)

        best = np.full(X.shape, 1e9, np.float32)
        stone_h = np.zeros(X.shape, np.float32)
        stone_id = np.full(X.shape, -1, np.int8)
        stone_u = np.zeros(X.shape, np.float32)
        feats = [s for s in p.stones if Y.min() - 500 < s["y"] < Y.max() + 500]
        if t > p.T_RISE - 0.2:
            feats = feats + [p.red]
        zone = np.zeros(X.shape, bool)
        fields = {}
        for st in feats:
            d, u = stone_fields(st, X, Y)
            fields[st["id"]] = d
            pr = p.ring_progress(st, t)
            R_zone = COLLAR + st["rings"] * SP
            front = COLLAR * 0.6 + (R_zone - COLLAR * 0.6) * pr
            if st["id"] == "red":
                take = (d < min(front, R_zone)) & (d < best) & (pr > 0)
            else:
                take = (d < front) & (d < best)
            best = np.where(take, d, best)
            zone |= take
            inside = d < 0
            if st["id"] == "red":
                k = p.red_rise(t)
                sh = st["h"] * (1 - u ** 2.4) ** 0.5 + 1.7 * smp("rock", 2.5) * (1 - u ** 3) + 0.35 * fine * (1 - u)
                sh = sh * 1.0 - (1 - k) * (st["h"] + 14)
                m = inside & (sh > 0)
                stone_h = np.where(m, np.maximum(stone_h, sh), stone_h)
                stone_id = np.where(m & (sh >= stone_h - 1e-3), 9, stone_id)
                stone_u = np.where(m, u, stone_u)
            else:
                rock = smp("rock", 3.0, st["seed"] * 333)
                sh = st["h"] * (1 - u ** 2.6) ** 0.55 + 2.2 * rock * (1 - u ** 3)
                m = inside
                stone_h = np.where(m, np.maximum(stone_h, sh), stone_h)
                stone_id = np.where(m, 1, stone_id)
                stone_u = np.where(m, u, stone_u)
        rings = DEPTH * rake_profile((best - COLLAR + wob * 0.5) / SP)
        collar = DEPTH * (0.62 + 0.38 * np.clip(1 - best / COLLAR, 0, 1))
        rh = np.where(best < COLLAR, collar, rings)
        sand = np.where(zone, rh, lines)
        # the rake front: a little spill of loose sand where it has just passed
        for st in feats:
            if st["id"].startswith("feed"):
                continue
            pr = p.ring_progress(st, t)
            if 0 < pr < 1:
                d = fields[st["id"]]
                R_zone = COLLAR + st["rings"] * SP
                front = COLLAR * 0.6 + (R_zone - COLLAR * 0.6) * pr
                sand = sand + 2.6 * np.exp(-((d - front - 5) / 7) ** 2) * (d < R_zone + 20)
        # the red stone: the sand heaves before it breaks, then lies thrown back round it
        if t > p.T_RISE - 0.2:
            d = fields["red"]
            k = p.red_rise(t)
            heave = ease((t - p.T_RISE) / 0.35) * (1 - k)
            sand = sand + 16 * heave * np.exp(-np.maximum(d + 40, 0) ** 2 / (2 * 70 ** 2)) * (1 + 0.2 * fine)
            pr = p.ring_progress(p.red, t)
            sand = sand + k * (1 - pr) * 9 * np.exp(-((d - 26) / 26) ** 2) * (1 + 0.35 * fine)
        sand = sand + 0.35 * fine + 0.28 * grain
        h = np.maximum(sand, stone_h)
        is_stone = stone_h > sand
        return h, np.where(is_stone, stone_id, -1), stone_u, sand

    # ------------------------------------------------------------------------------------------- shading
    def shade(self, t):
        p, W, H = self.p, self.W, self.H
        cx, cy, z = p.cam(t)
        X = (np.float32(cx) + (self.SX - W / 2) / np.float32(z)).astype(np.float32)
        Y = (np.float32(cy) + (self.SY - H / 2) / np.float32(z)).astype(np.float32)
        smp = Sampler(X, Y)
        h, sid, _, sand = self.heights(t, X, Y, smp)
        dw = 1.0 / (RS * z)
        h = h.astype(np.float32)
        gy, gx = np.gradient(h, dw)
        n = np.stack([-gx, -gy, np.ones_like(h)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        lam = np.clip(n @ LDIR, 0, 1)
        # cast shadows: light travels down the frame; a point is shadowed if anything up-frame is above its ray
        g = h + Y * TANE
        hor = np.maximum.accumulate(g, axis=0)
        sh = np.clip(1 - (hor - g) / 1.6, 0, 1)
        sh = cv2.GaussianBlur(sh, (0, 0), 2.2 * RS)
        ao = np.clip(1 - (cv2.GaussianBlur(h, (0, 0), 6 * RS) - h) * 0.07, 0.45, 1)
        grain = smp("grain", 0.75)
        fine = smp("fine", 1.0)
        alb = 0.060 * (1 + 0.22 * grain + 0.12 * fine)
        alb = np.stack([alb * 1.0, alb * 0.97, alb * 0.93], -1)
        rough_spec = np.zeros_like(h)
        st_mask = sid == 1
        if st_mask.any():
            rock = smp("rock", 1.0)
            a2 = 0.034 * (1 + 0.25 * rock)
            alb[st_mask] = np.stack([a2, a2 * 0.98, a2 * 0.96], -1)[st_mask]
            rough_spec[st_mask] = 0.10
        red_mask = sid == 9
        if red_mask.any():
            # the red stone, still dusted where it is just out of the sand
            k = p.red_rise(t)
            above = np.clip((h - sand) / 8.0, 0, 1)
            clean = np.clip(above * (0.6 + 0.6 * k) + 0.25 * fine * (1 - k) - 0.15 * (1 - k), 0, 1)
            redc = (self.red ** 2.2 * 0.62 * (1 + 0.22 * smp("rock", 1.5) + 0.10 * grain)[..., None]).astype(np.float32)
            mix = clean[..., None]
            alb[red_mask] = (alb * (1 - mix) + redc * mix)[red_mask]
            rough_spec[red_mask] = 0.035 * clean[red_mask]
        spark = smp("spark", 0.75) * (sid < 0)
        nh = np.clip(n @ HV, 0, 1)
        spec = (rough_spec * nh ** 14 * 1.4 + spark * nh ** 6 * 0.55)
        P = p.pool(t, self.SX, self.SY, W, H)
        key = 6.6 * P
        rad = alb * (key * lam * sh * ao)[..., None] + (spec * key * sh)[..., None] * np.array([1.0, 0.95, 0.88])
        sky = 0.016 * ao * (0.6 + 0.4 * n[..., 2])
        rad += alb * sky[..., None] * np.array([0.8, 0.9, 1.1]) * 6
        rad *= np.array([1.0, 0.93, 0.84])
        return cv2.resize(rad.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)

    def lens(self, img, t, vy):
        L = abs(vy) / self.p.fps * 0.5          # motion blur along the scroll (180-degree shutter)
        if L > 1.5:
            n = int(min(L, 220)) | 1
            k = np.full((n, 1), 1.0 / n, np.float32)
            img = cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REFLECT)
        blur = cv2.GaussianBlur(img, (0, 0), 5)  # shallow focus toward the top and bottom (overhead macro lens)
        img = img * (1 - self.focus) + blur * self.focus
        lum = img.max(axis=2)                    # halation on the brightest highlights and on the red
        glow = cv2.GaussianBlur(np.clip(lum - 0.28, 0, None), (0, 0), 10)
        img = img + glow[..., None] * np.array([0.5, 0.32, 0.22])
        img = img * self.vig
        img = np.clip(img, 0, None)
        return img / (1 + img * 0.35) * 1.35

    def captions(self, img, t):
        for txt, t0, t1, m in self.caps:
            if t0 - 0.05 <= t <= t1 + 0.3:
                o = ease((t - t0) / 0.16) * (1 - ease((t - t1) / 0.2))
                if o <= 0:
                    continue
                dy = int(round(10 * (1 - ease_out((t - t0) / 0.35))))
                h, w = m.shape
                x0 = (self.W - w) // 2
                y0 = CAP_BOTTOM - h + dy
                pd = 60                          # a soft dark halo first, so cream type holds over lit sand
                Y0, Y1 = max(0, y0 - pd), min(self.H, y0 + h + pd)
                X0, X1 = max(0, x0 - pd), min(self.W, x0 + w + pd)
                halo = np.zeros((Y1 - Y0, X1 - X0), np.float32)
                halo[y0 - Y0:y0 - Y0 + h, x0 - X0:x0 - X0 + w] = m
                halo = cv2.GaussianBlur(cv2.dilate(halo, np.ones((9, 9), np.uint8)), (0, 0), 18)
                img[Y0:Y1, X0:X1] *= (1 - np.clip(halo * 1.5, 0, 0.82) * o)[..., None]
                a = m[..., None] * o
                img[y0:y0 + h, x0:x0 + w] = img[y0:y0 + h, x0:x0 + w] * (1 - a) + self.cream * 1.06 * a
        return img

    def to8(self, img, i):
        g = cv2.resize(self.grain[i % len(self.grain)], (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        lum = img.mean(axis=2, keepdims=True)
        img = img + g[..., None] * (0.018 * (0.35 + 0.65 * np.sqrt(np.clip(lum, 0, 1))))
        x = np.clip(img, 0, None)
        x = np.where(x > 0.85, 0.85 + 0.15 * np.tanh((x - 0.85) / 0.15), x)
        dither = np.random.default_rng(1000 + i).uniform(-0.5, 0.5, (self.H, self.W, 1)).astype(np.float32)
        return np.clip(x * 255 + dither, 0, 255).astype(np.uint8)

    def picture(self, t, i):
        vy = (self.p.cam(t + 0.01)[1] - self.p.cam(t - 0.01)[1]) / 0.02
        img = self.shade(t)
        img = self.lens(img, t, vy)
        return self.to8(self.captions(img, t), i)

    def frame(self, i):
        return self.picture(i / self.p.fps, i)


# ----------------------------------------------------------------------------------------------- sound
def effects(plan):
    """The style's own effects: air on the flick and the carry, a low breath when the light moves, raked sand for each
    ring, a rumble and a sand pour under the rise, one struck bowl when the red stone is up."""
    n = int((plan.DUR + 6.0) * snd.SR)
    bus = np.zeros((n, 2))
    if plan.has_feed:
        snd.place(bus, snd.lp(snd.whoosh_air(1.1, 1, 200, 1800, 0.25), 3500), max(0.0, plan.T_FLICK - 0.05), 0)
        snd.place(bus, snd.lp(snd.whoosh_air(1.4, 2, 180, 1500, 0.5), 3000), plan.T_GO - 0.05, 0)
        for tl, _ in plan.lights:
            snd.place(bus, snd.lp(snd.whoosh_air(0.6, 40, 120, 700, 0.5), 900), tl - 0.1, -6)
    for k, st in enumerate(plan.loved):
        snd.place(bus, snd.fade(snd.sand(0.95, 10 + k, 1.2), 0.08, 0.35), st["ring_t"] - 0.12, -2)
    snd.place(bus, snd.fade(snd.sand(1.4, 20, 1.0), 0.1, 0.5), plan.T_RRING, -3)
    rum = snd.lp(np.random.default_rng(5).standard_normal(int(1.3 * snd.SR)), 140)
    rum *= np.sin(np.linspace(0, np.pi, len(rum))) ** 1.5
    snd.place(bus, rum * 3, plan.T_RISE - 0.1, 2)
    snd.place(bus, snd.fade(snd.sand(1.2, 30, 2.5), 0.2, 0.6), plan.T_RISE + 0.3, -1)
    snd.place(bus, snd.bowl(5.0, 220.0), plan.T_UP - 0.15, 3)
    return snd.reverb(bus, 2.0, 0.22)[: int(plan.DUR * snd.SR)]


def music(ctx, plan):
    """The spec's bed. Default: the zen bed, a low open drone that warms into a chord as the red stone rises."""
    bed = (ctx.spec.get("sound") or {}).get("bed")
    if bed in (None, "zen"):
        bed = {"name": "zen"}
    if isinstance(bed, dict):
        bed = dict(bed)
        if bed.get("name") == "zen":
            bed["rise"] = ctx.at(bed["rise"], "sound.bed.rise") if "rise" in bed else plan.T_RISE
        if "changes" in bed:
            bed["changes"] = [ctx.at(c, "sound.bed.changes") for c in bed["changes"]]
        for key in ("pulse_until", "swell_at"):
            if key in bed:
                bed[key] = ctx.at(bed[key], f"sound.bed.{key}")
    return bed


# ----------------------------------------------------------------------------------------------- layout record
def _hex(c):
    return "#" + "".join(f"{int(round(v * 255)):02X}" for v in np.clip(c, 0, 1))


def record(ctx, plan, garden):
    """layout.json: one beat per caption (its box at rest), and the garden's moments (the landing, each light move,
    each ring, the rise, the end) with the caption on screen then and, once it is up, the red stone as the one red."""
    W, H = ctx.w, ctx.h
    cream = _hex(garden.cream)
    red_hex = _hex(garden.red)

    def visible(t):
        return [(txt, m) for txt, t0, t1, m in garden.caps if t0 + 0.1 <= t <= t1]

    def add(kind, t0, t1, i):
        bt = ctx.layout.beat(kind, t0, t1, i=i)
        look = min(t0 + 0.4, (t0 + t1) / 2) if t1 > t0 else t0
        for txt, m in visible(look):
            ctx.layout.text(bt, txt, plan.caption_box(txt, m, W), role="words", color=cream, red=False,
                            size=cap_size())
        if look >= plan.T_UP - 0.35:
            ctx.layout.mark(bt, "red stone", plan.red_screen_box(look, W, H), red=True, color=red_hex)

    moments = []
    for txt, t0, t1, m in garden.caps:
        moments.append(("line", t0 + 0.08, t1))
    if plan.has_feed:
        moments.append(("feed", plan.T_LAND + 0.3, plan.lights[0][0] if plan.lights else plan.T_GO))
        for k, (tl, to) in enumerate(plan.lights):
            nxt = plan.lights[k + 1][0] if k + 1 < len(plan.lights) else plan.T_GO
            moments.append((f"light {to}", tl + 0.1, nxt))
    for st in plan.loved:
        moments.append(("ring", st["ring_t"], st["ring_t"] + 1.0))
    moments.append(("rise", plan.T_UP - 0.4, plan.T_UP + 0.6))
    moments.append(("end", plan.DUR - 1.2, plan.DUR))
    moments.sort(key=lambda m: m[1])
    for i, (kind, t0, t1) in enumerate(moments):
        add(kind, round(t0, 3), round(min(t1, plan.DUR), 3), i)


# ----------------------------------------------------------------------------------------------- the render
def build(ctx_at, spec, words, duration, W, H, fps, colors):
    plan = Plan(ctx_at, spec, words, duration, fps)
    plan.check()
    return plan, Garden(plan, W, H, colors)


def render(ctx):
    plan, garden = build(ctx.at, ctx.spec, ctx.words, ctx.duration, ctx.w, ctx.h, ctx.fps, ctx.brand["colors"])
    n = int(plan.DUR * ctx.fps)
    silent = ctx.work / "picture.mp4"
    ctx.say(f"Drawing {n} frames of the zen garden.")
    t0 = time.time()
    with heavy.lock("zen-garden frames"):
        enc = Encoder(silent, ctx.w, ctx.h, ctx.fps, tune="grain")
        draw_frames(enc, garden.frame, n, ctx.say)
        enc.close()
    secs = time.time() - t0
    ctx.say("Mixing the sound.")
    sfx = [{"array": effects(plan), "t": 0.0, "under_db": 25}]
    for k, e in enumerate((ctx.spec.get("sound") or {}).get("sfx") or []):
        e = dict(e)
        e["t"] = ctx.at(e.get("at", e.get("t")), f"sound.sfx[{k}].at")
        e.pop("at", None)
        sfx.append(e)
    levels = snd.mix(ctx.voice(), plan.DUR, ctx.out / "mix.wav", bed=music(ctx, plan), sfx=sfx, work=ctx.work)
    mux(silent, ctx.out / "mix.wav", ctx.out / "final.mp4")
    poster(ctx.out / "final.mp4", min(plan.DUR - 0.1, plan.T_UP + 0.6), ctx.out / "poster.png")
    record(ctx, plan, garden)
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4", "levels": levels, "frames": n, "draw_seconds": round(secs, 1),
            "frames_per_second": round(n / max(secs, 1e-6), 2)}


def stills(ctx_at, spec, words, duration, W, H, fps, colors, times):
    """Single frames at given times (seconds), for previews and the regression test."""
    plan, garden = build(ctx_at, spec, words, duration, W, H, fps, colors)
    return [garden.picture(t, int(round(t * fps))) for t in times], plan
