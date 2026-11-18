# Field notes: settings file

His build diary on cream paper at 1080 x 1440: typewritten entries (Special Elite), taped photo prints of his screen
and of him, and a red Permanent Marker note. Three to ten slides: a cover, steps, a close. No sound.

## Fields
`slides[]`, each one of:

| Kind | Fields |
|---|---|
| `cover` | `title` (his promise, `\n` breaks a line), `print` (a big print of him), `marker` (a short red note), `arrow` (true by default: a red arrow from the note to the print) |
| `step` | `step` (the step number, optional: without it the slide has no STEP label), `title` (the step in his words), `typed` (lines he said, one entry per sentence, `\n` breaks inside), `dim` (an aside, typed in grey), `list_title` + `list` (up to four short items, for caveats or a checklist), `print`, `marker`, `layout` ("step": print bottom left, "step-right": print bottom right, "step-list": print on the right beside the list) |
| `close` | `title` (his closing line), `underline` (the words of it underlined in red; the line is drawn to the measured length of those words), `print` (a wide print), `foot` (his call to save) |

`print`: `photo` (`{"source": "<name>", "t": <seconds>}` for a frame of his video, or `{"source": "<photo>"}`;
optional `x`, `y`, `zoom` as in every carousel: where the crop sits and how close), `caption` (small, under the
picture), and by hand if needed `box` `[x, y, w, h]`, `rotate` (degrees), `tapes` `[[x, y, turn], ...]`.
`marker`: `text`, and by hand `box` `[x, y, width]`, `size`, `rotate`. `typed_top` and `title_top` move a block.

Positions have round-one defaults per kind and layout; leave them out unless something overlaps.

## Text rules
- Every title, typed line, list item, caption, marker note and foot is his words: from his recordings in the project
  or lines he typed (`studio lines --add`).
- Fixed labels: "FIELD NOTES", the page count "01 / 05", "STEP 1" and up, "@bernardablola", "swipe →", "→",
  "Follow @bernardablola".
- The red Permanent Marker note: at most three in a carousel, never two on a slide. One red per slide (the note with
  its arrow, or the closing underline).

## Checks (besides the standard ones)
- `marker_notes`: at most three marker notes, none doubled on a slide.
- `no_old_captions`: text detection on every slide; fails on caption text left from his videos.
