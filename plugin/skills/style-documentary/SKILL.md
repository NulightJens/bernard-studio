---
name: style-documentary
description: The "Documentary" style guide. How to pick his words for this cinema-frame reel (a wide picture band, slow push-ins, a figure below that counts as he says it), choose the shots, write its settings file, and make the next version from his notes. Load when the studio skill has picked Documentary.
user-invocable: false
---

# Documentary

A short documentary in a phone frame. A wide picture band sits across the middle, framed by two thin lines, black
above and below, like a film on a phone. Inside it, his footage cut on his words: one slow push-in or one slow move
across per shot, a warm film grade, a soft glow on the highlights, film grain. Above the band, a small typewritten mark
("FIELD NOTES · REEL 01") and, when he first fills the band, his name. Below the band, the figure: a big serif number
on screen from the very first frame, a typewritten source line under it, a red brush under it on the word that proves
it, and then the number counts down (or up) to the new figure exactly as he says it. Documentary subtitles run under
the figure, and at the end a closing line in red takes their place while the picture fades out. A slow, dark score
with soft mallet notes on the figure moments, a projector running under the opening, clock ticks under the count.

## What it needs
- **A talking video of him**: 8 to 20 seconds about one thing. A calm, seated take in a warm, dim room suits it best.
  Any of his existing videos works.
- **B-roll** (best, not required): moments with no talking in them from the same video or another of his: his hands at
  work, his laptop or phone screen, his desk in low light, the thing he is talking about. A documentary cuts away from
  his face while his voice carries on, so his lips must not show in a B-roll shot.
- **A number in what he says** makes it land: a price, a count, a time ("$40,000", "2,000 posts", "365 days"). Then
  and now ("cost $40,000 ... now $20 a month", "zero ... 2,000") is the strongest. Without a number, leave the figure
  out; the subtitles and the closing line still carry it.
- Only the base tools are needed.

What to tell him to record if he has nothing yet: "Sit somewhere warm and dim, look just past the camera, and say the
before and after in one or two sentences, for example 'that used to take me eight weeks, now it takes an afternoon'.
Then film your hands doing the work for a minute, no talking."

## Picking the words
1. Ingest his video(s) and read the transcript.
2. Find 8 to 15 seconds that make one point, ideally with a number and a turn. Start on a full sentence. End on a short
   line that can be the closing line ("Here's how I did it.", "and a conversation.").
3. Old videos: check the picture stays on him for every word you will show him on (look at frames across the range).
   Cutaways in the source are fine only if you plan B-roll over them.
4. Show him the exact words in quotes and how long they run. On his yes:
   `studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then `studio voice "<project>"`.

## The shots (the band)
Read `passage/passage.json`; every word has a number `i`. Plan four or five shots for 10 to 12 seconds, each starting
on the word where his story moves on (`from`). The first shot starts at the first frame.
- **Open on B-roll** when you have it (frame one carries the claim; a moody shot under the figure looks like a film).
- **His face** (no `source`) when he makes the claim and the turn: the viewer should see him say the number.
- **B-roll** (`source` + `in`): only stretches with no talking, never his face speaking other words. Pick `in` by
  looking at frames of the source at 0.5 s steps; never guess.
  A bright screen is toned down by itself; for B-roll that is already dark (a room at night, a candle), set
  `"tone": "face"` so it is not pushed darker still.
- **Cuts inside his footage**: if the source itself cuts from one camera to another inside your words, start a new
  shot on that frame (find it on `passage/picture.mp4`), so each camera gets its own framing.
- **Last shot**: his closest framing, for the closing line.
- Frame each shot by looking at a full-size frame: `x`/`y` the point at the band's centre, `zoom` how close (1 is the
  source's full width). A seated medium shot: zoom about 1.7, his eyes a third down the band (`y` a little above his
  face's centre). The closest shot: about 2 to 2.3, no more on 1080p footage.
- One move per shot: either a slow push (`end.zoom` about 10 to 15 percent more than `start.zoom`) or a slow move
  across (`end.x` about 0.08 away from `start.x`, same zoom). Alternate them.
- **Captions burned into old videos**: the ingest marks where they sit. Frame every shot so they stay outside the band
  (look at the frames where the captions are longest), even if he is then a little off centre.

## The figure (below the band)
- `text`: the first figure as digits where he says a number ("$40,000", "0", "365"), up to 10 characters. It is on
  screen from the first frame, even if he says it later.
- `line`: a few of his words that place it, in capitals: "FROM AN AGENCY, 2019", "I WENT FROM". Up to 28 characters.
- `underline` (optional): the red brush under the figure on the word that proves it ("paid"). Leave it out if the
  closing line is red at the same time; one red at a time.
- `to`: the new figure, `at` the word he says it on (the count lands there), with an optional `unit` beside it
  ("/ month", "posts") and a new `line` ("NOW", "THIS YEAR").
- `size`: 190 as picked. "Make the number bigger" means about 30 more (up to 300; the studio refuses a size too wide
  for the frame and says the largest that fits).
- No number in the words: leave `figure` out.

## Subtitles, the closing line, his name
- `subtitles`: break his words into short lines on his phrasing, three to six words each, every word in one line, in
  order. Leaving them out makes them automatically.
- `close`: his last short line, in red, on its first word ("+ a conversation.", "Here's how I did it."). A plus sign
  may stand for "and".
- His name shows when he first fills the band. Under it there is room for a title, but only one he gives himself: ask
  him once ("Under your name, a title, or just your name?"). On a title, save it word for word with
  `studio brand set style.documentary.title "<his words>"` and put the same text in `lower_third.title`. Never
  invent one.
- `mark.reel`: number his documentary reels in order (1, 2, 3 ...).

## Sound
Copy the example's sound block and move its anchors to his words:
- Bed `documentary` at 16.5 dB under; its two `changes` on the turns of his story (the second on "now" or the new
  figure's sentence).
- Mallet notes: one at 0.3 s (note D4), one when his face first fills the band (note A3), one on the proof word
  (note F3), one on the new figure (note C4), two on the closing line (notes F4, and C5 0.02 s later).
- `sub-hit` on the spoken claim (28 dB under), `noise-swell` 0.92 s before the new figure (32 dB under). The projector
  and the clock ticks come by themselves (`film_sound`).

## Settings file
Write `spec.json` in the project folder from the worked example, `example-spec.json` beside this guide. It is the
example he picked: his design system on frame one under "$40,000 / FROM AN AGENCY, 2019", his face on "$40,000", a slow
move across on "I know", his templates on "Now", the count down to "$20 / month" on "$20", and "+ a conversation." in
red over his closest shot. Every field is described in the style's `SPEC.md` (in the plugin's
`engine/studio_engine/styles/documentary/`).

Then `studio render "<project>" --spec spec.json`.

## Before he sees it
Look at `v<N>/sheet.png` (a frame at every shot, figure, subtitle and the closing line) and at full-size frames:
- Does every shot show what it should: his face when he speaks on camera, B-roll with no talking, no burned-in
  caption inside the band, no black or frozen frame?
- Is the figure readable, in his words, centred, with its line under it? Does the count land as he says the number?
- One red at a time: the brush under the figure is gone before the closing line comes.
- `qa.json` passes: every word heard back, loudness, safe zones, one red, his words only.

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Make the number bigger / smaller": change `figure.size` by about 30.
- "Start on the second sentence": make a new passage from that sentence, then move every anchor (word numbers change;
  read the new `passage.json`), keep everything else.
- "Different shot here": change only that shot's `source`, `in` or framing.
- "Closer on me": raise that shot's `zoom` (both `start` and `end`) by about 0.2.
- "No title" or "just my name": remove `lower_third.title`.
- "Less sound": raise the effects' `under_db` by 2 or set `film_sound` to false.

## Common mistakes
- A figure or line he never said. Numbers as digits are fine; nothing else that is not his.
- A B-roll shot of him talking: his lips do not match the words.
- A title under his name that he did not give himself.
- Burned-in captions inside the band.
- A zoom past 2.3 on 1080p footage: soft.
- Word numbers copied from the example: they belong to the example's words, never to his new passage.
