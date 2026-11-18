---
name: style-moving-type
description: The Moving type style guide. How to pick his words for it, break them into camera stops and lines, write its settings file and make the next version from his notes. Load when the studio skill has picked Moving type.
user-invocable: false
---

# Moving type

His words set as a moving typeset page. One camera glides over a dark board and lands on each group of lines as he says
them. Lines rise in, small grey labels spread in, numbers land hard with a shake, a date types itself. Lines the camera
has left go dim and soft. At the end the camera pulls back to a poster of the whole thought, and one red brush strikes
(or underlines) the line that matters. It reads with the sound off.

Settings reference: `${CLAUDE_PLUGIN_ROOT}/engine/studio_engine/styles/moving-type/SPEC.md`.
Worked example: `${CLAUDE_PLUGIN_ROOT}/skills/style-moving-type/example-spec.json` (his "$40,000" piece).

## What it is good for
- One sharp thought with a turn in it: before and after, then and now, the old way and the new way, a cost and a
  saving. The red mark lands on the side he is against (strike) or the side he wants (underline).
- Lines with a number in them. Numbers are the strongest moment in this style.
- Any of his videos works as the voice, even one with a messy picture: only his voice is used.

Not good for: a long story, a list of more than three items, or lines with no single point to land on. For those
suggest another style.

## What he needs to give
Nothing new. A voice line of 10 to 20 seconds from any of his videos. If he has a new thought, he can record it on his
phone; only the sound is used.

## 1. Pick the words (10 to 20 seconds)
Read the transcript and look for:
- a passage that starts on its own feet (not "and so", not "that's why") and ends on its point;
- a turn or a number in the middle or at the end;
- 25 to 50 words. Under 10 seconds feels thin; over 20 seconds the board gets too long for the poster.

Show him the exact words in quotes and how long they run. On his yes:
`studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`

The passage reply gives the words with their numbers (`words[i]`). Keep it open: you need the numbers for the sound.

## 2. Break the words into stops and lines
Write the words out as he says them, then cut them into **stops** (where the camera lands) and **lines** (what is set at
each stop).

- **One stop per phrase**, about every 1.5 to 2.5 seconds of speech. Usually 5 to 8 stops for 15 seconds.
- **One to three lines per stop**, two to five words a line. Break lines where he breathes or where the meaning turns.
- **Every word he says appears on the board**, in order. Do not skip words, and never add or change one. You may write
  spoken numbers as digits ("ten people" can be "10 people"; "forty thousand dollars" can be "$40,000").
- Leave out filler he would not want on screen only if it is at the very start or end of a line; better still, choose
  a passage without it.

Then give each line a **look**:
- `strong`: the opening line (the first stop) and the one or two lines that carry the point. Big italic serif.
- `label`: short lead-ins to a number or a key line ("would have cost me", "now it costs", "I know because").
  Small grey capitals. Keep them to two to four words.
- `number`: a figure on its own line ("$40,000", "$20", "10x", "80%"). At most two in a piece; they slam.
- `italic`: lines with feeling, follow-on phrases.
- `serif`: plain connecting lines.
- `typed`: a date, a place or a short aside ("in 2019.", "last March."). At most one in a piece.

**Sizes:** leave them at the defaults for the first version. Bigger only for the line that matters most at that stop.

**keep:** when a stop finishes a sentence the previous stop started, set `"keep": true` so the camera frames both and
keeps them lit (for example "The whole thing," then "this right here,").

**Opening:** the first stop is already on screen on the first frame. Make it `strong`, one or two short lines.

## 3. The poster and the red mark
Pick the one line that matters for the ending:
- `"strike"`: the line he is against or the old number. It dims and gets a red brush through it.
- `"underline"`: the answer or the new way. It stays bright and gets a red brush under it.
One of the two, never both. It must be copied exactly from one of the lines. This is the only red in the film, so no
other line may be red.

## 4. The sound
Use the moving-type bed. It stays in a dark minor key with a slow pulse, then opens to a warm major chord on the last
stop. Leave out `changes` and they fall on the first words of the last three stops, which fits most pieces. Set them
yourself only if the turn of his thought is elsewhere: the third change should land on the word where the answer
starts. The style adds its own effects (camera air, number hits, typewriter keys, the brush). Add nothing else for the
first version.

## 5. Write the settings file
Write `spec.json` in the project folder:

```json
{"style": "moving-type", "spec_version": 1, "passage": "passage/passage.json",
 "beats": [
   {"kind": "stop", "lines": [{"text": "<his words>", "look": "strong"}, {"text": "<his words>", "look": "strong"}]},
   {"kind": "stop", "keep": true, "lines": [{"text": "<his words>", "look": "serif"}]},
   {"kind": "stop", "lines": [{"text": "<his words>", "look": "label"}, {"text": "<a number he says>", "look": "number"}]},
   {"kind": "stop", "lines": [{"text": "<his words>", "look": "italic"}, {"text": "<his words>", "look": "typed", "x": 200}]},
   {"kind": "stop", "lines": [{"text": "<his words>", "look": "label"}, {"text": "<his words>", "look": "strong"}]}
 ],
 "poster": {"strike": "<one of the lines, copied exactly>"},
 "sound": {"bed": {"name": "type"}}}
```

The worked example also carries `x`, `y`, `size` and `camera` values: those were set by hand to match the first piece
exactly. For a new piece leave `y` and `camera` out; the studio stacks the lines and moves the camera itself. Use `x`
only to nudge a short trailing line to the right.

Then: `studio render "<project>" --spec "<project>/spec.json"`. It checks the settings first and tells you in plain
words if a line is not his words or a field is wrong.

## 6. Check it before he sees it
Open `v<N>/sheet.png` (a frame at every stop and the poster) and look:
- every stop shows its lines fully inside the frame, readable on a phone;
- the numbers are the biggest thing at their stops;
- the poster shows the end of the thought, with exactly one red mark on the right line.
Then the reviewer agent. If the sheet shows a problem, fix the settings and render again before showing him.

## 7. His notes, the next version
Change only what he named. Common notes and what to change:
- **"Make the number bigger"**: raise that line's `size` (number default 240; try 320 to 420). At its own stop a
  number already fills the width, so it grows against the lines around it and on the closing poster. If he wants it
  to fill more of the screen at its stop, also move the lines beside it to a stop of their own.
- **"Too fast" / "the camera moves too much"**: fewer stops (merge two short stops into one), or `"keep": true`
  on stops that finish a sentence.
- **"Start on the second sentence" / "cut the first part"**: a new passage with `studio passage`, then rebuild the
  stops from the new words (the word numbers change).
- **"Strike the other line" / "underline instead"**: change `poster`.
- **"I can't read it"**: shorter lines (split a long line in two) or a bigger `size` on the line he means.
- **"Hold the end longer"**: `poster.hold` (default 1.75 seconds, up to 4).
- **"Different music"**: another bed by name (`studio sounds` lists them); keep the effects.
Record his note first (`studio note`), render the next version, check the sheet, then show him.

## Common mistakes
- A line with words he does not say, or words in a different order. The render refuses it.
- Too many words on one line: the camera zooms out to fit and the type gets small. Two to five words a line.
- Long stops with four lines each: the camera cannot land on a single thought. Split them.
- Both `strike` and `underline`, or the red line not copied exactly.
- More than two numbers: they stop feeling special.
- A passage that ends mid-thought: the poster then has nothing to land on.
