---
name: style-prompt-pack
description: The Prompt pack style guide. How to pick his prompts and the voice line for the moving cover, write its settings file and make the next version from his notes. Load when the studio skill has picked Prompt pack.
user-invocable: false
---

# Prompt pack

A carousel of his prompts, one per slide, ready to copy. The cover is a black raked-sand garden seen from above with
one stone per prompt, tagged 01, 02, 03, under his title ("A $40,000 brand kit in three prompts.") with one red
brush stroke. Each prompt slide opens on the garden lit on its own stone, then gives a short heading, a line of his,
the prompt in a copy box with one phrase underlined in red, and a tip. The last slide is his closing line on the
dimmed garden, with a call to save.

The cover also comes as a short video: the garden rakes itself while his own voice says one line, rings around each
stone first, then the straight lines, the last line landing on his last word. Prompt carousels are his
best-performing slideshow type. Slides are 1080 x 1440.

## What it needs
- **His prompts**, one to five, word for word: from a video where he reads or shows them, or typed by him.
- **One short voice line for the moving cover** (10 to 15 seconds), from any of his recordings. It should say why the
  prompts matter ("This would have cost me $40,000 from an agency... now it costs $20 a month and a conversation").
  If he has no recording, the studio makes the slides and a still cover; tell him that in one line and offer the
  moving cover if he records the line on his phone.
- The style needs the slide maker (`studio needs prompt-pack`).

## Picking the words
1. From a video: run the ingest and read the transcript. From typed lines: save each message he types for this pack
   with `studio lines "<project>" --add "<exactly what he typed>"` (one call per message, never tidied).
2. Find his prompts. Copy each one exactly as he said or typed it. You may cut a prompt short at a sentence end; never
   add or reword. Each prompt must stay under about 460 letters.
3. For each prompt pick, from his words: a two or three word heading ("The brand guide.", "Fifty templates."), one
   short line about it ("Start with your two visual inspirations."), the tool he uses it in if he names one, the one
   phrase to underline (the part to change, like "[your two inspirations]", or the phrase that does the work), and a
   tip ("Drag your screenshots right into the chat.") with its label: THEN (a next step), MINE (his own result), TRY
   or TIP.
4. The cover title: his promise, about three short lines ("A $40,000 / brand kit in / three prompts."). The close:
   his closing line ("Your taste is the input. AI just makes it real.") and his call to save ("Save this for your
   next rebrand").
5. The voice line: pick 10 to 15 seconds of him saying why this matters, ideally ending on a strong word.
6. Show him the title, each prompt slide (heading, line, prompt, underline, tip), the close and the voice line in
   quotes. Ask "Use these words?"
7. Make the passage from the voice line only: `studio passage "<project>" --source <name> --from "<first words>"
   --to "<last words>"`. Run `studio voice "<project>"` to clean it. The prompts on the slides are checked against
   all of his recordings and typed lines in the project, so they do not need to be in the voice line.

## Settings file
Write `spec.json` in the project folder:
- `style`: "prompt-pack", `spec_version`: 1, `passage`: "passage/passage.json" (leave it out if there is no voice
  line; the cover is then a still)
- `number`: "01" (his pack number), `title` (with `\n` between lines), `title_italic` (the word in italic)
- `cover`: `rings_until` (the word where the rings around the stones are done, about a quarter of the way in, at the
  end of his first phrase) and `lines_until` (the end of his last word: `{"word": <last>, "edge": "end"}`). Both
  can be left out for the defaults.
- `prompts`: one to five of `heading`, `heading_italic`, `sub`, `tool`, `text`, `mark`, `tip_label`, `tip`
- `close`: `kicker` (optional small line, his words, like "THREE PROMPTS · TWENTY MINUTES"), `line`, `italic`, `cta`

The worked example is `example-spec.json` next to this guide (three prompts). Copy its shape. Then run
`studio render "<project>" --spec "<project>/spec.json"`. The garden takes a few minutes to draw; say so while it runs.

## Before he sees it
Open every slide and play `cover.mp4` yourself. Check: the prompt is complete and readable in its box, the underline
sits on the right phrase, each slide has just one red, the cover's tags appear as each stone's rings finish, and his
voice is clear over the bowl and the rake sounds. Then have the reviewer check it. The studio's checks must pass.

## His notes
Change only what he names:
- "Fix the prompt" or "use the longer version" -> only that prompt's `text`, from his words.
- "Underline something else" -> `mark` for that prompt.
- "Shorter cover" or "start later" -> a shorter voice line (a new passage); the garden timing follows it.
- "Another prompt" -> add it (up to five); the garden gets a stone for it.
- Colours, fonts, the garden -> fixed in this style; offer `/studio-tune` for his colours or another style.

## Common mistakes
- Tidying his prompt. Keep his exact words, typos in the prompt included, unless he asks.
- An underline phrase that is not in the prompt word for word (the render stops and says so).
- A voice line that trails off. End on a strong word, so the last rake line lands on it.
- Five long prompts. Three is the sweet spot.
