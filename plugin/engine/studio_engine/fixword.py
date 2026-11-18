"""studio fix-word <project> "<heard>" "<said>" [--source <name>] [--at <seconds>] [--all]

Whisper mishears names and short words ("wait" for "weight", "work" for "worked") and sometimes drops one ("The of the
Superior Man" for "The Way of the Superior Man"). This puts his real word back:
  - in the source's transcript (ingest/<source>.json), so a new passage, captions and slides use it,
  - in the passage (passage/passage.json) when the passage holds it, keeping the word times,
  - in project.json "fixes", so the record says what was changed and why.
`heard` and `said` may be a few words each ("The of" -> "The Way of"). When they have the same number of words each
word keeps its own times; otherwise the heard words' time span is shared out by word length.

The words-heard-back check accepts the original hearing for a fixed word (whisper will mishear it again): every fixed
word carries {"fix": n, "fix_part": place, "heard": "<what whisper heard>"}.

Which place: `--at` (seconds in his source video) picks the one nearest; without it, the only place it is heard, or the
only place inside the passage; `--all` fixes every place.
"""
import json
import re

from . import ingest
from .errors import StudioError
from .project import now, write_json
from .util import say
from .words import plain


def _key(w):
    return " ".join(plain(w))


def _find(words, heard):
    want = [_key(h) for h in heard.split()]
    want = [k for k in want if k]
    if not want:
        raise StudioError("Say which word was heard wrong, for example: studio fix-word \"<project>\" wait weight")
    n = len(want)
    keys = [_key(w["w"]) for w in words]
    return [k for k in range(len(words) - n + 1) if keys[k:k + n] == want], n


def _carry_punct(old, new):
    """Keep the heard word's punctuation around his word ("wait." -> "weight.") unless he typed his own."""
    lead = re.match(r"^[^\w$]*", old).group(0)
    trail = re.search(r"[^\w%]*$", old).group(0)
    if new[:1].isalnum() and lead:
        new = lead + new
    if new[-1:].isalnum() and trail:
        new = new + trail
    return new


def replace_words(old, said, fix_id, heard_text, part=0):
    """New word dicts for `said` over the time span of `old` (a list of word dicts). Same count: each keeps its times
    and punctuation. Different count: the span is shared out by the length of each new word."""
    new_ws = said.split()
    if len(new_ws) == len(old):
        out = []
        for o, s in zip(old, new_ws):
            w = dict(o)
            w["w"] = _carry_punct(o["w"], s)
            out.append(w)
    else:
        t0, t1 = old[0]["t0"], old[-1]["t1"]
        lens = [max(1, len(re.sub(r"\W", "", s))) for s in new_ws]
        tot, acc, out = float(sum(lens)), 0.0, []
        for k, s in enumerate(new_ws):
            w = {key: v for key, v in old[min(k, len(old) - 1)].items() if key not in ("t0", "t1", "w")}
            a = t0 + (t1 - t0) * acc / tot
            acc += lens[k]
            b = t0 + (t1 - t0) * acc / tot
            w.update({"w": s, "t0": round(a, 3), "t1": round(b, 3)})
            out.append(w)
        lead = re.match(r"^[^\w$]*", old[0]["w"]).group(0)
        trail = re.search(r"[^\w%]*$", old[-1]["w"]).group(0)
        if out[0]["w"][:1].isalnum():
            out[0]["w"] = lead + out[0]["w"]
        if out[-1]["w"][-1:].isalnum():
            out[-1]["w"] += trail
    for w in out:
        w.update({"fix": fix_id, "fix_part": part, "heard": heard_text})
        w.pop("p", None)
    return out


def _passage_places(passage, source, starts, n):
    """For each place in the source (word index), the passage word indices that hold it, or None."""
    if not passage or passage.get("source_name") != source:
        return {k: None for k in starts}
    by_src = {}
    for w in passage["words"]:
        if "src" in w:
            by_src.setdefault(w["src"], []).append(w["i"])
    out = {}
    for k in starts:
        idx = [by_src.get(j) for j in range(k, k + n)]
        if all(x is None for x in idx):
            out[k] = None
        elif any(x is None for x in idx):
            raise StudioError("Those words run over the edge of the passage. Fix only the words inside it, or pick "
                              "the passage again after the fix.")
        else:
            flat = [i for x in idx for i in x]
            segs = {passage["words"][i].get("seg") for i in flat}
            if len(segs) > 1:
                raise StudioError("Those words sit on both sides of a cut in the passage. Fix one word at a time.")
            out[k] = flat
    return out


def fix_word(project, heard, said, source=None, at=None, every=False):
    heard, said = str(heard).strip(), str(said).strip()
    if not said or not plain(said):
        raise StudioError("Say the word he really said, for example: studio fix-word \"<project>\" wait weight")
    sources = [s["name"] for s in project.data["sources"] if s.get("ingest")]
    if source:
        project.source(source)
        sources = [source]
    try:
        passage = json.loads(project.path("passage", "passage.json").read_text())
    except (OSError, ValueError):
        passage = None
    # every place it is heard, in the chosen sources
    found = []
    for name in sources:
        rec = ingest.load(project, name)
        starts, n = _find(rec.get("words") or [], heard)
        places = _passage_places(passage, name, starts, n)
        found += [(name, k, n, rec["words"][k]["t0"], places[k]) for k in starts]
    if not found:
        raise StudioError(f'I could not find "{heard}" in what whisper heard. Check the words against the transcript.')
    if at is not None:
        best = min(abs(f[3] - float(at)) for f in found)
        pick = [f for f in found if abs(f[3] - float(at)) == best][:1]
    elif every or len(found) == 1:
        pick = found
    else:
        inside = [f for f in found if f[4] is not None]
        if len(inside) == 1:
            pick = inside
        else:
            where = ", ".join(f"{f[3]:.1f}" for f in found[:8])
            raise StudioError(f'"{heard}" is heard {len(found)} times (at {where} seconds). Say which with --at '
                              "<seconds>, or use --all to fix every one.")

    fixes = project.data.setdefault("fixes", [])
    fix_id = len(fixes)
    new_count = len(said.split())
    done, passage_shift = [], []
    # work back to front, so earlier word numbers stay right while later ones change
    for part, (name, k, n, t, pidx) in enumerate(sorted(pick, key=lambda f: (f[0], f[1]), reverse=True)):
        rec = ingest.load(project, name)
        old = rec["words"][k:k + n]
        heard_text = " ".join(t for t, _ in heard_alternative(old))     # a word fixed twice keeps the first hearing
        rec["words"][k:k + n] = replace_words(old, said, fix_id, heard_text, part)
        for i, w in enumerate(rec["words"]):
            w["i"] = i
        rec["text"] = " ".join(w["w"] for w in rec["words"])
        write_json(project.path("ingest", f"{name}.json"), rec)
        place = {"source": name, "t": round(t, 3), "heard": heard_text}
        if passage and passage.get("source_name") == name:
            delta = new_count - n
            for w in passage["words"]:
                if w.get("src") is not None and w["src"] >= k + n:
                    w["src"] += delta
            if pidx is not None:
                pw = [passage["words"][i] for i in pidx]
                neu = replace_words(pw, said, fix_id, heard_text, part)
                for j, w in enumerate(neu):
                    w["src"] = k + j
                a = pidx[0]
                passage["words"][a:a + len(pidx)] = neu
                for i, w in enumerate(passage["words"]):
                    w["i"] = i
                passage["text"] = " ".join(w["w"] for w in passage["words"])
                place["passage_words"] = list(range(a, a + new_count))
                place["passage_t"] = neu[0]["t0"]
                if delta:
                    passage_shift.append({"after": a + len(pidx) - 1, "by": delta})
        done.append(place)
    if passage and any("passage_words" in d for d in done):
        write_json(project.path("passage", "passage.json"), passage)
    fixes.append({"at": now(), "heard": heard, "said": said, "places": done[::-1]})
    project.save()
    inside = sum(1 for d in done if "passage_words" in d)
    say(f'Changed "{heard}" to "{said}" in {len(done)} place{"s" if len(done) != 1 else ""}'
        + (f", {inside} of them in the passage." if inside else "."))
    if passage_shift and project.data.get("versions"):
        say("The passage now has a different number of words: word numbers in the settings after this point move by "
            f"{passage_shift[0]['by']}. Check the settings before the next version.")
    return {"fix": fix_id, "heard": heard, "said": said, "places": done[::-1], "word_shift": passage_shift[::-1]}


def heard_alternative(words):
    """The passage words as whisper first heard them: each run of fixed words (same fix number, side by side) is put
    back to what was heard. Returns [(text, [word indices it stands for])]."""
    out, k = [], 0
    while k < len(words):
        w = words[k]
        if w.get("fix") is None or w.get("heard") is None:
            out.append((w["w"], [k]))
            k += 1
            continue
        j = k
        while j + 1 < len(words) and (words[j + 1].get("fix"), words[j + 1].get("fix_part")) == \
                (w["fix"], w.get("fix_part")) and words[j + 1].get("seg") == w.get("seg"):
            j += 1
        out.append((w["heard"], list(range(k, j + 1))))
        k = j + 1
    return out
