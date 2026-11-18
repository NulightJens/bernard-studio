---
name: style-your-feed
description: The "Your feed" style guide. How to pick his words for it, cut his own posts out of a recording of his feed (or use photos he posted), time the four scenes to his words, write its settings file and make the next version from his notes. Load when the studio skill has picked Your feed.
user-invocable: false
---

# Your feed

His real posts, re-staged in a dark feed. A column of identical grey posts flicks past and lands on his post; the
cursor clicks it. The camera pulls back: "YOUR POST" between the post above and the post below, and (if his words say
so) his post turns into the same grey post as everyone else. Then his post comes back in colour and the camera moves
into its picture, with a short line of his words on top. At the end a second post of his sits in the feed and its
picture lifts out of the card to the front, straight on, with one short red rule. Soft glassy pulse under his voice,
a whoosh on each move, clicks and ticks on the cursor.

Settings reference: `${CLAUDE_PLUGIN_ROOT}/engine/studio_engine/styles/your-feed/SPEC.md`.
Worked example: `${CLAUDE_PLUGIN_ROOT}/skills/style-your-feed/example-spec.json` ("When someone scrolls past your
post...").

## What it is good for
- A thought about content, posting, attention, brand, standing out, or what people see: anything where "a feed" and
  "his own post" are the picture of the idea.
- A line with a turn: everyone looks the same, then his own thing stands out.

Not good for: numbers and prices (use Screen and face or Moving type), a story about people, a list.

## What he needs to give
1. **A voice line** of 10 to 20 seconds from any of his videos (only the sound is used).
2. **Two of his own posts**, one of these ways (best first):
   - a short screen recording of his own LinkedIn activity page or Instagram grid, scrolling slowly past his posts
     (a phone or Mac recording; 10 seconds is enough). Old videos of his that show his own feed on screen work too.
   - two photos or slides he has posted (the files themselves). The style puts each into a plain post card.
3. The style needs the motion graphics part (`studio needs your-feed`).

Never use a recording where other people's posts, names or faces are the post you pick. Neighbouring posts are drawn
as anonymous grey posts by the style; only the two posts you pick are shown. If the recording shows his post next to
someone else's, that is fine: the style cuts out only his post. A post he reshared from someone else is not his post.

What to tell him if he has nothing yet: "Open your LinkedIn profile, tap Activity, and screen-record yourself scrolling
slowly through your posts for 10 seconds."

## 1. Pick the words (10 to 20 seconds)
Look for a passage that starts on its own feet and has three or four beats you can see as feed moments: someone
scrolls or sees posts; his post among others; what makes his stand out; a closing line. 25 to 50 words.
Show him the exact words in quotes and how long they run. On his yes:
`studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`, then `studio voice "<project>"`.
The reply gives the words with their numbers (`words[i]`). Keep it open.

## 2. Pick his two posts
- **From a recording**: ingest it (`studio ingest "<project>" "<file>"`), then look at frames of it yourself. For each
  post, find a second where the whole post is on screen and not moving (`at`), and a point inside it (`point`, in the
  recording's pixels: look at the frame's size). Pick posts whose picture reads at phone size: a bold slide, a short
  line of his, a strong photo of him. The first post's picture gets zoomed in; the second one's picture lifts out.
- **From photos**: ingest each file; the source name is in the ingest reply. Use `crop_y` to keep his face in frame on
  a tall photo (0.2 to 0.4).
- If the post's picture is smaller than the band it sits in (a slide on a light background), set `picture` to the
  slide itself, as fractions of the post. After the first render, check `v1/posts/first.png` and `second.png`.

## 3. Time the scenes to his words
Every time is a word number from the passage. Use plain anchors (`{"word": 12}`); add `"offset"` only to fix a
moment that feels late or early after you have watched it.
- `scroll.at`: leave it out (the feed starts moving at once). `scroll.click`: leave it out.
- `back.at`: the first word of his second thought (usually the second sentence or clause). Give the scroll at least
  1.5 seconds before it.
- `back.label`: leave it out, or the word that means "your post" / "you". It never comes in before the pull back has
  mostly happened (about half a second after `back.at`).
- `back.above` and `back.below`: only when he says something like "the person above you / below you", "everyone
  else", "the next post"; on those words.
- `back.same`: only when his words say his post looks like the others ("looks the same", "blends in", "like everyone").
  Not on a positive line: the collapse reads as "you disappear".
- `back.caption`: two or three of his words under the column, exactly as he says them ("looks like", "every post").
  Optional.
- `zoom.at`: the first word of the line about what makes his work his (his brand, his taste, his style). At least 1.2
  seconds after `back.at`.
- `zoom.title`: `small` is a short phrase of his words in capitals (up to 24 characters), `big` the words that carry
  the line (up to 18 characters), both exactly as he says them, for example "YOUR BRAND" / "already exists".
- `zoom.frame`: only if the picture has one detail worth pointing at (a headline on his slide); `box` is that detail
  as fractions of the picture; `at` the word that names it. Leave it out on a photo.
- `lift.at`: the first word of his last line. At least 1.2 seconds after `zoom.at`.
- `lift.pull`: the word of the release ("pull", "out", "show", "built", "right", "ready", the payoff word).
- `lift.red`: leave it out (it follows the pull), or the last word. `lift.rule_y`: leave it out on a photo; on a slide
  with a line of type, put it just above the type (fraction of the picture's height).

## 4. Sound
`"sound": {"bed": "feed"}`. The effects follow the scenes by themselves. For less sound: `"under_db": 20` (bed), or
`"effects": false`.

## 5. Settings file
Write `spec.json` in the project folder from the worked example: keep `style`, `spec_version`, `passage`; set
`sources` only if a file is not an ingested source; fill `posts`, `scroll`, `back`, `zoom`, `lift`, `sound`. Remove the
example's hand-tuned fields you do not need (`format`, `focus`, every `offset`, `rule_y`, `picture`). Then
`studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
Look at `v<N>/sheet.png` and at frames of `final.mp4` yourself: one in the scroll, one when "YOUR POST" is up, one in
the zoom, the last frame.
- Is the post the feed lands on his, whole, and sharp enough? No other person's name or face anywhere?
- Does the zoom land on the part of his picture that matters, with nothing cut off that should show?
- Does every on-screen line match his words exactly? Is the end frame clean, with one red mark?
- `qa.json` passes: every word heard back, loudness, safe zones, one red, his words. A second red area in the frame
  check during the zoom is fine when it is his own post's red.

## His notes
Change only what he named, then render the next version with `--version <next>`.
- "Use a different post" / "that's not my best post": change only that post's `at` and `point` (or its photo).
- "Zoom in more / less": add `zoom.focus.scale`. The default fits the picture to about 560 x 790 on screen (about 1 on
  a photo post, about 2.3 on a slide inside a LinkedIn post); 1.4 to 1.8 on a photo is "more". With a title, the
  camera keeps the picture's top edge below the title by itself.
- "Start on the second sentence": make a new passage from that sentence, then move every anchor (read the new
  `passage.json`; word numbers change) and keep everything else.
- "The red should be on X": set `lift.red` to that word.
- "Bigger title": the size is fixed in the style; offer a shorter `big` line instead.
- "Less sound": raise `sound.under_db` by 2, or set `"effects": false`.

## Common mistakes
- Word numbers copied from the example: they belong to the example's words, never to his new passage.
- A post picked mid-scroll: the edges cannot be found. Pick a second where the page is still.
- `back.same` on a line that is not about blending in.
- A title or caption he never said.
- Someone else's post as his post.
