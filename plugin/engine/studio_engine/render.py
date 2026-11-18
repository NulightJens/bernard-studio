"""studio render <project> --spec <spec.json> [--version N] [--notes 0,2] [--no-qa]

Validates the spec, finds the style's renderer (styles/<slug>/render.py), gives it a RenderContext, records the
version in project.json and runs QA. A style renderer is a module with:

    LABELS = ["THEN", "NOW"]        # fixed on-screen labels this style may show besides his words
    KIND = "reel"                   # reel, carousel or animated
    def render(ctx) -> dict         # returns {"output": "<file or folder inside ctx.out>"}

Shared helpers for renderers: Encoder (frames -> H.264 High, yuv420p, bt709), Reader (frames of a clip, streamed),
mux (picture + finished sound -> the deliverable), poster.
"""
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from . import brand as brand_mod
from . import passage as passage_mod
from . import paths
from .errors import StudioError
from .layout import Layout, resolve_at
from .project import now, write_json
from .util import fps_str, probe, say
from .media import safe_input


# ----------------------------------------------------------------------------------------------- styles
STYLE_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def style_module(slug):
    """The renderer of one of the styles listed in styles.json. Anything else (a name not listed, a folder starting
    with _ or ., a path) is refused with a plain message."""
    if not isinstance(slug, str) or not slug:
        raise StudioError("The spec needs a style name.")
    f = paths.style_dir(slug) / "render.py"
    if not STYLE_SLUG.fullmatch(slug) or slug not in paths.known_styles() or not f.exists():
        raise StudioError(f'There is no style called "{slug}" in this version of the studio. Type studio styles to '
                          "see them.")
    name = f"studio_engine.styles.{slug.replace('-', '_')}.render"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, f, submodule_search_locations=None)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    if not hasattr(mod, "render"):
        raise StudioError(f'The style "{slug}" is incomplete (it has no renderer).')
    return mod


def style_labels(slug):
    try:
        return list(getattr(style_module(slug), "LABELS", []))
    except StudioError:
        return []


def _path_str(p):
    out = ""
    for part in p:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "the spec"


def validate(spec, words, duration):
    """Common checks, then the style's own schema.json. Errors name the bad field in plain words."""
    if not isinstance(spec, dict):
        raise StudioError("The spec must be a JSON object.")
    if spec.get("spec_version", 1) != 1:
        raise StudioError("This spec was written for a different version of the studio (spec_version must be 1).")
    slug = spec.get("style")
    mod = style_module(slug)
    schema_f = paths.style_dir(slug) / "schema.json"
    if schema_f.exists():
        import jsonschema
        schema = json.loads(schema_f.read_text())
        errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(spec), key=lambda e: list(e.path))
        if errs:
            e = errs[0]
            raise StudioError(f"The spec's {_path_str(list(e.path))} is not right: {e.message}.")
    for k, b in enumerate(spec.get("beats", []) or []):
        if not isinstance(b, dict):
            raise StudioError(f"The spec's beats[{k}] must be an object.")
        for fld in ("at", "to", "until"):
            if fld in b:
                resolve_at(b[fld], words, duration, field=f"beats[{k}].{fld}")
    for k, e in enumerate((spec.get("sound") or {}).get("sfx", []) or []):
        if "at" in e:
            resolve_at(e["at"], words, duration, field=f"sound.sfx[{k}].at")
    if hasattr(mod, "validate"):
        mod.validate(spec, words, duration)
    return mod


def load_passage(project, spec):
    """The passage a spec renders from. A carousel whose spec names no passage renders from his typed lines and the
    project's transcripts instead (studio lines), with no voice and no picture."""
    if isinstance(spec, dict) and not spec.get("passage"):
        try:
            mod = style_module(spec.get("style"))
        except StudioError:
            mod = None
        if mod is not None and getattr(mod, "KIND", None) == "carousel":
            from . import lines
            return lines.words_passage(project)
    return passage_mod.load(project)


# ----------------------------------------------------------------------------------------------- context
class RenderContext:
    """What a style renderer gets. Everything it reads or writes goes through here."""

    def __init__(self, project, spec, n, mod, out=None):
        self.project = project
        self.spec = spec
        self.n = n
        self.out = Path(out) if out else project.version_dir(n)   # render() gives a staging folder
        self.passage = load_passage(project, spec)
        self.words = self.passage["words"]
        self.duration = float(self.passage["duration"])
        self.brand = brand_mod.load()
        if spec.get("brand"):
            from .brand import _merge
            self.brand = _merge(self.brand, spec["brand"])
        kind = getattr(mod, "KIND", project.kind)
        f = dict(self.brand["formats"].get(kind, {}))
        f.update(spec.get("format") or {})
        self.kind = kind
        self.w, self.h = int(f.get("w", 1080)), int(f.get("h", 1920))
        self.fps = float(f.get("fps", 24))
        self.labels = list(getattr(mod, "LABELS", []))
        self.layout = Layout(kind, self.w, self.h, self.labels, f.get("fps"))
        self.style_dir = paths.style_dir(spec["style"])
        self.work = self.out / "work"
        self.log = project.log_file(f"render-v{n}.log")

    def at(self, x, field="at"):
        return resolve_at(x, self.words, self.duration, field)

    def voice(self):
        """The passage voice to mix: the cleaned one when `studio voice` has run."""
        rel = self.passage.get("voice_clean") or self.passage.get("voice")
        if not rel:
            raise StudioError("This piece has no recording picked, so there is no voice to use. Pick his words from "
                              "a video or a voice memo with studio passage first.")
        return self.project.resolve(rel)

    def picture(self):
        if not self.passage.get("picture"):
            raise StudioError("This piece has no video picked, so there is no picture to use (it came from typed lines "
                              "or a sound file).")
        return self.project.resolve(self.passage["picture"])

    def source(self, name):
        """A named source from the spec's "sources" map, else one of the project's sources."""
        rel = (self.spec.get("sources") or {}).get(name)
        if rel:
            p = self.project.resolve(rel)
            if not p.exists():
                raise StudioError(f'The spec\'s source "{name}" points to a file that is not there.')
            return p
        return self.project.resolve(self.project.source(name)["file"])

    def say(self, msg):
        say(msg)

    def sound(self, out_name="mix.wav", **kw):
        """Mix the spec's sound block: {"bed": name or {...}, "sfx": [{"name", "at"|"t", "under_db"}]}.
        Word anchors in "at" and in bed "changes" are resolved here."""
        from . import sound as sound_mod
        s = dict(self.spec.get("sound") or {})
        bed = s.get("bed")
        if isinstance(bed, dict):
            bed = dict(bed)
            if "changes" in bed:
                bed["changes"] = [self.at(c, "sound.bed.changes") for c in bed["changes"]]
            for key in ("rise", "pulse_until", "swell_at"):
                if key in bed:
                    bed[key] = self.at(bed[key], f"sound.bed.{key}")
            if "mallets" in bed:
                bed["mallets"] = [dict(m, t=self.at(m.get("at", m.get("t")), "sound.bed.mallets")) for m in bed["mallets"]]
        sfx = []
        for k, e in enumerate(s.get("sfx") or []):
            e = dict(e)
            e["t"] = self.at(e.get("at", e.get("t")), f"sound.sfx[{k}].at")
            sfx.append(e)
        sfx += kw.pop("extra_sfx", [])
        return sound_mod.mix(self.voice(), kw.pop("duration", self.duration), self.out / out_name, bed=bed, sfx=sfx,
                             work=self.work, **kw)


# ----------------------------------------------------------------------------------------------- frames in and out
IN709 = "scale=in_color_matrix=bt709:in_range=tv:out_range=pc"


class Reader:
    """Frames of a clip through an ffmpeg filter, streamed forward; asking for an earlier frame restarts the stream.
    get(i) returns frame i (at `fps`) as an (h, w, 3) uint8 array; past the end it holds the last frame."""

    def __init__(self, path, size, fps, vf=None):
        self.path, self.size, self.fps = str(path), size, fps
        w, h = size
        self.vf = vf or f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        self.p, self.cur, self.frame = None, -1, None

    def _open(self, idx):
        if self.p:
            self.p.kill()
        t = idx / self.fps
        self.p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.4f}", *safe_input(self.path), "-vf",
                                   f"fps={fps_str(self.fps)},{self.vf},format=rgb24", "-f", "rawvideo", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.cur = idx - 1

    def get(self, idx):
        idx = max(0, int(idx))
        if idx == self.cur and self.frame is not None:
            return self.frame
        if self.p is None or idx < self.cur or idx > self.cur + 48:
            self._open(idx)
        w, h = self.size
        n = w * h * 3
        while self.cur < idx:
            buf = self.p.stdout.read(n)
            if len(buf) < n:
                break
            self.frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            self.cur += 1
        if self.frame is None:
            raise StudioError("I could not read the picture of this clip.")
        return self.frame

    def close(self):
        if self.p:
            self.p.kill()


class Encoder:
    """RGB frames in, H.264 High yuv420p with bt709 tags out (the stream every deliverable uses)."""

    def __init__(self, path, w, h, fps, crf=16, tune="film"):
        self.path = str(path)
        self.p = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
             "-r", fps_str(fps), "-i", "-", "-vf",
             "scale=in_range=pc:out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p,"
             "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-profile:v", "high", "-tune", tune,
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
             "-movflags", "+faststart", self.path], stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, rgb8):
        self.p.stdin.write(np.ascontiguousarray(rgb8, np.uint8).tobytes())
        self.frames += 1

    def close(self):
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise StudioError("The video could not be written.")


def draw_frames(enc, frame, n, say):
    """Draws frame(i) for every i < n on worker threads, a window ahead, and writes them to `enc` in order."""
    import os
    from concurrent.futures import ThreadPoolExecutor

    import cv2
    cv2.setNumThreads(1)
    workers = max(1, min(8, (os.cpu_count() or 4) - 1))
    window = workers * 2
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(frame, i) for i in range(min(n, window))]
        for i in range(n):
            fr = futs[i].result()
            futs[i] = None
            if i + window < n:
                futs.append(ex.submit(frame, i + window))
            enc.write(fr)
            if i % max(1, n // 10) == 0 and i:
                say(f"Drawing the frames: {int(100 * i / n)} percent")


def hold_last_frame(video, seconds, fps, out):
    """The picture with its last frame held until `seconds` (re-encoded the way Encoder writes every picture)."""
    v = probe(video)["duration"]
    frames = int(math.ceil(seconds * fps - 1e-6))
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(str(video)), "-vf",
                        f"tpad=stop_mode=clone:stop_duration={max(0.0, seconds - v) + 2.0 / fps:.4f},format=yuv420p,"
                        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
                        "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                        "-profile:v", "high", "-r", fps_str(fps), "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise StudioError("The picture could not be lengthened to cover the sound.")
    return out


def mux(video, audio, out):
    """Picture (already H.264) plus the finished sound -> the deliverable: AAC 48 kHz stereo, faststart.
    The picture always covers the whole sound: when it ends before the sound (a renderer a few frames short), its last
    frame is held to the end, so no word's tail is cut. The join ends at the sound's length (not -shortest, which cut
    the picture a frame or two before the sound's end): the last frame that starts inside the sound is kept."""
    vp, ap = probe(video), probe(audio)
    fps = (vp["video"] or {}).get("fps") or 24.0
    held = None
    if ap["duration"] > vp["duration"] + 0.25 / fps:
        held = Path(out).with_name(f".held-{Path(out).stem}.mp4")
        video = hold_last_frame(video, ap["duration"], fps, held)
    try:
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(str(video)), *safe_input(str(audio)),
                            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                            "-ac", "2", "-t", f"{ap['duration']:.4f}", "-movflags", "+faststart", str(out)],
                           capture_output=True, text=True)
    finally:
        if held is not None and held.exists():
            held.unlink()
    if r.returncode != 0:
        raise StudioError("The picture and sound could not be put together.")
    return out


def poster(video, t, out):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", *safe_input(str(video)), "-frames:v", "1",
                    "-vf", "scale=in_color_matrix=bt709:in_range=tv", str(out)], check=True)
    return out


# ----------------------------------------------------------------------------------------------- the command
def find_spec(project, given):
    """The spec file, which must be inside the project folder (real path checked). Accepts a full path, a path inside
    the project, or just the file name (Claude may pass "<project>/spec.json")."""
    from .project import within
    given = Path(str(given)).expanduser()
    tries = [given, project.dir / given, project.dir / given.name]
    inside = [t for t in tries if t.is_file() and within(t, project.dir)]
    if inside:
        return inside[0]
    if any(t.is_file() for t in tries):
        raise StudioError("The spec file must be inside the project folder. Write it there as spec.json.")
    raise StudioError(f'I could not find the spec file "{given.name}".')


def render(project, spec_path, n=None, notes=None, run_qa=True):
    spec_path = find_spec(project, spec_path)
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as e:
        raise StudioError(f"The spec file is not valid JSON (line {e.lineno}).")
    p = load_passage(project, spec)
    mod = validate(spec, p["words"], float(p["duration"]))
    n = int(n) if n else project.next_version()
    vdir = project.version_dir(n)
    # the version is made in a staging folder and takes v<N>'s place only when it is complete: a failed or stopped
    # render leaves the old v<N> and project.json exactly as they were
    stage = project.dir / f".v{n}-rendering"
    if stage.exists():              # left by a render that was stopped: kept in logs/ for reading, never deleted
        stage.rename(project.log_file(f"stopped-v{n}-{int(time.time())}"))
    stage.mkdir(parents=True)
    write_json(stage / "spec.json", spec)
    ctx = RenderContext(project, spec, n, mod, out=stage)
    ctx.work.mkdir(exist_ok=True)
    say(f"Rendering version {n} in the style {spec['style']}.")
    t0 = time.time()
    try:
        result = mod.render(ctx) or {}
        if not (stage / "layout.json").exists():
            ctx.layout.save(stage / "layout.json")
        out = result.get("output")
        if not out or not (stage / out).exists():
            raise StudioError("The render finished without making its file. The details are in the project's logs "
                              "folder.")
    except Exception as e:
        import traceback
        ctx.log.open("a").write(traceback.format_exc())
        # no half-made version left behind: move it into logs/ (kept for reading, never deleted)
        stage.rename(project.log_file(f"failed-v{n}-{int(time.time())}"))
        if isinstance(e, StudioError):
            raise
        raise StudioError("The render stopped with an error. The details are in the project's logs folder.") from e
    if result.get("keep_work") is not True:
        shutil.rmtree(ctx.work, ignore_errors=True)
    if vdir.exists():               # rendering over a version: keep the old one in logs/, never delete it
        vdir.rename(project.log_file(f"replaced-v{n}-{int(time.time())}"))
    stage.rename(vdir)
    applied = list(project.open_notes()) if notes is None else [int(x) for x in notes]
    for i in applied:
        if 0 <= i < len(project.data["notes"]):
            project.data["notes"][i]["applied_in"] = n
    entry = {"n": n, "spec": f"v{n}/spec.json", "output": f"v{n}/{out}", "layout": f"v{n}/layout.json",
             "style": spec["style"], "rendered": now(), "seconds": round(time.time() - t0, 1), "qa": None,
             "notes_applied": applied}
    project.data["style"] = spec["style"]
    project.data["status"] = "rendered"
    project.set_version(entry)
    say(f"Version {n} is rendered.")
    if run_qa:
        from . import qa
        qa.run(project, n)
        entry = project.version(n)
    return entry
