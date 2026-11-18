# The studio engine (for style builders)

`bin/studio` runs `python -m studio_engine` from the studio's own Python (`$STUDIO_HOME/venv`). A style is a folder
`studio_engine/styles/<slug>/` with `render.py`, `schema.json` and `SPEC.md`. The engine validates the spec, calls your
`render(ctx)`, records the version and runs QA. Only styles listed in `styles.json` render. A complete, small renderer
is the build repo's test fixture `tests/engine/styles/plain-captions/` (dev only, not shipped).

## A style renderer

```python
# styles/<slug>/render.py
from studio_engine import brand, heavy
from studio_engine.layout import text_box
from studio_engine.render import Encoder, Reader, mux

KIND = "reel"                       # reel, carousel or animated (sets the format from brand defaults)
LABELS = ["THEN", "NOW"]            # fixed on-screen words besides his; QA allows only these and his words

def render(ctx):
    t = ctx.at(ctx.spec["beats"][0]["at"])          # word anchor -> seconds on the passage clock
    b = ctx.layout.beat("figure", t, t + 2.0)       # one entry per beat, QA reads it
    f = brand.font("display", 160)                  # kit font at a pixel size
    ctx.layout.text(b, "$40,000", text_box(f, "$40,000", 540, 900, "ms"), role="words", color="#F5F5F5")
    rd = Reader(ctx.picture(), (ctx.w, ctx.h), ctx.fps)       # passage picture, filled to the format
    enc = Encoder(ctx.work / "picture.mp4", ctx.w, ctx.h, ctx.fps)
    for i in range(int(ctx.duration * ctx.fps + 0.999)):
        enc.write(rd.get(i))                        # your drawing goes here (uint8 RGB frames)
    enc.close()
    ctx.sound()                                     # the spec's "sound" block -> ctx.out/mix.wav, mastered
    mux(ctx.work / "picture.mp4", ctx.out / "mix.wav", ctx.out / "final.mp4")
    ctx.layout.save(ctx.out / "layout.json")
    return {"output": "final.mp4"}                  # a file, or a folder of slide PNGs for carousels
```

Optional in the module: `validate(spec, words, duration)` (raise `StudioError` with a plain sentence) and
`qa_extra(project, version_dir, layout) -> {"name": {"pass": bool, ...}}`.

## What `ctx` gives you (`render.RenderContext`)
| Field | What |
|---|---|
| `ctx.spec`, `ctx.passage`, `ctx.words`, `ctx.duration` | the spec; passage.json; its words `[{i, w, t0, t1}]`; seconds |
| `ctx.w, ctx.h, ctx.fps, ctx.kind` | format from `brand/defaults.json` `formats[KIND]`, overridden by the spec's `format` |
| `ctx.at(x, field)` | `layout.resolve_at` bound to this passage; errors name the field |
| `ctx.picture()`, `ctx.voice()`, `ctx.source(name)` | passage picture; clean voice (else raw); a spec `sources` entry or a project source |
| `ctx.out`, `ctx.work` | `v<N>/` (deliverables) and `v<N>/work/` (scratch, removed after; return `"keep_work": True` to keep) |
| `ctx.layout` | the `Layout` writer (below) |
| `ctx.sound(out_name="mix.wav", extra_sfx=[...], duration=...)` | mixes the spec's `sound` block; word anchors resolved |
| `ctx.brand` | merged brand settings (his `.settings/brand.json` over defaults, the spec's `brand` over both) |
| `ctx.say(msg)` | a plain progress line for Bernard |

## Module APIs
- **`layout.resolve_at(at, words, duration=None, field="at")`**: `{"word": i}`, `{"word": i, "edge": "end"|"mid",
  "offset": -0.1}`, `{"t": 1.2}`, or `7` / `1.2` shorthand -> seconds.
- **`layout.Layout(kind, w, h, labels)`**: `beat(kind, t0, t1, i=None, slide=None)`, `text(beat, text, box, role=
  "words"|"label", color="#hex", red=None)` (red defaults to the colour being `#B91C1C` or `#C42727`), `mark(beat,
  what, box, red=True)` for red brushes, underlines and boxes; `save(path)`. `text_box(font, text, x, y, anchor,
  tracking)` gives the box PIL draws. Red text and marks that touch count as one red.
- **`sound.mix(voice, duration, out, bed=None, sfx=(), music_under=18, sfx_under=27, duck_db=4)`** -> levels
  `{voice_lufs, bed_under_voice_db, sfx_loudest_under_voice_db, lufs, true_peak}`. `bed`: a name, `{"name",
  "under_db", "changes": [s], ...}` or a stereo array. `sfx`: `[{"name" | "array", "t", "under_db", "len",
  "gain_db"}]`. Beds: `pad-minor` (receipts), `documentary` (+ `mallets`), `cutout`, `type` (+ `pulse_until`,
  `swell_at`), `zen` (+ `rise`), `drone` (+ `root`), `none`. Effects: `sound.names()`; recordings in
  `library/sound/` (impact, impact-wet, impact-air, brush, brush-swirl, whoosh, card, cards, paper, riser, shimmer,
  paint-dabs, paint-flow, cloth) and code-made (sub-hit, low-hit, thud, mallet, bowl, air-whoosh, air-riser,
  noise-swell, sand, tick, pop, key, clock-tick, projector, marker; replacements for the Mixkit files). Building
  blocks: `chord_bed`, `pad_voice`, `drone_bed`, `reverb`, `lp/hp/bp`, `place`, `master(src, dst)`, `measure(path)`.
- **`fixword.fix_word(project, heard, said, source, at, every)`** (`studio fix-word`): puts his real word back where
  whisper misheard it, in the transcript and the passage, times kept; fixed words carry `fix`, `fix_part` and `heard`,
  and the words-heard-back check accepts the original hearing for them. Recorded in project.json `fixes`.
- **`brand`**: `load()`, `get("captions.size")`, `set_value(key, value)`, `color("red")` -> RGB, `hex(name)`,
  `rgb_of(hex)`, `font(kind, size)` (kinds: display, display_soft, title, title_light, caption, label, body,
  archive, hand, ui), `font_path(kind)`, `brush("red-a")`, `safe()`, `style_settings(slug)` (his saved preferences,
  set with `studio brand set style.<slug>.<key> <value>`).
- **`paths`**: every folder (`root()`, `home()`, `user()`, `style_dir(slug)`, `fonts_dir()`, `sound_library()`,
  `poses_dir()`, `objects_dir()`, `user_poses()`, `remotion_home()`, `birefnet_dir()` ...). Never build a path to a
  fixed place.
- **`heavy.lock(name)`**: a context manager; wrap every heavy step (matting, frame renders, Remotion).
  `STUDIO_HEAVY_LOCK=$HOME/.cache/bernard-studio-heavy.lock` on the build Mac.
- **`media.safe_input(path)`**: the input arguments for every ffmpeg or ffprobe call (`-protocol_whitelist
  file,pipe -i <path>`). A unit test fails if any engine file opens an input without it.
- **`matte`**: `alpha(pil_image)`, `rgba(frame, alpha)`, `finish_cutout(bgr, alpha, cut_y, grade)`,
  `matte_clip(project, ...)` (keeps `frames/f*.jpg` and `alpha/a*.png`; full-colour `rgba/p*.png` only for a
  `--frames` check run or `--cutouts`), `cutout(run, i)` (frame i as RGBA, made from the two), `matte_photo(file, ...)`;
  `available()` says whether the add-on is installed.
- **`render`**: `Reader(path, (w, h), fps, vf=None)`, `Encoder(path, w, h, fps, crf=16)` (H.264 High, yuv420p, bt709
  tags), `mux(video, audio, out)` (AAC 48 kHz stereo), `poster(video, t, out)`, `draw_frames(enc, frame, n, say)`
  (draws `frame(i)` on worker threads and writes them in order).
- **`film`**: the kit's film look on float RGB frames, shared by receipts, documentary and cutout: `grade_film`,
  `halation`, `vignette`, `grain`, `over`, and the text and brush helpers (`fit`, `draw_text`, `brush_draw`).
- **Words heard back** (`qa.check_words`): `sound.mix` also writes `mix-voice.wav`, his voice as it sits in the final
  (same gain and limiter, no bed or effects). A word lost in the final but heard there is excused under `masked`
  (music under a short word), never at a cut edge and never more than one word in ten.
- **`qa`** runs after every render: words heard back, loudness, safe zones, one red, his words only, streams, frame
  sheet at every beat. Carousels: return a folder of `*.png` slides (and an `*.mp4` cover if the style has one).

## Carousels from typed lines
`studio lines "<project>" --add "<text>"` keeps what he typed word for word (project.json `lines`, and
`his-lines.txt`). A carousel spec with no `"passage"` renders without one: `ctx.words` are his typed lines plus every
ingested transcript (no times), and `ctx.voice()` / `ctx.picture()` raise a plain error. For every carousel the
his-words check accepts his typed lines and every transcript in the project, not only the passage. `studio finish`
writes the caption draft from the passage, or, with no passage, from his typed lines word for word.

## Commands for the wizard (`browse`)
- **`studio transcript "<project>" [--source <name>] [--find "<words>"]`**: his words as timed lines
  (`browse.sentences`: a line ends at `.`, `?`, `!` or a pause of 0.8 s); `--find` gives every place a phrase is said,
  ignoring case and punctuation (`browse.find`).
- **`studio open drop|photos|projects|finished|folder|gallery`**, **`studio open project "<p>"`**,
  **`studio open version "<p>" [N]`**, **`studio open file "<path>"`**: shows his folders, a project, a version or one
  of his files. Two checks, one set of rules: the hook judges `studio open file` before it runs, and
  `browse.safe_to_open` judges every open again; both read `hooks/open-rules.json`. They refuse anything outside his
  folder and the examples, any bundle or package, and any file that is not a picture, video, PDF or text (`.html`
  only for the examples page). `tests/test_open_rules.py` runs one table of cases through both.
- **`studio needs --all`** (setup/doctor.sh): every style with the parts it still needs and their size;
  `studio doctor --json` has each part's `disk_gb` and `setup` (what the one-time setup still has to install).
- The plugin's PreToolUse hook (`hooks/auto-allow.js`) lets one plain `studio` call run without a permission question;
  `studio install` and links always ask him.

## Example spec (the `plain-captions` test fixture)
```json
{"style": "plain-captions", "spec_version": 1, "passage": "passage/passage.json",
 "beats": [{"kind": "caption", "at": {"word": 3}, "to": {"word": 6}, "red": 6}],
 "sound": {"bed": {"name": "pad-minor", "changes": [{"word": 7}]},
           "sfx": [{"name": "impact", "at": {"word": 20}, "under_db": 26}]}}
```

## Dev runs on the build Mac
`source .dev/env.sh` (sets `STUDIO_HOME`, `STUDIO_USER` under the worktree's `.dev/`, the shared heavy lock and
PATH), then `studio new ...`. Tests: `.dev/home/venv/bin/python -m pytest tests/engine` (add `STUDIO_E2E=1
STUDIO_FIXTURES=<the Bernard folder>` for the end-to-end run on new footage).
