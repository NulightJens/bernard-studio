"""The raked-sand garden for the Prompt pack cover, drawn in code: a height field (rake-tine grooves, rings at an
exact distance around each stone, weathered river stones), lit by a low raking light with cast shadows, ambient
occlusion, grain sparkle and a soft light pool. One stone per prompt. The rake draws the rings stone by stone, then
the straight lines top to bottom; the schedule comes from his words (see render.py).

    g = Garden(stones, t_rings=(0.15, 3.55), t_lines=(3.55, 11.75), ss=1.5)
    rgb01 = g.frame(t, zoom)          # float BGR 0..1 at 1080 x 1440
"""
import math

import cv2
import numpy as np

W0, H0 = 1080, 1440          # output size
MARGIN = 60                  # extra canvas around the frame for the slow push-in
SP = 11.0                    # tine spacing (px at 1x)
TINES = 5
BAND = SP * TINES            # one rake stroke
A_GROOVE = 1.35              # groove amplitude (px)
RING_STROKES = 2             # rake strokes around each stone (2 x 5 tines = 10 grooves)
LIGHT_AZ = math.radians(200)  # light comes from the upper left (image coords, y down)
LIGHT_EL = math.radians(17)

# stone layouts by prompt count: centre (x, y) in output px, radius, height, seed, squash and turn. Three is the
# round-one garden; the others keep the same sizes and the upper half of the frame (the title sits below y 840).
_S = dict(r=104, h=70, seed=3, sx=1.22, sy=0.86, rot=-18), dict(r=64, h=50, seed=11, sx=1.10, sy=0.92, rot=24), \
    dict(r=40, h=34, seed=29, sx=1.15, sy=0.88, rot=-40), dict(r=52, h=42, seed=41, sx=1.12, sy=0.9, rot=10), \
    dict(r=34, h=30, seed=53, sx=1.18, sy=0.86, rot=-25)
LAYOUTS = {
    1: [(540, 470)],
    2: [(372, 470), (772, 330)],
    3: [(372, 470), (772, 300), (742, 700)],
    4: [(330, 470), (772, 270), (760, 640), (190, 760)],
    5: [(330, 470), (772, 270), (760, 640), (190, 760), (560, 160)],
}
# where each stone's number tag sits (left, top) and its leader line (left, top, width, angle), round one for three
TAGS = {
    1: [((300, 248), (62, 20, 130, 28))],
    2: [((96, 248), (62, 20, 130, 28)), ((604, 120), (-6, 46, 84, 62))],
    3: [((96, 248), (62, 20, 130, 28)), ((604, 96), (-6, 46, 84, 62)), ((920, 640), (-10, 22, 60, 160))],
    4: [((96, 248), (62, 20, 130, 28)), ((604, 76), (-6, 46, 84, 62)), ((920, 600), (-10, 22, 60, 160)),
        ((96, 860), (62, 0, 40, -20))],
    5: [((96, 248), (62, 20, 130, 28)), ((604, 76), (-6, 46, 84, 62)), ((920, 600), (-10, 22, 60, 160)),
        ((96, 860), (62, 0, 40, -20)), ((380, 90), (62, 20, 60, 28))],
}


def stones_for(n):
    return [dict(_S[i], c=LAYOUTS[n][i]) for i in range(n)]


def film_grain(img, seed, amt=0.018):
    rng = np.random.default_rng(seed)
    n = rng.standard_normal(img.shape[:2]).astype(np.float32)
    n = cv2.GaussianBlur(n, (0, 0), 0.7)
    return np.clip(img + amt * n[..., None] * (0.4 + img), 0, 1)


def to8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def fbm(shape, seed, octaves=5, base=6, gain=0.55):
    rng = np.random.default_rng(seed)
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cells = base * (2 ** o)
        g = rng.standard_normal((int(cells * h / max(h, w)) + 3, cells + 3)).astype(np.float32)
        big = cv2.resize(g, (w + 2 * w // cells + 4, h + 2 * h // max(1, int(cells * h / max(h, w))) + 4),
                         interpolation=cv2.INTER_CUBIC)
        out += amp * big[:h, :w]
        tot += amp
        amp *= gain
    return out / tot


class Garden:
    def __init__(self, stones, t_rings=(0.15, 3.55), t_lines=(3.55, 11.75), ss=1.0):
        self.ss = ss
        self.stones, self.t_rings, self.t_lines = stones, t_rings, t_lines
        self.W = int(round((W0 + 2 * MARGIN) * ss))
        self.H = int(round((H0 + 2 * MARGIN) * ss))
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self.x = xx / ss - MARGIN    # output-pixel coordinates
        self.y = yy / ss - MARGIN
        self._stones()
        self._fields()
        self._static()

    # ---------- stones ----------
    def _stones(self):
        H, W = self.H, self.W
        self.stone_h = np.zeros((H, W), np.float32)
        self.stone_alb = np.zeros((H, W), np.float32)
        self.stone_mask = np.zeros((H, W), np.float32)
        self.dist = np.full((H, W), 1e9, np.float32)     # distance to nearest stone outline
        self.near = np.zeros((H, W), np.int32)
        self.ang = np.zeros((H, W), np.float32)
        for i, s in enumerate(self.stones):
            cx, cy = s['c']
            dx, dy = self.x - cx, self.y - cy
            th = math.radians(s['rot'])
            u = (dx * math.cos(th) + dy * math.sin(th)) / s['sx']
            v = (-dx * math.sin(th) + dy * math.cos(th)) / s['sy']
            rr = np.sqrt(u * u + v * v)
            ang = np.arctan2(v, u)
            # irregular outline: low harmonics with a seeded phase
            rng = np.random.default_rng(s['seed'])
            wob = np.zeros_like(ang)
            for k, a in ((2, .07), (3, .05), (5, .025), (7, .012)):
                wob += a * np.cos(k * ang + rng.uniform(0, 6.28))
            R = s['r'] * (1 + wob)
            q = rr / R                       # 1 at the outline
            n1 = fbm((self.H, self.W), s['seed'] + 100, octaves=3, base=3)
            n2 = fbm((self.H, self.W), s['seed'] + 200, octaves=4, base=60)
            ridge = 1 - np.abs(fbm((self.H, self.W), s['seed'] + 300, octaves=3, base=5))
            # steep shoulders, a broad uneven top (a river stone weathered flat)
            prof = np.power(np.clip(1 - q * q, 0, 1), 0.5)
            hh = s['h'] * prof * (0.80 + 0.22 * n1 + 0.06 * ridge + 0.012 * n2) * (q < 1)
            m = (q < 1).astype(np.float32)
            m = cv2.GaussianBlur(m, (0, 0), 0.6 * self.ss)
            self.stone_h = np.maximum(self.stone_h, hh)
            pits = (rng.random((self.H, self.W)) < 0.02).astype(np.float32)
            alb = 0.12 + 0.025 * n2 + 0.03 * n1 + 0.02 * ridge - 0.03 * pits
            self.stone_alb = np.where(m > 0.5, alb, self.stone_alb)
            self.stone_mask = np.maximum(self.stone_mask, m)
        # exact distance to the nearest stone outline (canvas px -> output px), nearest stone label
        inv = (self.stone_mask < 0.5).astype(np.uint8)
        dist = cv2.distanceTransform(inv, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        self.dist = cv2.GaussianBlur(dist.astype(np.float32), (0, 0), 1.2 * self.ss) / self.ss
        # nearest stone by centre distance weighted by radius (good enough for the rake order)
        best = np.full((self.H, self.W), 1e9, np.float32)
        for i, s in enumerate(self.stones):
            cx, cy = s['c']
            dd = np.hypot(self.x - cx, self.y - cy) - s['r']
            sel = dd < best
            best = np.where(sel, dd, best)
            self.near = np.where(sel, i, self.near)
            self.ang = np.where(sel, np.arctan2(self.y - cy, self.x - cx), self.ang)

    # ---------- rake fields ----------
    def _fields(self):
        ring_extent = RING_STROKES * BAND + 3
        d = np.maximum(self.dist, 0) + 4.0          # first groove starts a little off the stone
        self.in_ring = (self.dist < ring_extent).astype(np.float32)
        self.in_ring = cv2.GaussianBlur(self.in_ring, (0, 0), 1.0 * self.ss)
        self.ring_phase = d / SP
        y0 = -MARGIN
        self.line_phase = (self.y - y0) / SP
        # reveal time per pixel
        nst = len(self.stones)
        r0, r1 = self.t_rings
        per_stone = (r1 - r0) / nst
        per_stroke = per_stone / RING_STROKES
        stroke = np.clip(np.floor(np.maximum(self.dist, 0) / BAND), 0, RING_STROKES - 1)
        a01 = ((self.ang + math.pi) / (2 * math.pi) + 0.25) % 1.0
        t_ring = r0 + self.near * per_stone + stroke * per_stroke + a01 * per_stroke
        l0, l1 = self.t_lines
        nb = int(math.ceil((H0 + 2 * MARGIN) / BAND))
        band = np.clip(np.floor((self.y - y0) / BAND), 0, nb - 1)
        per_band = (l1 - l0) / nb
        xs = np.clip((self.x + MARGIN) / (W0 + 2 * MARGIN), 0, 1)
        along = np.where(band % 2 == 0, xs, 1 - xs)
        t_line = l0 + band * per_band + along * per_band
        self.t_reveal = np.where(self.in_ring > 0.5, t_ring, t_line).astype(np.float32)
        self.t_reveal = np.where(self.stone_mask > 0.5, -1, self.t_reveal)
        self.schedule = dict(rings=[r0 + i * per_stone for i in range(nst)], bands=nb, per_band=per_band)

    def _static(self):
        sh = (self.H, self.W)
        self.base = 0.35 * fbm(sh, 7, octaves=5, base=4) + 0.12 * fbm(sh, 8, octaves=3, base=60)
        rng = np.random.default_rng(5)
        self.grain = rng.standard_normal(sh).astype(np.float32)
        self.grain = cv2.GaussianBlur(self.grain, (0, 0), 0.55 * self.ss) * 0.22
        self.sparkle = (rng.random(sh) < 0.0012 / (self.ss * self.ss)).astype(np.float32) * rng.random(sh).astype(np.float32)
        self.alb_sand = 0.105 + 0.012 * fbm(sh, 9, octaves=4, base=8)
        # tine wobble: real rake lines are not perfect
        self.wob_l = 0.10 * fbm(sh, 21, octaves=3, base=5)
        self.wob_r = 0.10 * fbm(sh, 22, octaves=3, base=5)
        # stone cast shadow (static, long march)
        self.stone_shadow = self._shadow(self.stone_h, steps=int(160 * self.ss), soft=True)

    def _shadow(self, h, steps, soft):
        lx, ly = math.cos(LIGHT_AZ), math.sin(LIGHT_AZ)
        tanE = math.tan(LIGHT_EL) / self.ss    # height is in output px, distance in canvas px
        hs = h * 1.0
        occl = np.zeros_like(h)
        for k in range(1, steps + 1, 1 if steps < 40 else 2):
            dx, dy = int(round(lx * k)), int(round(ly * k))
            sh = np.roll(np.roll(hs, -dy, axis=0), -dx, axis=1)
            diff = sh - h - k * tanE
            if soft:
                occl = np.maximum(occl, np.clip(diff / (2 + 0.18 * k), 0, 1))
            else:
                occl = np.maximum(occl, np.clip(diff / 1.2, 0, 1))
        return 1 - occl

    # ---------- one frame ----------
    def height(self, t):
        raked = np.clip((t - self.t_reveal) * 40.0, 0, 1)        # quick ease at the frontier
        front = np.exp(-((t - self.t_reveal) * 9.0) ** 2) * (self.t_reveal > 0)   # sand pushed ahead
        ph_r = self.ring_phase + self.wob_r
        ph_l = self.line_phase + self.wob_l
        g_r = np.cos(2 * np.pi * ph_r)
        g_l = np.cos(2 * np.pi * ph_l)
        g = self.in_ring * g_r + (1 - self.in_ring) * g_l
        # sharpen the ridges a touch (sand ridges are peaked, grooves are rounder)
        g = np.sign(g) * np.power(np.abs(g), 0.8)
        h = self.base + self.grain + raked * A_GROOVE * g + 0.9 * front
        h = h * (1 - self.stone_mask) + self.stone_h + self.stone_mask * 0.5
        return h

    def shade(self, h):
        ss = self.ss
        gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8.0 * ss
        gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8.0 * ss
        nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1)
        nx, ny = -gx * nz, -gy * nz
        lx = math.cos(LIGHT_EL) * math.cos(LIGHT_AZ)
        ly = math.cos(LIGHT_EL) * math.sin(LIGHT_AZ)
        lz = math.sin(LIGHT_EL)
        # light vector points toward the light: the light sits at azimuth +180 of its travel
        ndl = nx * lx + ny * ly + nz * lz
        diff = np.clip(ndl, 0, 1)
        wrap = np.clip((ndl + 0.25) / 1.25, 0, 1)
        # local shadow of grooves (short march)
        self_sh = self._shadow(h * (1 - self.stone_mask), steps=int(10 * ss), soft=False)
        sh = np.minimum(self_sh, self.stone_shadow)
        # specular (half vector with the camera straight above)
        hx, hy, hz = lx, ly, lz + 1
        hn = math.sqrt(hx * hx + hy * hy + hz * hz)
        ndh = np.clip((nx * hx + ny * hy + nz * hz) / hn, 0, 1)
        spec_sand = np.power(ndh, 60) * 0.35 + self.sparkle * np.power(ndh, 8) * 1.1
        spec_stone = np.power(ndh, 30) * 0.45
        alb = self.alb_sand * (1 - self.stone_mask) + self.stone_alb * self.stone_mask
        spec = spec_sand * (1 - self.stone_mask) + spec_stone * self.stone_mask
        # ambient occlusion from local height
        blur = cv2.GaussianBlur(h, (0, 0), 6 * ss)
        ao = np.clip(1 + 0.08 * (h - blur), 0.55, 1.15)
        ao_contact = np.clip(1 - 0.55 * np.exp(-np.maximum(self.dist, 0) / (14 * 1.0)) * (1 - self.stone_mask), 0.35, 1)
        key = (diff * sh * 1.55 + 0.05 * wrap) * alb * ao * ao_contact + spec * sh
        # light pool: a soft spot from the upper left, falling off to the frame edges and the title zone
        px = (self.x / W0)
        py = (self.y / H0)
        pool = np.exp(-(((px - 0.50) / 0.52) ** 2 + ((py - 0.33) / 0.36) ** 2))
        pool = 0.07 + 1.45 * pool
        lum = key * pool
        return lum

    def frame(self, t, zoom=1.0):
        lum = self.shade(self.height(t))
        return self.finish(lum, zoom)

    def finish(self, lum, zoom):
        ss = self.ss
        # tone map + grade: warm highlights, neutral deep blacks (obsidian)
        x = np.clip(lum, 0, None)
        tm = x / (x + 0.42) * 1.32
        tm = np.clip(tm, 0, 1)
        r = np.power(tm, 1.08) * 1.02
        g = np.power(tm, 1.10) * 1.0
        b = np.power(tm, 1.13) * 0.965
        img = np.stack([b, g, r], -1)
        img = img * 0.97 + 0.012          # lift the floor a hair (obsidian, never pure 0)
        # crop with a centred zoom
        cw, chh = (W0 + 2 * MARGIN) * ss, (H0 + 2 * MARGIN) * ss
        vw, vh = W0 * ss / zoom, H0 * ss / zoom
        x0, y0 = (cw - vw) / 2, (chh - vh) / 2
        M = np.float32([[1 / (vw / W0), 0, -x0 / (vw / W0)], [0, 1 / (vh / H0), -y0 / (vh / H0)]])
        out = cv2.warpAffine(img.astype(np.float32), M, (W0, H0), flags=cv2.INTER_AREA if ss > 1 else cv2.INTER_LINEAR)
        out = np.clip(out, 0, 1)
        return out
