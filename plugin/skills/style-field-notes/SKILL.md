---
name: style-field-notes
description: The Field notes style guide. How to pick his steps for this cream-paper build diary, choose the screen and photo prints, write its settings file and make the next version from his notes. Load when the studio skill has picked Field notes.
user-invocable: false
---

# Field notes

His process, shown the way he did it: a build diary on cream paper. Each slide has typewritten entries, a taped
photo print (his screen, or him at work) and, on a few slides, a short handwritten red marker note. A cover with his
promise and a print of him, one slide per step, and a close with his closing line underlined in red. Slides are
1080 x 1440. No sound.

## What it needs
- **His steps**, from a video where he walks through how he did something ("step one, step two"), or typed by him.
- **Prints:** frames of his screen recordings or of the video itself (him at his desk), and one photo of him for the
  cover. Frames come straight from his footage; photos he adds are brought in with `studio ingest`.
- The style needs the slide maker (`studio needs field-notes`).

## Picking the words
1. From a video: run the ingest on it and read the transcript. From typed lines: save every message he types for this
   carousel with `studio lines "<project>" --add "<exactly what he typed>"` (one call per message, never tidied).
2. Find the steps. Three to five steps, one slide each. Each step's title is his own sentence for it ("I brainstorm
   in Claude Design.", "Start with the mindset.").
3. Under each title, two to four of his sentences, word for word (`typed`), and at most one aside (`dim`). If he lists
   warnings or tips, up to four short items go in `list` with a `list_title` from his words ("CAVEATS").
4. The cover title is his promise in one or two short lines ("My brand kit. Built in an afternoon, for $20."). The
   close is his strongest closing sentence; pick the two or three words of it to underline in red ("you direct.").
5. Marker notes: a short phrase of his (under about 40 letters) that is the emotional point of a slide ("this will be
   the worst it ever is"). At most three in the whole carousel, at most one on a slide; the cover usually has one.
6. Show him every slide's words in quotes. Ask "Use these words?"
7. No passage is needed for this style: leave `passage` out. The studio checks every word on the slides against his
   recordings and typed lines in the project.

## Choosing the prints
- Read the ingest's list of sharp moments (`sharp`) and pick frames where his screen shows the step or he is
  clearly at work. A print is `{"source": "<name>", "t": <seconds>}`.
- If the video has burned-in captions, pick a moment where they are small or away from what matters: the studio
  always crops captions out of a print (it moves or shrinks the crop) and checks every slide for leftover caption
  text.
- Use `x` and `y` (0 to 1) to say where the crop sits (0 = far left or top, 1 = far right or bottom), `zoom` (1 to 3)
  to move in. A short `caption` under a print may only use his words.
- Vary the layout between steps: "step" (print bottom left), "step-right" (print bottom right), "step-list" (print
  on the right beside a short list).

## Settings file
Write `spec.json` in the project folder:
- `style`: "field-notes", `spec_version`: 1, and `slides`: a `cover`, the `step` slides, a `close`.
- Each slide's fields are in the style's settings description: cover (`title`, `print`, `marker`), step (`step`,
  `title`, `typed`, `dim`, `list_title`, `list`, `print`, `marker`, `layout`), close (`title`, `underline`, `print`,
  `foot`).

The worked example is `example-spec.json` next to this guide ("My brand kit. Built in an afternoon, for $20.", five
slides). Copy its shape. Then run `studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
Open every slide yourself at full size. Check: no typed line runs under a print, the prints show something clear (a
screen you can read at phone size, his face), each marker note sits in open paper, at most three marker notes. Then
have the reviewer check it. The studio's checks must pass, including the marker count and old captions.

## His notes
Change only what he names:
- "Use a different screenshot" -> that slide's `print.photo` (a new moment or photo).
- "Too much text" -> drop his least important sentence from that slide's `typed`.
- "Move the note" -> that slide's `marker.box`.
- "Add a step" -> a new step slide, from his words.
- Fonts or paper -> fixed in this style; offer another style if he wants a different look.

## Common mistakes
- Writing captions or notes in your words. Every word on the paper is his.
- More than three marker notes. The render stops and says so.
- Full screenshots of busy screens. Crop in (`zoom`) to the part that shows the step.
- A typed block so long it runs under the print. Trim to his best two sentences.
