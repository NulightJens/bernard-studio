---
name: style-zen-garden
description: The Zen garden style guide. How to pick his words for it, map them to the garden (the feed of stones, the rings, the red stone), write its settings file and make the next version from his notes. Load when the studio skill has picked Zen garden.
user-invocable: false
---

# Zen garden

One overhead shot of black raked sand under a single low, warm light. Dark stones sit in the sand. As he speaks, the
camera can scroll down a column of identical stones like a feed, a rake draws rings round the stones he names, and at
the end one red stone comes up out of the sand. That red stone is the only red in the film. His words sit as captions,
one phrase at a time, in his italic serif. It is calm, dark and slow, and reads with the sound off.

Settings reference: `${CLAUDE_PLUGIN_ROOT}/engine/studio_engine/styles/zen-garden/SPEC.md`.
Worked example: `${CLAUDE_PLUGIN_ROOT}/skills/style-zen-garden/example-spec.json` (his "Your brand already exists"
piece).

## What it is good for
- One quiet thought that ends on a reveal: something that was there all along, the answer under the noise, the one
  thing that matters. The red stone rising is that moment.
- A thought that names two to four things on the way (what you love, what you already have, black and white): each
  one gets a stone and a ring.
- A thought that starts from sameness (the feed, everyone looking alike, the crowd): the scroll down identical stones
  shows it.
- Any of his videos works as the voice, even one with a messy picture: only his voice is used.

Not good for: numbers, prices, lists of steps, a before-and-after with figures, or anything loud or fast. For those
suggest another style.

## What he needs to give
Nothing new. A voice line of 10 to 20 seconds from any of his videos. If he has a new thought, he can record it on his
phone; only the sound is used.

## 1. Pick the words (10 to 20 seconds)
Read the transcript and look for:
- a passage that starts on its own feet (not "and so", not "that's why") and ends on its point;
- a reveal or an answer near the end, on a word you can raise the red stone on ("out", "light", "you", "already");
- two to four things he names on the way, if you want rings;
- 25 to 50 words.

Check the transcript words in the passage. If a word was heard wrong ("wait" where he said "weight"), the caption can
only show the word as it was heard, so choose a passage without it, or start after it.

Show him the exact words in quotes and how long they run. On his yes:
`studio passage "<project>" --source <name> --from "<first words>" --to "<last words>"`

The passage reply gives the words with their numbers (`words[i]`). Keep it open: every beat uses those numbers.

## 2. Map his words to the garden
Write the words out with their numbers, then decide which parts of the garden this piece uses. There are three beats,
always in this order:

**Feed (optional).** Use it only when he opens on sameness: scrolling, a feed, a crowd, "everyone", "the person above
you". The camera flicks down a column of identical stones and comes to rest.
- `flick`: the word the scroll starts on, early in the first phrase (often word 1 to 3).
- `land`: the first word of his next phrase (the scroll has stopped by then).
- `light` (optional): when he points at others, the light moves: `{"to": "above", "at": <word>}` or
  `{"to": "below", "at": <word>}` on the word "above", "below", "next", "other" and so on. At most three.
- `go`: the last word of the feed part. Leave it out unless the carry on to the stones starts too early or late.
Leave the feed out for any other opening: the film then opens gliding down onto the stones.

**Stones (optional).** The things he names. One ring per thing, one to four.
- `rings`: the word numbers of the things, in order (the noun itself: "brand", "things", "white").
- The first ring at least one second into the passage: the light is still coming up before that. If he names
  something sooner, skip that one.
- Ring words at least a third of a second apart; better one per phrase.
- Leave `arrive` out.

**Rise (always, last).** The red stone.
- `up`: the word the reveal lands on, near the end ("out", "light", "now"). The stone is fully out just after it.
- Leave `at` and `ring` out: the sand starts to heave about a second before, and the rake rings it right after.
- After `up` there should be at least a second of his words or the hold, so the stone is seen.

## 3. The captions
Cut every word of the passage into phrases, in order, one caption each:
- one phrase per caption, where he breathes or the sentence turns; usually 5 to 8 captions for 15 seconds;
- three to eight words, up to 60 characters (it wraps into two lines by itself; very long phrases are refused);
- his words exactly as in the transcript, with his punctuation. Do not skip, add or change a word. Spoken numbers may be
  written as digits.

## 4. The sound
Use the zen bed: a low open drone that warms into a chord as the red stone starts to rise. Leave out `rise`: it
follows the stone. The style adds its own effects (air on the scroll, the breath of the light, raked sand for each
ring, the rumble and the bowl when the stone is up). Add nothing else for the first version.

## 5. Write the settings file
Write `spec.json` in the project folder:

```json
{"style": "zen-garden", "spec_version": 1, "passage": "passage/passage.json",
 "beats": [
   {"kind": "feed", "flick": <word>, "land": <word>, "light": [{"to": "above", "at": <word>}]},
   {"kind": "stones", "rings": [<word>, <word>, <word>]},
   {"kind": "rise", "up": <word>}
 ],
 "captions": [
   {"text": "<his phrase>"},
   {"text": "<his phrase>"}
 ],
 "sound": {"bed": "zen"}}
```

Leave out the feed beat when he does not open on sameness, and the stones beat when he names nothing. The worked
example also carries `go`, `arrive`, `at`, `ring` and `hold`: those were set to match the first piece exactly. For a new
piece leave them out.

Then: `studio render "<project>" --spec "<project>/spec.json"`. It checks the settings first and tells you in plain
words if a caption is not his words or a beat is out of order.

## 6. Check it before he sees it
Open `v<N>/sheet.png` (a frame at every caption and every moment of the garden) and look:
- every caption is fully inside the frame and readable on a phone;
- each ring is being drawn on its word, round the stone it belongs to;
- the red stone is out on its word and is the only red thing in the frame;
- the poster (`v<N>/poster.png`) shows the red stone up among the others.
Then the reviewer agent. If the sheet shows a problem, fix the settings and render again before showing him.

## 7. His notes, the next version
Change only what he named. Common notes and what to change:
- **"Bring the red stone up on '<word>'"**: change `up` in the rise beat to that word's number. Keep it after the
  first ring.
- **"Ring the other thing" / "ring on '<word>'"**: change that number in `rings`.
- **"Too slow at the start"**: start the passage later (a new `studio passage`), or drop the feed.
- **"Start on the second sentence" / "cut the first part"**: a new passage with `studio passage`, then rebuild the
  beats and captions from the new words (the numbers change).
- **"Hold the end longer"**: `hold` (seconds after his last word, default 2, up to 4).
- **"I can't read it"**: shorter captions (split a long phrase in two).
- **"Different music"**: another bed by name (`studio sounds` lists them); keep the effects.
Record his note first (`studio note`), render the next version, check the sheet, then show him.

## Common mistakes
- A feed beat on a thought that has nothing to do with sameness: the scroll then means nothing.
- Rings on filler words ("the", "it") instead of the things he names.
- The red stone on the first half of the passage: the reveal belongs at the end.
- A caption with a word he did not say, or a misheard word fixed by hand. The render refuses it.
- A passage that ends mid-thought: the red stone then has nothing to land on.
