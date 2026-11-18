# Screen and face: the settings file

A 1080x1920 reel in three bands: his screen on top (820 px), a black seam (190 px) where the figure lands, and him
below at the bottom (910 px). Everything is drawn by the shared motion project, then film grain, then the sound.

Needs: the base and the motion graphics part (`studio needs screen-and-face`).

## Fields
```json
{"style": "screen-and-face", "spec_version": 1, "passage": "passage/passage.json",
 "sources": {"screen": "sources/screen.mov"},
 "face": {"x": 0.49, "y": 0.03, "zoom": 1.19},
 "screens": [{"source": "screen", "from": {"word": 0}, "in": 150.65, "out": 155.25, "speed": 0.8,
              "push": [1.0, 1.05], "origin": "40% 55%"}],
 "beats": [{"kind": "figure", "at": {"word": 0}, "text": "$40,000",
            "lines": [{"text": "from an agency,"}, {"text": "2019"}],
            "rule": {"word": 7}, "strike": {"word": 24}}],
 "sound": {"bed": {"name": "drone", "under_db": 18}, "sfx": [{"name": "impact", "at": {"word": 7}}]}}
```

- `sources.screen`: his screen recording or a screenshot (a file inside the project; a screenshot is held for the
  whole shot). A screen shot can also come from any source of
  the project by its name (for example the talking video itself, when it has screen parts).
- `face` (optional): where he sits in the bottom band. `zoom` 1 fills the band with his whole frame (1 to 3); `x` is
  the point across his frame (0 left, 1 right) placed at the band's centre line; `y` the point down his frame (0 top)
  placed at the band's top edge. Defaults: x 0.5, y 0, zoom 1.
- `screens` (one or more, in order): each shot runs from its `from` (a word anchor; the first always starts at the
  first frame) until the next shot starts. `in` is the second on the screen recording it starts from; `out` (optional)
  where the recording stops, after which the shot holds its last frame. `speed` 0.25 to 4 (1 is real time; scrolls
  read well at 2). `push` is the slow push-in over the shot, start and end scale (default 1.0 to 1.05); `origin` the
  point it pushes towards ("50% 50%" is the centre).
- `beats` (one to six figures, in the order he says them). Each figure:
  - `at`: when the figure rises in. A first figure at word 0 is on screen from the first frame, already set (the
    claim on the first frame), settling in over half a second.
  - `text`: the figure, up to 9 characters: a number as digits ("$40,000", "50", "20%") or one or two of his words.
  - `scale` (optional): the figure's size, 0.7 to 1.4 (default 1, which is 168 px); the brush strike grows with it,
    the cream rule stays where it is. The figure must stay inside the seam's hairlines (a comma or a descender may
    reach 8 px past, as at scale 1) and 24 px clear of its lines; a scale that does not fit is an error that names
    the most it can take. Measured: "$40,000" next to "from an agency," takes up to 1.14, "$20" 1.31, "50" 1.4.
  - `lines` (up to two): short italic lines on the right, each his words (up to 24 characters), each with its own
    `at` (default: with the figure). A plus sign may stand for "and".
  - `rule` (optional): a thin cream line draws under the figure at this word (when he says the number).
  - `strike` (optional): the red brush strikes through the figure at this word; its lines leave as it strikes.
  - `underline` (optional): a red line draws under the lines at this word.
  - `until` (optional): when the figure starts to leave. Default: a quarter second before the next figure; the last
    figure stays to the end.
  - One red per figure at most: `strike` or `underline`, never both.
- `join_sound` (optional): the effect under every join between two pieces of his speech. Default a soft whoosh 29 dB
  under his voice, 0.08 s before the join; `false` for none.
- `finish.grain` (optional): film grain strength, 0 to 20, default 7.
- `sound`: the shared sound block. This style's bed is `drone` 18 dB under; effects 26 to 29 dB under: `impact` on the
  spoken figure, `brush` on the strike, `card` on a later figure.

Every anchor is `{"word": i}`, optionally with `"edge": "end"` and `"offset"` in seconds.

## Fixed in the style (as he picked it)
Figures in the kit serif at 168 px (times `scale`), 80 px from the left; lines in the kit serif italic at 50 px, right-aligned 80 px
from the right; cream text on the black seam with a hairline above and below; the screen band darkens at its foot and
its edges; his band has a soft shadow under the seam; every second piece of his speech is pushed in 6 percent to soften
the jump cut; figures rise out of a mask and sharpen as they land, and leave upwards with a short blur.

## Labels
None: every word on screen is his.
