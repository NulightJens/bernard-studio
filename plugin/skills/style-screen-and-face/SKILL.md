---
name: style-screen-and-face
description: The "Screen and face" style guide. How to pick his words for this split reel (his screen on top, him below, the figure in the seam between them), choose the screen shots and the figures, write its settings file, and make the next version from his notes. Load when the studio skill has picked Screen and face.
user-invocable: false
---

# Screen and face

A reel in three bands. On top, his real screen: the thing he is talking about, slowly pushing in. At the bottom, him
talking. Between them, a black seam where the figure lands: a big serif number on the left and one or two short italic
lines of his on the right. The claim is on screen from the very first frame. When the story turns ("now it costs..."),
a red brush strikes through the old figure and the new one rises in its place. Quiet low drone under his voice, a soft
boom when he says the number, a brush sound on the strike.

It is the one format that has grown his Instagram: a screenshot next to his face, made editorial.

## What it needs
- **A talking video of him**: 10 to 20 seconds about one thing, ideally one camera angle, his face clearly lit. Old
  videos work if the part you use stays on him (no cutaways inside the words you pick; a cutaway would show in his
  band).
- **His screen**: a screen recording of what he is talking about (a phone or Mac recording, any length), or a
  screenshot. Old videos that already show his screen can be the screen source too.
- **A figure in what he says**: a price, a time, a count ("$40,000", "20 bucks a month", "50 templates", "days",
  "a couple of hours"). Two figures that contrast (then and now) make the strongest version.
- The style needs the motion graphics part (`studio needs screen-and-face`).

What to tell him to record if he has nothing yet: "Talk to the camera for 10 to 20 seconds about one thing you did on
screen, say the before and after if there is one, then record that screen for a minute."

## Picking the words
1. Ingest the talking video, and the screen recording too if it is a separate file. Read the transcript.
2. Find 8 to 18 seconds that make one point and contain a figure. Best: a then-and-now in one or two sentences
   ("This would have cost me $40,000 ... Now it costs $20 a month"). Start on a full sentence, end on the payoff.
3. If the point is spread over two places, use two ranges (`--from .. --to .. --from .. --to ..`); add `--gap 0` so
   the second follows straight on, as in the example. Check with him that it still reads as one thought.
4. Old videos: check the picture stays on him for every word you pick. Look at frames across the range (the ingest's
   frame scan helps). If a cutaway falls inside, pick other words or another range.
5. Show him the exact words in quotes and how long they run. On his yes:
   `studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then `studio voice "<project>"`.

## The figures (the seam)
Read `passage/passage.json`; every word has a number `i`. Plan one to three figures.
- **Figure one** is the claim. Give it `"at": {"word": 0}` so it is on screen, already set, from the first frame, even
  if he says it later. Put a `rule` on the word where he says it.
- **Then and now**: put a `strike` on figure one at the word where the story turns ("Now", "today", "but"), and start
  figure two on the new figure's word, with its lines on the words that follow.
- **A count or a result** as the last figure: an `underline` under its lines, on the last word of the line.
- `text` is the figure itself as digits where he says a number ("$40,000", "$20", "50"), up to 9 characters. A
  figure can also be one or two of his words ("Days", "Hours") when he contrasts times without numbers.
- `lines` are the words around the figure, trimmed, never reworded: "from an agency," / "2019"; "a month" /
  "+ a conversation" (a plus may stand for "and"); "templates," / "all on brand". Each line up to 24 characters.
- One red per figure: either the strike or the underline.
- Time the lines to the words: a line's `at` is the first word of that line (or one word earlier, so it is up as he
  says it).

## The screen shots (the top band)
Plan one shot per idea, in order, each starting on the word where his talk moves to it (`from`). The first shot
always starts at the first frame. Four or five shots in 15 seconds is the right pace; never leave the top band on one
static frame for more than about 5 seconds.
- Find the moment on the screen recording that shows what he is saying (`in`, in seconds). Look at frames of the
  recording to pick them; never guess.
- If the recording moves on to something else, set `out` where the right part ends; the shot then holds that frame.
- A scroll through a long page reads well at `"speed": 2`; a calm page at 0.8 to 1.
- `push` and `origin` aim the slow push-in at the part that matters (for example "30% 40%" for something up and left).
- For a part of his talk with no matching screen, stay on the last shot that relates rather than show something
  unrelated.

## His band (the bottom)
Look at a frame of his footage at full size. Set `face` so his face sits in the upper third of the band with some
room above his head: `x` is where his face is across the frame (0.5 when centred), `y` how far down to start (0.03 cuts
off a little ceiling), `zoom` 1.2 for a seated medium shot, up to 2 for a wide shot where he is small.

## Sound
`"bed": {"name": "drone", "under_db": 18}`. Effects: `impact` on the spoken figure (27 dB under, `"len": 1.6`),
`brush` on the strike (26, 0.7), `card` when a later count lands (28, 0.5). Two or three effects in a reel, no more.
The join between two ranges gets a soft whoosh by itself.

## Settings file
Write `spec.json` in the project folder from the worked example, `example-spec.json` beside this guide. It is the
example he picked: "$40,000 from an agency, 2019", struck on "Now", then "$20 a month + a conversation", then
"50 templates, all on brand", over five shots of his design system, the Claude Design page and the template library.
Every field is described in the style's `SPEC.md` (in the plugin's `engine/studio_engine/styles/screen-and-face/`).

Then `studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
Look at `v<N>/sheet.png` (a frame at every figure) and at frames of the screen band yourself:
- Is the figure readable and in his words? Do the lines fit, with no line running into the figure?
- Does every screen shot show what he is saying at that moment? No shot of something unrelated, no shot of himself
  in the top band, no black or frozen frame by accident.
- Is his face fully in his band, not cut by the seam?
- `qa.json` passes: every word heard back, loudness, safe zones, one red.

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Make the number bigger / smaller": set that figure's `scale` (default 1; 1.2 is clearly bigger, 0.85 clearly
  smaller; 0.7 to 1.4). If the render says the figure does not fit at that scale, use the most it names, and tell him
  that is as big as it goes next to its lines (shorter lines leave more room).
- "Start on the second sentence": make a new passage from that sentence, then move every anchor (word numbers
  change; read the new `passage.json`) and keep everything else as it was.
- "Different screen here": change only that shot's `in` (and `out`).
- "The red should be on X": move the `strike` or `underline` to that word.
- "Less sound": raise the effects' `under_db` by 2 (never past 30) or remove one.

## Common mistakes
- A figure he never said. Every figure and line must be his words; numbers as digits are fine.
- Figure one not at word 0: the first frame then has an empty seam.
- A strike and an underline on the same figure (two reds).
- A screen shot that runs past the right part of the recording and shows something else: set `out`.
- Picking words from an old video where the picture cuts away from him: his band shows the cutaway.
- Word numbers copied from the example: they belong to the example's words, never to his new passage.
