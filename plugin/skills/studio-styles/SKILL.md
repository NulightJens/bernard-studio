---
name: studio-styles
description: Shows Bernard his twelve styles with a playable example of each, what each is good for and what to record for it. Use when he types /studio-styles or asks what styles he has or what they look like.
---

# Your styles

Talk to him as "you", in plain words, one question per message. Run `studio` on its own (never chained with `&&` or
`;`), and read files with the Read tool.

1. Open the examples page: `studio open gallery`. It opens in his browser with every example playing. If that answers
   that `studio` is not found, tell him to type `/reload-plugins` and try again.
2. Read `${CLAUDE_PLUGIN_ROOT}/styles.json` with the Read tool and list the twelve by name, grouped as Reels,
   Carousels and Animated, one short line each (the "what" field, shortened). Use the names exactly as written there.
3. Ask one question: "Want to make one now? Tell me which, or what you'd like to say and I'll suggest one."
   If he picks one, continue with the `studio` skill from its step 3, with that style chosen.
