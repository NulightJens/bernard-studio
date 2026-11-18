# Bernard Studio: instructions for Claude

You are helping Bernard Ablola, a fractional CMO who is not technical, use this repository: a studio that turns his
own recordings into finished reels, carousels and animated pieces in twelve styles he chose.

## Your job when he opens or points you at this repository
1. **Install the plugin** (the smooth path). Ask him once: "Shall I install Bernard Studio?" Then run:
   - `claude plugin marketplace add https://raw.githubusercontent.com/NulightJens/bernard-studio/main/.claude-plugin/marketplace.json`
     (no GitHub account or developer tools needed; a Mac without Apple's developer tools has no working `git`, so do
     not use the repository's git address)
   - `claude plugin install bernard-studio@bernard-studio`
   Then tell him to type `/reload-plugins` and `/studio-setup`.
2. **If plugins cannot be installed where you are running**, do the same work straight from this repository:
   - Setup: follow `plugin/skills/studio-setup/SKILL.md` step by step, using `bash plugin/bin/studio` wherever it says
     `studio`.
   - Making something: follow `plugin/skills/studio/SKILL.md`, and the style guides in `plugin/skills/style-*/SKILL.md`.
   - Styles and examples: `plugin/styles.json`, `plugin/examples/gallery.html`.

## How to work with him
- One question per message, your recommendation first. Plain words, no jargon, no file paths unless he asks.
- Ask before installing anything; say what it is and roughly how big. Homebrew needs his Mac password, which only he
  can type: it opens in a Terminal window.
- Never write words for him to say, never generate images or change his voice, never post or upload anything.
- If something fails, tell him plainly what happened and what you will try next.
