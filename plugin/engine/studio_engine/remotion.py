"""Run a composition of the one Remotion project (engine/remotion/) for a style renderer.

    from studio_engine import remotion
    remotion.render("screen-and-face", props, public_dir, ctx.work / "motion.mp4", log=ctx.log)

`studio install remotion` copies engine/remotion/ to STUDIO_HOME/remotion/<first 12 of the lockfile's sha256>/ and
runs `npm ci` and `remotion browser ensure` there. Each render copies the current src/ and config over that copy (so a
plugin update that keeps the lockfile still renders its newest code), then runs the Remotion command with:
  - the props as a JSON file (every time already in frames),
  - `--public-dir` pointing at the render's own folder, which holds the media, fonts and brushes the composition
    reads through staticFile(). Remotion copies that folder and skips symlinks: put files there with `place()`.
  - PNG frames, bt709, H.264 at a high quality (crf 10): an intermediate that the style then finishes.
Heavy: the whole run holds heavy.lock("remotion <composition>").
"""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import heavy, paths
from .errors import StudioError
from .util import say

NOT_INSTALLED = ("This style needs the motion graphics part of the studio, which is not installed yet. "
                 "Type /studio-setup, or run: studio install remotion")


def lock_hash():
    f = paths.remotion_src() / "package-lock.json"
    if not f.exists():
        raise StudioError("This version of Bernard Studio is missing its motion graphics files. Update the plugin.")
    return hashlib.sha256(f.read_bytes()).hexdigest()[:12]


def project_dir():
    return paths.remotion_home() / lock_hash()


def node_bin():
    return paths.home() / "bin"


def available():
    try:
        d = project_dir()
    except StudioError:
        return False
    return (d / "node_modules" / ".bin" / "remotion").exists() and (node_bin() / "node").exists()


def _sync(d):
    src = paths.remotion_src()
    shutil.copytree(src / "src", d / "src", dirs_exist_ok=True)
    for name in ("remotion.config.ts", "tsconfig.json"):
        if (src / name).exists():
            shutil.copy2(src / name, d / name)


def place(src, dst):
    """Put a file into a render's public folder: a hard link when it can (no copy), else a copy."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return dst


def concurrency():
    n = os.cpu_count() or 4
    return max(1, min(4, n // 3))


def render(composition, props, public_dir, out, log=None, crf=10, timeout=3600):
    """Render `composition` with `props` to `out` (H.264 intermediate). Returns `out`."""
    if not available():
        raise StudioError(NOT_INSTALLED)
    d = project_dir()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    props_f = out.with_suffix(".props.json")
    props_f.write_text(json.dumps(props))
    env = dict(os.environ, PATH=f"{node_bin()}:{os.environ.get('PATH', '/usr/bin:/bin')}")
    env.pop("NODE_OPTIONS", None)
    cmd = [str(d / "node_modules" / ".bin" / "remotion"), "render", "src/index.ts", composition, str(out),
           f"--props={props_f}", f"--public-dir={public_dir}", "--codec=h264", f"--crf={crf}",
           f"--concurrency={concurrency()}", "--timeout=180000", "--log=error"]
    with heavy.lock(f"remotion {composition}"):
        _sync(d)
        say("Drawing the motion graphics (this is the slow part).")
        fh = open(log, "a") if log else subprocess.DEVNULL
        try:
            r = subprocess.run(cmd, cwd=d, env=env, stdout=fh, stderr=fh, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise StudioError("The motion graphics took too long and were stopped. Try again; if it happens again, "
                              "the details are in the project's logs folder.")
        finally:
            if log:
                fh.close()
    if r.returncode != 0 or not out.exists():
        raise StudioError("The motion graphics could not be drawn. The details are in the project's logs folder.")
    return out
