"""Safe media inputs. Every ffmpeg and ffprobe call in the engine (and in every style) opens files through here.

A crafted file (an HLS playlist or a concat list renamed .mp4, an image-sequence pattern) can make ffmpeg read other
files on his Mac or fetch addresses on the internet. So:
  - safe_input(path) gives the input arguments with `-protocol_whitelist file,pipe` in front of `-i`: ffmpeg may only
    read plain local files and pipes;
  - check_source(path) probes a file he brings in (or one yt-dlp downloaded) and refuses anything that is not a plain
    audio or video container.

    cmd = ["ffmpeg", "-v", "error", "-ss", "1.0", *media.safe_input(src), "-frames:v", "1", out]
"""
import json
import subprocess
from pathlib import Path

from .errors import StudioError

PROTOCOLS = "file,pipe"
# ffprobe format_name values of plain containers. Anything else (hls, concat, image2 patterns, tee, network streams,
# subtitle or playlist formats) is refused.
ALLOWED = {"mov", "mp4", "m4a", "3gp", "3g2", "mj2", "matroska", "webm", "avi", "wav", "w64", "flac", "mp3", "aac",
           "ogg", "aiff", "caf", "mpegts"}
REFUSE = "This file isn't a normal video, so I won't open it."


def safe_input(path):
    """The ffmpeg/ffprobe input arguments for one file: local files and pipes only."""
    p = str(path)
    if p != "-" and ("://" in p or p.startswith(("concat:", "subfile:", "data:", "pipe:"))):
        raise StudioError(REFUSE)
    return ["-protocol_whitelist", PROTOCOLS, "-i", p]


def probe_json(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", PROTOCOLS, "-show_streams", "-show_format",
                        "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def check_source(path):
    """Refuse anything that is not a plain audio or video file. Returns the probe data."""
    p = Path(path)
    if not p.is_file():
        raise StudioError(f'I could not find the file "{p.name}".')
    head = p.open("rb").read(1024)
    if head and b"\0" not in head:
        try:                         # plain text (a playlist or a list of files), never a real media file
            head.decode("utf-8")
            raise StudioError(REFUSE)
        except UnicodeDecodeError:
            pass
    d = probe_json(p)
    if not d:
        raise StudioError(f'I could not read "{p.name}". Is it a video or audio file?')
    names = set((d.get("format", {}).get("format_name") or "").split(","))
    if not names or not names <= ALLOWED:
        raise StudioError(REFUSE)
    return d

REFUSE_IMAGE = "This file isn't a normal photo, so I won't open it."
HEIF_BRANDS = (b"heic", b"heix", b"mif1", b"msf1", b"heim", b"heis")


def check_image(path):
    """Refuse anything that is not a real JPEG, PNG, WebP, HEIC or TIFF photo, judged by its first bytes, not its name."""
    p = Path(path)
    if not p.is_file():
        raise StudioError(f'I could not find the file "{p.name}".')
    head = p.open("rb").read(16)
    ok = (head[:3] == b"\xff\xd8\xff"                                   # JPEG
          or head[:8] == b"\x89PNG\r\n\x1a\n"                           # PNG
          or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")              # WebP
          or (head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS)       # HEIC
          or head[:4] in (b"II*\x00", b"MM\x00*"))                          # TIFF
    if not ok:
        raise StudioError(REFUSE_IMAGE)
    return p


def is_heic(path):
    """True for an iPhone HEIC photo, judged by its bytes (whatever its name)."""
    head = Path(path).open("rb").read(16)
    return head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS


def heic_to_jpeg(src, dst):
    """An iPhone HEIC photo -> a JPEG the studio can read (its Python image library has no HEIC reader). Uses macOS's
    own sips. The photo is checked by its bytes first; the JPEG is written only where the caller says (inside the
    project or the studio's own temporary folder) and checked again after."""
    src, dst = Path(src).resolve(), Path(dst)
    check_image(src)
    if dst.is_symlink():                    # never write through a link to somewhere else
        dst.unlink()
    if dst.resolve() == src:                # never over the photo itself (it may be his own file, linked in)
        raise StudioError(f'I could not read the photo "{src.name}". Try saving it as a JPEG and bring it in again.')
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", "-s", "formatOptions", "best", str(src), "--out",
                        str(dst)], capture_output=True, text=True)
    if r.returncode != 0 or not dst.is_file() or dst.open("rb").read(3) != b"\xff\xd8\xff":
        raise StudioError(f'I could not read the photo "{src.name}". Try saving it as a JPEG and bring it in again.')
    return dst


def check_any(path, kind):
    """The one gate for a file he brings in: photos by their bytes, audio and video by their container."""
    return check_image(path) if kind == "image" else check_source(path)
