# Zen garden: the settings file

One continuous overhead shot of black raked sand under a single low, warm light. Smooth dark stones sit in the sand.
A rake draws rings round the stones as he names them, and at the end one red stone comes up out of the sand: the only
red in the film. His words sit as captions, one phrase at a time. The voice is a passage from any of his videos; the
picture is drawn in code (no footage, nothing generated). 1080x1920, 24 frames a second by default.

```json
{"style": "zen-garden", "spec_version": 1, "passage": "passage/passage.json",
 "beats": [
   {"kind": "feed", "flick": 2, "land": 6, "light": [{"to": "above", "at": 11}, {"to": "below", "at": 16}]},
   {"kind": "stones", "rings": [19, 24, 26]},
   {"kind": "rise", "up": 33}
 ],
 "captions": [{"text": "When someone scrolls past your post,"}, {"text": "it looks like the person above you"}],
 "sound": {"bed": "zen"}}
```

Every time is a word anchor: a word number from the passage (`7`), or `{"word": 7, "offset": -0.1}`, or
`{"t": 1.2}` in seconds. A plain word number means "as he starts that word"; the style adds its own small lead or lag
to each kind of moment (listed below), so plain word numbers are almost always right.

## beats: up to three, in this order
- **`feed`** (optional, first). The camera flicks down a column of identical stones, each with identical rings, like
  scrolling a feed, and inertia brings it to rest on one. For sameness: a feed, a crowd, everyone looking alike.
  - `flick` (required): the word the scroll starts on (0.05 s before it).
  - `land`: the word it has come to rest by (default 1.6 s after the flick).
  - `light`: up to three moves of the light, each `{"to": "above" | "below" | "here", "at": word}`: the light leaves
    the stone in view for the one above it, the one below it, or comes back. Starts 0.1 s before the word.
  - `go`: the word after which the camera carries on to the stones (0.25 s after it starts; default 0.75 s after the
    last light move).
- **`stones`** (optional). A few stones that are each a different shape. A rake draws rings round each one on its word.
  For the things he names: what you love, what you already have, the parts of a whole.
  - `rings` (required): one to four words, in order, one per stone. The rake starts just before the word and takes
    about a second. Ring words at least a third of a second apart.
  - `arrive`: the word the camera arrives at the stones on (0.05 s after it; default 0.2 s before the first ring).
    Without a feed the film opens on the stones, gliding down onto them, with their sand still unraked.
- **`rise`** (required, last). Between the stones the sand heaves, and the red stone comes up through it with sand
  falling off; the rake rings it and the light closes in on it. For the answer, the thing that was there all along.
  - `up` (required): the word on which the stone is fully out (0.25 s after it starts).
  - `at`: the word the sand starts to heave on (0.3 s before it; default about a second before `up`).
  - `ring`: the word the rake rings it on (0.15 s after it; default just after `up`).

Without a `feed` or a `stones` beat the garden is the same; that part is simply not in the film.

## captions: his words, one phrase each
`[{"text": "..."}]` in the order he says them. Each caption appears as he starts its first word and holds until the
next one (the last holds to the end). Up to 60 characters; a caption wraps into one to three balanced lines in the
kit's italic serif, cream on a soft dark halo, ending 335 px above the bottom of the frame. A caption he does not say,
or one out of order, is refused before rendering. `at` (a word anchor) only when the same words come twice.

## hold
Seconds the film runs on after his last word ends (default 2.0, 0.8 to 4).

## sound
His voice on top. The bed defaults to `zen`: a low open drone (A and E) that warms into an add9 chord as the red stone
starts to rise (`{"name": "zen", "rise": word}` moves the chord). Any other bed by name works too. The style adds its
own effects: air on the flick and the carry, a low breath when the light moves, raked sand for each ring, a rumble and
a pour of sand under the rise, one struck bowl when the red stone is up. `sfx` adds more by name with an `at`.

## On-screen words
Every caption is his words; there are no fixed labels in this style.

## What QA reads
`layout.json` has one beat per caption (its box at rest) and one for each moment of the garden (the landing, each
light move, each ring, the rise, the end) carrying the caption on screen then. From just before the red stone is out,
those beats also carry the red stone's footprint as the one red mark.
