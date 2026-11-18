# Cutout: the settings file

A 1080x1920 reel at 24 fps. He is cut out of his own video and stands on black at the bottom of the frame; the
picture that explains his words sits up top, a new one on a spoken word, and his corner switches on that word. Frame
one carries the claim over one of his screens. Pictures, figure cards on black, one or two shots of his own room, and a
picture that builds in under a figure as the figure lifts away. Captions in phrases on the lower line. Drawn frame by
frame in Python, film grade and grain, then the sound.

Needs: the base and the cutout model (`studio needs cutout`). The first render cuts him out of every frame of the
passage (about 1.5 to 2.5 seconds a frame on an Apple Silicon Mac, so 5 to 15 minutes for a 10 to 15 second reel); the
cut frames are kept in the project's `matte/` folder and every later version reuses them.

## Fields
```json
{"style": "cutout", "spec_version": 1, "passage": "passage/passage.json",
 "sources": {"screen": "sources/screen.mov"},
 "cutout": {"x": 0.49, "width": 0.69, "scale": 0.86, "band": 0, "brighten": 1.0},
 "opening": {"kicker": 1, "figure": "$40,000", "trail": "from an agency, 2019", "scale": 1.0, "side": "right",
             "picture": {"source": "screen", "in": 0.15, "crop": {"x": 0.03, "y": 0, "w": 0.79}}},
 "beats": [
  {"kind": "figure", "at": {"word": 7, "offset": -0.02}, "text": "$40,000", "size": 1.0, "side": "left",
   "label": [{"text": "AN AGENCY", "at": {"word": 10}}, {"text": "2019", "at": {"word": 12}}]},
  {"kind": "room", "at": {"word": 17}},
  {"kind": "figure", "at": {"word": 27, "offset": -0.02}, "text": "$20", "unit": "/ month", "old": "$40,000",
   "size": 1.16, "side": "right"},
  {"kind": "picture", "at": {"word": 32}, "source": "screen", "in": 9.4, "crop": {"x": 0.17, "y": 0.02, "w": 0.57},
   "keep_figure": true}
 ],
 "room": {"x": 0.49, "zoom": 1.4, "top": 440},
 "captions": [{"at": {"t": 0}, "text": "THIS RIGHT HERE"}, {"at": {"word": 21}, "text": "PAID FOR IT.", "red": "PAID"}],
 "tail": 1.0, "effects": {"softer_db": 0}, "finish": {"grain": 0.03}}
```

- `cutout` (optional): how he is cut out and placed.
  - `x` (0 to 1, default 0.5): where the middle of his body is across his video. His body's middle lands on the
    corner's centre line (left 300 px, right 780 px, centre 540 px).
  - `width` (0.3 to 1, default 0.69): how much of his video's width around `x` is used. Anything else the model
    finds outside it (a lamp, a screen) is never shown; inside it only his body and what touches it is kept.
  - `scale` (0.5 to 1.3, default 0.86): his picture is `scale` x 1080 px tall in a corner, its bottom on the frame's
    bottom edge; in the centre it is 1.5 times that.
  - `band` (0 to 61 px, default 0): a feathered ring of his own video around the cutout. On footage shot in a dark
    room this brings back dark hair the model drops (his room is black there, so it reads as shadow). Leave it at 0 on
    a lit room: it would show the room as a glow around him.
  - `brighten` (1 to 1.4, default 1): lifts a dim cutout before the grade.
- `opening` (optional): frame one.
  - `kicker`: the typewriter label "FIELD NOTES · NO. 01" (a number 1 to 99 sets the NO.; false hides it).
  - `figure`: up to 12 characters of his words (digits where he says a number), kit serif italic 200 px (times
    `scale`, 0.6 to 1.4) with the red brush under it. Too wide at that scale is an error.
  - `trail`: up to 28 characters of his words under it (kit sans 54 px).
  - `side`: his corner for the opening (default right).
  - `picture`: one of his screens or photos up top, behind the claim, its top darkened and defocused:
    `source` (a `sources` name or a project source; a video or a still), `in` (seconds into a video), `crop` (below).
- `beats` (1 to 12, in the order he says them; each starts at `at` and lasts until the next):
  - `kind: "picture"`: his screen, a frame of one of his videos, or a photo he gave, 1080 x 768 px with its top edge at
    330 px and its bottom 150 px fading to black, popping in (93 percent to full size with a 1.5 percent overshoot over
    0.3 s). `source`, `in`, `crop` as for the opening picture. `keep_figure: true` (only right after a figure card):
    the figure turns white, shrinks to 55 percent and rises over 0.32 s, the old figure fades, and the picture builds
    in under it at 400 px, 0.18 s later.
  - `kind: "figure"`: a card on black. `text` (up to 9 characters, his figure as digits where he said a number) in kit
    serif italic 285 px times `size` (0.6 to 1.5), red (`red: false` for white), popping in over 0.28 s. `unit`
    (optional, up to 10 characters, his word after the figure, "/ month") small beside it. `old` (optional, up to 9
    characters, an earlier figure of his) small, grey and struck above it; the figure sits 40 px lower then. `label`
    (optional, up to 3 parts of his words, each up to 18 characters) in typewriter capitals under the figure, parts
    joined by " · ": the first part appears on its word, each later one types on letter by letter from its word.
    A label pushes down 150 px for every 1.0 of `size` above 1.
  - `kind: "room"`: no cutout; his own video full width from `room.top` down, faded in from black at its top, with
    the film glow. Use it once or twice.
  - `side` (any beat but room): `left`, `right` or `centre`. Default: the corner switches on every picture, a lifted
    figure keeps its corner.
- `room` (optional): the room shot's framing. His video scaled so it is `zoom` x 1080 px tall (and at least the frame's
  width), `x` across it centred (default `cutout.x`), its top at `top` px. Defaults: zoom 1.4, top 440.
- `crop` (pictures): `x`, `y` (the box's top left, as fractions of the source's width and height) and `w` (its width
  as a fraction). The box keeps the picture's 1080 x 768 shape (cut at the source's bottom if it runs past it), so only
  the width is set. Default: the full width from the top left.
- `captions` (optional): `[{"at", "text", "red", "until"}]`, his words in capitals, 2 to 5 words each, Raleway 800 at
  58 px (smaller if a line would pass the 80 px side margins) on the baseline 1498 px, with the kit shadow. `red`: one
  word of that caption in red kit serif italic, shown red only while no red figure is on screen. Without `captions`
  the style makes phrases from his words: a break at full stops and commas, at every beat, at a pause of 0.3 s, at four
  words, never ending on a small word ("the", "a", "and"). Captions end half a second after his last word.
- `tail` (0 to 2, default 0.8): seconds the last frame holds after his last word.
- `effects` (optional): `{"softer_db": 2}` makes every effect 2 dB softer (up to 6); `false` removes them.
- `finish.grain` (0 to 0.08, default 0.03).
- `sound` (optional): the engine's sound block. Default bed: the cutout pad (A minor, F on the second beat, C on the
  third) 16 dB under his voice before it ducks 4 dB under his words.

## Effects (all code-made, at the levels he approved)
An air whoosh 0.12 s before every picture and figure (30 dB under his voice at its loudest), a low hit under each
figure card (27 dB under, the next ones 28), and four typewriter keys 0.05 s apart as each later label part types on
(31 dB under). The room shot has none.

## Fixed labels
"FIELD NOTES · NO. 01" to "NO. 99". Every other word on screen is his.

## The record and its checks
`layout.json` holds one beat per section (opening, picture, figure, room) and one per caption, with the box of every
text and the red brush. Besides the studio's checks, `qa.json` has:
- `cutout_found`: the cutout kept at least 2 percent of the picture in every frame (else the model lost him: look at
  those frames);
- `picture_pace`: how long each picture holds and how many room shots there are (more than two fails; a hold over 4.5
  seconds is a warning).
`v<N>/cutout.json` has the matte's speed and how much of the frame he fills.

## How his video is read
The cutout model runs on every frame of the passage at the reel's frame rate (never more than his video's own), once.
A new passage starts a new matte. Where his video cuts to another camera within 0.2 s of the edge of a range (old
videos often do, inside the last word), the cutout and the room shot hold the last good frame over it.
