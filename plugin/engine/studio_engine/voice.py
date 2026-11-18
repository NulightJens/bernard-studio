"""studio voice <project>: clean up his voice in the passage.

Default: an ffmpeg chain (rumble out, light broadband denoise, a little presence, gentle compression; the chain the
editing styles used). If his own Auphonic key is in the Mac's Keychain under BERNARD_STUDIO_AUPHONIC, the voice goes
to Auphonic instead (his account, his choice). Writes passage/voice-clean.wav and records it in passage.json; sound.mix
uses the clean voice when it is there.
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from . import passage as passage_mod
from .errors import StudioError
from .project import write_json
from .util import run, say
from .media import safe_input

CHAIN = ("highpass=f=75:poles=2,afftdn=nf=-48:nr=8,equalizer=f=3800:t=q:w=1.2:g=1.5,"
         "equalizer=f=220:t=q:w=1.0:g=-1.0,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=120:makeup=2")
KEYCHAIN_NAME = "BERNARD_STUDIO_AUPHONIC"
AUPHONIC = "https://auphonic.com/api"


def auphonic_key():
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_NAME, "-w"], capture_output=True,
                           text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def clean_ffmpeg(src, dst, log=None):
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(src), "-af", CHAIN, "-ar", "48000", "-ac", "1",
         "-c:a", "pcm_s24le", dst], log=log)


def _req(method, url, key, data=None, headers=None):
    h = {"Authorization": f"bearer {key}"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def clean_auphonic(src, dst, key, log=None, timeout=900):
    """Upload to Auphonic (simple API), wait, download the result, and convert it to the passage's format.
    Not verified end to end in the build (no key on the build Mac)."""
    import uuid
    boundary = uuid.uuid4().hex
    body = []
    for k, v in (("title", "Bernard Studio voice"), ("action", "start"), ("denoise", "true"), ("leveler", "true"),
                 ("loudnesstarget", "-16"), ("output_basename", "voice-clean")):
        body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="input_file"; filename="voice.wav"\r\n'
                f'Content-Type: audio/wav\r\n\r\n'.encode() + Path(src).read_bytes() + b"\r\n")
    body.append(f"--{boundary}--\r\n".encode())
    say("Sending his voice to Auphonic for cleaning.")
    resp = json.loads(_req("POST", f"{AUPHONIC}/simple/productions.json", key, b"".join(body),
                           {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    uid = resp["data"]["uuid"]
    t0 = time.time()
    while True:
        d = json.loads(_req("GET", f"{AUPHONIC}/production/{uid}.json", key))["data"]
        if d.get("status") == 3:
            break
        if d.get("status") in (2, 11, 13) or time.time() - t0 > timeout:
            raise StudioError("Auphonic could not clean the voice this time. I used the built-in clean-up instead.")
        time.sleep(5)
    files = d.get("output_files") or []
    if not files:
        raise StudioError("Auphonic finished but sent no file back.")
    got = Path(dst).with_suffix(".auphonic" + Path(files[0].get("filename", "x.wav")).suffix)
    got.write_bytes(_req("GET", files[0]["download_url"], key))
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", *safe_input(got), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", dst],
        log=log)


def clean(project, method="auto"):
    p = passage_mod.load(project)
    src = project.resolve(p["voice"])
    dst = project.path("passage", "voice-clean.wav")
    log = project.log_file("voice.log")
    used = "ffmpeg"
    key = auphonic_key() if method in ("auto", "auphonic") else None
    if method == "auphonic" and not key:
        raise StudioError("There is no Auphonic key in this Mac's Keychain yet. Add it with /studio-tune.")
    if key:
        try:
            clean_auphonic(src, dst, key, log)
            used = "auphonic"
        except Exception as e:
            log.open("a").write(f"auphonic failed: {e!r}\n")
            say("Auphonic did not work this time, so I used the built-in clean-up.")
    if used == "ffmpeg":
        say("Cleaning up his voice.")
        clean_ffmpeg(src, dst, log)
    p["voice_clean"] = "passage/voice-clean.wav"
    p["voice_method"] = used
    write_json(project.path("passage", "passage.json"), p)
    project.save()
    say("His voice is clean.")
    return {"voice_clean": p["voice_clean"], "method": used}
