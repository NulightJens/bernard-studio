# your-feed spec

Animated, 1080x1920 (24 fps unless `format.fps` says otherwise). Drawn by the shared motion graphics project
(`engine/remotion/src/your-feed/YourFeed.tsx`); needs the `remotion` component. His voice starts `lead` seconds in
(default 0.35) and the picture holds `tail` seconds after his last word (default 1.25).

Every time field is a word anchor (`{"word": i}`, `{"word": i, "offset": -0.1}`, `{"word": i, "edge": "end"}`,
`{"t": seconds}`) on the passage's words. Scenes run in this order and must not overlap: scroll, back, zoom, lift.

## posts (required)
`{"first": post, "second": post}`. `first` is the post the feed lands on and the zoom moves into; `second` is the
post whose picture lifts out at the end. A post is either:
- **cut from a screen recording of his own feed**: `{"source": "<name>", "at": seconds, "point": [x, y]}`. `at` is a
  second of the recording where the whole post is on screen and still; `point` is any pixel inside the post, in the
  recording's own pixels. The style finds the post's thin border around that point and cuts it out (a LinkedIn post
  in a 1080p recording is 554 x 878 pixels). It stops with a plain message if it cannot find a whole post there.
- **made from a photo of his**: `{"source": "<name of an ingested photo>", "crop_y": 0.4}`. The style makes a warm
  white post card with the photo in it at 4:5 and grey lines where the text would be; no words are written on it.
  `crop_y` (0 top to 1 bottom) picks which part of a tall photo stays.
Optional on both: `"picture": [left, top, right, bottom]`, fractions of the post: the picture inside it (the part the
zoom moves into, and the part that lifts out). Default: the longest run of non-white rows of a cut post (its picture
band), or the photo on a photo post.
The two cut posts are saved in `v<N>/posts/` so they can be checked.

## scroll
`{"at", "land", "click"}`, all optional. The feed of grey posts flicks down from `at` (default 0.05 s) and lands on
his post at `land`; the cursor clicks it at `click`. Defaults: `click` 0.1 s before `back.at`, `land` 0.15 s before
`click`.

## back (required: `at`)
The camera pulls back to his post between the post above and the post below (0.85 s from `at`).
- `label`: when "YOUR POST" and the cream corner brackets come in (default `at` + 0.65 s). "YOUR POST" is the
  style's one fixed label.
- `above`, `below`: a cream outline pulses on the post above / below.
- `same`: his post turns into the same grey post as the others (0.4 s). "YOUR POST" turns red from then on; that is
  this scene's one red.
- `caption`: `{"text", "at"}`, two or three of his words in serif italic under the column (up to 22 characters).
Everything in this scene fades out just before `zoom.at`.

## zoom (required: `at`)
His post comes back in colour, the camera moves into its picture (0.9 s) and the rest goes dark.
- `focus`: `{"x", "y", "scale"}`, the point of the post (fractions) the camera centres on and how far it zooms. Default:
  the picture's centre, scaled to about 560 x 790 on screen.
- `title`: `{"small", "big"}`: a small typewriter line (up to 24 characters) over a big serif italic line (up to 18),
  centred near the top. Both his words.
- `frame`: `{"box": [left, top, right, bottom], "at"}`: the cursor draws a cream frame around a detail of the picture
  (fractions of the picture), the rest dims.

## lift (required: `at`, `pull`)
From `at` his second post sits in an anonymous feed. On `pull` its picture comes out of the card (0.67 s) and settles
straight on, up to 880 wide and 1000 tall. On `red` (default `pull` + 0.57 s) a short red rule draws on the picture,
`rule_y` (fraction of the picture's height from its top, default 0.12) down: the one red mark of the closing frame.

## sound
`{"bed": "feed" | any engine bed | "none", "under_db": 18, "effects": true}`. `feed` is the style's own bed: a glassy
pad over a soft pulse at 100 beats a minute. Effects come from the scenes by themselves: a whoosh on the scroll, the
pull back, the zoom and the lift, clicks on the cursor, ticks on the label and the pulses, a swell on the collapse and
the pull, a soft tap after the red rule; each 25 to 30 dB under his voice.

## finish
`{"grain": 0.06}`: film grain strength (0 turns it off).

## What QA reads (layout.json)
Beats: scroll (no text), back (from `label`: "YOUR POST" as a label, red when `same` is set, and the caption), zoom
(from 0.55 s after `zoom.at`: the title lines), lift (from `red`: the red rule as a mark). His posts are pictures of
his own screen and are not read as text. A post's own red (a red band on his poster) can show as a second red area in
the frame check (a warning, not a failure): it is his real post.
