"""studio qa <project> --version N  ->  v<N>/qa.json and v<N>/sheet.png (CONTRACT section 6)

Checks, each measured on the real output:
  words     the sound transcribed back with whisper.cpp: every passage word present, in order (number forms
            normalised; a misheard word counts, a missing one does not)
  loudness  -14 LUFS integrated (plus or minus 0.5), true peak at or under -1.5 dBTP
  safe      text boxes from layout.json inside the safe zones (reels and animated: 80 px sides, below 220, above the
            bottom 300; carousels: 80 px sides)
  red       one red per frame: red elements per beat from layout.json (touching red text and marks count as one),
            plus a pixel scan of sampled frames (reported as a warning to look at: footage can hold red of its own)
  his_words every on-screen text is his words (tokens in the passage) or one of the style's labels
  streams   H.264 High, yuv420p, bt709, AAC 48 kHz stereo, the style's size, no 4K; slides at the style's size
  sheet     a frame at every beat, for the reviewer and for him
Style hooks: a renderer module may define `qa_extra(project, version_dir, layout) -> {name: {"pass": bool, ...}}`.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from . import brand as brand_mod
from . import ingest, sound
from . import passage as passage_mod
from .errors import StudioError
from .layout import load as load_layout
from .project import write_json
from .util import probe, say
from .words import compare, phrase_tokens, plain, token_map
from .media import safe_input

RED_RGB = [(185, 28, 28), (196, 39, 39)]
SHEET_COLS = 6
THUMB = (270, 480)


# ----------------------------------------------------------------------------------------------- single checks
def check_streams(mp4, kind, w, h):
    m = probe(mp4)
    v, a = m["video"] or {}, m["audio"] or {}
    problems = []
    if v.get("codec") != "h264":
        problems.append(f"video codec is {v.get('codec')}, not H.264")
    if (v.get("profile") or "").lower() != "high":
        problems.append(f"H.264 profile is {v.get('profile')}, not High")
    if v.get("pix_fmt") != "yuv420p":
        problems.append(f"pixel format is {v.get('pix_fmt')}")
    for k in ("color_primaries", "color_transfer", "color_space"):
        if v.get(k) != "bt709":
            problems.append(f"{k.replace('_', ' ')} is {v.get(k)}, not bt709")
    if (v.get("w"), v.get("h")) != (w, h):
        problems.append(f"size is {v.get('w')}x{v.get('h')}, not {w}x{h}")
    if max(v.get("w") or 0, v.get("h") or 0) > 2000:
        problems.append("larger than 1080p")
    if a.get("codec") != "aac" or a.get("sample_rate") != 48000 or a.get("channels") != 2:
        problems.append(f"sound is {a.get('codec')} {a.get('sample_rate')} Hz {a.get('channels')} channels, "
                        "not AAC 48 kHz stereo")
    return {"pass": not problems, "problems": problems, "video": v, "audio": a, "duration": m["duration"]}


def check_loudness(mp4, settings):
    I, tp = sound.measure(mp4)
    ok_i = abs(I - settings["lufs"]) <= settings["lufs_tolerance"]
    ok_tp = tp <= settings["true_peak_max"]
    return {"pass": ok_i and ok_tp, "lufs": I, "true_peak": tp, "target": settings["lufs"],
            "tolerance": settings["lufs_tolerance"], "true_peak_max": settings["true_peak_max"]}


def hear(audio_file, work, log, label, cache=None):
    """whisper.cpp words of a sound or video file; cached in `cache` (JSON) while the file is unchanged."""
    st = Path(audio_file).stat()
    key = {"size": st.st_size, "mtime": int(st.st_mtime)}
    if cache and Path(cache).exists():
        c = json.loads(Path(cache).read_text())
        if c.get("key") == key:
            return c["words"]
    wav = work / "qa-16k.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(str(audio_file)), "-vn", "-ac", "1",
                    "-ar", "16000", str(wav)], check=True)
    words = ingest.transcribe(wav, work / "qa-whisper", log, label=label)
    if cache:
        write_json(cache, {"key": key, "words": words})
    return words


def edge_words(passage):
    """The first and last word of every cut segment: where a cut can clip a word."""
    by_seg = {}
    for w in passage["words"]:
        by_seg.setdefault(w.get("seg", 0), []).append(w["i"])
    return {i for ids in by_seg.values() for i in (ids[0], ids[-1])}


def missing_words(words, heard):
    """Indices of passage words not heard, in order. A word fixed with studio fix-word also counts as heard when
    whisper hears it the way it first misheard it ("wait" for "weight"): missing only when missing both ways."""
    from .fixword import heard_alternative
    said, owner = token_map(words)
    miss = {owner[m["pos"]] for m in compare(said, heard)[0]}
    if miss and any(w.get("fix") is not None for w in words):
        alt = heard_alternative(words)
        toks, own = [], []
        for k, (text, idx) in enumerate(alt):
            for t in plain(text):
                toks.append(t)
                own.append(k)
        miss_alt = set()
        for m in compare(toks, heard)[0]:
            miss_alt.update(alt[own[m["pos"]]][1])
        miss &= miss_alt
    return miss


MASKED_MAX = 0.1     # at most one word in ten may be excused as "heard in his voice as mixed"


def check_words(mp4, passage, work, log=None, voice_files=(), cache_dir=None, mix_voice=None):
    """Every passage word heard back in the finished sound, in order.

    Two excuses, neither ever for the first or last word of a cut segment (where a cut could have clipped it):
    - "elided": a word he swallows (a 40 ms "of") is borderline for whisper in his own recording too. Missing from the
      final and also dropped by any of his passage recordings (`voice_files`: the raw and the cleaned voice, both
      before any of our sound) -> excused.
    - "masked": music under a short word can make whisper hear two words as one ("I crossed" as "across"). Missing
      from the final but heard in his voice as mixed (`mix_voice`: the same voice, placement, length and end fade as
      the final, without bed or effects) -> excused, with the reason. Never more than one word in ten: more than that
      means the bed is burying him, and they all count as missing."""
    heard_words = hear(mp4, work, log, "the finished sound")
    said, _ = token_map(passage["words"])
    heard, _ = token_map(heard_words)
    miss_set = missing_words(passage["words"], heard)
    matched = len(said) - sum(len(plain(passage["words"][i]["w"])) for i in miss_set)
    miss_words = sorted(miss_set)
    elided, masked, notes = [], [], []
    edges = edge_words(passage)
    if miss_words:
        not_in_voice = set()
        for vf in voice_files:
            if vf and Path(vf).exists():
                cache = Path(cache_dir) / f"heard-{Path(vf).stem}.json" if cache_dir else None
                in_voice, _ = token_map(hear(vf, work, log, "his voice", cache))
                not_in_voice |= missing_words(passage["words"], in_voice)
        elided = [i for i in miss_words if i in not_in_voice and i not in edges]
        miss_words = [i for i in miss_words if i not in elided]
    if miss_words and mix_voice and Path(mix_voice).exists():
        in_mix_voice, _ = token_map(hear(mix_voice, work, log, "his voice as mixed"))
        lost_there = missing_words(passage["words"], in_mix_voice)
        cand = [i for i in miss_words if i not in lost_there and i not in edges]
        limit = int(len(passage["words"]) * MASKED_MAX)
        if len(cand) > limit:
            notes.append(f"{len(cand)} words are heard in his voice alone but lost under the music, more than one "
                         f"in ten of {len(passage['words'])}: the bed is too loud, so they count as missing.")
        else:
            masked = cand
            miss_words = [i for i in miss_words if i not in masked]
    out = {"pass": not miss_words, "said": len(said), "matched": matched,
           "missing": [{"word": passage["words"][i]["w"], "i": i} for i in miss_words],
           "elided": [{"word": passage["words"][i]["w"], "i": i} for i in elided],
           "masked": [{"word": passage["words"][i]["w"], "i": i,
                       "reason": "heard in his voice as mixed (no music or effects), lost in the finished sound: "
                                 "whisper merges it with a word beside it when the music is under it"}
                      for i in masked],
           "heard": " ".join(w["w"] for w in heard_words)}
    if notes:
        out["notes"] = notes
    return out


def check_safe(layout, safe):
    W, H = layout["format"]["w"], layout["format"]["h"]
    carousel = layout["kind"] == "carousel"
    x0, x1 = safe["side"], W - safe["side"]
    y0, y1 = (0, H) if carousel else (safe["top"], H - safe["bottom"])
    bad = []
    for b in layout["beats"]:
        for t in b["texts"]:
            x, y, w, h = t["box"]
            if x < x0 - 0.5 or x + w > x1 + 0.5 or y < y0 - 0.5 or y + h > y1 + 0.5:
                bad.append({"beat": b["i"], "text": t["text"], "box": t["box"]})
    return {"pass": not bad, "zone": [x0, y0, x1, y1], "outside": bad}


def _near(a, b, gap=40):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax > bx + bw + gap or bx > ax + aw + gap or ay > by + bh + gap or by > ay + ah + gap)


def red_groups(beat):
    boxes = [t["box"] for t in beat["texts"] if t.get("red")] + [m["box"] for m in beat["marks"] if m.get("red")]
    groups = []
    for bx in boxes:
        hit = [g for g in groups if any(_near(bx, o) for o in g)]
        merged = [bx] + [o for g in hit for o in g]
        groups = [g for g in groups if g not in hit] + [merged]
    return len(groups)


def red_mask(rgb):
    x = rgb.astype(np.int16)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    d = np.min([np.abs(x - np.array(c)).sum(-1) for c in RED_RGB], axis=0)
    return (d < 70) & (r > 120) & (r > 2.2 * g) & (r > 2.2 * b)


def red_clusters(rgb, min_area=60):
    import cv2
    m = red_mask(rgb).astype(np.uint8)
    if m.sum() < min_area:
        return 0
    k = max(9, rgb.shape[1] // 25) | 1
    d = cv2.dilate(m, np.ones((k, k), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(d)
    count = 0
    for i in range(1, n):
        if (m[lab == i]).sum() >= min_area:
            count += 1
    return count


def check_red(layout, frames):
    per_beat = [{"beat": b["i"], "reds": red_groups(b)} for b in layout["beats"]]
    over = [p for p in per_beat if p["reds"] > 1]
    pix = []
    for t, img in frames:
        c = red_clusters(img)
        if c > 1:
            pix.append({"t": round(t, 2), "red_areas": c})
    return {"pass": not over, "beats_with_more_than_one_red": over,
            "warn": bool(pix), "frames_with_more_than_one_red_area": pix}


def his_other_words(project):
    """Carousels only: slides may quote anything he said in the project's recordings (every ingested transcript)
    or lines he typed himself (studio lines)."""
    from .lines import all_words
    return all_words(project)


def check_his_words(layout, passage, labels, extra_words=()):
    have = set()
    for w in passage["words"]:
        have.update(plain(w["w"]))
    for w in extra_words:
        have.update(plain(w))
    lab = {" ".join(plain(x)) for x in labels} | {x.strip().lower() for x in labels}
    bad = []
    for b in layout["beats"]:
        for t in b["texts"]:
            if t["role"] == "label":
                if t["text"].strip().lower() not in lab and " ".join(plain(t["text"])) not in lab:
                    bad.append({"beat": b["i"], "text": t["text"], "why": "not one of the style's labels"})
                continue
            extra = [tok for tok in phrase_tokens(t["text"]) if tok not in have]   # word by word: "10 people"
            if extra:
                bad.append({"beat": b["i"], "text": t["text"], "why": "not in his words: " + " ".join(extra)})
    return {"pass": not bad, "problems": bad}


# ----------------------------------------------------------------------------------------------- frames and sheet
def beat_times(layout, duration):
    ts = []
    for b in layout["beats"]:
        t0, t1 = b["t0"], max(b["t1"], b["t0"])
        ts.append((b, min(t0 + 0.4, (t0 + t1) / 2) if t1 > t0 else t0))
    if not ts:
        ts = [(None, t) for t in np.arange(0.5, max(duration, 0.6), 1.5)]
    return [(b, min(max(0.0, t), max(0.0, duration - 0.05))) for b, t in ts]


def grab(mp4, t, w=None):
    vf = "scale=in_color_matrix=bt709:in_range=tv" + (f",scale={w}:-2" if w else "")
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", *safe_input(str(mp4)), "-frames:v", "1",
                        "-vf", vf, "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    from PIL import Image
    import io
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"))


def make_sheet(items, out, fmt_w, fmt_h, safe=None, carousel=False):
    """items: [(label, RGB array)]. A grid of thumbnails with a caption under each and faint safe-zone lines."""
    from PIL import Image, ImageDraw
    tw = THUMB[0]
    th = int(round(tw * fmt_h / fmt_w))
    cols = min(SHEET_COLS, max(1, len(items)))
    rows = int(np.ceil(len(items) / cols)) or 1
    cap = 34
    sheet = Image.new("RGB", (cols * (tw + 12) + 12, rows * (th + cap + 12) + 12), (24, 23, 22))
    d = ImageDraw.Draw(sheet)
    f = brand_mod.font("body", 15)
    sx = tw / fmt_w
    for k, (label, img) in enumerate(items):
        x = 12 + (k % cols) * (tw + 12)
        y = 12 + (k // cols) * (th + cap + 12)
        if img is not None:
            sheet.paste(Image.fromarray(img).resize((tw, th), Image.LANCZOS), (x, y))
        if safe:
            g = (90, 200, 120)
            l, r = x + safe["side"] * sx, x + (fmt_w - safe["side"]) * sx
            d.line([(l, y), (l, y + th)], fill=g)
            d.line([(r, y), (r, y + th)], fill=g)
            if not carousel:
                for yy in (safe["top"], fmt_h - safe["bottom"]):
                    d.line([(x, y + yy * sx), (x + tw, y + yy * sx)], fill=g)
        d.text((x, y + th + 7), label[:40], font=f, fill=(225, 220, 210))
    sheet.save(out)
    return out


# ----------------------------------------------------------------------------------------------- run
def run(project, n):
    from .render import style_labels, style_module
    entry = project.version(n)
    vdir = project.version_dir(n)
    out = project.resolve(entry["output"])
    if not out.exists():
        raise StudioError(f"Version {n} has no output file to check.")
    layout = load_layout(vdir / "layout.json")
    try:
        passage = passage_mod.load(project)
    except StudioError:
        passage = None
    if passage is None and layout["kind"] == "carousel":
        passage = {"words": []}                 # typed lines only: his words come from his_other_words below
    b = brand_mod.load()
    labels = style_labels(entry["style"])
    work = vdir / "qa"
    work.mkdir(exist_ok=True)
    log = project.log_file(f"qa-v{n}.log")
    checks = {}
    say(f"Checking version {n}.")
    W, H = layout["format"]["w"], layout["format"]["h"]
    videos = [out] if out.is_file() and out.suffix.lower() in (".mp4", ".mov") else \
        sorted(p for p in out.glob("*.mp4")) if out.is_dir() else []
    slides = sorted(p for p in out.glob("*.png")) if out.is_dir() else []
    items, frames = [], []
    if videos:
        mp4 = videos[0]
        if out.is_file():
            sw, sh = W, H
        else:                       # an animated cover beside slides: its own size, set by the style
            v = probe(mp4)["video"] or {}
            sw, sh = v.get("w"), v.get("h")
        checks["streams"] = check_streams(mp4, layout["kind"], sw, sh)
        checks["loudness"] = check_loudness(mp4, b["sound"])
        say(f"Loudness {checks['loudness']['lufs']:.1f} LUFS, true peak {checks['loudness']['true_peak']:.1f} dBTP.")
        if passage and passage.get("words"):
            vfs = [project.resolve(v) for v in (passage.get("voice"), passage.get("voice_clean")) if v]
            mix_voice = sound.voice_stem_path(vdir / "mix.wav") if out.is_file() else None
            checks["words"] = check_words(mp4, passage, work, log, vfs, project.path("passage"), mix_voice)
            wc = checks["words"]
            if not wc["pass"]:
                say(f"Words missing when heard back: {', '.join(m['word'] for m in wc['missing'])}.")
            else:
                say("Every word heard back, in order." + (
                    " Except words he says very softly in his own recording too: "
                    f"{', '.join(m['word'] for m in wc['elided'])}." if wc["elided"] else "") + (
                    " The music under it hides these from the checker, but they are clear in his voice as mixed: "
                    f"{', '.join(m['word'] for m in wc['masked'])}." if wc["masked"] else ""))
        dur = checks["streams"]["duration"]
        for bt, t in beat_times(layout, dur):
            img = grab(mp4, t)
            frames.append((t, img[::2, ::2] if img is not None else None))
            lab = f"{t:.1f}s  " + (f"beat {bt['i']} {bt['kind']}" if bt else "")
            items.append((lab, img))
        for t in np.arange(0.5, dur, 1.0):
            img = grab(mp4, float(t), 540)
            if img is not None:
                frames.append((float(t), img))
    if slides:
        from PIL import Image
        bad = []
        for k, s in enumerate(slides):
            im = Image.open(s)
            if im.size != (W, H):
                bad.append(f"{s.name} is {im.size[0]}x{im.size[1]}, not {W}x{H}")
            arr = np.asarray(im.convert("RGB"))
            items.append((s.stem, arr))
            frames.append((float(k), arr[::2, ::2]))
        checks["slides"] = {"pass": not bad, "count": len(slides), "problems": bad}
    frames = [(t, f) for t, f in frames if f is not None]
    checks["safe"] = check_safe(layout, b["safe"])
    checks["red"] = check_red(layout, frames)
    if passage:
        extra = his_other_words(project) if layout["kind"] == "carousel" else ()
        checks["his_words"] = check_his_words(layout, passage, labels, extra)
    try:
        mod = style_module(entry["style"])
        if hasattr(mod, "qa_extra"):
            checks.update(mod.qa_extra(project, vdir, layout) or {})
    except StudioError:
        pass
    make_sheet(items, vdir / "sheet.png", W, H, b["safe"], layout["kind"] == "carousel")
    ok = all(c.get("pass", True) for c in checks.values())
    report = {"version": n, "style": entry["style"], "output": entry["output"], "pass": ok,
              "checks": checks, "sheet": f"v{n}/sheet.png",
              "warnings": [k for k, c in checks.items() if c.get("warn")]}
    write_json(vdir / "qa.json", report)
    entry["qa"] = {"pass": ok, "file": f"v{n}/qa.json", "sheet": f"v{n}/sheet.png"}
    project.set_version(entry)
    for k, c in checks.items():
        if not c.get("pass", True):
            say(f"Not passing: {k}.")
    say("All checks pass." if ok else "Some checks do not pass yet; the details are in qa.json.")
    return report
