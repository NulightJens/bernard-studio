---
name: studio-setup
description: Sets up Bernard Studio on Bernard's Mac, step by step, with his yes before each install, and ends with a plain list of what is left. Safe to run again; it only does what is missing. Use when he types /studio-setup, right after the plugin is installed, or when /studio finds the setup missing.
---

# Set up Bernard Studio

Bernard is not technical. Do the work for him, explain each step in one plain line, and get his yes before you
install anything. One question per message.

Talk to him as "you", never about him as "Bernard" or "he". Use plain words: no commands, file paths, exit codes,
"engine", "venv" or other technical terms in what you say to him. Never add notes meant for a developer.

Run `studio` on its own, one command per call: never chain it with `&&`, `||` or `;`, and never run other shell tools.
Read files with the Read tool. Installs are the steps he is asked to allow; ask him in chat first and run them only on
his yes.

The first command is `studio doctor --json`. If it answers that `studio` is not found, the plugin is not switched on
yet: tell him to type `/reload-plugins`, then `/studio-setup` again, and stop there.

## 1. Check his Mac
Run `studio doctor --json`. Tell him in two or three lines what you found: his Mac (chip, memory, free space) and
what is already there. If free space is under 20 GB, say so: his videos and the tools need room.

## 2. Say what will happen, then ask once
The doctor's `setup` field lists what the one-time setup still has to install (`missing`) and its size (`disk_gb`).
Say it in plain words with that size, for example: "To make videos, the studio needs a few free tools: Homebrew
(installs the others), ffmpeg (video), whisper (turns speech into words), and its own Python. That is about
<disk_gb> GB. Some styles need one more tool, and I'll ask you about those the first time you pick one. Shall I
start?" Name only the parts that are missing. If nothing is missing, say so in one line and go to step 5.

## 3. Homebrew (only if missing)
Homebrew asks for his Mac password, and only he can type it. Say: "A Terminal window will open and ask for your Mac
password. Type it there (you won't see the letters as you type) and press Return." Then run
`studio install homebrew --json` with the Bash timeout set to 600000. It waits up to 9 minutes; if it exits with code
75 ("still working"), run it again to keep waiting. If it reports that the window was closed or the password was wrong,
offer to open it again.

## 4. The base
Run `studio install base --json` with the Bash timeout set to 600000. It prints progress; pass the gist on in short
lines ("Downloading the speech model, 1.5 GB"). On a slow connection it may stop at the time limit; run it again and it
picks up the download where it left off.

Exit codes for every `studio install` step: 0 done, 1 failed (its last line is one plain sentence with the fix),
3 another part must be installed first (it names it), 4 his Mac is too small for this part, 75 still working (run it
again). If a step fails twice, add it to the "what's left" list with the fix it gives.

## 5. His folder
The base step makes his Bernard Studio folder (in his Movies folder) with four folders: `Drop footage here`,
`My photos`, `Projects`, `Finished`. Open it for him with `studio open folder` and say what each folder is for, one
line each.

## 6. What's left
Run `studio needs --all --json`: for every style it lists the parts still missing and their size. Give him a short
list, only of what is true:
- Videos to drop in `Drop footage here` (or links he can paste to you later).
- Optional: an Auphonic account for even cleaner voice. If he wants it, run `studio install auphonic`: a Terminal
  window opens where he pastes his Auphonic key; it goes straight into his Mac's Keychain and is checked with Auphonic.
  Never ask him to paste the key into this chat.
- Styles that need one more part, by their names in `styles.json`, with the part and its size. They are installed the
  first time he picks them.
- Anything that failed, and its fix.
End with: "You're set. Type /studio to make something, or /studio-styles to see your styles first."

## Running it again
Run the same steps; skip whatever doctor reports as installed, and say so in one line. Never reinstall something that
works.
