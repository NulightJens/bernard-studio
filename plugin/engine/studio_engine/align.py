"""Word times that do not clip his words.

Whisper's word times run short or spill into the pause, so the passage refines them:
  - forced alignment (wav2vec2 MMS_FA, character CTC; port of v8 prosody/align.py) when the matte component is
    installed (it brings torch and torchaudio) and its weights are in STUDIO_HOME/models/torch;
  - otherwise whisper's times with each word's edges pulled in to the voice's own loudness (energy_correct).
"""
import numpy as np

from . import paths
from .words import spoken

HOP = 0.01


def available():
    if not paths.mms_fa_weights().exists():
        return False
    try:
        import torch  # noqa: F401
        import torchaudio  # noqa: F401
        return True
    except Exception:
        return False


def energy_correct(words, db, thr, hop=HOP, reach=0.15):
    """Pull each word's start and end in to where his voice is above `thr` (dB), never across a neighbour.
    words: [{"t0","t1"}] on the same clock as `db` (10 ms steps). Returns new list (copies)."""
    out = [dict(w) for w in words]
    n = len(db)

    def loud(t):
        k = int(round(t / hop))
        return 0 <= k < n and db[k] >= thr

    for i, w in enumerate(out):
        lo = out[i - 1]["t1"] if i else 0.0
        hi = words[i + 1]["t0"] if i + 1 < len(words) else n * hop
        t0, t1 = w["t0"], w["t1"]
        # start: if quiet, move forward to the first loud step inside the word; if loud, walk back to the onset
        if not loud(t0):
            t = t0
            while t < t1 - 0.03 and not loud(t):
                t += hop
            t0 = t if loud(t) else t0
        else:
            t = t0
            while t - hop >= max(lo, t0 - reach) and loud(t - hop):
                t -= hop
            t0 = t
        # end: look just before the end (whisper.cpp glues a word's end to the next word's onset, which is loud);
        # if loud there, walk forward to the quiet (never into the next word); if quiet, walk back to the last loud step
        t = min(t1, hi) - hop
        if loud(t):
            while t + hop < min(hi, t1 + reach) and loud(t + hop):
                t += hop
            t1 = t + hop
        else:
            while t > t0 + 0.04 and not loud(t):
                t -= hop
            t1 = t + hop if loud(t) else t1
        w["t0"], w["t1"] = round(t0, 3), round(max(t1, t0 + 0.03), 3)
    return out


def _chars(tokens):
    return ["".join(c for c in t if c in "abcdefghijklmnopqrstuvwxyz'") or "a" for t in tokens]


def force_align(x16, words, t_offset=0.0):
    """Align the known words to 16 kHz mono audio `x16` (numpy float32). Returns [(t0, t1)] per word, seconds, plus
    t_offset. Numbers are aligned in their spoken form ("$40,000" -> forty thousand dollars)."""
    import torch
    import torchaudio
    paths.configure_env()
    bundle = torchaudio.pipelines.MMS_FA
    model = _model(bundle)
    tok = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    flat, owner = [], []
    for i, w in enumerate(words):
        for t in _chars(spoken(w["w"]) or ["a"]):
            flat.append(t)
            owner.append(i)
    wav = torch.from_numpy(np.ascontiguousarray(x16, np.float32))[None]
    with torch.inference_mode():
        em, _ = model(wav)
        spans = aligner(em[0], tok(flat))
    ratio = wav.size(1) / em.size(1) / 16000
    out = [[None, None] for _ in words]
    for k, sp in enumerate(spans):
        i = owner[k]
        a, b = t_offset + sp[0].start * ratio, t_offset + sp[-1].end * ratio
        out[i][0] = a if out[i][0] is None else min(out[i][0], a)
        out[i][1] = b if out[i][1] is None else max(out[i][1], b)
    return [(round(a, 3), round(b, 3)) for a, b in out]


_MODEL = {}


def _model(bundle):
    if "m" not in _MODEL:
        _MODEL["m"] = bundle.get_model(with_star=False).eval()
    return _MODEL["m"]
