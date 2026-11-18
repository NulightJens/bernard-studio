---
name: style-top-5
description: The Top 5 style guide. How to pick his list for this countdown carousel, choose a real picture for each item (including from old TikToks with captions), write its settings file and make the next version from his notes. Load when the studio skill has picked Top 5.
user-invocable: false
---

# Top 5

A countdown list with his real screens and footage, one item per slide. The cover shows him at the top fading into
black, "TOP 5" set huge, his headline and "(#1 will surprise you)". Each item slide has the big number with a red bar,
the item in capitals with a small line under it, a picture, and his quote about it in italic. Number one gets a red
number and the "save this, follow" line. Lists are his biggest format. Slides are 1080 x 1440. No sound.

The count follows his list: three to ten items. The cover then says "TOP 3" or "TOP 7".

## What it needs
- **A list**, from a video where he counts things down or up ("number one... number two"), or typed by him.
- **A picture for each item**: his screen showing it, or a moment of his video where he holds or shows it. Old
  TikToks and reels work: the studio keeps their burned-in captions out of every picture.
- **A picture of him** for the cover.
- The style needs the slide maker (`studio needs top-5`).

## Picking the words
1. From a video: run the ingest on it and read the transcript. From typed lines: save each message he types for this
   list with `studio lines "<project>" --add "<exactly what he typed>"` (one call per message, never tidied).
2. Find the items and their order. If he numbered them, keep his order: his number one is the last slide. If not,
   ask him which one is number one (the surprise).
3. For each item: a short title from his words ("Meditations", "30 quote cards in one sitting"), an optional small
   line (his words: who wrote it, where it lives), and his best one or two sentences about it as the quote.
4. The cover headline is his promise ("Three books to become a strong man").
5. Check names against what he says: speech-to-text mishears names and titles. Use only the parts it heard right
   ("The Superior Man" when it heard "The Weight of the Superior Man"), or ask him to type the exact name and save it
   with `studio lines --add`.
6. Show him the cover and every item (title, small line, quote) in quotes. Ask "Use these words?"
7. No passage is needed: leave `passage` out. Every word is checked against his recordings and typed lines.

## Choosing the pictures
- A picture can be a moment (`"t"`) or a stretch (`"from"` and `"to"`, a few seconds while he talks about that
  item): the studio picks the sharpest still moment, never mid-scroll.
- For screens, crop in on what matters with `zoom` and `x`/`y` (0 = far left or top, 1 = far right or bottom).
- From old TikToks and reels: just pick the stretch. The studio finds the captions (the ingest marks them), cuts every
  picture clear of them and of the big on-screen words his old edit added, and the check fails if any caption text is
  left on a slide.
- Keep other people's names and faces out (crop a feed to his own posts).

## Settings file
Write `spec.json` in the project folder:
- `style`: "top-5", `spec_version`: 1
- `cover`: `title`, `photo`, and `kicker` (the small line at the top): "Ranked" by default; "Ranked · from my own
  build" only when every item is something he built or uses himself; "Countdown" or "My list" otherwise; or a short
  line of his words; "" for none
- `items`: from the highest number down to number one, each `title`, `small`, `photo`, `from` (optional), `quote`

The worked example is `example-spec.json` next to this guide ("What $20 a month built for my brand", five items).
Copy its shape. Then run `studio render "<project>" --spec "<project>/spec.json"`.

## Before he sees it
For the cover photo, pick a moment where his face sits to one side or high in the frame: the big number moves off his
face by itself (to the other side, or smaller), and the `cover_face_clear` check fails if any text still covers it;
then pick another moment or move the crop with `cover.photo.y`.
Open every slide yourself. Check: each picture shows the item clearly (not a blurred hand, not mid-blink), no old
caption or on-screen word from his old edit is left in a picture, quotes end before the footer, the cover headline
does not crowd the "(#1 will surprise you)" line. Then have the reviewer check it. The studio's checks must pass.

## His notes
Change only what he names:
- "Different picture for number 3" -> that item's `photo` (another moment or stretch).
- "Shorter quote" -> that item's `quote`, trimmed from his words.
- "Swap the order" -> move the items; number one stays his choice.
- "Add one" -> a new item from his words; the count on the cover follows.
- Colours or fonts -> fixed in this style; offer `/studio-tune` or another style.

## Common mistakes
- A misheard name on a slide. Check names against the video or ask him to type them.
- Pictures with captions or big words from his old edit. The studio cuts them out; if a picture still looks crowded,
  pick another stretch.
- Quotes longer than two short sentences.
- Writing an item title in your words. Titles come from what he said.
