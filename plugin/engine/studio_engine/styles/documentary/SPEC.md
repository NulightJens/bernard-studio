# Documentary: the settings file

A 1080x1920 reel framed like a short documentary: a 2:1 picture band (1080 x 540, from y 470 to 1010) between two
hairlines, black above and below. Above the band a small archive mark and, when he first fills the band, a lower third
with his name. In the bottom third the figure (on screen from the first frame), its source line, a red brush under it
on the word that proves it, then the count to the new figure on the word he says it; documentary subtitles under it,
and a closing red line that takes their place. Film grade, halation, gate weave and grain; the documentary score.

Needs: the base only (`studio needs documentary`).

## Fields
```json
{"style": "documentary", "spec_version": 1, "passage": "passage/passage.json",
 "sources": {"broll": "sources/broll.mov"},
 "shots": [{"from": {"word": 0}, "source": "broll", "in": 0.12,
            "start": {"x": 0.47, "y": 0.52, "zoom": 1.13}, "end": {"x": 0.45, "y": 0.52, "zoom": 1.26}},
           {"from": {"word": 7, "offset": -0.02}, "start": {"x": 0.49, "y": 0.31, "zoom": 1.67}}],
 "figure": {"text": "$40,000", "line": "FROM AN AGENCY, 2019", "underline": {"word": 21}, "size": 190,
            "to": {"text": "$20", "unit": "/ month", "line": "NOW", "at": {"word": 27}}},
 "subtitles": [{"from": 0, "to": 2}, {"from": 3, "to": 7}],
 "close": {"text": "+ a conversation.", "at": {"word": 32}},
 "lower_third": {"title": "..."},
 "mark": {"reel": 1},
 "film_sound": true,
 "sound": {"bed": {"name": "documentary", "under_db": 16.5, "changes": [{"word": 13}, {"word": 24}],
                   "mallets": [{"at": {"word": 7}, "note": "A3", "gain_db": -2}]},
           "sfx": [{"name": "sub-hit", "at": {"word": 7}, "under_db": 28}]}}
```

- `shots` (1 to 12, in order): what the band shows. Each runs from its `from` (a word anchor; the first always starts
  at the first frame) until the next one starts.
  - No `source`: his talking picture, in sync with his words.
  - `source`: a name from `sources` or any source of the project (another video of his, a screen recording, a
    photo), played from second `in` at `speed` (0.25 to 4, default 1). Use it for B-roll with no talking in it: his
    lips would not match.
  - `start` and `end`: the frame at the start and end of the shot, eased between (one slow push or one slow move
    across). `x` and `y` are the point of the source picture (0 to 1 across and down) at the band's centre; `zoom` 1
    shows the source's full width (a 16:9 source is then cropped top and bottom to 2:1). Up to about 2.3 on 1080p
    footage before it goes soft. `end` defaults to `start` (a still frame).
  - `tone` (optional): "face" lifts his talking picture a little (the default without a `source`); "screen" tones a
    bright screen or B-roll down to sit in the dark film (the default with a `source`).
- `figure` (optional; leave it out when the words have no number):
  - `text`: the figure as digits or one or two of his words, up to 10 characters. On screen from the first frame;
    `at` (optional) fades it in on a word instead.
  - `line` (optional): a short source line under it in typewriter caps, his words, up to 28 characters.
  - `underline` (optional): the red brush draws under the figure on this word (the word that proves it).
  - `size` (optional): the figure's size in pixels, 120 to 300, default 190. The line under it moves with it. A figure
    too wide for the frame at that size is refused, with the largest size that fits.
  - `to` (optional): the new figure. `at` is the word he says it on: the count runs for 0.55 s and lands exactly
    there (numbers count; words give way to each other). `unit` (optional, up to 12 characters) appears beside it as he
    says it ("/ month"); `line` replaces the source line. Clock ticks run under the count.
- `subtitles` (optional): the lines of his words under the figure, as word ranges `from`..`to`, in order, every word
  in one line. Left out, they are made from his words (a line ends on a full stop or comma, at five words or about 26
  letters). Shown in capitals.
- `close` (optional): a closing line in red, his words, up to 28 characters ("+" may stand for "and"). From its `at`
  it takes the subtitles' place until the end.
- `lower_third` (optional): his name in small caps above the band, for 2.45 s when he first fills the band (or from
  `at`). `title` adds a second line under his name, only a title he gave himself: save it first with
  `studio brand set style.documentary.title "<his title>"`; any other title is refused. `false` hides the lower third.
- `mark` (optional): the archive mark above the band, "FIELD NOTES · REEL 01"; `reel` sets the number (1 to 99).
  `false` hides it.
- `film_sound` (optional, default true): the projector under the open (31 dB under his voice) and the clock ticks
  under the count (33 dB under), both made in code. `false` for neither.
- `grain` (optional): film grain strength, 0 to 0.08, default 0.04.
- `sound`: the shared sound block. This style's bed is `documentary`, 16.5 dB under his voice before it dips under
  him (about 20 dB under while he talks); `changes` are the two chord changes (D minor, B flat, F), on the turns of
  his story; `mallets` are felt notes on the figure moments. Effects: `sub-hit` on the spoken claim (28 dB under),
  `noise-swell` 0.9 s before the new figure (32 dB under).

Every anchor is `{"word": i}`, optionally with `"edge": "end"` and `"offset"` in seconds.

## Fixed in the style (as he picked it)
The 2:1 band at y 470 with hairlines; the figure in the kit serif italic, centred, baseline at y 1235; the source line
in the typewriter face; subtitles in the caption face at 42 px, y 1490; the closing line in the serif italic at 96 px,
red on footage; the mark at y 250; the lower third at x 120; every shot eases with a little constant drift, a gate
weave under half a pixel, the cinema grade (ink-blue shadows, warm highlights), halation, a soft vignette in the band;
the picture fades out 0.6 s after his last word; the piece ends 1.4 s after it.

## Labels
"BERNARD ABLOLA", "FIELD NOTES  ·  REEL 01" to "REEL 99", and his saved title. Every other word on screen is his.
