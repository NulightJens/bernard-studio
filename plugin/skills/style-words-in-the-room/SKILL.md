---
name: style-words-in-the-room
description: The "Words in the room" style guide. How to check his footage suits it (a still camera, some wall around him), pick his words, place them on the wall behind him, write its settings file, and make the next version from his notes. Load when the studio skill has picked Words in the room.
user-invocable: false
---

# Words in the room

His own room is the picture. His words are set on the wall behind him, and he stays in front of them: his head covers
the foot of the big number, his hands pass in front of the smaller lines. The claim is on the wall from the very first
frame and glows once when he says it. When the story turns ("now it costs..."), a red brush strikes the old number and
the new one rises beside him; later the wall clears and a last word sets above his head. One slow push towards his face
carries the room, the words and him together, so the words look painted on the wall. Quiet low drone under his voice,
a soft boom on the number, a brush sound on the strike, a breath of air when the wall clears.

## What it needs
- **A talking video shot on a tripod.** The camera must not move at all: no handheld, no slider, no zoom, no cuts to
  other angles inside the words you pick. Words fixed to a wall only work if the wall stays put.
- **Some wall around him**: beside his head or above it. A dark or plain wall reads best (warm white words on it).
- **One shot, 8 to 18 seconds** of him making one point, ideally with a figure in it (a price, a time, a count).
- The style needs the motion graphics part and the cutout model (`studio needs words-in-the-room`). The cutout model
  runs on Apple silicon Macs with 16 GB of memory or more.

What to tell him to record if he has nothing yet: "Put the phone or camera on a tripod, sit a little to one side of the
frame with some wall showing beside or above your head, and talk for 10 to 20 seconds about one thing. Say the number
out loud if there is one."

## Is the camera still?
Ask him first: "Was the camera on a tripod for this one?" If he says it was handheld, or it is an edited video that cuts
between angles, recommend another style straight away (below).

The studio also measures it. The first step of every version (about half a minute, before the long cutout step) cuts
him out of five frames across his words, masks him away, and lines up what is left (the room) against the first frame:
a frame difference on the background. If the room moves more than a few pixels, or the picture cuts to something
else, the version stops with a plain message, and the project's `matte/camera-check.png` shows why: the first frame,
the frame that moved most, and the difference of their backgrounds with him greyed out. Read that picture yourself:
- the wall and furniture are black in the third panel: the camera is still;
- the edges of the furniture, frames and wall show as bright outlines: the camera moved (handheld drift, a slow push or
  a slider);
- the second panel shows a different picture: the words cross a cut.
The numbers are in the version's `qa.json` under `camera_still` (`worst_px` against `limit_px`).

When the camera moves, tell him in one line and offer the closest style that works with it:
- **Screen and face** if he talks about something on his screen (it needs a screen recording or screenshot);
- **Documentary** for a calm talking take with a number in it (it reframes any footage);
- **Cutout** for a well-lit take where a new picture on each key word fits.
Or, if the video has a still part, pick words from that part instead.

## Picking the words
1. Ingest the video and read the transcript.
2. Find 8 to 18 seconds in ONE shot that make one point. Best: a claim with a number, a turn ("now..."), and a short
   last line that can be the final word on the wall ("This is just the foundation. Now we build upon it.").
3. Old videos: edited videos cut between angles and to screens. Pick words that sit inside one shot. Burned-in
   captions from the old edit stay in the picture; prefer a part without them, or frame them out (see the room).
4. Show him the exact words in quotes and how long they run. On his yes:
   `studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then
   `studio voice "<project>"`. One range is best: a cut inside the words jumps the picture.

## The room (where his video sits)
Leave `room` out for the first version: the studio frames him as in the example (his video 972 px tall, his head a
right of centre (x 713) with its top at y 795, the room's own colour carried up above it). After the first version,
`v1/room.json` says where his head landed (`his_head_in_reel`: its top, its centre and width in reel pixels), where it
is in his own video (`camera.him`: `head_x`, `head_top` in his video's pixels) and the framing used (`room`). Change the framing only if the sheet shows a problem:
- **The room above him is light or busy** (a pale wall, a painting, a window): the carried-up colour looks like a flat
  grey band, and warm white words do not read on a pale wall. Either let the room fade into black above him
  (`"fill": "#0A0908"`, like a spotlit room) and set the words in the dark above his head, or fill the frame with the
  room (a larger `scale`, 1.3 to 1.6 for a 1080-line video, `top` at 0 or just below) and set them on a darker part
  of the wall beside his head. The first keeps the look he picked; prefer it.
- **He sits in the middle of a wide shot**: `scale` 1.0 to 1.2 brings him closer; keep his head about 0.6 of the way
  across (`left` = 650 - his head's x in his video x `scale`).
- **Something from the old edit shows at an edge** (a caption, a screen, the edge of the set): move `left` or raise
  `scale` until it is outside the reel. A point x of his video lands at `left + x * scale`.
- Keep his face on the upper half of the reel and his body down to at least y 1500.

## The words on the wall
Read `passage/passage.json`; every word has a number `i`. Plan two to six blocks, never more than three on the wall at
once. Every block is his words, trimmed, never reworded.
- **The claim** (a `figure`, 236 px): the number he leads with, `"at": {"word": 0}` so it is on the wall from the first
  frame even if he says it later, `"x": "center"`, and `warm` on the word where he says it. Set it high, with its foot
  just behind the top of his head: `y` about (top of his head + 15) - 0.82 x size. In the example his head top is at
  795, so the $40,000 sits at y 612.
- **Small lines beside him** (`type`, 36 px, typed on as he says them): "AN AGENCY", "2019", "A MONTH". Put them on
  the wall beside his head or shoulder, `x` 130 or more (the push moves text near the edge outwards), stacked about 49
  px apart. Capitals.
- **A short italic line** (`line`, 64 px): "+ a conversation.", "worth doing." (a plus may stand for "and").
- **Then and now**: on the turning word (the "Now"), `strike` the claim (the one red in the piece); from the next
  word, `dim` it and let the small lines of the old figure leave (`until`, `"leave": "fade"`); the new figure (a
  `figure` at 150 px on the side wall) rises on its word with its lines after it.
- **Clearing the wall**: give every block on the wall the same `until` on the word where his thought turns ("But
  we're not done yet"): they lift and go soft together.
- **The last word** (a `title`, 76 px spaced capitals): the one word that sums it up ("FOUNDATION"), centred above his
  head, rising on its word; `stack` lays up to three thin rules above it on the words that follow ("build", "upon",
  "it"). The example starts each a fifth of a second early (`"offset": -0.2`) so it is up as he says it.
- Positions are reel pixels: `x` the left edge (or "center"), `y` the top of the text, `size` its height. Keep every
  block between x 80 and 1000 and between y 220 and 1620.
- `at`: the word where it appears; a typed line starts on its first word. Word numbers come from his passage, never
  from the example.

## Sound
`"bed": {"name": "drone", "under_db": 18}`. Effects: `impact` on the spoken figure (27 dB under, `"len": 1.6`, about
a tenth of a second after the word starts), `brush` on the strike (26, 0.7), `air-whoosh` when the wall clears (26,
1.4). Two or three effects in a reel, no more. Without a strike, leave the brush out.

## Settings file
Write `spec.json` in the project folder from the worked example, `example-spec.json` beside this guide. It is the
example he picked: "$40,000" on the wall from the first frame, "AN AGENCY" and "2019" typed beside him, struck on
"Now", "$20 / A MONTH / + a conversation." on the left wall, the wall clearing on "But we're not done yet", then
"FOUNDATION" above his head with three rules laid on "build upon it". Every field is described in the style's
`SPEC.md` (in the plugin's `engine/studio_engine/styles/words-in-the-room/`).

Then `studio render "<project>" --spec "<project>/spec.json"`. The first version cuts him out of every frame, which is
the slow part; later versions of the same words reuse that cutout and are much quicker. If you change the words
(a new passage), the cutout runs again.

## Before he sees it
Look at `v<N>/sheet.png` (a frame at every block) and at full-size frames yourself:
- Is every block readable? His head may cover the foot of the big number, never most of it. A small line hidden behind
  his hand for a moment is fine; hidden for its whole time is not: move it.
- The cutout's edges: look at his hair and both hands at full size against the words. No halo of the old wall around
  him, no missing fingers. Fast hand moves blur in the video itself; that is fine.
- Nothing from an old edit (a caption, a screen) at the edges, and no frame of another shot at the start or the end.
- `qa.json` passes: every word heard back, loudness, safe zones, one red, his words only, `camera_still`, and
  `wall_fit` (blocks on the wall at the same time keep 12 px apart; it names any two that touch).

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Move the words higher / lower": lower or raise the named block's `y` by 60 to 120 px (a group of lines that sit
  together moves together). Higher means a smaller `y`. Stay below y 220.
- "Bigger / smaller": multiply the named block's `size` by about 1.25 (or 0.8). For a centred block that is all; for a
  block with an `x`, check it still ends before x 1000 (its width grows with the size). A figure whose foot sits
  behind his head grows upwards: raise its `y` by 0.82 x the growth so the foot stays where it was. If `wall_fit` in
  `qa.json` then names a block it runs into, move that block away by the overlap (that is part of making it bigger,
  not a new change), and tell him in one line.
- "Move it to the other side": change its `x` (left wall 130, right wall about 700 for short lines).
- "Closer on me / more of the room": `room.scale` up or down by 0.1, keeping `his_head_in_reel` where it was by moving
  `left` and `top` with it.
- "Less movement": `camera.push` 0.04, or 0 for none.
- "The red should be on X": move the `strike` to that word (figures only).
- "Less sound": raise the effects' `under_db` by 2 (never past 30) or remove one.
- "Start on the second sentence": make a new passage from that sentence, then move every anchor (word numbers change;
  read the new `passage.json`) and keep everything else. The cutout runs again for the new words.

## Common mistakes
- Footage where the camera moves, or words that cross a cut: the first step stops. Offer another style.
- A claim not at word 0: the first frame shows an empty wall.
- The big number behind his face: set it higher, so only its foot passes behind his head.
- Text closer than 130 px to the left or right edge: the push carries it past the safe margin.
- Words he never said. Every block is his words; numbers as digits are fine.
- More than one strike (two reds).
- Word numbers copied from the example.
