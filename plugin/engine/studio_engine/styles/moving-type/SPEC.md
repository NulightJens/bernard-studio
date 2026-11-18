# Moving type: the settings file

A camera glides over a typeset board on a dark ground and lands on each group of lines as he says them. The voice is a
passage from any of his videos; the picture is drawn in code (no footage). 1080x1920, 24 frames a second by default.

```json
{"style": "moving-type", "spec_version": 1, "passage": "passage/passage.json",
 "beats": [
   {"kind": "stop", "lines": [{"text": "Most teams", "look": "strong"}, {"text": "use AI once", "look": "strong"}]},
   {"kind": "stop", "lines": [{"text": "and then forget it.", "look": "italic"}]},
   {"kind": "stop", "lines": [{"text": "used by", "look": "label"}, {"text": "10 people", "look": "number"}]}
 ],
 "poster": {"strike": "use AI once"},
 "sound": {"bed": "type"}}
```

## beats: the camera stops
Each beat is one stop of the camera (`"kind": "stop"`), in the order he speaks. Two to twelve stops.
- `lines`: one to four lines shown at this stop, top to bottom. Each line:
  - `text`: his words, exactly as he says them (a phrase cut from the passage). Numbers may be written as digits
    ("$40,000", "10"). Up to 40 characters; short lines read best.
  - `look`: `strong` (large italic serif, for the opening and the key lines), `italic` (italic serif), `serif`
    (upright serif, for plain connecting lines), `label` (small spaced capitals in grey, for lead-ins like "NOW IT
    COSTS"), `number` (a big bold figure that lands hard with a shake and a pass of light), `typed` (typewriter, types
    itself letter by letter, for a date or an aside). Default `serif`.
  - `size`: the type size on the board (defaults: strong 220, italic 130, serif 120, label 40, number 240, typed 70).
    The camera frames each stop to fit, so sizes are relative: a bigger line next to a smaller one.
  - `at`: when the line appears. Leave it out: it appears as he starts saying it (found from the text). A word anchor
    (`{"word": 7}`) only when the same words come twice and the wrong one would be found.
  - `x`, `y`: where the line sits on the board, in pixels from the middle. Leave them out: lines are stacked down the
    board, closer inside a stop and with more air between stops. `x` alone nudges a short line to the right (100 to
    250) under a longer one, which the original piece does for its trailing words.
- `keep`: true keeps the previous stop's lines lit (labels aside) and frames them together with this stop's lines.
  Use it when this stop finishes a sentence the previous stop started.
- `camera` (optional fine-tuning, leave out at first):
  - `land` / `leave`: the view as the camera arrives and as it leaves for the next stop: `zoom` (1.0 is fitted),
    `dy` (pixels, negative looks higher so the type sits lower), `roll` (degrees, small: under 1).
    Defaults: stops alternate a slight roll left and right and drift out 3 percent while they hold; a stop with a
    number arrives pushed in and eases out as the number lands.
  - `keys`: extra views in between, each with an `at` word anchor.
  - `lead`: seconds before the stop's first word that the camera starts moving (default 0.36).
  - `arrive`: seconds from the first word when it lands (default -0.04, just before).
  - `width`: how wide the stop's lines may be on screen in pixels (default 820, 800 with a number).

The first stop's lines are already set on the first frame, so the film opens on words, not on black.

## poster: the closing frame
After the last word the camera pulls back over the board to a poster: numbers and the last stop's lines bright, the
labels half lit, the rest faint, the opening stop gone. Then one red brush marks one line, the only red in the film.
- `strike`: a line's text (copied exactly): the brush strikes through it and the line dims. For the old way, the old
  price, the thing he is against.
- `underline`: instead of `strike`, the brush underlines the line. For the answer, the new way.
- `from`: the first stop the poster shows (default: the first stop after the opening; later if the board is very tall).
- `at`: when the pull back starts (default 0.4 seconds after the last word begins). `hold`: seconds the poster holds
  (default 1.75).

## sound
His voice on top. The bed defaults to `type`: a dark minor pad with a slow pulse that lifts to a major chord on the last
stop (its chord changes fall on the first words of the last three stops; set them with
`{"name": "type", "changes": [{"word": i}, {"word": j}, {"word": k}]}`). Any other bed by name works too. The style adds
its own effects: air on each camera move, a low hit under each number, typewriter keys on typed lines, a long whoosh on
the pull back and a brush swish on the red mark. `sfx` adds more by name with an `at`.

## On-screen words
Every line is his words; there are no fixed labels in this style. A line he does not say is refused before rendering.

## What QA reads
`layout.json` has one beat per stop (the lines the camera frames, as boxes where it lands) and one for the poster (every
line still visible, plus the red brush as the one red mark). Faint lines the camera has moved away from drift out of
the frame on purpose; they are background, not recorded as text.
