"""studio ingest <project> <file-or-link>...

For each source: copy it into the project's sources/ (or download a YouTube or TikTok link with yt-dlp), then
  - transcribe with whisper.cpp medium.en, one word per segment, so every word has a start and an end,
  - a silence map from his voice's own loudness (10 ms steps, quiet = 25 dB under his speaking level, 80 ms or more),
  - a sharp-frame scan (Laplacian variance twice a second, captions masked out),
  - burned-in caption boxes (Apple Vision text recognition through ocrmac, once a second),
and write ingest/<name>.json. The words file is what `studio passage` reads.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from . import paths
from .errors import StudioError
from .project import write_json
from .util import need, probe, run, say
from .media import safe_input, check_any, heic_to_jpeg, is_heic

SR_ENV = 48000
HOP = 0.01
QUIET_DB = 25.0       # quiet = this far under his speaking level (90th percentile of the 10 ms loudness)
MIN_SILENCE = 0.08    # a real pause is 80 ms; a stop consonant's gap is shorter
FLOOR_PCT = 15        # the room's own sound: the 15th percentile of the 10 ms loudness over the whole recording
FLOOR_ABOVE = 6.0     # quiet reaches up to this far over the room's own sound...
QUIET_MIN_DB = 15.0   # ...but stays at least this far under his speaking level
AUDIO_EXT = {".wav", ".flac", ".mp3", ".m4a", ".aac", ".aif", ".aiff", ".ogg"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}


# ----------------------------------------------------------------------------------------------- audio
def decode_mono(path, sr=SR_ENV, ss=None, to=None):
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.4f}"]
    if to is not None:
        cmd += ["-to", f"{to:.4f}"]
    cmd += [*safe_input(str(path)), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise StudioError(f'I could not read the sound in "{Path(path).name}".')
    return np.frombuffer(r.stdout, np.float32).copy()


def envelope_db(x, sr=SR_ENV, hop=HOP):
    """Loudness in dB per 10 ms step (the measure voice_cuts.py cuts on)."""
    k = int(sr * hop)
    n = len(x) // k
    if n == 0:
        return np.array([-120.0])
    rms = np.sqrt(np.mean(x[:n * k].reshape(n, k) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def speaking_level(db):
    """His speaking level: the 90th percentile of the 10 ms loudness, leaving out the quietest fifth."""
    speech = db[db > np.percentile(db, 20)]
    return float(np.percentile(speech if len(speech) else db, 90))


def quiet_threshold(db, ref=None, quiet_db=QUIET_DB):
    """Loudness under which a 10 ms step counts as quiet. `quiet_db` under his speaking level `ref` (25 dB), raised
    to 6 dB over the measured room tone when the room is louder than that (a pause in a noisy room sits at the room's
    level, not 25 dB under him), and never closer than 15 dB to his speaking level."""
    ref = speaking_level(db) if ref is None else float(ref)
    floor = float(np.percentile(db, FLOOR_PCT))
    return float(min(max(ref - quiet_db, floor + FLOOR_ABOVE), ref - QUIET_MIN_DB))


def silence_map(db, hop=HOP, quiet_db=QUIET_DB, min_len=MIN_SILENCE):
    """Stretches of real quiet: [[start, end], ...] in seconds, plus the threshold used."""
    thr = quiet_threshold(db, quiet_db=quiet_db)
    q = db < thr
    out, i, n = [], 0, len(q)
    while i < n:
        if q[i]:
            j = i
            while j < n and q[j]:
                j += 1
            if (j - i) * hop >= min_len:
                out.append([round(i * hop, 3), round(j * hop, 3)])
            i = j
        else:
            i += 1
    return out, float(thr)


# ----------------------------------------------------------------------------------------------- transcription
def norm_token(w):
    return re.sub(r"[^a-z0-9$%']", "", w.lower())


def transcribe(wav16k, out_base, log=None, label="your video"):
    """whisper.cpp medium.en with one word per segment. Returns [{"w", "t0", "t1", "p"}] (seconds)."""
    need("whisper-cli", "The speech-to-text tool (whisper.cpp)")
    model = paths.whisper_model()
    if not model.exists():
        raise StudioError("The speech model is not downloaded yet. Type /studio-setup and I will fetch it.")
    cmd = ["whisper-cli", "-m", str(model), "-f", str(wav16k), "-l", "en", "-ml", "1", "-sow", "-oj", "-ojf",
           "-of", str(out_base), "-pp", "-np"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    last = -10
    tail = []
    for line in p.stdout:
        tail = (tail + [line])[-60:]
        m = re.search(r"progress\s*=\s*(\d+)%", line)
        if m:
            pct = int(m.group(1))
            if pct >= last + 10:
                say(f"Transcribing {label}: {pct} percent")
                last = pct
    rc = p.wait()
    if log:
        Path(log).open("a").write("$ " + " ".join(cmd) + "\n" + "".join(tail) + "\n")
    if rc != 0 or not Path(str(out_base) + ".json").exists():
        raise StudioError("Transcription failed. The details are in the project's logs folder.")
    return words_from_whisper_json(Path(str(out_base) + ".json"))


def words_from_whisper_json(path):
    d = json.loads(Path(path).read_text())
    words = []
    for seg in d.get("transcription", []):
        txt = seg.get("text", "").strip()
        off = seg.get("offsets", {})
        if not txt or txt.startswith("[") or txt.startswith("("):
            continue
        t0, t1 = off.get("from", 0) / 1000.0, off.get("to", 0) / 1000.0
        probs = [t.get("p", 1.0) for t in seg.get("tokens", []) if not t.get("text", "").startswith("[_")]
        p = float(np.mean(probs)) if probs else 1.0
        # whisper sometimes splits "$40,000" or "don't" across segments: glue a piece with no leading space
        raw = seg.get("text", "")
        if words and not raw[:1].isspace():
            words[-1]["w"] += txt
            words[-1]["t1"] = max(words[-1]["t1"], t1)
            continue
        if not norm_token(txt):
            if words:
                words[-1]["w"] += txt            # punctuation on its own
            continue
        words.append({"w": txt, "t0": round(t0, 3), "t1": round(max(t1, t0 + 0.02), 3), "p": round(p, 3)})
    words = [w for w in words if norm_token(w["w"])]
    for i, w in enumerate(words):
        w["i"] = i
    return words


# ----------------------------------------------------------------------------------------------- pictures
def sample_frames(path, every, width, duration):
    """Frames every `every` seconds in one ffmpeg pass (much faster than seeking per frame)."""
    vf = f"fps=1/{every},scale={width}:-2,format=rgb24"
    meta = probe(path)["video"]
    h = int(round(meta["h"] * width / meta["w"] / 2) * 2)
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *safe_input(str(path)), "-vf", vf, "-f", "rawvideo", "-"],
                       capture_output=True)
    if r.returncode != 0:
        raise StudioError("I could not read the pictures in this video.")
    n = len(r.stdout) // (width * h * 3)
    arr = np.frombuffer(r.stdout[:n * width * h * 3], np.uint8).reshape(n, h, width, 3)
    return [((k + 0.5) * every, arr[k]) for k in range(n)]


def caption_boxes(frames, level="fast"):
    """Apple Vision text boxes per sampled frame: [{"t", "boxes": [{"x","y","w","h","text","conf"}]}], boxes in
    0..1 of the frame with the origin top-left. Returns (samples, available)."""
    try:
        from ocrmac import ocrmac
        from PIL import Image
    except Exception:
        return [], False
    out = []
    for t, fr in frames:
        try:
            res = ocrmac.OCR(Image.fromarray(fr), recognition_level=level).recognize()
        except Exception:
            return out, False
        boxes = []
        for text, conf, (x, y, w, h) in res:
            boxes.append({"x": round(x, 4), "y": round(1 - y - h, 4), "w": round(w, 4), "h": round(h, 4),
                          "text": text, "conf": round(float(conf), 3)})
        out.append({"t": round(t, 2), "boxes": boxes})
    return out, True


def caption_band(samples, min_share=0.3):
    """Where burned-in captions live: the band (0..1, top-left origin) covered by text in at least `min_share` of
    the samples, or None. Kept out of crops and frame picks."""
    if not samples:
        return None
    rows = np.zeros(100)
    for s in samples:
        hit = np.zeros(100, bool)
        for b in s["boxes"]:
            if b["conf"] < 0.3 or len(b["text"].strip()) < 2:
                continue
            hit[int(b["y"] * 100):int(min(1.0, b["y"] + b["h"]) * 100) + 1] = True
        rows += hit
    share = rows / len(samples)
    on = np.where(share >= min_share)[0]
    if not len(on):
        return None
    y0, y1 = on.min() / 100, (on.max() + 1) / 100
    xs = [(b["x"], b["x"] + b["w"]) for s in samples for b in s["boxes"] if y0 <= b["y"] + b["h"] / 2 <= y1]
    x0 = min(x[0] for x in xs) if xs else 0.0
    x1 = max(x[1] for x in xs) if xs else 1.0
    return {"x": round(x0, 3), "y": round(y0, 3), "w": round(x1 - x0, 3), "h": round(y1 - y0, 3),
            "share": round(float(share[on].mean()), 2)}


def sharpness(frames, band=None):
    """Laplacian variance per sampled frame (higher = sharper), with any caption band masked out."""
    import cv2
    out = []
    for t, fr in frames:
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        if band:
            h = g.shape[0]
            g = g.copy()
            g[int(band["y"] * h):int((band["y"] + band["h"]) * h)] = int(np.median(g))
        out.append({"t": round(t, 2), "sharp": round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 1)})
    if out:
        vals = np.array([o["sharp"] for o in out])
        cut = np.percentile(vals, 80)
        for o in out:
            o["top"] = bool(o["sharp"] >= cut)
    return out


# ----------------------------------------------------------------------------------------------- bring a source in
def is_link(s):
    return bool(re.match(r"^https?://", s))


def fetch_link(url, dest_dir, log=None):
    need("yt-dlp", "The video downloader (yt-dlp)")
    say("Downloading the video from the link.")
    tmpl = str(Path(dest_dir) / "%(extractor)s-%(id)s.%(ext)s")
    r = run(["yt-dlp", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4", "-o", tmpl, "--no-playlist",
             "--print", "after_move:filepath", url], log=log, text=True)
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    got = Path(lines[-1]) if lines else None
    if not got or not got.is_file() or Path(dest_dir).resolve() not in got.resolve().parents:
        raise StudioError("The download did not produce a file. Check the link and try again.")
    return got


def source_name(path, taken):
    base = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(path).stem).strip("-").lower()[:40] or "source"
    name, k = base, 2
    while name in taken:
        name, k = f"{base}-{k}", k + 1
    return name


def ingest(project, items, link=False, scan=True):
    """Bring each file or link into the project and analyse it. Returns the list of ingest records."""
    need("ffmpeg", "ffmpeg")
    log = project.log_file("ingest.log")
    results = []
    for item in items:
        taken = {s["name"] for s in project.data["sources"]}
        if is_link(item):
            src_file = fetch_link(item, project.path("sources"), log)
            name = source_name(src_file, taken)
        else:
            p = Path(item).expanduser()
            if not p.exists():
                raise StudioError(f'I could not find the file "{item}".')
            name = source_name(p, taken)
            src_file = project.path("sources", name + p.suffix.lower())
            if not src_file.exists():
                if link:
                    src_file.symlink_to(p.resolve())
                else:
                    say(f'Copying "{p.name}" into the project.')
                    shutil.copy2(p, src_file)
        ext = src_file.suffix.lower()
        kind = "image" if ext in IMAGE_EXT else ("audio" if ext in AUDIO_EXT else "video")
        check_any(src_file, kind)               # real photos, plain audio or video only; never a playlist or a list of files
        if kind == "image" and is_heic(src_file):    # iPhone photos: a JPEG copy the studio can read, inside the project
            say(f'Turning "{src_file.name}" into a JPEG the studio can read.')
            jpg = name + ("-photo.jpg" if src_file.suffix.lower() in (".jpg", ".jpeg") else ".jpg")
            src_file = heic_to_jpeg(src_file, project.path("sources", jpg))
        rec = {"name": name, "file": project.rel(src_file), "kind": kind}
        if kind == "image":
            project.add_source(rec)
            results.append(rec)
            continue
        meta = probe(src_file)
        if meta["video"] is None and kind == "video":
            kind = rec["kind"] = "audio"
        rec.update({"duration": round(meta["duration"], 3), "video": meta["video"], "audio": meta["audio"]})
        if meta["audio"]:
            wav = project.path("ingest", f"{name}.16k.wav")
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(src_file), "-vn", "-ac", "1", "-ar", "16000", wav],
                log=log)
            words = transcribe(wav, project.path("ingest", f"{name}.whisper"), log)
            say(f"Heard {len(words)} words.")
            x = decode_mono(src_file)
            db = envelope_db(x)
            sil, thr = silence_map(db)
            rec.update({"words": words, "text": " ".join(w["w"] for w in words),
                        "silences": sil, "quiet_threshold_db": round(thr, 1)})
        else:
            rec.update({"words": [], "text": "", "silences": []})
        if kind == "video" and scan:
            say("Looking for the sharpest frames and any captions burned into the picture.")
            every = 1.0 if meta["duration"] <= 600 else meta["duration"] / 600
            frames = sample_frames(src_file, every / 2, 480, meta["duration"])
            caps, ok = caption_boxes(frames[::2])
            band = caption_band(caps) if ok else None
            rec.update({"sharp": sharpness(frames, band), "captions": {"available": ok, "band": band,
                                                                       "samples": caps}})
            if band:
                say("Found captions burned into the picture; I will keep them out of crops and frame picks.")
        write_json(project.path("ingest", f"{name}.json"), rec)
        entry = {k: rec[k] for k in ("name", "file", "kind")}
        entry["ingest"] = f"ingest/{name}.json"
        entry["duration"] = rec.get("duration")
        project.add_source(entry)
        results.append(rec)
        say(f'"{name}" is ready.')
    return results


def load(project, name):
    f = project.path("ingest", f"{name}.json")
    if not f.exists():
        raise StudioError(f'"{name}" has not been read yet. Run studio ingest on it first.')
    return json.loads(f.read_text())
