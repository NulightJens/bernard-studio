# Top 5: settings file

A countdown carousel at 1080 x 1440 in his kit (obsidian, Raleway, Cormorant Garamond, Special Elite). Slide 1 is the
cover, then one slide per item, counted down to 01. Three to ten items (the cover says "TOP" and the count). No sound.

## Fields
| Field | What |
|---|---|
| `cover.title` | his headline for the list, about two short lines, `\n` breaks ("What $20 a month\nbuilt for my brand") |
| `cover.kicker` | optional, the small line at the top of the cover: one of "Ranked" (the default), "Countdown", "My list", "Ranked · from my own build" (only for a list of things he built or uses himself), a short line of his words, or "" for none |
| `cover.photo` | a picture of him for the top of the cover (fades into black). The studio finds his face on it: when his head sits where "TOP 5" goes, the number moves to the left, then up or down, then gets smaller (down to half size) until it is clear of his head |
| `items[]` | from the highest number down to number one: `title` (the item, his words), `small` (a short line under it), `photo` (his screen or his footage), `from` (optional small line on where the picture comes from, his words), `quote` (his line about it, one or two sentences) |

A picture (`photo`) is `{"source": "<name>", "t": <seconds>}` for a frame of his video, `{"source": "<name>", "from":
<s>, "to": <s>}` to let the studio pick the best still moment in that stretch (sharp, never mid-scroll), or
`{"source": "<photo>"}`. Optional `x`, `y` (0 to 1: where the crop sits) and `zoom` (1 to 3). Burned-in captions are
always cut out.

## Text rules
- Titles, small lines, sources and quotes are his words: from his recordings in the project or lines he typed.
- Fixed labels: the kicker choices above, "TOP", the count, "(#1 will surprise you)", the numbers "01" to "10",
  "Bernard Ablola", "→", "Top 5 · 05" and the like, "Save this · Follow @bernardablola".
- One red per slide: the underline under "#1" on the cover, the bar under each number, the red "01".
- A quote that runs into the footer stops the render with a plain message.

## Checks (besides the standard ones)
- `cover_face_clear`: his face on the cover photo (Apple Vision, brow to chin) is found and no text on the cover covers
  it (a sliver under 1 percent of the face is let through). layout.json holds the face (`faces`) and, when the number
  moved, where it went (`cover_number`). Fails with the text that sits on his face: pick a cover photo with his face to
  one side or higher in the frame (`cover.photo.y`).
- `no_old_captions`: text detection on every slide, plus the captions found on each source frame mapped into the part
  the slide shows; fails on any caption text left from his videos. Overlays in `v<N>/qa/captions/`.
