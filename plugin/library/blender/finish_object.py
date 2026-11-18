"""Finish new object renders for The art of: merge each render (A) with its shadow-only pass (B, half res) into one
RGBA PNG (shadow = black at alpha_B * strength, softened, only around the object's own footprint), trim to content and
write <id>.box (the object's own box, used for sizing on the slide).
  python finish_object.py <render folder> <out folder> [strength]"""
import sys, glob, os
import numpy as np
from PIL import Image, ImageFilter
rd, od = sys.argv[1], sys.argv[2]; k = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
os.makedirs(od, exist_ok=True)
for fa in sorted(glob.glob(os.path.join(rd, '*.png'))):
    if fa.endswith('_shadow.png'): continue
    fb = fa[:-4] + '_shadow.png'
    A = Image.open(fa).convert('RGBA')
    if os.path.exists(fb):
        B = Image.open(fb).convert('RGBA').resize(A.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(A.width / 300))
        sa = np.asarray(B)[..., 3].astype(np.float32) / 255
        h, w = sa.shape; edge = np.concatenate([sa[:h//12].ravel(), sa[:, :w//12].ravel(), sa[:, -w//12:].ravel()])
        base = float(np.percentile(edge, 90)); sa = np.clip((sa - base) / max(1e-3, 1 - base), 0, 1) * k
        # keep the shadow only around the object's own footprint (no floor tint, no box edges)
        import cv2
        oa = (np.asarray(A)[..., 3] > 128).astype(np.uint8)
        r = max(3, int(A.width * 0.05)); near = cv2.dilate(oa, np.ones((r, r), np.uint8)).astype(np.float32)
        near = cv2.GaussianBlur(near, (0, 0), A.width * 0.03); sa = sa * np.clip(near * 1.4, 0, 1)
        sh = np.zeros((A.height, A.width, 4), np.uint8); sh[..., 3] = (np.clip(sa, 0, 1) * 255).astype(np.uint8)
        out = Image.alpha_composite(Image.fromarray(sh, 'RGBA'), A)
    else: out = A
    a = np.asarray(out)[..., 3]; ys, xs = np.where(a > 6)
    pad = 4; box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(out.width, xs.max() + pad), min(out.height, ys.max() + pad))
    # object-only bbox (for layout: captions hang off the object, not the shadow)
    ao = np.asarray(A)[..., 3]; yo, xo = np.where(ao > 128)
    out.crop(box).save(os.path.join(od, os.path.basename(fa)))
    with open(os.path.join(od, os.path.basename(fa)[:-4] + '.box'), 'w') as f:
        f.write(f"{xo.min()-box[0]} {yo.min()-box[1]} {xo.max()-box[0]} {yo.max()-box[1]}")
    print(os.path.basename(fa), out.crop(box).size)
