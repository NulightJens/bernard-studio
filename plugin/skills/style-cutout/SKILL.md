---
name: style-cutout
description: The "Cutout" style guide. How to judge whether his video can be cut out cleanly (check a cut-out frame before committing), pick the words, plan a new picture on a spoken word every two to four seconds from his own screens, video frames and photos, set the figure cards, the room shot and the captions, write its settings file, and make the next version from his notes. Load when the studio skill has picked Cutout, or to check whether a video suits it.
user-invocable: false
---

# Cutout

The fastest reel in the set. He is cut out of his own video and stands on black at the bottom of the frame, flush with
the edge where the camera cuts him. Up top sits the picture that explains what he is saying, and a new picture lands
on a spoken word every two to four seconds while his corner switches on that word. Frame one already carries the claim:
a small typewriter "FIELD NOTES · NO. 01", the big figure in his serif italic with his red brush under it, and a short
line of his words, over one of his screens. Then, on his words: his screens, a figure card on black (the figure pops in
red, a small label types on as he says it), one shot of his own room with him full frame, and at the end a picture that
builds in under the figure as the figure lifts away and turns white. Captions in short phrases on the lower line. A
dark pad under his voice, soft air whooshes on each picture, low hits under the figures, typewriter keys on the label.

## What it needs
- **A talking video of him** that cuts out cleanly (judge it first, below). 8 to 18 seconds of his words, with him on
  camera the whole time.
- **Pictures for the top**, only from what he gives you: his screen recordings or screenshots, frames of his own videos
  (a screen he shows, his desk, a slide), or photos he hands you. Never make or generate a picture. Three to five
  different pictures for 10 to 15 seconds. Each picture shows the thing he is saying at that moment.
- The base install and the cutout model (`studio needs cutout`; about 6 GB, Apple Silicon with 16 GB of memory).

What to tell him to record if he has nothing yet: "Sit facing a window or a lamp, with a lighter wall a little behind
you, and say it in one or two sentences. Then record your screen showing what you talk about, or send me photos of it."

## Judge the footage first (before picking words)
The cutout model has to find the edge of his hair, ears and shoulders in every frame. Look at a full-size frame of the
part you would use (`studio frame "<project>" --source <name> --at <second>` saves one in the project folder; read it
with the Read tool). It suits this style when:
- **His face and hair are well lit**, with clear detail in the hair.
- **His hair stands apart from what is behind it**: a lighter or brighter wall, or a light on the back of his head.
  Dark hair against a dark room is where the model fails: it cuts the hair off.
- **His head is fully in the frame**, and the camera stays on him (no cut-aways inside the words you will use).
- Big burned-in captions near his head are a problem only if they touch him; the cutout leaves the rest behind.

**Then check one cut-out frame before committing** (a few seconds per frame):
`studio matte "<project>" --source <name> --t0 <second> --t1 <second + 0.5> --frames 1`. It writes
`matte/<run>/rgba/p00001.png` (him with the background removed) and `sheet.png` (on a grey check). Look at both at full
size: is all of his hair there, and his ears, glasses and hands? Is any of the room left around him? Do this at two or
three moments across the words (his head turns, a hand comes up).

**If his footage is too dark, or the hair is cut off:**
- If the room behind him is black (a dark room, a black wall), set `"band": 31` in `cutout`: a soft ring of his own
  video around him brings the hair back and reads as shadow on the black ground. Check a version at full size around
  his head. It only works on a dark room: on a lit room it shows a glow of the wall around him.
- If it is only a bit dim, `"brighten": 1.15` (up to 1.4) lifts him.
- Otherwise tell him plainly: "This video is too dark around your hair for a clean cutout." Recommend re-recording
  with the setup above, or a style that keeps his room as it is: **Receipts** (a figure before and after),
  **Documentary** (a calm story) or **Screen and face** (his screen above him).

## Picking the words
1. Ingest the talking video and any screen recordings or photos (`studio ingest`). Read the transcript.
2. Find 8 to 18 seconds that make one point, ideally with a figure in it (a price, a count, a time) and a line that
   lands at the end. Two ranges are fine when they read as one thought (`--from .. --to .. --from .. --to ..`,
   `--gap 0`).
3. Check the camera stays on him through every range: look at frames every half second, and at the very first and
   last tenth of a second of each range. Old videos often cut to another camera or a screen right at the end of a
   word; a frame or two there is fine (the style holds his last good frame), more is not: pick other words.
4. Show him the exact words in quotes and how long they run. On his yes:
   `studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then
   `studio voice "<project>"`.

## Planning the reel
Read `passage/passage.json`: every word has a number `i` and a start time. Plan the beats on paper first:
1. **Frame one**: the claim over one of his screens. Him in a corner (right by default).
2. **A new picture every 2 to 4 seconds**, each on a word he stresses. The first one lands 2 to 4 seconds in. Vary the
   gaps; never hold one picture more than 4 seconds. A picture can be:
   - `picture`: one of his screens, a frame of his video or a photo, up top;
   - `figure`: a figure card on black, landing one frame before he says the figure
     (`{"word": i, "offset": -0.02}`);
   - `room`: him full frame in his own room, no cutout. Once, at most twice, on a line he says straight to camera.
     Only when his room looks good lit as it is.
3. **His corner** switches on every picture (left, right; `centre` makes him big in the middle, for a line he says
   straight to us). Never three in a row on one side. You can leave `side` out and the style switches for you.
4. **The ending**: if the last thing he says answers a figure, use a `picture` with `keep_figure: true` right after the
   figure card: the figure lifts away, turns white and the picture builds in under it ("a conversation." under
   "$20 / month").

### The claim (`opening`)
- `figure`: the most striking figure or few words of the piece, his words, digits where he says a number
  ("$40,000", "365 days"). Up to 12 characters; `scale` 0.6 to 1.4 if it needs to be smaller or bigger.
- `trail`: a short line of his words under it, up to 28 characters ("from an agency, 2019", "every single day").
- `kicker`: the piece's number in his field notes series (1, 2, 3 ...), or `false`.
- `picture`: the screen that shows what the piece is about.

### Pictures (`source`, `in`, `crop`)
- Name each source in `sources` (`"screen": "sources/screen.mov"`) or use a project source by its name.
- `in`: the second of the recording to start from (a still photo needs none). Look at frames there; pick a moment
  that shows the thing clearly, with no old captions and no cut inside the next three seconds.
- `crop`: the box to show, as fractions of the source: `x` and `y` its top left, `w` its width (the height follows the
  picture's shape, 1080 by 768). Crop in on the part that matters (a page title, a headline) so it reads on a phone.
  Leave it out to show the full width.

### Figure cards
- `text`: his figure as digits where he says a number ("$40,000", "365", "2,000") or one or two of his words, up to 9
  characters. His serif sets numbers in the old style: a lone small digit ("2") reads small, so prefer the word he
  said, or a bigger `size`.
- `size` (0.6 to 1.5, default 1): the figure's size. 1.16 is clearly bigger, 0.85 clearly smaller. Too wide for the
  frame is an error: take the largest that fits.
- `unit` (optional): his word after the figure, small beside it ("/ month", "days").
- `old` (optional): an earlier figure of his, small, grey and struck above ("$40,000" over "$20").
- `label` (optional, up to three parts): his words in small typewriter capitals under the figure, each typing on at
  its word ("AN AGENCY" then "2019").
- `red: false` keeps the figure white (when a caption should carry the red instead).

### Captions
Write them yourself, in phrases of 2 to 5 of his words, in capitals, each starting at its first word:
`{"at": {"word": i}, "text": "WOULD HAVE COST ME"}`. Break where he breathes or where a picture lands, never after
"the", "a" or "and". One word may be red (`"red": "PAID"`) on a caption where no figure is red; that is the one red on
screen. Left out, the style makes phrases on its own.

### Him and his room
- `cutout`: `x` is where the middle of his body sits across his video (0.5 when centred; look at a frame), `scale` how
  tall he stands (0.86 for a seated medium shot; smaller, about 0.7, when his video is a close-up so his chin stays
  above the captions at 78 percent down), `width` how much of his video around him to use (0.69; narrower if
  something else is close to him). `band` and `brighten` as above.
- `room`: the room shot's framing, `x` the same as `cutout.x`, `zoom` 1.4 for a seated medium shot.

### Sound
Nothing to write: a dark pad that changes chord on the second and third pictures, soft air whooshes as each picture
lands, a low hit under each figure, typewriter keys as a label types on, at the levels he approved.
`"effects": {"softer_db": 2}` makes every effect softer; `"effects": false` removes them.

## Settings file
Write `spec.json` in the project folder from the worked example, `example-spec.json` beside this guide: "$40,000 from
an agency, 2019" over his design-system screen, the $40,000 card with "AN AGENCY · 2019" typing on, his room on "the
company", the "$20 / month" card over the struck $40,000, and his templates screen building in under the lifted $20 on
"conversation". Every field is described in the style's `SPEC.md` (in the plugin's
`engine/studio_engine/styles/cutout/`). Word numbers in the example belong to its own words: take every number from
his new `passage.json`. The example's `"band": 31` is there because that video was shot in a dark room.

Then `studio render "<project>" --spec "<project>/spec.json"`. The first version cuts him out of every frame and takes
5 to 15 minutes; tell him so. Later versions of the same words reuse the cutout and take a minute or two.

## Before he sees it
Look at `v<N>/sheet.png` (a frame at every part and caption), then at full-size frames of every beat:
- **The cutout edge at full size**: hair, ears, glasses, shoulders, hands. No room left around him, no hair cut off,
  no flicker between frames (look at two frames a quarter second apart).
- Each picture shows what he is saying, lands on its word, and nothing covers his body.
- The figure is right, red at the right moment, and only one red on screen at a time.
- His chin is above the captions in every corner; the captions read.
- `qa.json` passes: every word heard back, loudness, safe zones, one red, his words only, `cutout_found`
  (he was found in every frame) and `picture_pace`.

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Make the number bigger / smaller": raise or lower that card's `size` (0.1 to 0.2 at a time); for the opening claim,
  `opening.scale`.
- "Start on the second sentence": make a new passage from that sentence, then move every word number (read the new
  `passage.json`) and drop the beats that fell outside it. The new words need a new cutout run (minutes).
- "Different picture there": change that beat's `source`, `in` or `crop`.
- "Put me on the other side": change that beat's `side`.
- "Too fast / too slow": move beats to other stressed words, keeping 2 to 4 seconds between them.
- "I look dark": `cutout.brighten` 1.1 to 1.2.
- "Less sound": `"effects": {"softer_db": 2}` (up to 6).
- "Hold the end longer": raise `tail` (up to 2 seconds).

## Common mistakes
- A dark video with dark hair against a dark wall, and no band: the hair gets cut off.
- A band on a lit room: a pale glow around him.
- A picture that does not match his words, or one that was generated. Pictures only from what he gave you.
- A picture held over 4 seconds, or three corners in a row on one side.
- More than two room shots.
- A range with a cut-away to another camera inside it.
- Word numbers copied from the example.
