"""Sound for every style: his voice on top, a code-made bed about 18 dB under, effects 24 to 30 dB under, both ducked
while he talks, mastered to -14 LUFS with true peak at or under -1.5 dBTP (aim -2).

Ported from the original style builds: the measuring, ducking and chord pads of the editing styles' common.py, the drone
bed and the 192 kHz limiter master of mix.py, the zen drone of the garden's sound.py and the kinetic-type chord bed.
All arrays are stereo float (n, 2) at 48 kHz.

    from studio_engine import sound
    levels = sound.mix(voice="passage/voice-clean.wav", duration=15.4, out="v1/mix.wav",
                       bed={"name": "pad-minor", "changes": [9.5]},   # or sound.make_bed(name, seconds)
                       sfx=[{"name": "impact", "t": 3.1}, {"name": "card", "t": 6.2, "under_db": 28}])
    sound.names()   # every effect and bed a spec may name
"""
import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import signal

from . import paths
from .errors import StudioError
from .media import safe_input

SR = 48000
TARGET_LUFS = -14.0
LIMIT_DB = -2.2          # limiter ceiling; true peak lands near -2 after the 192 kHz pass and AAC


# ----------------------------------------------------------------------------------------------- in and out
def decode(path, ss=None, to=None, channels=2):
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.4f}"]
    if to is not None:
        cmd += ["-to", f"{to:.4f}"]
    cmd += [*safe_input(str(path)), "-vn", "-ac", str(channels), "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise StudioError(f'I could not read the sound file "{Path(path).name}".')
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    return x.reshape(-1, channels) if channels > 1 else x


def write(path, x):
    x = np.asarray(x, np.float32)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac",
                        str(x.shape[1]), "-i", "-", "-c:a", "pcm_s24le", str(path)],
                       input=np.ascontiguousarray(x).tobytes())
    if r.returncode != 0:
        raise StudioError("I could not write a sound file.")
    return path


def stereo(x):
    x = np.asarray(x, np.float64)
    return np.stack([x, x], 1) if x.ndim == 1 else x


def place(buf, clip, t, gain_db=0.0, fade_out=None):
    """Add `clip` into `buf` at time t (seconds), with a gain and an optional fade at its end."""
    clip = stereo(clip)
    i = int(round(t * SR))
    if i < 0:
        clip, i = clip[-i:], 0
    n = min(len(clip), len(buf) - i)
    if n <= 0:
        return buf
    c = clip[:n] * (10 ** (gain_db / 20))
    if fade_out:
        k = int(fade_out * SR)
        if 0 < k < n:
            c[-k:] *= np.linspace(1, 0, k)[:, None]
    buf[i:i + n] += c
    return buf


def fit(x, n):
    """Pad with silence or trim to exactly n samples."""
    x = stereo(x)
    return np.pad(x, ((0, max(0, n - len(x))), (0, 0)))[:n]


def fade(x, a=0.02, b=0.05):
    x = stereo(x).copy()
    na, nb = int(a * SR), int(b * SR)
    if na:
        x[:na] *= np.linspace(0, 1, na)[:, None]
    if nb:
        x[-nb:] *= np.linspace(1, 0, nb)[:, None]
    return x


# ----------------------------------------------------------------------------------------------- measuring
def k_weight(x):
    """ITU-R BS.1770 K-weighting (two biquads at 48 kHz)."""
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def _blocks(x, blk, hop):
    y = k_weight(stereo(x)) ** 2
    c = np.cumsum(np.concatenate([np.zeros((1, y.shape[1])), y]), axis=0)
    starts = np.arange(0, max(1, len(y) - blk), hop)
    ends = np.minimum(starts + blk, len(y))
    return ((c[ends] - c[starts]) / np.maximum(ends - starts, 1)[:, None]).sum(1)


def lufs(x):
    """Integrated loudness, BS.1770-4 with gating."""
    ms = _blocks(x, int(0.4 * SR), int(0.1 * SR))
    ld = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[ld > -70]
    if len(g) == 0:
        return -99.0
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = ms[(ld > -70) & (ld > rel)]
    return float(-0.691 + 10 * np.log10(g2.mean()))


def momentary_max(x):
    ms = _blocks(x, int(0.4 * SR), int(0.05 * SR))
    return float(-0.691 + 10 * np.log10(ms.max() + 1e-12))


def measure(path):
    """ffmpeg's EBU R128 meter on a file: (integrated LUFS, true peak dBTP)."""
    out = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", *safe_input(str(path)), "-af",
                          "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    tail = out[out.rfind("Summary:"):]
    try:
        I = float(tail.split("I:")[1].split("LUFS")[0])
        tp = float(tail.split("Peak:")[1].split("dBFS")[0])
    except (IndexError, ValueError):
        raise StudioError(f'I could not measure the loudness of "{Path(path).name}".')
    return I, tp


# ----------------------------------------------------------------------------------------------- filters
def lp(x, f, order=2):
    b, a = signal.butter(order, min(f, SR / 2 - 100) / (SR / 2))
    return signal.lfilter(b, a, x, axis=0)


def hp(x, f, order=2):
    b, a = signal.butter(order, f / (SR / 2), "high")
    return signal.lfilter(b, a, x, axis=0)


def bp(x, f0, f1, order=2):
    b, a = signal.butter(order, [f0 / (SR / 2), min(f1, SR / 2 - 100) / (SR / 2)], "band")
    return signal.lfilter(b, a, x, axis=0)


def reverb(x, seconds=2.4, wet=0.25, predelay=0.02, tone=6000, seed=3):
    x = stereo(x)
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-6.9 * t / seconds)[:, None]
    b, a = signal.butter(2, tone / (SR / 2))
    ir = signal.lfilter(b, a, ir, axis=0)
    ir = np.pad(ir, ((int(predelay * SR), 0), (0, 0)))
    ir /= np.sqrt((ir ** 2).sum(0, keepdims=True))
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    return x * (1 - wet) + y * wet


# ----------------------------------------------------------------------------------------------- tones and beds
def note_hz(name):
    names = {"C": -9, "C#": -8, "Db": -8, "D": -7, "D#": -6, "Eb": -6, "E": -5, "F": -4, "F#": -3, "Gb": -3, "G": -2,
             "G#": -1, "Ab": -1, "A": 0, "A#": 1, "Bb": 1, "B": 2}
    if isinstance(name, (int, float)):
        return float(name)
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[n] + 12 * (o - 4)) / 12)


def pad_voice(freq, dur, detune=0.08, cutoff=900, seed=0):
    """A soft analog string pad: three detuned saws spread across the stereo field, low-passed."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros((len(t), 2))
    for k, d in enumerate((-detune, 0.0, detune)):
        f = freq * 2 ** (d / 12)
        saw = 2 * ((f * t + rng.uniform(0, 1)) % 1) - 1
        pan = (k - 1) * 0.6
        out[:, 0] += saw * (1 - pan) * 0.5
        out[:, 1] += saw * (1 + pan) * 0.5
    return lp(out, cutoff) / 3


def chord_bed(chords, total, cutoff=900, vol=1.0, xfade=1.2, seed=0):
    """chords: [(t_start, t_end, [note names or Hz])]; each chord swells in and out over `xfade` seconds."""
    buf = np.zeros((int(total * SR), 2))
    for j, (a, b, notes) in enumerate(chords):
        dur = max(0.2, b - a) + xfade
        for n_i, nm in enumerate(notes):
            v = pad_voice(note_hz(nm), dur, cutoff=cutoff, seed=seed + j * 10 + n_i)
            env = np.ones(len(v))
            k = min(int(xfade * SR), len(v) // 2)
            env[:k] = np.sin(np.linspace(0, np.pi / 2, k)) ** 2
            env[-k:] = np.cos(np.linspace(0, np.pi / 2, k)) ** 2
            place(buf, v * env[:, None] * vol, a - xfade / 2)
    return buf


def drone_bed(dur, root=73.42, seed=7):
    """Warm low drone: detuned additive saws on a minor triad, slow drift, low-passed, a long synthetic room."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for f0, amp in [(root, 1.0), (root * 1.5, 0.55), (root * 2, 0.5), (root * 2 * 1.189, 0.18), (root * 3, 0.12)]:
        for cents in (-4, 0, 3.5):
            f = f0 * 2 ** (cents / 1200)
            ph = rng.uniform(0, 2 * np.pi)
            v = np.zeros(n)
            for h in range(1, 10):
                v += np.sin(2 * np.pi * f * h * t + ph * h) / h ** 1.35
            lfo = 0.75 + 0.25 * np.sin(2 * np.pi * rng.uniform(0.04, 0.11) * t + rng.uniform(0, 6.28))
            x += amp * v * lfo
    x = lp(x, 520)
    ir_n = int(3.2 * SR)
    ir = lp(rng.standard_normal(ir_n) * np.exp(-np.arange(ir_n) / (0.75 * SR)), 1800)
    wet = signal.fftconvolve(x, ir)[:n]
    wet *= np.std(x) / (np.std(wet) + 1e-9)
    y = 0.6 * x + 0.55 * wet
    env = np.ones(n)
    fi, fo = min(int(1.6 * SR), n // 2), min(int(1.2 * SR), n // 2)
    env[:fi] = np.linspace(0, 1, fi) ** 2
    env[-fo:] = np.linspace(1, 0, fo) ** 1.5
    return stereo(y * env)


def _edges(bed, dur, fade_in=0.4, fade_out=1.5):
    k2 = min(int(fade_out * SR), len(bed))
    bed[-k2:] *= np.linspace(1, 0, k2)[:, None] ** 2
    k1 = min(int(fade_in * SR), len(bed))
    bed[:k1] *= np.linspace(0, 1, k1)[:, None]
    return bed


def _times(changes, count, dur):
    """Chord change times: the spec's, else spread evenly."""
    c = sorted(float(x) for x in (changes or []))[: count - 1]
    while len(c) < count - 1:
        c.append(dur * (len(c) + 1) / count)
    return [0.0] + c + [dur + 1.0]


def bed_pad_minor(dur, changes=None, **_):
    """A dark D minor pad that opens to F at the change (the receipts bed)."""
    t = _times(changes, 2, dur)
    bed = chord_bed([(t[0], t[1], ["D2", "A2", "F3", "A3"]), (t[1], t[2], ["F2", "C3", "A3", "C4"])],
                    dur, cutoff=700, seed=4)
    bed += chord_bed([(0, dur + 1, ["D1"])], dur, cutoff=200, seed=9) * 0.8
    return reverb(_edges(bed, dur), 2.8, 0.35)


def bed_documentary(dur, changes=None, mallets=None, **_):
    """D minor, B flat, F, with a sub D under it and felt mallet notes on the key words (the documentary bed).
    mallets: [{"t": s, "note": "A3", "gain_db": -2}]"""
    t = _times(changes, 3, dur)
    bed = chord_bed([(t[0], t[1], ["D2", "A2", "E3", "F3"]), (t[1], t[2], ["A#1", "F2", "D3", "A3"]),
                     (t[2], t[3] + 1, ["F2", "C3", "A3", "E4"])], dur, cutoff=800, seed=31)
    bed += chord_bed([(0, dur + 2, ["D1"])], dur, cutoff=140, seed=5) * 0.9
    bed = _edges(bed, dur, 0.8, 1.6)
    for m in mallets or []:
        place(bed, mallet(note_hz(m.get("note", "A3")), 4.0, 0.8) * 0.5, float(m["t"]), m.get("gain_db", -3))
    return reverb(bed, 3.4, 0.42)


def bed_cutout(dur, changes=None, **_):
    """A minor, F, C (the cutout bed)."""
    t = _times(changes, 3, dur)
    bed = chord_bed([(t[0], t[1], ["A1", "E2", "C3", "E3"]), (t[1], t[2], ["F1", "C2", "A2", "C3"]),
                     (t[2], t[3], ["C2", "G2", "E3", "G3"])], dur, cutoff=650, seed=12)
    return reverb(_edges(bed, dur, 0.3, 1.4), 3.0, 0.4)


def bed_type(dur, changes=None, pulse_until=None, swell_at=None, **_):
    """D minor, B flat, F, F with an added top (the moving-type bed), a slow sub pulse that stops at `pulse_until`
    and a swell from `swell_at`."""
    t = _times(changes, 4, dur)
    D2, F2, A2, C3, D3, F3, A3, Bb2, G3, C4 = 73.42, 87.31, 110.0, 130.81, 146.83, 174.61, 220.0, 116.54, 196.0, 261.63
    music = chord_bed([(t[0], t[1] - 0.2, [D2, A2, D3, F3, A3]), (t[1] - 0.4, t[2] - 0.1, [Bb2, F3, D3, A3]),
                       (t[2] - 0.3, t[3] - 0.05, [F2, C3, F3, A3]), (t[3] - 0.2, dur + 1, [F2, C3, F3, A3, C4, G3])],
                      dur + 1.5, cutoff=1300)[: int(dur * SR)]
    tt = np.arange(len(music)) / SR
    stop = pulse_until if pulse_until is not None else t[2] - 0.3
    env = np.clip(1 - np.maximum(tt - stop, 0) / 0.4, 0, 1) * np.clip(tt / 1.0, 0, 1)
    ph = (tt % (60 / 64)) / (60 / 64)
    music += (0.5 * np.sin(2 * np.pi * 49 * tt) * np.exp(-ph * 9) * env)[:, None]
    sw = swell_at if swell_at is not None else t[3]
    music *= (1 + 0.5 * _smooth((tt - sw) / 1.2))[:, None]
    return _edges(music, dur, 0.3, 1.2)


def bed_zen(dur, rise=None, **_):
    """A low open drone (A and E) that warms into an add9 chord when the payoff rises (the zen garden bed)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    A1, E2, A2, Cs3, E3, B3, Fs3 = 55.0, 82.41, 110.0, 138.59, 164.81, 246.94, 185.0
    pad = chord_bed([(0, dur + 1, [A2, E3])], dur, cutoff=700, seed=4)[:, 0]
    drone = np.sin(2 * np.pi * A1 * t) * 0.6 + np.sin(2 * np.pi * E2 * t + 0.3) * 0.4 + 0.25 * lp(pad, 900)
    drone *= 0.8 + 0.2 * np.sin(2 * np.pi * t / 5.5)
    music = stereo(drone * np.clip(t / 1.2, 0, 1))
    r = rise if rise is not None else dur * 0.6
    music += chord_bed([(r - 0.3, dur, [A2, Cs3, E3, B3, Fs3 * 2])], dur + 1.5, cutoff=1600)[:n] * 0.9
    return reverb(_edges(music, dur, 0.0, 1.2), 3.5, 0.35)


def bed_drone(dur, root=73.42, **_):
    """The low drone the screen-and-face and words-in-the-room styles use."""
    return drone_bed(dur, float(root))


BEDS = {"pad-minor": bed_pad_minor, "documentary": bed_documentary, "cutout": bed_cutout, "type": bed_type,
        "zen": bed_zen, "drone": bed_drone}


def make_bed(name, dur, **opts):
    if name in (None, "none", ""):
        return np.zeros((int(dur * SR), 2))
    if name not in BEDS:
        raise StudioError(f'There is no music bed called "{name}". Beds: {", ".join(BEDS)}, none.')
    b = BEDS[name](dur, **opts)
    n = int(dur * SR)
    return np.pad(b, ((0, max(0, n - len(b))), (0, 0)))[:n]


# ----------------------------------------------------------------------------------------------- code-made effects
def _smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def sub_hit(freq=48, dur=1.6):
    t = _t(dur)
    f = freq * (1 + 1.2 * np.exp(-t / 0.05))
    return stereo(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45) * np.clip(t / 0.004, 0, 1))


def low_hit(dur=1.6, f=48, seed=0):
    t = _t(dur)
    pitch = f * (1 + 0.6 * np.exp(-t * 18))
    body = np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t * 3.2)
    click = lp(np.random.default_rng(seed).standard_normal(len(t)), 2500) * np.exp(-t * 60) * 0.35
    return stereo(body + click)


def thud(dur=0.5, f=70, seed=0, click=0.4):
    """A heavy block landing: pitched body, a short knock and grit."""
    t = _t(dur)
    body = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.8 * np.exp(-t * 40))) / SR) * np.exp(-t * 14)
    rng = np.random.default_rng(seed)
    knock = bp(rng.standard_normal(len(t)), 600, 2400) * np.exp(-t * 90) * click
    grit = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t * 35) * 0.08
    return stereo(body + knock + grit)


def mallet(freq, dur=4.0, bright=1.0):
    """Felt mallet / singing-bowl tone: a few inharmonic partials, soft attack, long decay."""
    t = _t(dur)
    x = np.zeros(len(t))
    for r, amp, dec in [(1.0, 1.0, 1.6), (2.0, 0.35 * bright, 0.9), (2.76, 0.18 * bright, 0.7), (5.4, 0.06 * bright, 0.35)]:
        x += amp * np.sin(2 * np.pi * freq * r * t) * np.exp(-t / dec)
    x *= np.clip(t / 0.012, 0, 1)
    st = np.stack([x, np.roll(x, 24)], 1)
    return st / (np.abs(st).max() + 1e-9)


def bowl(dur=5.0, f=220.0):
    """A struck singing bowl: inharmonic partials with beating."""
    t = _t(dur)
    y = np.zeros(len(t))
    for ratio, amp, decay in ((1, 1, 0.9), (2.71, 0.5, 1.6), (5.15, 0.25, 2.8), (8.4, 0.12, 4.0)):
        for det in (-0.6, 0.6):
            y += amp * np.sin(2 * np.pi * (f * ratio + det) * t) * np.exp(-t * decay)
    return stereo(y * np.clip(t / 0.004, 0, 1) / 4)


def whoosh_air(dur=0.7, seed=0, f0=300, f1=3000, rise=0.75):
    """Band-passed noise swept up then down."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    u = np.linspace(0, 1, n)
    env = np.where(u < rise, (u / rise) ** 2, (1 - (u - rise) / (1 - rise)) ** 1.5)
    out = np.zeros(n)
    chunks = 24
    for k in range(chunks):
        a, b = k * n // chunks, (k + 1) * n // chunks
        q = k / chunks
        fc = f0 * (f1 / f0) ** (q if q < rise else (1 - (q - rise) / (1 - rise)))
        seg = bp(noise[max(0, a - 2000):b], fc * 0.6, min(fc * 1.6, 20000))
        out[a:b] = seg[-(b - a):]
    return stereo(out * env)


def riser_air(dur=1.0, seed=0, f0=200, f1=4000):
    return whoosh_air(dur, seed, f0, f1, rise=0.92)


def noise_swell(dur=1.2, lo=300, hi=4000, seed=1, rev=False):
    x = bp(np.random.default_rng(seed).normal(0, 1, (int(dur * SR), 2)), lo, hi)
    env = np.linspace(0, 1, len(x)) ** 2.5
    return x * (env[::-1] if rev else env)[:, None] / (np.abs(x).max() + 1e-9)


def sand(dur=1.0, seed=0, density=1.0):
    """Raked sand: band-limited crackle with a grainy texture."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    base = bp(rng.standard_normal(n), 1200, 7000)
    grains = (rng.random(n) < 0.004 * density).astype(float)
    grains = signal.lfilter([1], [1, -0.97], grains * rng.uniform(-1, 1, n))
    tex = lp(np.abs(rng.standard_normal(n)), 30)
    tex = tex / (tex.max() + 1e-9)
    return stereo((base * 0.5 + hp(grains, 1500) * 2.0) * (0.4 + 0.6 * tex))


def tick(seed=0, f=3500, dur=0.05):
    t = _t(dur)
    return stereo(bp(np.random.default_rng(seed).standard_normal(len(t)), f * 0.7, f * 1.3) * np.exp(-t * 120))


def pop(f=900, dur=0.12):
    """A soft round pop (a card or a mark appearing)."""
    t = _t(dur)
    ff = f * (1 + 1.5 * np.exp(-t * 60))
    return stereo(np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * 45) * np.clip(t / 0.002, 0, 1))


def key(seed=0):
    """A typewriter key: a sharp click on a small wooden knock."""
    rng = np.random.default_rng(seed)
    t = _t(0.12)
    click = bp(rng.standard_normal(len(t)), 2500, 9000) * np.exp(-t * 180)
    knock = bp(rng.standard_normal(len(t)), 300, 1400) * np.exp(-t * 70) * 0.6
    return stereo(click + knock)


def clock_tick(seed=0):
    return tick(seed, 2600, 0.04)


def projector(dur=2.4, rate=18.0, seed=0):
    """An old projector running: a motor hum with a fast shutter clatter."""
    rng = np.random.default_rng(seed)
    t = _t(dur)
    hum = (np.sin(2 * np.pi * 100 * t) * 0.3 + np.sin(2 * np.pi * 200 * t) * 0.15) * 0.3
    clat = np.zeros(len(t))
    for k in range(int(dur * rate)):
        i = int(k / rate * SR)
        c = tick(seed + k, 1800 + rng.uniform(-200, 200), 0.03)[:, 0]
        clat[i:i + len(c)] += c[: len(clat) - i] * rng.uniform(0.6, 1.0)
    return stereo((hum + clat) * np.linspace(1, 0, len(t)) ** 1.5)


def marker(dur=0.5, seed=0):
    """A marker pen drawing a line: a dry, squeaky scrape."""
    rng = np.random.default_rng(seed)
    t = _t(dur)
    x = bp(rng.standard_normal(len(t)), 1800, 6000)
    am = 0.6 + 0.4 * np.sin(2 * np.pi * 23 * t + rng.uniform(0, 6))
    env = np.clip(t / 0.03, 0, 1) * np.clip((dur - t) / 0.08, 0, 1)
    return stereo(x * am * env)


SYNTH = {
    "sub-hit": lambda: sub_hit(48, 1.6), "low-hit": lambda: low_hit(), "thud": lambda: thud(),
    "mallet": lambda: mallet(220.0), "bowl": lambda: bowl(), "air-whoosh": lambda: whoosh_air(),
    "air-riser": lambda: riser_air(), "noise-swell": lambda: noise_swell(), "sand": lambda: sand(),
    "tick": lambda: tick(), "pop": lambda: pop(), "key": lambda: key(), "clock-tick": lambda: clock_tick(),
    "projector": lambda: projector(), "marker": lambda: marker(),
}


@lru_cache(None)
def _library():
    f = paths.sound_library() / "sounds.json"
    return {k: v for k, v in json.loads(f.read_text()).items() if not k.startswith("_")} if f.exists() else {}


def names():
    return {"effects": sorted(list(_library()) + list(SYNTH)), "beds": sorted(BEDS) + ["none"],
            "library": {k: v["what"] for k, v in _library().items()}}


def effect(name):
    """An effect by name: one of the shipped recordings (library/sound) or a code-made one."""
    lib = _library()
    if name in lib:
        return decode(paths.sound_library() / lib[name]["file"])
    if name in SYNTH:
        return SYNTH[name]()
    raise StudioError(f'There is no sound effect called "{name}". Effects: {", ".join(names()["effects"])}.')


def onset_trim(x):
    """Start an effect at its attack, so it lands on the frame it is placed on."""
    x = stereo(x)
    a = np.abs(x).max(1)
    pk = a.max() + 1e-9
    i = int(np.argmax(a > 0.1 * pk))
    return x[max(0, i - int(0.004 * SR)):]


# ----------------------------------------------------------------------------------------------- ducking and master
def env_follow(x, attack=0.02, release=0.35):
    a = np.abs(stereo(x)).max(1)
    k0 = math.exp(-1 / (0.01 * SR))
    a = signal.lfilter([1 - k0], [1, -k0], a)
    blk = 48
    nb = int(math.ceil(len(a) / blk))
    peaks = np.pad(a, (0, nb * blk - len(a))).reshape(nb, blk).max(1)
    ka, kr = math.exp(-blk / (attack * SR)), math.exp(-blk / (release * SR))
    out = np.empty(nb)
    v = 0.0
    for i, s in enumerate(peaks):
        k = ka if s > v else kr
        v = k * v + (1 - k) * s
        out[i] = v
    return np.repeat(out, blk)[: len(a)]


def duck_gain(voice, depth_db=4.0, thresh=0.02):
    e = env_follow(voice)
    return 10 ** (-depth_db * np.clip(e / thresh, 0, 1) / 20)


def _finish(src, dst, gain, ceiling_db=LIMIT_DB):
    af = (f"volume={gain:.3f}dB,aresample=192000,alimiter=limit={ceiling_db}dB:attack=1:release=60:level=false,"
          f"aresample=48000")
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(str(src)), "-af", af, "-ar", str(SR),
                        "-c:a", "pcm_s24le", str(dst)], capture_output=True)
    if r.returncode != 0:
        raise StudioError("The sound could not be finished (mastering failed).")


def master(src, dst, target=TARGET_LUFS, ceiling_db=LIMIT_DB):
    """Gain to -14 LUFS, then a true-peak-safe limiter run at 192 kHz; measure and repeat until within 0.15 LU.
    Returns the measured levels and the gain used (`gain_db`)."""
    I0, _ = measure(src)
    gain = target - I0
    I = tp = None
    for _ in range(5):
        _finish(src, dst, gain, ceiling_db)
        I, tp = measure(dst)
        if abs(I - target) <= 0.15:
            break
        gain += target - I
    return {"lufs": round(I, 2), "true_peak": round(tp, 2), "gain_db": round(gain, 3)}


def voice_stem_path(out):
    """Where mix() keeps his voice as mixed, beside the finished sound: mix.wav -> mix-voice.wav."""
    out = Path(out)
    return out.with_name(out.stem + "-voice.wav")


def mix(voice, duration, out, bed=None, sfx=(), music_under=None, sfx_under=None, duck_db=None, work=None):
    """Build the finished sound. Returns the measured levels.

    voice: a wav path (the passage voice, placed at 0) or a stereo array.
    bed: None, a bed name, {"name", "under_db", "changes": [s], ...options}, or a stereo array.
    sfx: [{"name" or "array", "t", "under_db" (24..30, default 27), "len" (seconds, optional), "gain_db"}]
    Levels are set from the voice's own loudness: the bed `music_under` dB under it (integrated), each effect's
    loudest 400 ms `under_db` under it. Bed and effects dip while he talks. Also writes his voice as mixed, without
    bed or effects, beside `out` (`voice_stem_path(out)`, for the words check)."""
    from . import brand
    snd = brand.sound_settings()
    music_under = snd["music_under_db"] if music_under is None else music_under
    sfx_under = snd["sfx_under_db"] if sfx_under is None else sfx_under
    duck_db = snd["duck_db"] if duck_db is None else duck_db
    n = int(round(duration * SR))
    v = np.zeros((n, 2))
    place(v, decode(voice) if isinstance(voice, (str, Path)) else stereo(voice), 0.0)
    k = int(0.012 * SR)
    vl = lufs(v)
    if vl < -60:
        raise StudioError("The voice track is silent. Check the passage before rendering.")
    levels = {"voice_lufs": round(vl, 2)}
    g = fit(duck_gain(v, duck_db), n)[:, :1]

    b = np.zeros_like(v)
    if bed is not None and not (isinstance(bed, str) and bed in ("none", "")):
        if isinstance(bed, np.ndarray):
            b = stereo(bed)
            under = music_under
        else:
            opts = {"name": bed} if isinstance(bed, str) else dict(bed)
            name = opts.pop("name")
            under = float(opts.pop("under_db", music_under))
            b = make_bed(name, duration, **opts)
        b = fit(b, n)
        if np.any(b):
            b = b * 10 ** ((vl - under - lufs(b)) / 20)
            b = b * g
            levels["bed_under_voice_db"] = round(vl - lufs(b), 1)

    fx = np.zeros_like(v)
    for e in sfx or ():
        x = onset_trim(e["array"] if "array" in e else effect(e["name"]))
        if e.get("len"):
            x = x[: int(float(e["len"]) * SR)].copy()
            kk = min(int(0.06 * SR), len(x))
            x[-kk:] *= np.linspace(1, 0, kk)[:, None]
        under = float(e.get("under_db", sfx_under))
        x = x * 10 ** ((vl - under - momentary_max(x)) / 20)
        place(fx, x, float(e["t"]), float(e.get("gain_db", 0.0)))
    if np.any(fx):
        fx = fx * (0.5 + 0.5 * g)
        levels["sfx_loudest_under_voice_db"] = round(vl - momentary_max(fx), 1)

    fade = np.ones((n, 1))
    fade[-k:, 0] = np.linspace(1, 0, k)
    mixed = (v + b + fx) * fade
    out = Path(out)
    work = Path(work) if work else out.parent
    work.mkdir(parents=True, exist_ok=True)
    pre = work / (out.stem + "-premaster.wav")
    write(pre, mixed)
    levels.update(master(pre, out))
    # his voice exactly as it sits in the finished sound (placement, length, end fade, mastering gain and limiter),
    # without bed or effects: the words check listens to it when a word is lost in the final (see qa.check_words)
    write(pre, v * fade)
    _finish(pre, voice_stem_path(out), levels.pop("gain_db"))
    pre.unlink(missing_ok=True)
    return levels
