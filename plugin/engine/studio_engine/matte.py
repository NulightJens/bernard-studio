"""Cut Bernard out of his footage or photos with BiRefNet HR matting (ZhengPeng7/BiRefNet_HR-matting, MIT), the setup
from reel-edit-lab: each frame resized to 2048 x 2048, fp16 on the Mac's GPU (MPS), alpha resized back. Heavy: runs
under heavy.lock(). Needs the matte component (torch, transformers and the model in STUDIO_HOME/models/birefnet-hr).

    studio matte <project> [--source <name>] [--t0 s --t1 s] [--fps N] [--frames N]
        -> <project>/matte/<run>/frames/f00001.jpg, alpha/a00001.png, rgba/p00001.png, sheet.png
    studio matte-photo <file> [--name <pose name>] [--cut-y px] [--grade none|bright|warm]
        -> a clean trimmed cutout PNG in his pose folder (.settings/poses/<name>.png, the only place poses are read
           from): largest body kept, holes filled, edge colour cleaned. It never writes anywhere else.

Python API: alpha(pil_image) -> uint8 array; rgba(frame, alpha); finish_cutout(bgr, alpha, cut_y, grade).
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import numpy as np

from . import heavy, paths
from .errors import StudioError
from .project import write_json
from .util import fps_str, nice_fps, probe, say
from .media import check_image, check_source, heic_to_jpeg, is_heic, safe_input

SIZE = 2048
_NET = {}
GRADES = {"none": (1, 1, (1, 1, 1)), "bright": (1.10, 1.04, (1.0, 1.0, 1.0)), "kit": (1.12, 1.03, (1.0, 1.0, 1.0)),
          "warm": (1.02, 1.02, (1.03, 1.0, 0.97)), "dark-room": (1.55, 1.06, (1.0, 1.0, 1.0))}
CHOKE = {"bright": (0.30, 0.90, 0.85), "kit": (0.10, 0.92, 0.6), "dark-room": (0.25, 0.9, 0.8)}


def available():
    if not (paths.birefnet_dir() / "config.json").exists():
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _need():
    if not available():
        raise StudioError("Cutting him out needs the matting add-on. Type /studio-setup and say yes to matting.")


def model():
    _need()
    if "net" not in _NET:
        paths.configure_env()
        import torch
        from transformers import AutoModelForImageSegmentation
        dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        net = AutoModelForImageSegmentation.from_pretrained(str(paths.birefnet_dir()), trust_remote_code=True,
                                                            local_files_only=True)
        net = net.to(dev).eval()
        net = net.half() if dev.type == "mps" else net
        _NET.update(net=net, dev=dev)
    return _NET["net"], _NET["dev"]


def alpha(im):
    """PIL image -> alpha (uint8, same size), BiRefNet HR at 2048 px."""
    import torch
    from torchvision import transforms
    net, dev = model()
    tf = transforms.Compose([transforms.Resize((SIZE, SIZE)), transforms.ToTensor(),
                             transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    x = tf(im.convert("RGB"))[None].to(dev)
    x = x.half() if dev.type == "mps" else x
    with torch.no_grad():
        p = net(x)[-1].sigmoid().float()
        p = torch.nn.functional.interpolate(p, size=(im.height, im.width), mode="bilinear", align_corners=False)
    return (p[0, 0].clamp(0, 1).cpu().numpy() * 255 + 0.5).astype(np.uint8)


def rgba(frame_rgb, a):
    """Straight-alpha RGBA cutout (the alpha used as it is)."""
    return np.dstack([np.asarray(frame_rgb)[..., :3], np.asarray(a)])


def finish_cutout(I_bgr8, a8, cut_y=None, grade="none"):
    """Port of the carousel cutout finisher: keep the largest body, fill small interior holes, choke the soft edge,
    remove the old background's colour from the edge (F = (I - (1 - a) B) / a with B inpainted), drop backlight glow
    and matte haze, clamp green spill, grade. Returns (RGBA uint8 trimmed, report)."""
    import cv2
    I = I_bgr8.astype(np.float32) / 255
    a = a8.astype(np.float32) / 255
    if cut_y:
        a[int(cut_y):] = 0
    hard = (a > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hard)
    if n > 1:
        body = lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))
        near = cv2.dilate(body.astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
        a[~near] = 0
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats((~body).astype(np.uint8))
        H, W = a.shape
        for i in range(1, n2):
            x, y, w, h, ar = st2[i]
            if x > 0 and y > 0 and x + w < W and y + h < H and ar < 0.002 * H * W:
                a[lab2 == i] = 1
    lo, hi, edgemix = CHOKE.get(grade, (0.04, 0.96, 0.5))
    a = np.clip((a - lo) / (hi - lo), 0, 1)
    if lo >= 0.2:
        a = cv2.GaussianBlur(a, (0, 0), 0.7)
    m = cv2.dilate((a > 0.02).astype(np.uint8), np.ones((25, 25), np.uint8)) * 255
    small = cv2.resize((I * 255).astype(np.uint8), None, fx=0.5, fy=0.5)
    ms = cv2.resize(m, None, fx=0.5, fy=0.5)
    B = cv2.resize(cv2.inpaint(small, ms, 9, cv2.INPAINT_TELEA), (I.shape[1], I.shape[0])).astype(np.float32) / 255
    B = cv2.GaussianBlur(B, (0, 0), 6)
    A3 = a[..., None]
    F = np.clip(np.where(A3 > 0.03, (I - (1 - A3) * B) / np.maximum(A3, 0.03), I), 0, 1)
    solid = (a > 0.95).astype(np.uint8)
    if solid.any():
        Fs = F.copy()
        Fs[solid == 0] = 0
        w = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 3)
        Fb = cv2.GaussianBlur(Fs, (0, 0), 3) / np.maximum(w[..., None], 1e-3)
        edge = (a > 0.02) & (a < 0.95)
        mix = np.clip((0.95 - a) / 0.93, 0, 1)[..., None] * edgemix

        def lum(X):
            return X[..., 0] * 0.114 + X[..., 1] * 0.587 + X[..., 2] * 0.299
        Fb2 = cv2.GaussianBlur(Fs, (0, 0), 9) / np.maximum(
            cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 9)[..., None], 1e-3)
        glow = (a < 0.9) & (a > 0.01) & ((lum(F) - lum(Fb2)) > 0.18)
        a = np.where(glow, a * 0.25, a)
        F = np.where(edge[..., None], F * (1 - mix) + Fb * mix, F)
    if lo >= 0.2:
        dist = cv2.distanceTransform((a < 0.95).astype(np.uint8), cv2.DIST_L2, 5)
        a = np.where((a < 0.6) & (dist > 6), 0, a)
    ring = cv2.dilate((a < 0.5).astype(np.uint8), np.ones((29, 29), np.uint8)).astype(bool) & (a > 0.01)
    gmax = np.maximum(F[..., 0], F[..., 2])
    F[..., 1] = np.where(ring & (F[..., 1] > gmax), gmax, F[..., 1])
    ex, con, wb = GRADES.get(grade, GRADES["none"])
    G = np.clip(F * ex, 0, 1)
    G = np.clip((G - 0.5) * con + 0.5, 0, 1)
    G = np.clip(G * np.array(wb[::-1], np.float32), 0, 1)
    ys, xs = np.where(a > 0.02)
    if not len(ys):
        raise StudioError("I could not find a person in that picture.")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba_bgr = (np.dstack([G, a])[y0:y1, x0:x1] * 255 + 0.5).astype(np.uint8)
    g = cv2.cvtColor((G[y0:y1, x0:x1] * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
    hh = max(8, int((y1 - y0) * 0.22))
    head, hm = g[:hh], a[y0:y0 + hh, x0:x1] > 0.9
    sc = 320 / max(1, head.shape[1])
    hs = cv2.resize(head, None, fx=sc, fy=sc)
    ms2 = cv2.resize(hm.astype(np.uint8), None, fx=sc, fy=sc).astype(bool)
    lapl = cv2.Laplacian(hs, cv2.CV_64F)
    lv = float(lapl[ms2].var()) if ms2.sum() > 100 else float(lapl.var())
    out = cv2.cvtColor(rgba_bgr, cv2.COLOR_BGRA2RGBA)
    return out, {"size": [int(x1 - x0), int(y1 - y0)], "head_sharpness": round(lv, 1), "cut_y": cut_y, "grade": grade}


def cutout(run, i):
    """Frame i of a matte run as a straight-alpha RGBA PIL image, made from the saved frame and alpha (the run keeps
    no full-colour cutouts unless asked: they took about 200 MB per 10 seconds)."""
    from PIL import Image
    run = Path(run)
    im = Image.open(run / "frames" / f"f{i:05d}.jpg").convert("RGB")
    a = Image.open(run / "alpha" / f"a{i:05d}.png").convert("L")
    return Image.fromarray(rgba(np.asarray(im), np.asarray(a)), "RGBA")


def contact_sheet(rgba_files, out, cols=6, tw=240):
    """Cutouts on a mid grey with a checker, so halos and holes show."""
    from PIL import Image, ImageDraw
    ims = [f if hasattr(f, "size") else Image.open(f) for f in rgba_files]      # files or PIL images
    if not ims:
        return None
    th = int(max(im.height * tw / im.width for im in ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), (40, 40, 40))
    for k, im in enumerate(ims):
        t = im.resize((tw, int(im.height * tw / im.width)), Image.LANCZOS)
        bg = Image.new("RGB", t.size, (128, 128, 128))
        d = ImageDraw.Draw(bg)
        for yy in range(0, t.height, 16):
            for xx in range(0, t.width, 16):
                if (xx // 16 + yy // 16) % 2:
                    d.rectangle([xx, yy, xx + 15, yy + 15], fill=(150, 150, 150))
        bg.paste(t, (0, 0), t)
        sheet.paste(bg, (8 + (k % cols) * (tw + 8), 8 + (k // cols) * (th + 8)))
    sheet.save(out)
    return out


def source_identity(src, t0, t1, fps, frames):
    """What a run's frames were taken from: the file (real path, size, change time) and the stretch. A cached run is
    reused only when all of it matches."""
    st = os.stat(src)
    return {"file": os.path.realpath(str(src)), "size": st.st_size, "mtime_ns": st.st_mtime_ns,
            "t0": round(float(t0), 3), "t1": round(float(t1), 3), "fps": float(fps),
            "limit": int(frames) if frames else None}


def _clear(folder, pattern):
    for f in folder.glob(pattern):
        f.unlink()


def extract_frames(run, src, ident):
    """The run's frames, taken out of the video once. Reused only when run/source.json says the same source and stretch
    finished extracting with exactly the frames on disk; otherwise (an interrupted extraction, a check run's single
    frame, a changed or replaced video) they are taken out again. His alpha mattes are kept when only the extraction
    was incomplete (same source and stretch: the same frames), and dropped when the source itself changed."""
    fdir, adir = run / "frames", run / "alpha"
    rec_f = run / "source.json"
    try:
        rec = json.loads(rec_f.read_text())
    except (OSError, ValueError):
        rec = None
    have = sorted(fdir.glob("f*.jpg"))
    old = (rec or {}).get("source") or {}
    same = bool(rec) and {k: v for k, v in old.items() if k != "limit"} == {k: v for k, v in ident.items() if k != "limit"}
    whole = same and old.get("limit") is None        # every frame of the stretch: good for any shorter check too
    if rec and rec.get("complete") and rec.get("frames") == len(have) and have and (old == ident or whole):
        return have
    _clear(fdir, "f*.jpg")
    if not same:
        _clear(adir, "a*.png")
        _clear(run / "rgba", "p*.png")
    write_json(rec_f, {"source": ident, "complete": False})
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{ident['t0']:.3f}", "-to", f"{ident['t1']:.3f}",
           *safe_input(str(src)), "-vf", f"fps={fps_str(ident['fps'])}", "-q:v", "2"]
    if ident["limit"]:
        cmd += ["-frames:v", str(ident["limit"])]
    r = subprocess.run(cmd + [str(fdir / "f%05d.jpg")], capture_output=True, text=True)
    have = sorted(fdir.glob("f*.jpg"))
    if r.returncode != 0 or not have:
        raise StudioError("I could not take the frames out of the video.")
    write_json(rec_f, {"source": ident, "complete": True, "frames": len(have)})
    return have


def _save_atomic(im, path, **kw):
    """Save a picture so a stopped run never leaves half a file that a later run would take as done."""
    tmp = path.with_name(f".tmp-{path.name}")
    im.save(tmp, format="PNG", **kw)
    os.replace(tmp, path)


def matte_clip(project, source=None, t0=None, t1=None, fps=None, frames=None, cutouts=None):
    """Matte a stretch of footage frame by frame (resumable: frames already done are skipped). Keeps the frames
    (`frames/f*.jpg`) and his alpha (`alpha/a*.png`); renderers combine them (`cutout(run, i)`). Full-colour cutouts
    (`rgba/p*.png`) are written only when `cutouts` is true, by default only for a short check run (`frames` given)."""
    _need()
    from PIL import Image
    if source:
        src = project.resolve(project.source(source)["file"])
    else:
        from . import passage as passage_mod
        src = project.resolve(passage_mod.load(project)["picture"])
    check_source(src)                       # never hand ffmpeg anything but a plain video
    meta = probe(src)
    if not meta["video"]:
        raise StudioError("That source has no picture to cut him out of.")
    fps = float(fps) if fps else nice_fps(meta["video"]["fps"])
    t0 = float(t0 or 0.0)
    t1 = float(t1) if t1 is not None else meta["duration"]
    run = project.path("matte", f"{source or 'passage'}-{t0:.2f}-{t1:.2f}-{fps:g}")
    cutouts = bool(frames) if cutouts is None else bool(cutouts)
    fdir, adir, pdir = run / "frames", run / "alpha", run / "rgba"
    for d in (fdir, adir) + ((pdir,) if cutouts else ()):
        d.mkdir(parents=True, exist_ok=True)
    todo = extract_frames(run, src, source_identity(src, t0, t1, fps, frames))
    if frames:
        todo = todo[: int(frames)]
    log = project.log_file("matte.log")
    with heavy.lock(f"matte {project.dir.name}") as info:
        tstart, done = time.time(), 0
        say("Cutting him out of the picture.")
        if any(not (adir / f"a{int(f.stem[1:]):05d}.png").exists() for f in todo):
            model()                         # loading it takes seconds: only when a frame still needs matting
        last = -10
        for k, f in enumerate(todo, 1):
            i = int(f.stem[1:])
            ap, pp = adir / f"a{i:05d}.png", pdir / f"p{i:05d}.png"
            if not ap.exists():
                im = Image.open(f).convert("RGB")
                a = alpha(im)
                _save_atomic(Image.fromarray(a, "L"), ap)
                done += 1
            if cutouts and not pp.exists():
                _save_atomic(cutout(run, i), pp, compress_level=1)
            pct = int(100 * k / len(todo))
            if pct >= last + 10:
                say(f"Cutting him out of the picture: {pct} percent")
                last = pct
        dt = time.time() - tstart
    step = max(1, len(todo) // 12)
    sheet = contact_sheet([cutout(run, int(f.stem[1:])) for f in todo[::step][:12]], run / "sheet.png")
    # the speed record belongs to the runs that did the work: a later version that reuses every frame (or resumes a
    # few) adds to it instead of replacing it with "0 frames matted"
    prev = {}
    if (run / "matte.json").exists():
        try:
            prev = json.loads((run / "matte.json").read_text())
        except ValueError:
            prev = {}
    matted = int(prev.get("matted", prev.get("matted_now") or 0)) + done
    seconds = float(prev.get("seconds") or 0.0) * (matted > done) + (dt if done else 0.0)
    info_rec = {"run": project.rel(run), "frames": len(todo), "matted_now": done, "matted": matted,
                "seconds": round(seconds, 1), "s_per_frame": round(seconds / matted, 3) if matted else None,
                "fps": fps, "t0": t0, "t1": t1,
                "device": str(_NET["dev"]) if done else prev.get("device", str(_NET.get("dev", ""))),
                "waited_for_lock": info["waited"], "sheet": project.rel(sheet)}
    if not done and prev:
        info_rec["reused"] = True
    write_json(run / "matte.json", info_rec)
    project.data.setdefault("mattes", [])
    project.data["mattes"] = [m for m in project.data["mattes"] if m.get("run") != info_rec["run"]] + [info_rec]
    project.save()
    log.open("a").write(json.dumps(info_rec) + "\n")
    say(f"He is cut out of {len(todo)} frames.")
    return info_rec


POSE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,59}")


def pose_name(name, photo):
    """The file name a new pose gets in his pose folder: his chosen name, or the photo's own name made plain."""
    if name is None:
        name = re.sub(r"[^a-z0-9-]+", "-", Path(photo).stem.lower()).strip("-")[:60] or "pose"
    if not POSE_NAME.fullmatch(str(name)):
        raise StudioError("A pose name may only use small letters, digits and dashes, for example bernard-front-a.")
    return str(name)


def matte_photo(file, name=None, cut_y=None, grade="none"):
    """One photo -> a clean cutout PNG in his pose folder (never anywhere else)."""
    name = pose_name(name, file)
    _need()
    import cv2
    from PIL import Image
    p = Path(file).expanduser()
    if not p.exists():
        raise StudioError(f'I could not find the photo "{file}".')
    check_image(p)                          # a real photo by its bytes, whatever its name
    if is_heic(p):                          # an iPhone photo: read through a JPEG copy in the studio's own folder
        import tempfile
        paths.home().mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=paths.home(), prefix=".heic-") as tmp:
            im = Image.open(heic_to_jpeg(p, Path(tmp) / "photo.jpg")).convert("RGB")
    else:
        im = Image.open(p).convert("RGB")
    with heavy.lock(f"matte-photo {p.name}"):
        say("Cutting him out of the photo.")
        a = alpha(im)
    bgr = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
    cut, rep = finish_cutout(bgr, a, cut_y, grade)
    out = paths.user_poses() / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(cut, "RGBA").save(out)
    rep["file"] = str(out)
    say(f'The cutout is saved as "{out.name}".')
    return rep
