#!/usr/bin/env python
"""khpi5 watchdog for the headless Colab render (self-healing control plane).

v2: multi-session (two-lane split of The Armed Struggle).

Runs forever on khpi5 (tool venv python). Every LOOP seconds, for EACH lane:

  1. Re-adopt the assignment if the local sessions.json entry for the lane was
     pruned, or its keep-alive daemon died -> respawns keep-alive so Colab
     does not reclaim the billing VM.
  2. Refresh the stored runtime-proxy token when it is within 15 min of
     expiry (an expired token makes `colab exec` 404, which is exactly what
     pruned the registry on 2026-09-24 and blinded the harvest loop).
  3. Probe the VM's runner process + remaining scope; if the runner has
     exited (10h budget or crash) and the lane's scope is NOT finished,
     relaunch it (state-resumable).

Probe semantics (v2 /tmp/runner_probe.py): `ALIVE|DEAD <remain>` where
remain = chapters of this lane's /content/as_chapters.txt scope not yet in
as_state.json. remain==0 means the lane's scope is complete.

Failure mode handling: if the assignment itself is gone (VM reclaimed), just
log it - re-provisioning stays a MANUAL step so a transient empty assignment
list can never spawn a second billing VM.

Incident this exists for: 2026-09-24 17:31 BST, kernel 404 -> exec pruned
'sessions.json' -> prune killed keep-alive -> harvest loop blind while the
assignment kept billing.
"""
import base64
import json
import os
import subprocess
import sys
import time

sys.path.insert(
    0, "/home/dave/.local/share/uv/tools/google-colab-cli/lib/python3.13/site-packages"
)

from colab_cli.commands.session import spawn_keep_alive
from colab_cli.common import state
from colab_cli.state import SessionState

SESSIONS = [
    ("render", "gpu-l4-s-kkb-ass1a1-rxwdks0v6xni"),
    ("render2", "gpu-l4-s-kkb-ass1b0-1hw8fhv01sh9f"),
]
LOOP = 300
TOKEN_MARGIN = 900  # refresh stored token if it expires within 15 min
LOG = "/tmp/watchdog.log"


def log(msg):
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))


def colab(*args, timeout=240):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin") + ":" + env.get("PATH", "")
    try:
        return subprocess.run(
            ["colab"] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except Exception as e:
        log("colab %s failed: %s" % (" ".join(args), e))
        return None


def assignments():
    try:
        return state.client.list_assignments()
    except Exception as e:
        log("list_assignments error: %s" % e)
        return None  # distinct from []: unknown vs definitely-gone


def token_fresh(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload))["exp"]
        return exp - time.time() > TOKEN_MARGIN
    except Exception:
        return False


def keep_alive_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ensure_registry(asg, name, ep):
    """Returns True if the local registry entry for `name` is usable."""
    s = state.store.get(name)
    if s and s.endpoint == ep and keep_alive_alive(s.keep_alive_pid):
        if not token_fresh(s.token):
            rpi = asg.runtime_proxy_info
            s.token = rpi.token
            s.url = rpi.url
            state.store.add(s)
            log("[%s] refreshed runtime-proxy token" % name)
        return True

    rpi = asg.runtime_proxy_info
    s = SessionState(
        name=name,
        token=rpi.token,
        url=rpi.url,
        endpoint=ep,
        variant="GPU",
        accelerator="L4",
        machine_shape="STANDARD",
    )
    state.store.add(s)
    pid = spawn_keep_alive(ep, name)
    s.keep_alive_pid = pid
    state.store.add(s)
    log("[%s] RE-ADOPTED registry (keep_alive_pid=%s)" % (name, pid))
    return True


def probe_runner(name):
    """Returns (alive, remain, raw) or (None, None, raw) if inconclusive."""
    r = colab("exec", "-s", name, "-f", "/tmp/runner_probe.py", timeout=180)
    if r is None:
        return None, None, ""
    raw = ""
    for ln in reversed((r.stdout or "").splitlines()):
        ln = ln.strip()
        if ln and not ln.startswith("["):
            raw = ln
            break
    parts = raw.split()
    if len(parts) == 2 and parts[0] in ("ALIVE", "DEAD"):
        try:
            return parts[0] == "ALIVE", int(parts[1]), raw
        except ValueError:
            pass
    return None, None, raw


def relaunch_runner(name):
    mark = "/tmp/.watchdog_relaunch_" + name
    if os.path.exists(mark) and time.time() - os.path.getmtime(mark) < 900:
        return  # already relaunched within the last 15 min
    open(mark, "w").write(str(time.time()))
    r = colab("exec", "-s", name, "-f", "/tmp/launch.py", timeout=300)
    out = ((r.stdout or "") + (r.stderr or "")).strip()[-300:] if r else "no-result"
    log("[%s] RELAUNCHED runner: %s" % (name, out))


def cycle(asgs):
    for name, ep in SESSIONS:
        a = next((x for x in asgs if getattr(x, "endpoint", None) == ep), None)
        if a is None:
            log("[%s] assignment gone (VM reclaimed) - manual re-provision required" % name)
            continue
        ensure_registry(a, name, ep)
        alive, remain, raw = probe_runner(name)
        if alive is None:
            log("[%s] runner probe inconclusive: %r" % (name, raw))
            continue
        if not alive and remain and remain > 0:
            relaunch_runner(name)
        elif not alive:
            log("[%s] lane scope complete (remain=0) - idle" % name)


def main():
    log("watchdog v2 started (pid %d, lanes=%s, loop=%ds)"
        % (os.getpid(), ",".join(n for n, _ in SESSIONS), LOOP))
    while True:
        try:
            asgs = assignments()
            if asgs is not None:
                cycle(asgs)
        except Exception as e:
            log("cycle error: %r" % e)
        time.sleep(LOOP)


if __name__ == "__main__":
    main()
