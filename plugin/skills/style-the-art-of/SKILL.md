---
name: style-the-art-of
description: The "The art of" style guide. How to pick a topic and his lines for this object-grid carousel, choose the objects and the two photos of him, write its settings file and make the next version from his notes. Load when the studio skill has picked The art of.
user-invocable: false
---

# The art of

A carousel on a flat light grey, set in Inter. The cover says "The art of" and his topic ("building your brand"),
ringed by five objects, with two cut-out photos of him in the bottom corners and a plus between them. Then one slide
per idea: the idea's name in capitals in the centre, six real objects around it, each with one short line of his under
it. The last slide is a full photo of him with "Welcome to my account." and his closing line in white, top left.

It is a format that is working on Instagram right now, and it puts his face on the cover twice. No sound.

## What it needs
- **A topic and his lines.** From one of his videos where he walks through several parts of one subject (a how-to,
  "step one, step two", a year in review), or lines he types to you himself. Both work equally well.
- **Two photos of him for the cover.** The library already has poses (from his desk video, his studio video, his
  glasses video, his kit photo). New poses can come from any sharp moment of his footage (see "New poses" below).
- **A photo for the last slide.** A frame of one of his videos, or a photo of him (bring it in with `studio ingest`),
  ideally a calm, wide, atmospheric shot.
- The style needs the slide maker (`studio needs the-art-of`). The cutout tool is only needed for new poses.

## Picking the words
1. From a video: run the ingest on it and read the transcript. From typed lines: save every message he types for
   this carousel with `studio lines "<project>" --add "<exactly what he typed>"` (one call per message, never
   tidied or corrected), then read them back with `studio lines "<project>"`.
2. Find the subject. The topic is a short phrase from what he said, lower case: "daily posting", "building your
   brand". It must fit under "The art of" on one line (about 22 letters at most).
3. Find three to eight parts of it. Each part becomes a slide. Its name is one or two words he said, in capitals:
   "MINDSET", "SYSTEM", "THE PROMPT", "DAY 100". If he numbers steps, his steps are the parts.
4. For each part pick six short lines he said about it. Trim his sentences, never reword them: "Put your back against
   the wall", "Reps build competence", "Progress over perfection". Under about 45 letters each; the render stops and
   names any line that is too long. Every word must be one he said (or typed).
5. Pick a closing line for the last slide (`headline`, under about 30 letters) and optionally a second line (`line`,
   two short lines joined with `\n`). His strongest closing words: "Just keep going anyway." / "None of this happens
   if you stay invisible."
6. Show him the topic, the part names and every line, slide by slide, in quotes. Ask "Use these words?"
7. From a video, make the passage from the first to the last words you used:
   `studio passage "<project>" --source <name> --from "<first words of the stretch>" --to "<last words>"`, and put
   `"passage": "passage/passage.json"` in the settings. From typed lines, skip this step and leave `passage` out of
   the settings: the studio checks every slide word against his typed lines and his transcripts.

## Choosing objects
The objects are real 3D renders and phones or laptops showing his own templates and posts. The list with what each
one can stand for is in the library's `objects/tags.json` (read it: `what` and `can_stand_for`).
- One object per line. Pick the object whose `can_stand_for` fits the line, or a plain visual pun: a tape measure for
  "progress over perfection", a lion for "competence builds confidence", a compass for "opportunities".
- Never repeat an object on the same slide. Repeats across slides are fine but use them sparingly.
- Mix big and small, round and tall. A slide of six boxes looks dull.
- Phones and laptops (`ph_*`, `lt_*`) show his own work: use them where the line is about his posts, his templates,
  his feed.
- Cover: five objects in the order top left, top centre, top right, middle left, middle right. A laptop and a phone
  showing his work at the top left and centre, one tall object top right (a candle, a lamp), and two thin or flat
  objects in the middle (a sword, glasses, a watch), because the middle row sits beside the title.
- If no object fits a line at all, tell him, and suggest a different line rather than a weak object. New objects can
  be made on request with the Blender add-on, which is large: offer it only if he asks for something specific.

## Choosing the poses
The pose list is in the library's `poses/library.json`, plus any he added himself (kept in his settings folder under
`poses`). Each pose says where he looks (`facing`) and which bottom corner it fits (`cover_side`).
- Two different poses. A pose with `cover_side` "right" must go on the right.
- Two poses from the same video look like a pair; one from each of two videos looks like a range. Both work.
- The plus sits between them at `[489, 1085]` by default; move it (`cover.plus`) if it touches either photo.

### New poses from his footage
1. Find sharp moments of him: the ingest lists the sharpest moments (`sharp`, highest first). Pick a few where he is
   in shot, facing the camera or in profile, nothing in front of him.
2. For each moment: `studio matte "<project>" --source <name> --t0 <t> --t1 <t + 0.2> --frames 1`. Its result names a
   folder; the frame is `frames/f00001.jpg` inside it.
3. Clean it into his pose library: `studio matte-photo "<that frame>" --name <name>` (name it like
   `bernard-glasses-front-a`: small letters, digits and dashes). It is saved in his own pose folder, and the pose is
   then used by that name.
4. Look at each cutout before using it. Skip any with caption text or a screen left beside him, a cut-off head, or a
   smeared edge.

## The last slide
`last.photo` is `{"source": "<source name>", "t": <seconds>}`. The studio cuts a tall picture from that frame and
always keeps burned-in captions out of it (it moves the crop sideways, or makes it a little smaller). Optional: `x` and
`y` (0 to 1) say where the crop sits (0 = far left or top, 1 = far right or bottom), `zoom` (1 to 3) moves in closer. Pick a calm frame where he is not
mid-word; a wide, dark, atmospheric shot works best because the text sits on top in white.

## Settings file
Write `spec.json` in the project folder. Fields:
- `style`: "the-art-of", `spec_version`: 1, `passage`: "passage/passage.json" (leave it out for typed lines)
- `topic`: his short topic phrase
- `cover`: `objects` (five names), `left` and `right` (`{"pose": "<name>"}`), optional `plus`
- `sections`: three to eight of `{"name": "<CAPITALS>", "items": [six of {"object": "<name>", "text": "<his line>"}]}`,
  items in the order top left, top right, middle left, middle right, bottom left, bottom right
- `last`: `photo`, `headline`, optional `line`

The worked example is `example-spec.json` next to this guide ("The art of building your brand", eight slides). Copy
its shape. Then run `studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
Open the frame sheet and every slide yourself. Check: no caption crowds the next row, no object is cut off or tiny,
the two photos of him are clean, the plus sits in the gap, the closing text reads clearly on the photo. Then have the
reviewer check it. The studio's own checks must pass, including the check for old caption text on any slide.

## His notes
Change only what he names, then make the next version:
- "Use a different photo of me" -> swap `cover.left` or `cover.right` (or `last.photo`). Nothing else.
- "That object doesn't fit" -> swap that one object.
- "Shorter" -> fewer sections, keep his strongest.
- "Bigger title" or a new layout -> the layout is fixed in this style; tell him so kindly and offer another style.
- New words -> only his: from the recording, or lines he types (save them with `studio lines --add` first).

## Common mistakes
- Writing lines for him. Every line is trimmed from what he said or typed.
- Lines that are full sentences. One short thought each.
- Objects that need explaining. If you have to explain why the object is there, pick another.
- Using a pose with caption text, a screen or another person left beside him.
- A last-slide frame where he is mid-blink or mid-word.
