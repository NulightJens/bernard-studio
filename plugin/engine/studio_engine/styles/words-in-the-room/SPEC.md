# Words in the room: the settings file

A 1080x1920 reel. His own room is the picture; his words are set on the wall behind him, and a cutout of him (every
frame through the matte) is laid back over them, so his head and hands pass in front of the words. One slow camera push
carries room, words and him together, so the words stay fixed to the wall. Drawn by the shared motion project, then
film grain, then the sound.

Needs: the base, the motion graphics part and the cutout model (`studio needs words-in-the-room`). The camera must
not move: the render's first step checks it (below) and stops before the long cutout step if it does.

## Fields
```json
{"style": "words-in-the-room", "spec_version": 1, "passage": "passage/passage.json",
 "room": {"scale": 0.9, "left": -153, "top": 700},
 "camera": {"push": 0.085, "drift": -14, "focus": [693, 934], "light": [351, 1078]},
 "wall": [{"kind": "figure", "text": "$40,000", "at": {"word": 0}, "x": "center", "y": 612, "size": 236,
           "warm": {"word": 7}, "strike": {"word": 24}, "dim": {"word": 26}, "until": {"word": 33}},
          {"kind": "type", "text": "AN AGENCY", "at": {"word": 10}, "x": 130, "y": 864.5,
           "until": {"word": 26}, "leave": "fade"},
          {"kind": "title", "text": "FOUNDATION", "at": {"word": 42}, "x": "center", "y": 689,
           "stack": [{"word": 45}, {"word": 46}, {"word": 47}]}],
 "sound": {"bed": {"name": "drone", "under_db": 18},
           "sfx": [{"name": "impact", "at": {"word": 7, "offset": 0.11}, "under_db": 27, "len": 1.6}]}}
```

- `room`: where his video sits in the reel, in reel pixels (1080 wide, 1920 tall). `scale` is reel pixels per pixel
  of his video; `left` and `top` are where his video's top-left corner lands (negative moves it off the left or top
  edge). A point (x, y) of his video lands at (left + x * scale, top + y * scale). Above his video the reel carries the
  room's own colour (measured from the top rows of his video, or `fill` as "#RRGGBB"); the video fades into it over
  150 px, and fades out again into the dark from y 1480 to 1672 (under the caption zone). Defaults: a landscape video
  at 972 px tall with its top at 700 and centred; a vertical video filling the width from the top.
- `camera` (optional): `push` is how much the camera moves in over the whole piece (0.085 is 8.5 percent, 0 for none,
  up to 0.2); `drift` how far it rises, in pixels (-14); `focus` the reel point it pushes towards (his face); `light`
  the reel point the room's light falls on (the edges darken away from it).
- `wall` (one to ten, in the order he says them): each is one block of his words on the wall.
  - `kind`: `figure` (the big serif number, 236 px), `line` (serif italic, 64 px), `type` (typewriter capitals, 36 px,
    typed on letter by letter), `title` (spaced heavy capitals, 76 px).
  - `text`: his words, up to 24 characters. Numbers as digits. A plus sign may stand for "and". Typewriter and title
    words in capitals.
  - `at`: when it appears. Word 0 (anything in the first quarter second): on the wall from the first frame, already
    set, settling in over half a second (the claim on the first frame). Otherwise a figure or title rises in, a line
    rises in, a typewriter line types on.
  - `x`: the left edge in reel pixels, or "center". `y`: the top of the text in reel pixels. `size`: the text's
    height in pixels (defaults above). Keep text 80 px from the sides and between y 220 and 1620, allowing for the
    push: text near the left edge moves out by up to 9 percent of its distance from `focus`.
  - `warm` (optional): the glow around it swells once here (when he says it).
  - `strike` (optional, figures only, one in the piece): the red brush strikes through it here.
  - `dim` (optional): it steps back to a third of its brightness here (an old figure making room for a new one).
  - `until` (optional): it leaves here. `leave`: `lift` (default: rises and goes soft over two thirds of a second, the
    wall clearing) or `fade` (fades in place). Without `until` it stays to the end.
  - `stack` (optional, titles only, up to three): a thin rule is laid above the title on each of these words, the first
    nearest the title, each one wider ("now we build upon it").
- `color` (optional): the words' colour, default warm white "#EFE4CF".
- `end_hold` (optional): seconds the last frame holds while the reel fades out, default 0.6.
- `finish.grain` (optional): film grain strength, 0 to 20, default 7.
- `sound`: the shared sound block. This style's bed is `drone` 18 dB under; effects 26 to 28 dB under: `impact` on
  the spoken figure, `brush` on the strike, `air-whoosh` when the wall clears.

Every anchor is `{"word": i}`, optionally with `"edge": "end"` and `"offset"` in seconds.

## The camera check
Before anything else the render cuts him out of five frames across the passage, masks him away and lines the rest of
the frame (the room) up against the first frame. If the room moves more than 4 pixels (on a 1080-line video), the
render stops with a plain message and suggests another style. The picture `matte/camera-check.png` in the project shows
the first frame, the frame that moved most, and the difference of their backgrounds (him greyed out): black means
still, outlines of the furniture and wall mean the camera moved. QA reports the numbers as `camera_still`.

## Checks of its own (in qa.json)
- `camera_still`: the measured move (`worst_px`) against the limit, the samples, and how well each lined up (`match`,
  below 0.5 means a cut to another picture).
- `wall_fit`: blocks on the wall at the same time (from `at` until `until`) keep 12 px apart, measured on their ink.

## Fixed in the style (as he picked it)
The warm glow on every word, the room's light falling off towards the edges over everything, the cutout used as the
matte gives it (no erode, no feather), the first-frame settle, rise and type-on timings, the strike's angle (3 degrees)
and size (the figure's width plus 0.8 of its height), the end fade over the last 16 frames.

## Labels
None: every word on the wall is his.
