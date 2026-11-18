# The motion project (one Remotion project for every style that needs it)

Dev notes for style builders; nothing here is shown to Bernard.

## Layout
```
engine/remotion/
  package.json, package-lock.json   exact pins (remotion 4.0.459, react 19.3.1). Change only together, with
                                    `npm install --package-lock-only` under Node 22; the lockfile's hash names the
                                    installed copy, so a new lockfile means Bernard re-runs `studio install remotion`.
  remotion.config.ts                PNG frames, ANGLE, bt709 (no browser path: `remotion browser ensure` puts it in
                                    node_modules at install)
  src/index.ts                      registerRoot
  src/Root.tsx                      one <Composition> per style, id = the style's slug, size/rate/length from props
  src/kit.tsx                       shared: easing, prog(), Word (rises out of a mask), useFonts(), Guides
  src/<slug>/<Name>.tsx             one folder per style (screen-and-face, words-in-the-room, your-feed, ...)
```

## Adding a composition
1. Make `src/<slug>/<Name>.tsx`. Take every time as a frame number in the props (Python resolves word anchors), and
   take colours and font files from the props (his brand settings), not constants.
2. Add one line to `Root.tsx`:
   `<Composition id="<slug>" component={<Name> as any} width={1080} height={1920} fps={24} durationInFrames={24}
   defaultProps={blank as any} calculateMetadata={sized} />` (the props must carry `w`, `h`, `fps`, `frames`).
3. From the style's `render.py`:
   ```python
   from studio_engine import remotion
   public = ctx.work / "public"
   remotion.place(brand.font_path("title"), public / "fonts" / "serif.ttf")   # media, fonts, brushes
   motion = remotion.render("<slug>", props, public, ctx.work / "motion.mp4", log=ctx.log)
   ```
   `place()` hard-links (or copies) a file into the public folder: Remotion copies that folder into its bundle and
   skips symlinks. `render()` holds the heavy lock, copies the current `src/` over the installed copy, and renders
   H.264 at crf 10 as an intermediate; the style then adds grain and the bt709 encode and mixes the sound.
4. Fonts: call `useFonts([[family, file, descriptors], ...])` once at the top of the composition.

## Install (owned by setup/install.sh)
`studio install remotion` copies this folder (without node_modules) to
`$STUDIO_HOME/remotion/<first 12 hex of sha256(package-lock.json)>/`, runs `npm ci` and `remotion browser ensure`.
`studio_engine.remotion.available()` checks that copy and `$STUDIO_HOME/bin/node`.

## Who owns what
- `kit.tsx`, `Root.tsx`, `index.ts`, config and package files: shared. Add, do not change what others use.
- `src/screen-and-face/`, `src/words-in-the-room/`: the editing styles.
- `src/your-feed/`: the animated styles.
