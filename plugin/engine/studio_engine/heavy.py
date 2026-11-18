"""Heavy work one job at a time (matting, garden and frame renders, Remotion renders).

Ported from reel-edit-lab's heavy_job.py: one shared lock file, taken with flock so it is released when the process
ends (even if it crashes); a holder file says who has it; before starting, wait until enough memory is free, so two
big jobs never fill the swap and stall each other.

    from studio_engine import heavy
    with heavy.lock("matte"):
        ...                       # the heavy step

STUDIO_HEAVY_LOCK overrides the lock path (builders on one Mac share one file).
"""
import contextlib
import fcntl
import os
import re
import subprocess
import time
from datetime import datetime

from . import paths
from .util import say

MIN_FREE = 20          # percent of memory free (macOS memory_pressure) needed to start
MEMORY_WAIT_MAX = 600  # seconds; after this, start anyway and say so


def memory_free_percent():
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=20).stdout
        m = re.search(r"free percentage:\s*(\d+)%", out)
        return int(m.group(1)) if m else 100
    except Exception:
        return 100


def holder():
    f = paths.heavy_lock_file().with_suffix(".holder")
    try:
        return f.read_text().strip()
    except OSError:
        return ""


@contextlib.contextmanager
def lock(name, wait_for_memory=True, poll=5.0):
    """Hold the heavy lock while the block runs. Prints a plain line while it waits."""
    path = paths.heavy_lock_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    h = open(path, "a+")
    t0, said = time.time(), False
    while True:
        try:
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if not said:
                who = holder()
                say("Waiting for another heavy job to finish first" + (f" ({who})." if who else "."))
                said = True
            time.sleep(poll)
    hold = path.with_suffix(".holder")
    try:
        hold.write_text(f"{name}, pid {os.getpid()}, since {datetime.now():%H:%M:%S}\n")
        if wait_for_memory:
            t1, said = time.time(), False
            while memory_free_percent() < MIN_FREE and time.time() - t1 < MEMORY_WAIT_MAX:
                if not said:
                    say("Waiting for some memory to free up before the heavy step.")
                    said = True
                time.sleep(15)
        yield {"waited": round(time.time() - t0, 1)}
    finally:
        try:
            hold.write_text("")
        except OSError:
            pass
        fcntl.flock(h, fcntl.LOCK_UN)
        h.close()
