#!/usr/bin/env python
"""lane_probe.py — runs ON the Colab VM (sent by `colab exec -f`).

Prints exactly one machine-readable line:

    __LANE_JSON__ {"state": ..., "remain": [...], "alive": bool,
                   "heartbeat_age": int, "log_tail": str}

`state` is the runner's as_state.json verbatim, which is what
webapp/fish_lane.py::_state_done reads (progress[slug] + completed[]).
"""
import json
import os
import time
from pathlib import Path

BASE = Path(os.environ.get("FISH_BASE", "/content"))
STATE = BASE / "as_state.json"
LOG = BASE / "render.log"
PIDF = BASE / "runner.pid"
# Only used when the bundle carries no manifest and no scope file — the same
# defaults scripts/fish_colab_runner.py falls back to.
DEFAULT_ORDER = ["preface", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7",
                 "ch8", "conclusion"]


def _tail(path, n=4000):
    try:
        blob = path.read_bytes()
    except Exception:
        return ""
    return blob[-n:].decode("utf-8", "replace")


def _expected():
    scope = BASE / "as_chapters.txt"
    if scope.exists():
        return [s for s in scope.read_text().split(",") if s and s.strip()]
    mf = BASE / "manifest.json"
    if mf.exists():
        try:
            ch = json.loads(mf.read_text(encoding="utf-8")).get("chapters") or []
            if ch:
                return [c["slug"] for c in ch]
        except Exception:
            pass
    return DEFAULT_ORDER


def _alive():
    """PID-file liveness. The runner re-execs itself into the fishenv venv
    (os.execv), which PRESERVES the pid, so one pidfile stays valid across the
    bootstrap. A process-name probe would self-match its own pgrep cmdline."""
    pid = None
    try:
        pid = int(PIDF.read_text().strip())
    except Exception:
        pid = None
    if pid:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except Exception:
            return False
    # No pidfile (e.g. launched by hand): fall back to log freshness.
    try:
        return (time.time() - LOG.stat().st_mtime) < 900
    except Exception:
        return False


state = {}
try:
    state = json.loads(STATE.read_text(encoding="utf-8"))
except Exception:
    state = {}

completed = list(state.get("completed") or [])
remain = [s for s in _expected() if s not in completed]

now = time.time()
ages = []
for p in (STATE, LOG):
    try:
        ages.append(now - p.stat().st_mtime)
    except Exception:
        pass
heartbeat = int(min(ages)) if ages else 10 ** 9

print("__LANE_JSON__ " + json.dumps({
    "state": state,
    "completed": completed,
    "remain": remain,
    "alive": _alive(),
    "heartbeat_age": heartbeat,
    "log_tail": _tail(LOG),
}, ensure_ascii=False))
