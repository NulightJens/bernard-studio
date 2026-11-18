"""His words as tokens: number forms normalised, so "$40,000", "40,000 dollars" and "forty thousand dollars" compare
equal, and phrases can be found in a transcript the way he would type them.

    spoken("$40,000")        -> ["forty", "thousand", "dollars"]
    spoken("2019.")          -> ["twenty", "nineteen"]
    find_phrase(words, "would have cost me")  -> (i0, i1) word indices, inclusive
"""
import difflib
import re

from .errors import StudioError

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
       "seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
SCALES = [(10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")]
SUFFIX = {"k": ["thousand"], "m": ["million"], "b": ["billion"], "x": ["x"], "%": ["percent"]}


def num_words(n):
    n = int(n)
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (num_words(n % 100) if n % 100 else [])
    for size, name in SCALES:
        if n >= size:
            return num_words(n // size) + [name] + (num_words(n % size) if n % size else [])
    return [str(n)]


def year_words(n):
    hi, lo = divmod(n, 100)
    if lo == 0:
        return num_words(hi) + ["hundred"]
    if hi == 20 and lo < 10:
        return num_words(n)                       # 2005 -> two thousand five
    return num_words(hi) + (["oh"] + num_words(lo) if lo < 10 else num_words(lo))


def spoken(word):
    """One written word -> the lowercase tokens he would say."""
    w = word.strip().lower().replace("’", "'")
    m = re.fullmatch(r"[^\w$#]*(#?)(\$?)(\d[\d,]*)(?:\.(\d+))?([kmbx%]?)(s?)[^\w%]*", w)
    if m:
        hash_, dollar, num, dec, suf, plural = m.groups()
        digits = num.replace(",", "")
        n = int(digits)
        if not dollar and not dec and not suf and "," not in num and len(digits) == 4 and 1100 <= n <= 2099:
            toks = year_words(n)
        else:
            toks = num_words(n)
        if dec:
            toks += ["point"] + [ONES[int(c)] for c in dec]
        toks += SUFFIX.get(suf, [])
        if plural and toks:
            toks[-1] = toks[-1] + "s"
        if dollar:
            toks += ["dollars"]
        return (["number"] if hash_ else []) + toks         # "#1" is said "number one"
    w = w.replace("&", " and ").replace("%", " percent")
    return [t for t in re.split(r"[^a-z0-9']+", w) if t.strip("'")]


def plain(text):
    """Spoken tokens with apostrophes dropped, for comparing (don't == dont). Works word by word, so a whole line
    ("10 people") normalises its numbers too."""
    return [t.replace("'", "") for part in str(text).split() for t in spoken(part)]


def token_map(words):
    """Flatten [{"w": ...}] into tokens, with the index of the word each token came from."""
    toks, owner = [], []
    for i, w in enumerate(words):
        for t in plain(w["w"] if isinstance(w, dict) else w):
            toks.append(t)
            owner.append(i)
    return toks, owner


def phrase_tokens(phrase):
    out = []
    for p in phrase.split():
        out += plain(p)
    return out


def find_phrase(words, phrase, after=0):
    """First place the phrase is said at or after word index `after`. Exact first; then the closest match (at least 80
    percent alike), so small transcript differences ("worked" for "work") still find it. Returns (i0, i1)."""
    toks, owner = token_map(words)
    want = phrase_tokens(phrase)
    if not want:
        raise StudioError("That phrase has no words in it.")
    start = next((k for k, o in enumerate(owner) if o >= after), len(toks))
    n = len(want)
    for k in range(start, len(toks) - n + 1):
        if toks[k:k + n] == want:
            return owner[k], owner[k + n - 1]
    best, where = 0.0, None
    for k in range(start, len(toks) - n + 1):
        r = sum(difflib.SequenceMatcher(None, a, b).ratio() for a, b in zip(toks[k:k + n], want)) / n
        if r > best:
            best, where = r, k
    if where is not None and best >= 0.8:
        return owner[where], owner[where + n - 1]
    raise StudioError(f'I could not find "{phrase}" in what he said. Check the words against the transcript.')


def compare(said, heard, fuzzy=0.75):
    """Is every token of `said` in `heard`, in order? Returns (missing tokens with positions, matched count).
    A token counts as matched when it is equal or at least `fuzzy` alike (a misheard word, not a dropped one)."""
    sm = difflib.SequenceMatcher(None, said, heard, autojunk=False)
    missing = []
    for tag, a0, a1, b0, b1 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace",):
            for k in range(a0, a1):
                j = b0 + min(k - a0, b1 - b0 - 1)
                if b1 > b0 and difflib.SequenceMatcher(None, said[k], heard[j]).ratio() >= fuzzy:
                    continue
                missing.append({"pos": k, "token": said[k]})
        elif tag == "delete":
            missing += [{"pos": k, "token": said[k]} for k in range(a0, a1)]
    return missing, len(said) - len(missing)
