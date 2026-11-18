# Prompt pack: settings file

A carousel of 1080 x 1440 slides in his kit (obsidian, Cormorant Garamond, Raleway, Special Elite), with a raked-sand
garden drawn in code: one stone per prompt. Slide 1 is the cover, then one slide per prompt (one to five), then the
close. With a voice line picked (`studio passage`), it also makes `cover.mp4`: the garden rakes itself while his voice
plays, rings stone by stone, then straight lines top to bottom, the last line landing on his last word. Without a
recording, the slides and a still cover are made.

## Fields
| Field | What |
|---|---|
| `passage` | `"passage/passage.json"`: his voice line for the moving cover (10 to 15 seconds is best). Leave it out when there is no recording |
| `number` | the pack number on the cover, two digits ("01") |
| `title` | the cover title, his words, about 3 lines; `\n` breaks a line ("A $40,000\nbrand kit in\nthree prompts.") |
| `title_italic` | the phrase of the title set in italic (usually the last word) |
| `cover.rings_until` | when the rings around the stones are done (a word anchor). Default: about a quarter of the way in |
| `cover.lines_until` | when the last straight line lands (a word anchor). Default: the end of his last word |
| `prompts[]` | one to five of: `heading` (two or three words, his), `heading_italic`, `sub` (one line of his), `tool` (the app the prompt goes in, as he says it), `text` (the prompt word for word), `mark` (the phrase to change or the one that does the work, underlined in red; must be in `text` word for word), `tip_label` (THEN, MINE, TRY or TIP), `tip` (one line of his) |
| `close` | `kicker` (small line at the top), `line` (his closing line, `\n` breaks), `italic`, `cta` (his call to save) |

## Text rules
- Every heading, line, prompt and tip is his words: from his recordings in the project or lines he typed
  (`studio lines --add`).
- Fixed labels: "Prompt pack", "Nº 01" and up, the stone tags "01" to "05", "PROMPT 01 / 03", "Prompt 01", "Copy",
  "Bernard Ablola", "Save this", "THEN", "MINE", "TRY", "TIP", "Follow @bernardablola" and the arrow.
- One red per slide: the brush on the cover and the close, the underline on each prompt.
- The underlined phrase always sits on one line: a phrase that would break moves whole to the next line, and a phrase
  wider than the box shrinks the prompt's text (down to 24 px) until it fits.
- A prompt longer than about 460 letters does not fit: the render stops with a plain message.

## Checks (besides the standard ones)
- `no_old_captions`: text detection on every slide; fails on caption text left from his videos.
- `underline_one_line`: every red underline is one piece on one line.
- The moving cover gets the sound checks: every word of his voice line heard back, -14 LUFS, true peak under -1.5.
