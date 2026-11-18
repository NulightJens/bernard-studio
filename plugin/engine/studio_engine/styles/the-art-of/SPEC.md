# The art of: settings file

A carousel of 1080 x 1350 slides on a flat light grey (#E5E5E5), set in Inter. Slide 1 is the cover, then one slide
per section (three to eight), then a closing photo slide. No sound.

## Fields
| Field | What |
|---|---|
| `topic` | the cover line under "The art of", his words, lower case, at most about 22 letters ("building your brand") |
| `cover.objects` | five object names from the library, in this order: top left, top centre, top right, middle left, middle right. The top three are best as a laptop or phone showing his own work (`lt_*`, `ph_*`) plus one object; the middle two are thin or small objects (a sword, a watch, glasses) |
| `cover.left`, `cover.right` | `{"pose": "<pose name>"}`: the two cutouts of him in the bottom corners. A pose's `cover_side` in the pose library says which corner it fits. `box` `[x0, y0, x1, y1]` places it by hand; leave it out to use the standard place |
| `cover.plus` | `[x, y]` centre of the plus between the cutouts (default `[489, 1085]`); move it so it sits in the gap |
| `sections[]` | `{"name": "<one or two words, capitals>", "items": [six of {"object": "<name>", "text": "<his line>"}]}` |
| `sections[].items[]` order | top left, top right, middle left, middle right, bottom left, bottom right |
| `last.photo` | `{"source": "<source name>", "t": <seconds>}`: a frame of his video (or `{"source": "<photo>"}` for a photo). Optional `zoom` (1 to 3), `x` and `y` (0 to 1: where the crop sits, 0 flush left or top, 1 flush right or bottom). The crop always keeps burned-in captions out |
| `last.headline` | his closing line, shown under "Welcome to my account." |
| `last.line` | optional second line (a `\n` breaks it in two) |

## Text rules
- Every caption, section name, topic and closing line is his words: trimmed from what he said, or lines he typed.
- Fixed labels: "The art of", "Welcome to my account."
- Captions: one short line, at most four lines at slide size (about 60 letters). The render stops with a plain
  message naming any line that is too long.

## Objects and poses
- Objects: `library/objects/tags.json` (`what`, `can_stand_for`). New objects made for one project go in that
  project's `objects/` folder as `<name>.png` (transparent background).
- Poses: `library/poses/library.json`, plus any he added (`studio matte-photo`), kept in his settings folder under
  `poses/`. A pose name is its file name without `.png`.

## Checks (besides the standard ones)
- `no_old_captions`: text detection on every slide; fails if any burned-in caption text from his videos is left on a
  slide. The overlay of every detected box is saved in `v<N>/qa/captions/`.
