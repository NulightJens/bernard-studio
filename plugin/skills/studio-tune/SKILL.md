---
name: studio-tune
description: Lets Bernard change his look and preferences in plain questions - colours, fonts, the one red, caption size, sound level, new photos of himself for cutouts, and saved preferences per style. Use when he types /studio-tune or asks to change how his videos or carousels look or sound.
---

# Tune your studio

His settings live in his own folder and apply to every new version from now on (finished files never change).
One question per message, plain words. Talk to him as "you", never about him as "Bernard" or "he", and never mention
commands, setting names, file names or paths to him. Run `studio` on its own (never chained with `&&` or `;`), read
files with the Read tool, and never run other shell tools.

1. Run `studio brand get --json` to see his current settings.
2. Ask: "What would you like to change: your colours and fonts, caption size, sound level, new photos of you, or how
   a particular style behaves?"
3. Then, for what he picked:
   - **Colours and fonts:** show the current ones by name and colour. His kit uses one red, once per frame; if he wants
     a different accent colour, it replaces the red, it does not join it. Fonts come from his kit; a new font must be a
     file he gives you. Save with `studio brand set <key> <value>`.
   - **Caption size:** ask "a bit bigger, much bigger, or smaller?" and save it with
     `studio brand set captions.size <size>` (62 is the standard size). Every style's captions grow or shrink by the
     same step. They always stay inside the safe area of the phone screen, so a long caption at a large size is set to
     fit or wraps onto more lines.
   - **Sound level:** music and effects sit well under his voice. Ask "music a little louder, quieter, or off?" and
     save it. His voice always stays on top.
   - **New photos of him:** ask him to drop sharp photos (face lit, plain background helps) into `My photos`; open the
     folder for him with `studio open photos`. See the new photos with `studio list photos`. Then run
     `studio matte-photo "<photo>"` on each new one (it needs the cutout tool; ask him first and install it on his yes if missing). Look at each cutout it
     reports with the Read tool, then show it to him with `studio open file "<the cutout>"`. Keep only the ones he likes.
   - **A style's preferences:** ask which style and what he wants different (for example "always open on the number"),
     save it with `studio brand set style.<slug>.<key> <value>` in his words. The next time that style is made, the
     studio reads it back and follows it.
4. Confirm in one line what changed, and that the next version he makes will use it.
