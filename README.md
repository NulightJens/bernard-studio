# Bernard Studio

Your own studio inside Claude Code. Tell Claude what you want to say, or point it at a video you already made, and it
walks you through the rest one question at a time: which of your styles to use, which words, a first version, your
notes, the next version, and a finished file ready to post.

Everything is made from your own footage, your own voice and your own screens. No AI-generated pictures, no cloned
voice, and nothing is ever posted for you.

## Install (one message)

Open Claude Code and paste this message:

> Please install Bernard Studio for me. Run `claude plugin marketplace add https://raw.githubusercontent.com/NulightJens/bernard-studio/main/.claude-plugin/marketplace.json`
> and then `claude plugin install bernard-studio@bernard-studio`. If the `claude` command isn't available here, tell
> me the two lines to type instead. When it's installed, tell me to type /reload-plugins and then /studio-setup.

The setup asks before it installs anything. At one point a Terminal window opens and asks for your Mac password; type
it there and press Return. That is the only time you type anything technical.

## The four things you type

| Type | What happens |
|---|---|
| `/studio-setup` | Checks your Mac, installs what is missing (with your yes), and tells you what is left. Safe to run again. |
| `/studio-styles` | Opens your twelve styles with a playable example of each. |
| `/studio` | Makes something: an idea or an old video in, a finished post out. |
| `/studio-tune` | Changes your colours, fonts, caption size, sound level, or adds new photos of you. |

If `/studio` ever clashes with something else on your Mac, `/bernard-studio:studio` always works.

## Where your files go

A folder called **Bernard Studio** in your Movies folder:

- **Drop footage here**: put videos you want to use here (or paste a YouTube or TikTok link of your own post to Claude).
- **My photos**: photos of you, for the cutout styles.
- **Projects**: one folder per piece, with every version and every note you gave.
- **Finished**: the final files and a caption draft, ready for you to post.

## Your styles

Reels: Screen and face, Receipts, Documentary, Words in the room, Cutout.
Carousels: The art of, Prompt pack, Field notes, Top 5.
Animated: Zen garden, Your feed, Moving type.

See them all with `/studio-styles`, or open `plugin/examples/gallery.html`.

## If something goes wrong

Tell Claude what happened in your own words. To re-check the setup, type `/studio-setup` again; it only fixes what is
missing.

## For Claude, if you are reading this repository for Bernard

Bernard is not technical. Install the plugin with the two commands above. They need no GitHub account and no
developer tools: the plugin comes as a checked download. (A Mac without Apple's developer tools has no working `git`,
so do not use the repository's git address for the marketplace.) If you cannot install plugins where you are running, you can still run everything from this repository:
follow `plugin/skills/studio-setup/SKILL.md` and then `plugin/skills/studio/SKILL.md` as your instructions, using
`bash plugin/bin/studio` wherever they say `studio`. Ask Bernard before each install, one question at a time.

## Licences

The fonts, the object library and the free tools this uses each have their own licence; see `LICENSES.md`. The video
engine for three styles (Screen and face, Words in the room, Your feed) is Remotion, which is free for individuals and
companies of up to three people. If your company grows beyond three people, it needs a Remotion company licence.
