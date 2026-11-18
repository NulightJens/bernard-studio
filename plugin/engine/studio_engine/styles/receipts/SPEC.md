# Receipts: the settings file

A 1080x1920 reel at 24 fps in four parts: the opening (his screen or him, with the claim set from the first frame),
card one "FIG. 01 Then." with a receipt for the old figure, him on camera, and card two "FIG. 02 Now." with the old
receipt greyed and struck at the side and a new receipt for the new figure. Drawn frame by frame in Python, film grade
and grain on everything, then the sound.

Needs: the base only (`studio needs receipts`).

## Fields
```json
{"style": "receipts", "spec_version": 1, "passage": "passage/passage.json",
 "sources": {"screen": "sources/screen.mov"},
 "opening": {"figure": "$40,000", "trail": "from an agency, 2019", "kicker": true, "scale": 1.0,
             "until": {"word": 7}, "screen": {"source": "screen", "in": 0.2, "x": 0.38}},
 "face": {"x": 0.49, "zoom": 1.4, "top": 440},
 "then": {"at": {"word": 7, "offset": -0.025}, "until": {"word": 12, "edge": "end", "offset": 0.07},
          "total": "$40,000", "scale": 1.0, "item": "THE WHOLE THING",
          "rows": [{"label": "FROM", "text": "AN AGENCY", "at": {"word": 10}},
                   {"label": "DATE", "text": "2019", "at": {"word": 12}}]},
 "keyword": {"at": {"word": 21}, "text": "PAID", "trail": "FOR IT.", "trail_at": {"word": 22}},
 "now": {"at": {"word": 24}, "total": "$20", "unit": "/ month", "total_at": {"word": 27},
         "hand": {"text": "a conversation.", "at": {"word": 32}}},
 "captions": [{"at": {"t": 0}, "text": "THIS RIGHT"}, {"at": {"word": 2}, "text": "HERE"}],
 "tail": 1.0, "effects": {"softer_db": 0}, "finish": {"grain": 0.03}}
```

- `opening` (optional): the claim on the first frame.
  - `figure`: up to 9 characters, his figure as digits or one or two of his words, kit serif italic 200 px (times
    `scale`, 0.7 to 1.4), centred, with the kit's red brush under it. Too wide for the frame at that scale is an error.
  - `trail`: up to 28 characters of his words under the figure (kit sans 54 px).
  - `kicker`: the typewriter label "THE RECEIPTS" above the figure (default true).
  - `until`: when the opening ends (default: when card one comes in). Whatever lies between `until` and card one is
    him on camera.
  - `screen` (optional): `source` (a `sources` name or a project source; a video or a still), `in` (seconds into the
    recording), `x` (0 to 1, where the full-height 9:16 crop is centred across the recording). The screen pushes in
    3.5 percent over the opening, darker and defocused at the top under the claim. Without `screen` the opening shows
    him.
- `face` (optional): his picture while on camera. Scaled so its height is `zoom` x 1080 px (and at least the frame's
  width), the point `x` across it centred, its top edge at `top` px with a 140 px fade from black. Defaults: x 0.5,
  zoom 1.4, top 440.
- `then` and `now` (both required), the two receipts:
  - `at`: when the card comes in (the slip lands over 0.22 s: drops 26 px, settles from 103 percent).
  - `until` (`then` only): when card one leaves (default: when card two comes in). Card two stays to the end.
  - `total`: up to 9 characters, kit serif italic 178 px times `scale` (0.7 to 1.4); the slip widens from 640 px for a
    big figure, up to 860 px (wider is an error naming the field). `unit` (up to 10 characters) sits beside it at
    64 px times `scale`.
  - `total_at`: when the figure appears (default: with the card). Card one's figure is red; card two's is red until
    the handwritten line starts, then ink.
  - `rows` (up to two): `label` (FROM, DATE, FOR, TIME, WHO, PLUS), `text` (his words, up to 18 characters, typed in
    capitals at 0.03 s a letter from `at`; default: with the card).
  - `item`: one typed row above the total (his words, up to 18 characters).
  - `hand` (`now` only, instead of rows): `text` up to 18 characters in the kit's marker face, red, written on over
    0.55 s from `at`, under the label `label` (PLUS, FOR or FROM; default PLUS).
- `keyword` (optional): one of his words, up to 8 characters, kit serif italic 210 px in red while he is on camera,
  from `at` until the next card; `trail` (up to 16 characters) under it from `trail_at`. Must fall while he is on
  camera.
- `captions` (optional): `[{"at", "text", "until"}]`, his words in capitals (up to 22 characters). Each shows from
  `at` until the next caption, the end of its part, the keyword or the handwritten line. On him: kit sans 800 at the
  kit's caption size with its shadow, top at y 1210. On the cards: 50 px in an ivory box centred on y 1530. Without
  `captions`, two-word captions are made from his words (breaking after a comma or full stop).
- `tail` (0 to 2, default 0.8): seconds the last card holds after his last word.
- `effects` (optional): `false` for none, or `{"softer_db": n}` (0 to 6) to make every effect that much softer.
- `finish.grain` (0 to 0.08, default 0.03): film grain strength.
- `sound` (optional): the shared sound block. Default bed: `pad-minor` 16 dB under his voice before the duck (about
  20 after), changing on card two. Add `sfx` here only for something the style does not already place.

Every anchor is `{"word": i}`, optionally with `"edge": "end"` and `"offset"` in seconds, or `{"t": seconds}`.

## Effects the style places (as he heard them, dB under his voice at their loudest)
A pop at 0 s (30) and on the keyword (30); paper as each card comes in (27, 0.6 s, 0.04 s early); three typewriter
keys 0.06 s apart on each typed row (31); a soft thud on the keyword (27); a marker line on the handwriting (28). All
code-made except paper (the studio's own recording).

## Fixed in the style (as he picked it)
The kit's dark card ground with corner ticks; FIG. label in the typewriter face at (112, 268), title at 168 px at
(104, 420); slip one at 2 degrees centred at y 470, slip two at -2.5 degrees 70 px right of centre at y 500, the old
slip at 7 degrees, 74 percent, 72 percent opacity, at (-40, 610) running off the left edge on purpose (it is
decoration, recorded as a mark, not text); torn paper edges and a soft contact shadow; film grade (ink-blue lift, warm
highlights, halation, vignette) on him and on the screen; grain on every frame; one red at a time.

## Labels
THE RECEIPTS, FIG. 01, FIG. 02, Then., Now., RECEIPT, ITEM, TOTAL, * * *, and the row labels FROM, DATE, FOR, TIME,
WHO, PLUS. Every other word on screen is his.
