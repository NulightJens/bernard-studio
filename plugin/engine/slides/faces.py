"""Where his face is in a picture, so big type can stay off it.

Apple Vision's face finder (on the Mac, no download: the same Vision framework the caption reader uses). Boxes are
(x, y, w, h) in pixels of the picture, origin top-left. The box Vision gives covers brow to chin; `head_box` grows it
to the whole head (hair above, a little each side), which is what type must stay clear of.
"""
import io


def find(pil_image, min_conf=0.5):
    """Face boxes in the picture, largest first. An empty list when there is no face or Vision is not available."""
    try:
        import Vision
    except Exception:
        return []
    buf = io.BytesIO()
    pil_image.convert("RGB").save(buf, format="PNG")
    req = Vision.VNDetectFaceRectanglesRequest.alloc().init()
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(buf.getvalue(), None)
    ret = handler.performRequests_error_([req], None)
    ok = ret[0] if isinstance(ret, tuple) else bool(ret)
    if not ok:
        return []
    W, H = pil_image.size
    out = []
    for r in req.results() or []:
        if float(r.confidence()) < min_conf:
            continue
        bb = r.boundingBox()
        x, y, w, h = bb.origin.x * W, (1 - bb.origin.y - bb.size.height) * H, bb.size.width * W, bb.size.height * H
        out.append((round(x, 1), round(y, 1), round(w, 1), round(h, 1)))
    return sorted(out, key=lambda b: -b[2] * b[3])


def head_box(face, W=None, H=None):
    """The face box grown to his whole head: 45 percent of its height above (hair), 15 percent each side and below."""
    x, y, w, h = face
    x0, y0, x1, y1 = x - 0.15 * w, y - 0.45 * h, x + 1.15 * w, y + 1.15 * h
    if W is not None:
        x0, x1 = max(0.0, x0), min(float(W), x1)
    if H is not None:
        y0, y1 = max(0.0, y0), min(float(H), y1)
    return (round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1))


def overlap(a, b):
    """Area two boxes share, in square pixels."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)
