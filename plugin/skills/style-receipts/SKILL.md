---
name: style-receipts
description: The "Receipts" style guide. How to spot a then-and-now pair of figures in his words, pick the passage, set the two receipt cards, the opening claim and the captions, write its settings file, and make the next version from his notes. Load when the studio skill has picked Receipts, or to check whether a passage suits it.
user-invocable: false
---

# Receipts

A reel that proves a before and after with two paper receipts. It opens on his screen (or on him) with the claim
already set: a small typewriter "THE RECEIPTS", the big figure in his serif italic with his red brush under it, and a
short line of his words. When he says the old figure, a black card "FIG. 01 Then." comes in and a receipt slip lands
on it with that figure in red, the small rows typing on as he says them. Then he is on camera, with two-word captions
and sometimes one big red word. When he turns ("now", "today", "this year"), the card "FIG. 02 Now." comes in: the old
receipt greyed and struck at the side, the new receipt landing with the new figure. A handwritten line can take the red
at the very end ("a conversation."). A dark pad under his voice that opens on the turn, paper sounds, typewriter keys.

## What it needs
- **A talking video of him** with a then-and-now pair in it (below). 8 to 18 seconds of his words.
- **His screen** for the opening, if he has it: a screen recording, a screenshot, or a part of an old video that shows
  the thing he is talking about. Without it, the opening shows him with the claim over the dark top of the frame.
- Only the base install (`studio needs receipts`).

What to tell him to record if he has nothing yet: "Say what something cost you, or took you, before, and what it costs
or takes now, in one or two sentences. Then record that screen for a few seconds."

## Is there a then-and-now pair? (decide this first)
Receipts only works when he says **two figures of the same thing, one before and one after**, and both are in his
words. Read the transcript and look for:
- **A turn word** between them: "now", "today", "this year", "these days", "used to ... now", "went from ... to",
  "before ... after", "back then", "instead of".
- **Two values of one measure**: two prices ("$40,000 ... $20 a month"), two counts ("posting zero times ... 2,000
  posts"), two times ("days ... a couple of hours"), two sizes ("a team of ten ... just me").
- Both values said out loud by him. A value he only implies ("it was expensive") is not a figure.

Good pairs: "would have cost me $40,000 ... Now it costs $20 a month"; "I went from posting zero times, this year I
crossed 2,000 posts"; "What used to take me days ... now it takes me a couple of hours".

**No pair? Do not force it.** Tell him in one line why this style does not fit these words, and recommend instead:
- one striking figure, no before: **Screen and face** (the figure in the seam between his screen and him);
- a figure he counts up to, or a calm story: **Documentary**;
- a strong line with no number: **Moving type** or **Words in the room**.
Offer to look for a then-and-now moment elsewhere in his videos if he would rather keep Receipts.

## Picking the words
1. Ingest the talking video (and the screen recording, if separate). Read the transcript.
2. Find 8 to 18 seconds that hold the pair: start a sentence or two before the old figure, end on the new one (or on
   the short phrase right after it, which can become the handwritten line).
3. The two figures can sit in different places of the video: use two ranges, in the order that makes the story
   (`--from .. --to .. --from .. --to ..`, with `--gap 0` if the second should follow straight on). Check with him it
   still reads as one thought. Example: "A year ago, none of this existed." then "I went from posting zero times, this
   year I crossed 2,000 posts ...".
4. His on-camera parts must stay on him: look at frames across the range; if the video cuts away inside it (a quote, a
   b-roll shot), pick other words. Burned-in captions on the old video are fine if they sit away from his face (the
   style crops a tall strip around him); check a frame.
5. Show him the exact words in quotes and how long they run. On his yes:
   `studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then
   `studio voice "<project>"`.

## Planning the reel
Read `passage/passage.json`: every word has a number `i` and a start time. The reel is four parts, in this order:
1. **Opening** (from the first frame): his screen and the claim. Ends when the first card comes in, or earlier with
   `opening.until` if he says something on camera before the old figure.
2. **Card one, Then.** (`then.at`): starts one frame before he says the old figure (`{"word": i, "offset": -0.025}`).
   It leaves (`then.until`) in the pause after that sentence, before his next word. Default: it stays until card two.
3. **On camera**: whatever lies between the cards (and between the opening and card one). Two-word captions, and an
   optional `keyword`.
4. **Card two, Now.** (`now.at`): on the turn word ("Now", "this year"). It stays to the end, plus `tail` seconds.

### The opening claim
- `figure`: the big figure, usually the most striking one of the pair (the old price, the new count). Digits where he
  says a number ("$40,000", "2,000"), up to 9 characters.
- `trail`: a short line of his words around it, up to 28 characters ("from an agency, 2019", "posts, videos, texts").
- `screen`: `source` (the name in `sources`, or a project source), `in` (the second of the recording to start from)
  and `x` (where to centre the tall crop across the recording, 0 left to 1 right). Look at frames of the recording and
  pick a moment that shows what he is talking about; never guess. Leave `screen` out to open on him.

### The receipts
Each card has a receipt with:
- `total`: the figure, as digits where he says a number ("$40,000", "$20", "0", "2,000"), or one or two of his words
  ("Days", "Hours"). Up to 9 characters. His serif sets numbers in the old style, where 0, 1 and 2 sit at the height
  of small letters: a lone small digit ("0", "2") reads tiny on the slip, so write the word he said ("Zero") or set a
  bigger `scale`.
- `unit` (optional): his word after the figure, small, beside it ("/ month", "times", "posts"). A slash may stand for
  "a" or "per".
- `total_at` (optional): when the figure appears. Card one: leave it out (the figure is there as the slip lands, he is
  saying it). Card two: the word where he says the new figure (the slip lands empty first, then the figure lands).
- `rows` (card one, up to two): small typed rows under the figure, each a `label` (FROM, DATE, FOR, TIME, WHO or PLUS)
  and his words as `text` (up to 18 characters), typed on at `at` (the first word of that text). "FROM / AN AGENCY",
  "DATE / 2019", "DATE / A YEAR AGO".
- `hand` (card two, optional): a short phrase in a handwritten marker that takes the red at the end, at its first word
  ("a conversation.", "live streams."). The label above it is PLUS unless you set `label`. Use it for the last thing he
  says after the new figure; leave it out if he ends on the figure.
- `item` (optional, either card): one typed row above the total, his words ("THE WHOLE THING"). Only words inside the
  passage.
- `scale` (optional, 0.7 to 1.4, default 1): the size of that receipt's figure. The slip widens for a bigger figure.

### Captions and the keyword
- Leave `captions` out and the style makes two-word captions from his words, breaking at commas and full stops. Write
  them yourself when a pair reads badly ("THIS RIGHT" / "HERE"): each `{"at": {"word": i}, "text": "..."}`, his words
  in capitals, two or three words. On the cards they sit in an ivory box at the bottom; on him in the 63 percent slot.
- `keyword` (optional, one per reel): one word of his that carries the moment, big in red while he is on camera ("PAID"
  with the trail "FOR IT."). `at` its word; `trail` (optional) the next two or three words, at `trail_at`. Captions
  give way to it until the next card.

### Him on camera
Look at a full-size frame. `face`: `x` is where his face is across the frame (0.5 when centred), `zoom` how big (1.4
for a seated medium shot, 1 for a vertical phone video), `top` the row where the top of his picture sits (440 leaves
the dark top band the claim style is built on; 0 for a vertical video).

### Sound
Nothing to write: the style lays a dark pad that opens on card two, a soft pop at the start and on the keyword, paper as
each card comes in, typewriter keys on each typed row, a soft hit on the keyword and a marker line on the handwriting,
at the levels he approved. `"effects": {"softer_db": 2}` makes every effect 2 dB softer; `"effects": false` removes
them.

## Settings file
Write `spec.json` in the project folder from the worked example, `example-spec.json` beside this guide: the "$40,000
from an agency, 2019" claim over his design-system screen, card one with FROM and DATE typed on, "PAID / FOR IT." on
camera, then "$20 / month" and the handwritten "a conversation.". Every field is described in the style's `SPEC.md`
(in the plugin's `engine/studio_engine/styles/receipts/`). Word numbers in the example belong to its own words: take
every number from his new `passage.json`.

Then `studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
Look at `v<N>/sheet.png` (a frame at every part and caption) and at full-size frames of both cards:
- Does each receipt carry the right figure, in red at the right moment, and only one red at a time?
- Do the rows type on as he says them, and does the handwritten line read?
- Is his face fully in frame and clear of the captions while he is on camera? No burned-in caption of the old video
  showing?
- Does the opening screen show what he is talking about?
- `qa.json` passes: every word heard back, loudness, safe zones, one red, his words only.

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Make the number bigger / smaller": raise or lower that receipt's `scale` (0.1 to 0.2 at a time; 1.25 is clearly
  bigger), or `opening.scale` for the claim. If the studio says the figure is too wide, offer the largest that fits.
- "Start on the second sentence": make a new passage from that sentence, then move every word number (read the new
  `passage.json`) and keep everything else as it was.
- "Different screen at the start": change `opening.screen.in` (and `x`).
- "The red should be on X": move the handwritten line, or change which figure is the claim.
- "Less sound": `"effects": {"softer_db": 2}` (up to 6), or remove them.
- "Hold the end longer": raise `tail` (up to 2 seconds).

## Common mistakes
- A figure he never said, or a pair where one side is implied. Both figures must be his words.
- Card one starting late: it should land as he says the old figure, one frame before.
- Card one leaving in the middle of a word: put `then.until` in the pause after his sentence.
- A keyword outside the on-camera part (it only shows while he is on camera).
- Rows on card two together with a handwritten line: pick one.
- Word numbers copied from the example.
