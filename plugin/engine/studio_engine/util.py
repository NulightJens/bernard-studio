"""Small shared helpers: plain progress lines, running tools, probing media."""
import shutil
import subprocess
import sys

from .errors import StudioError

_JSON_MODE = False


def set_json(flag):
    global _JSON_MODE
    _JSON_MODE = bool(flag)


def say(msg):
    """A short plain progress line for Bernard. With --json these go to stderr so stdout ends in one JSON object."""
    print(msg, file=sys.stderr if _JSON_MODE else sys.stdout, flush=True)


def need(tool, what):
    if not shutil.which(tool):
        raise StudioError(f"{what} is not installed yet. Type /studio-setup and I will add it.")
    return shutil.which(tool)


def run(cmd, log=None, **kw):
    """Run a tool; on failure raise a plain error and keep the details in the log file."""
    kw.setdefault("capture_output", True)
    r = subprocess.run([str(c) for c in cmd], **kw)
    if log is not None:
        with open(log, "a") as f:
            f.write("$ " + " ".join(str(c) for c in cmd) + "\n")
            for s in (r.stdout, r.stderr):
                if s:
                    f.write(s if isinstance(s, str) else s.decode("utf-8", "replace")[-20000:])
                    f.write("\n")
    if r.returncode != 0:
        tail = r.stderr if isinstance(r.stderr, str) else (r.stderr or b"").decode("utf-8", "replace")
        raise StudioError(f"A step failed ({cmd[0]}). The details are in the project's logs folder.",
                          ) from RuntimeError(tail[-2000:])
    return r


def probe(path):
    """Duration, size, frame rate and audio facts of a media file."""
    from .media import probe_json
    need("ffprobe", "ffmpeg")
    d = probe_json(path)
    if d is None:
        raise StudioError(f'I could not read "{path}". Is it a video or audio file?')
    out = {"duration": float(d.get("format", {}).get("duration") or 0), "video": None, "audio": None}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and out["video"] is None and s.get("disposition", {}).get("attached_pic") != 1:
            num, den = (s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1").split("/")
            fps = float(num) / float(den) if float(den) else 0.0
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = int(sd["rotation"])
            rot = int((s.get("tags") or {}).get("rotate", rot))
            w, h = int(s["width"]), int(s["height"])
            if abs(rot) % 180 == 90:
                w, h = h, w
            out["video"] = {"w": w, "h": h, "fps": round(fps, 4), "codec": s.get("codec_name"),
                            "pix_fmt": s.get("pix_fmt"), "profile": s.get("profile"),
                            "color_primaries": s.get("color_primaries"), "color_transfer": s.get("color_transfer"),
                            "color_space": s.get("color_space")}
        if s.get("codec_type") == "audio" and out["audio"] is None:
            out["audio"] = {"codec": s.get("codec_name"), "sample_rate": int(s.get("sample_rate") or 0),
                            "channels": int(s.get("channels") or 0)}
    return out


def nice_fps(fps):
    """Snap a measured frame rate to the standard one it means (23.976, 24, 25, 29.97, 30, 50, 59.94, 60)."""
    for std in (24000 / 1001, 24, 25, 30000 / 1001, 30, 50, 60000 / 1001, 60):
        if abs(fps - std) < 0.02:
            return std
    return fps


def fps_str(fps):
    """ffmpeg rate string, exact for the NTSC rates."""
    for num, std in ((24000, 24000 / 1001), (30000, 30000 / 1001), (60000, 60000 / 1001)):
        if abs(fps - std) < 1e-3:
            return f"{num}/1001"
    return f"{fps:g}"
