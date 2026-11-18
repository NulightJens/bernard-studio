"""studio passage <project> --source <name> --from "<first words>" --to "<last words>" [--from .. --to ..]
                                           or --t0 <s> --t1 <s> [--t0 .. --t1 ..]

Cuts the words he picked out of a source, only inside real pauses (port of v8 voice_cuts.py): the start is the quiet
just before the first word, the end the first stretch of quiet after the last word, never past the next word. Writes
passage/passage.json (CONTRACT section 4), passage/voice.wav (48 kHz mono) and passage/picture.mp4 (for video).
Several ranges are joined in order with a short breath (`gap`) between them.
"""
import json

import numpy as np

from . import align, ingest
from .errors import StudioError
from .project import write_json
from .util import fps_str, need, nice_fps, run, say
from .words import find_phrase
from .media import safe_input

SR = 48000
HOP = 0.01
FADE = 0.008          # 8 ms fade at every cut (all cuts sit in measured pauses)
GAP = 0.30            # breath between joined ranges


def cut_bounds(db, s, e, prev_end, prev_start, next_start, nxt2, hop=HOP):
    """Port of voice_cuts.py: cut points for a run of words that starts at `s` and ends at `e` (whisper times),
    snapped to his voice's own loudness `db` (dB per 10 ms). Returns (start, end, start_in_pause, end_in_pause):
    the flags say whether a real pause was found, or the cut fell back to the quietest point between words."""
    n = len(db)
    a, b = max(0, int(s / hop)), min(n, int(e / hop) + 1)
    ref = np.percentile(db[a:b], 90) if b > a else np.max(db)
    thr = ingest.quiet_threshold(db, ref)          # follows the room tone in a noisy room
    # start: walk back from the first word to 80 ms of quiet; else the quietest point since the previous word
    # The search may reach back into the previous word's span (to just after its start), not only to its end:
    # whisper.cpp often gives the previous word the pause and the first word too ("thing." 0.84-1.71 over a pause at
    # 1.22-1.42 and "This" at 1.43). An 80 ms quiet run inside a single word is rare, so a pause found there is the
    # real gap before the first word. (voice_cuts.py stopped at the previous word's end, which suited whisper times
    # that run short, not glued ones.)
    k, lo, start = int(s / hop), int(max(prev_start + 0.05, s - 0.8) / hop), None
    while k - 8 >= max(lo, 0):
        if np.all(db[k - 8:k] < thr):
            start = k * hop - 0.01
            break
        k -= 1
    start_quiet = start is not None
    if start is None:
        l0 = int(max(0.0, prev_start + 0.05, s - 0.15) / hop)
        l1 = int((s + 0.02) / hop) + 1
        start = (l0 + int(np.argmin(db[l0:l1]))) * hop if l1 > l0 and l0 < n else max(0.0, s - 0.03)
    # end: walk forward from the last word to 60 ms of quiet; else the quietest point before the next word ends
    # (voice_cuts.py bounded this walk by the word after next; bounded here by the next word's onset, as its docstring
    # promises "never past the next word")
    k, hi, end = int(e / hop), int(min(e + 1.0, next_start) / hop), None
    while k + 6 <= min(hi, n):
        if np.all(db[k:k + 6] < thr):
            end = k * hop + 0.05
            break
        k += 1
    end_quiet = end is not None
    if end is None:
        a0, b0 = int(e / hop), min(n, int(min(next_start + 0.25, nxt2) / hop) + 1)
        end = (a0 + int(np.argmin(db[a0:b0]))) * hop if b0 > a0 else e
    return round(max(0.0, start), 3), round(end, 3), start_quiet, end_quiet


def plain_tokens(heard):
    from .words import token_map
    return token_map(heard)[0]


def word_range_for_times(words, t0, t1):
    inside = [w["i"] for w in words if w["t0"] >= t0 - 0.05 and w["t1"] <= t1 + 0.05]
    if not inside:
        raise StudioError(f"No whole words fall between {t0:.1f} and {t1:.1f} seconds.")
    return inside[0], inside[-1]


def early_end(db, W, i0, i1, e, thr, hop=HOP):
    """A pause inside the last word's own span, for when whisper put the last word in the quiet after it ("it." at
    12.72 to 12.88 in a pause that runs 12.46 to 12.85, with a breath at 12.85): the first 60 ms of quiet after the
    word before it starts. Returns the end there, or None. Only a candidate: plan_segments keeps it only when the
    words are still heard from a cut there."""
    if i1 <= i0:
        return None
    k, hi = int(W[i1 - 1]["t0"] / hop) + 1, min(len(db), int(e / hop))
    while k + 6 <= hi:
        if np.all(db[k:k + 6] < thr):
            return round(k * hop + 0.05, 3)
        k += 1
    return None


def plan_segments(words, db, ranges, hears=None):
    """ranges: [(i0, i1)] word index ranges in order. Returns segments [{"in","out","i0","i1"}] on the source clock.
    hears(t0, t1): optional, the words whisper hears in that stretch of the source; used to check an early end."""
    from .qa import missing_words
    segs = []
    thr = ingest.quiet_threshold(db)
    for i0, i1 in ranges:
        if i1 < i0:
            raise StudioError("The last words come before the first words. Check the order of --from and --to.")
        # whisper.cpp glues each word's end to the next word's start, so the pause hides inside the word before it:
        # pull the edges of the words around the cut in to his voice's own loudness first
        lo, hi = max(0, i0 - 1), min(len(words), i1 + 3)
        local = align.energy_correct(words[lo:hi], db, thr)
        W = {lo + k: w for k, w in enumerate(local)}
        s, e = W[i0]["t0"], W[i1]["t1"]
        prev_end = W[i0 - 1]["t1"] if i0 > 0 else 0.0
        prev_start = W[i0 - 1]["t0"] if i0 > 0 else 0.0
        has_next = i1 + 1 < len(words)
        next_start = W[i1 + 1]["t0"] if has_next else e + 2.0
        nxt2 = W[i1 + 2]["t0"] if i1 + 2 < len(words) else next_start + 2.0
        start, end, sq, eq = cut_bounds(db, s, e, prev_end, prev_start, next_start, nxt2)
        if has_next:
            end = min(end, next_start - 0.01)
        if not eq and has_next and hears is not None:
            cand = early_end(db, W, i0, i1, e, thr)
            if cand is not None:
                t0 = max(start, cand - 3.0)                 # the last few seconds are enough to hear the last words
                tail = [w for w in words[i0:i1 + 1] if w["t0"] >= t0 + 0.3]
                if tail and not missing_words(tail, plain_tokens(hears(t0, cand))):
                    end, eq, e = cand, True, cand
        segs.append({"in": round(start, 3), "out": round(max(end, e), 3), "i0": i0, "i1": i1,
                     "pause_before": bool(sq or i0 == 0), "pause_after": bool(eq or not has_next)})
    for a, b in zip(segs, segs[1:]):
        if b["in"] < a["out"]:
            raise StudioError("Two of the ranges overlap. Pick ranges that do not share words.")
    return segs


def place_segments(segs, fps, gap=GAP):
    """Give each segment its place on the passage clock, starting on a frame so picture and voice stay exact."""
    at = 0.0
    for k, sg in enumerate(segs):
        sg["at"] = round(at, 4)
        frames = int(round((sg["out"] - sg["in"]) * fps))
        sg["frames"] = frames
        at += frames / fps
        if k + 1 < len(segs):
            g = int(round(gap * fps))
            sg["gap_frames"] = g
            at += g / fps
        else:
            sg["gap_frames"] = 0
    return round(at, 4)


def assemble_voice(x, segs, total, sr=SR):
    """The passage's voice: each segment at its place, 8 ms fades at every cut."""
    out = np.zeros(int(round(total * sr)) + 1, np.float32)
    k = int(FADE * sr)
    for sg in segs:
        a, b = int(round(sg["in"] * sr)), int(round(sg["out"] * sr))
        seg = x[a:b].copy()
        if len(seg) > 2 * k:
            seg[:k] *= np.linspace(0, 1, k)
            seg[-k:] *= np.linspace(1, 0, k)
        i0 = int(round(sg["at"] * sr))
        m = min(len(seg), len(out) - i0)
        out[i0:i0 + m] += seg[:m]
    return out


def write_wav(path, x, sr=SR, channels=1):
    import subprocess
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac", str(channels),
                        "-i", "-", "-c:a", "pcm_s24le", str(path)], input=np.ascontiguousarray(x, np.float32).tobytes())
    if r.returncode != 0:
        raise StudioError("I could not write a sound file.")


def cut_picture(src, segs, fps, out, log=None):
    """picture.mp4: the same segments of the picture, each running on through its breath, H.264 at the passage rate."""
    parts, labels = [], []
    for k, sg in enumerate(segs):
        n = sg["frames"] + sg["gap_frames"]
        parts.append(f"[0:v]trim=start={sg['in']:.4f},setpts=PTS-STARTPTS,fps={fps_str(fps)},"
                     f"trim=end_frame={n},setpts=PTS-STARTPTS[v{k}]")
        labels.append(f"[v{k}]")
    fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(segs)}:v=1:a=0,format=yuv420p[out]"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(src), "-filter_complex", fc, "-map", "[out]", "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-r", fps_str(fps), out], log=log)


def build(project, source, phrases=None, times=None, gap=GAP, refine=True):
    """Make the passage. phrases: [(first words, last words)]; times: [(t0, t1)] seconds on the source."""
    need("ffmpeg", "ffmpeg")
    rec = ingest.load(project, source)
    words = rec.get("words") or []
    if not words:
        raise StudioError(f'"{source}" has no speech in it that I could hear.')
    src = project.resolve(rec["file"])
    log = project.log_file("passage.log")
    ranges, after = [], 0
    for first, last in phrases or []:
        i0, _ = find_phrase(words, first, after)
        _, i1 = find_phrase(words, last, i0)
        ranges.append((i0, i1))
        after = i1 + 1
    for t0, t1 in times or []:
        ranges.append(word_range_for_times(words, float(t0), float(t1)))
    if not ranges:
        raise StudioError("Tell me which words to use: --from and --to, or --t0 and --t1.")
    say("Finding the real pauses around his words.")
    x = ingest.decode_mono(src)
    db = ingest.envelope_db(x)
    work = project.path("passage") / "work"

    def hears(t0, t1):              # whisper on a stretch of the source, half a second of quiet after it
        work.mkdir(parents=True, exist_ok=True)
        y = np.concatenate([x[int(t0 * SR):int(t1 * SR)], np.zeros(SR // 2, np.float32)])
        write_wav(work / "tail-48k.wav", y)
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(str(work / "tail-48k.wav")), "-ar", "16000",
             str(work / "tail.wav")])
        return ingest.transcribe(work / "tail.wav", work / "tail", log, label="the end of the cut")

    segs = plan_segments(words, db, ranges, hears)
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    video = rec.get("video")
    fps = nice_fps(video["fps"]) if video else 24.0
    total = place_segments(segs, fps, gap)
    voice = assemble_voice(x, segs, total)
    pdir = project.path("passage")
    pdir.mkdir(exist_ok=True)
    write_wav(pdir / "voice.wav", voice)

    # words on the passage clock
    pwords = []
    for k, sg in enumerate(segs):
        for i in range(sg["i0"], sg["i1"] + 1):
            w = words[i]
            pwords.append({"i": len(pwords), "w": w["w"], "seg": k,
                           "t0": round(max(0.0, w["t0"] - sg["in"]) + sg["at"], 3),
                           "t1": round(min(w["t1"], sg["out"]) - sg["in"] + sg["at"], 3), "src": w["i"]})
            pwords[-1].update({k: w[k] for k in ("fix", "fix_part", "heard") if k in w})   # studio fix-word
    method = "whisper"
    if refine:
        pdb = ingest.envelope_db(voice)
        thr = ingest.quiet_threshold(pdb) if len(pdb) > 10 else -60
        if align.available():
            say("Lining up every word with the sound.")
            try:
                x16 = ingest.decode_mono(pdir / "voice.wav", 16000)
                for k, sg in enumerate(segs):
                    ws = [w for w in pwords if w["seg"] == k]
                    a = int(sg["at"] * 16000)
                    b = int((sg["at"] + sg["out"] - sg["in"]) * 16000)
                    for w, (t0, t1) in zip(ws, align.force_align(x16[a:b], ws, sg["at"])):
                        w["t0"], w["t1"] = t0, t1
                method = "forced-alignment"
            except Exception as e:  # keep going on whisper times; note why in the log
                log.open("a").write(f"forced alignment failed, using whisper plus loudness: {e!r}\n")
        if method == "whisper":
            fixed = energy_correct_by_segment(pwords, segs, pdb, thr)
            for w, f in zip(pwords, fixed):
                w["t0"], w["t1"] = f["t0"], f["t1"]
            method = "whisper+energy"

    if video:
        say("Cutting the picture to match.")
        cut_picture(src, segs, fps, pdir / "picture.mp4", log)
    data = {"source": rec["file"], "source_name": source,
            "segments": [{"in": s["in"], "out": s["out"], "at": s["at"], "pause_before": s["pause_before"],
                          "pause_after": s["pause_after"]} for s in segs],
            "duration": total, "words": pwords, "text": " ".join(w["w"] for w in pwords),
            "voice": "passage/voice.wav", "picture": "passage/picture.mp4" if video else None,
            "fps": round(fps, 4), "size": [video["w"], video["h"]] if video else None, "align": method}
    write_json(pdir / "passage.json", data)
    project.data["passage"] = "passage/passage.json"
    project.data["status"] = "passage"
    project.save()
    say(f"The passage is {total:.1f} seconds: \"{data['text']}\"")
    tight = [k for k, s in enumerate(segs) if not (s["pause_before"] and s["pause_after"])]
    if tight:
        say("He runs straight on from the words around this part, so a cut may sound tight. Listen to the start and "
            "end, or pick words that sit between pauses.")
    return data


def energy_correct_by_segment(pwords, segs, db, thr):
    out = []
    for k, sg in enumerate(segs):
        ws = [w for w in pwords if w["seg"] == k]
        out += align.energy_correct(ws, db, thr)
    return out


def load(project):
    f = project.path("passage", "passage.json")
    if not f.exists():
        raise StudioError("This project has no passage yet. Pick his words with studio passage first.")
    return json.loads(f.read_text())
