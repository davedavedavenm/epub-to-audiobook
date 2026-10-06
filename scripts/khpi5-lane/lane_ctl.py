#!/usr/bin/env python3
"""lane_ctl.py — control plane for the webapp's Colab fish lane.

Contract, from webapp/fish_lane.py (render_colab) and webapp/lanes.py
(_status_colab):

    lane_ctl.sh status                  -> JSON {sessions, harvest, scopes,
                                                progress, guard}
    lane_ctl.sh submit  <job_tag>       -> push bundle + runner, launch
    lane_ctl.sh progress <job_tag>      -> JSON {state, dead_permanent,
                                                 log_tail, remain}
    lane_ctl.sh fetch   <job_tag> <mp3> -> /content/out/<mp3> -> jobs/<tag>/out/
    lane_ctl.sh log     <job_tag>       -> remote render.log tail
    lane_ctl.sh done    <job_tag>       -> stop the session (billing ends)
    lane_ctl.sh stop    <job_tag>       -> stop the session

Everything this script creates or stops is named ``lane-<job_tag>``. It never
touches a session it did not create, so a webapp job can neither inspect the
cost of nor reclaim the production book sessions (``render`` / ``render2``).

Concurrency guard: the Colab account's proven concurrent-GPU budget is
LANE_COLAB_MAX_SESSIONS (default 2, what the two-lane book render holds).
Submit refuses to create a session while that budget is in use rather than
risk reclaiming a running render — Colab reclaims VMs to stay inside limits.
A refused submit is a loud, actionable failure, never a silent kill.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import NoReturn

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs"
CACHE = HERE / "cache"
PROBE = HERE / "lane_probe.py"
LAUNCH = HERE / "lane_launch.py"

GPU = os.environ.get("LANE_COLAB_GPU", "L4")
MAX_SESSIONS = int(os.environ.get("LANE_COLAB_MAX_SESSIONS", "2"))
MAX_RELAUNCH = int(os.environ.get("LANE_COLAB_MAX_RELAUNCH", "2"))
STATUS_TTL = 45          # /api/lanes polls every 10 s; do not hammer the CLI
PROGRESS_TTL = 45        # fish_lane polls every 60 s
HEARTBEAT_S = 900        # a healthy runner rewrites state about every 7 min
SCOPE_PFX = "lane-"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MP3_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.mp3$")
# Chunk checkpoints written by the runner (see scripts/higgs_colab_runner.py): Colab removes
# these VMs after ~1 hour, so finished chunks are pulled off the VM on every progress poll and
# re-uploaded to the next VM. ckpt_<slug>_<lo>-<hi>.tgz
CKPT_RE = re.compile(r"^ckpt_([A-Za-z0-9]+)_\d{4}-\d{4}\.tgz$")


def pull_ckpts(tag: str, scope: str, payload: dict) -> int:
    """Download checkpoints the runner has published but we do not have yet. Best effort:
    a failed download is retried on the next poll."""
    names = (payload.get("state") or {}).get("ckpts") or []
    out = JOBS / tag / "out"
    out.mkdir(parents=True, exist_ok=True)
    got = 0
    for n in names:
        if not CKPT_RE.match(str(n)) or (out / n).is_file():
            continue
        try:
            colab("download", "-s", scope, f"/content/out/{n}", str(out / n), timeout=300)
            got += 1
        except RuntimeError:
            break
    return got


def ckpts_to_upload(jd: Path, scope_slugs) -> list:
    """Checkpoint files on this side that a NEW VM needs: only chapters still to render."""
    res = []
    for f in sorted((jd / "out").glob("ckpt_*.tgz")):
        m = CKPT_RE.match(f.name)
        if m and (scope_slugs is None or m.group(1) in scope_slugs):
            res.append(f)
    return res


def die(msg: str) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(1)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _env() -> dict:
    e = dict(os.environ)
    e["PATH"] = str(Path.home() / ".local/bin") + os.pathsep + e.get("PATH", "")
    return e


def colab(*args, timeout: int = 240) -> str:
    try:
        r = subprocess.run(["colab", *args], capture_output=True, text=True,
                           timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"colab {' '.join(args)} timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError("colab CLI not found (google-colab-cli not on PATH)")
    if r.returncode != 0:
        lines = (r.stderr or r.stdout or "").strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"colab exited {r.returncode}")
    return r.stdout


def check_tag(tag: str) -> None:
    if not tag or not TAG_RE.match(tag):
        die(f"refusing bad job tag {tag!r} (want [A-Za-z0-9._-], max 64)")


def scope_for(tag: str) -> str:
    return f"{SCOPE_PFX}{tag}"


# A session line looks like "[name] gpu-l4-... | Hardware: L4 | ..." ("[?]" when the local
# record was pruned but the VM is still assigned and billing). Anything else on stdout,
# notably the CLI's "[colab] A new version ... is available" notices and "[colab] No
# active sessions found", is NOT a session. (Before 2026-10-06 those lines were parsed as
# phantom sessions named "colab", so the 2-slot guard saw 4/2 and refused every submit.)
REAL_SESSION_RE = re.compile(r"^\[([^\]]+)\]\s+\S+\s+\|\s*Hardware:")


def list_sessions() -> list[str]:
    out = colab("sessions", timeout=60)
    names = []
    for ln in out.splitlines():
        m = REAL_SESSION_RE.match(ln.strip())
        if m and m.group(1) != "colab":
            names.append(m.group(1))
    return names


def session_state(name: str) -> str:
    try:
        out = colab("status", "-s", name, timeout=60)
    except RuntimeError:
        return "gone"
    m = re.search(r"Status:\s*(\S+)", out)
    return (m.group(1).upper() if m else "UNKNOWN")


def _fresh(path: Path, ttl: int) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) < ttl
    except OSError:
        return False


# --------------------------------------------------------------------------
# probe
# --------------------------------------------------------------------------

def exec_probe(scope: str, timeout: int = 150) -> dict:
    """Run lane_probe.py inside the session and parse its single JSON line."""
    out = colab("exec", "-s", scope, "-f", str(PROBE),
                "--timeout", str(max(30, min(timeout - 60, 90))),
                timeout=timeout)
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("__LANE_JSON__"):
            return json.loads(line[len("__LANE_JSON__"):].strip())
    raise RuntimeError("lane probe returned no JSON line")


def launch(scope: str) -> None:
    colab("exec", "-s", scope, "-f", str(LAUNCH), "--timeout", "60", timeout=180)


def relaunch_count(job_dir: Path) -> int:
    try:
        return int((job_dir / "relaunches").read_text().strip() or "0")
    except Exception:
        return 0


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_status() -> None:
    """Read-only. Never raises: a broken lane must not break the panel."""
    cf = CACHE / "status.json"
    if _fresh(cf, STATUS_TTL):
        sys.stdout.write(cf.read_text(encoding="utf-8"))
        return
    payload = {
        "sessions": [], "harvest": [], "scopes": {}, "progress": {},
        "guard": {"max_sessions": MAX_SESSIONS, "reason": ""},
        "checked_at": int(time.time()),
    }
    try:
        names = list_sessions()
        for n in names:
            payload["sessions"].append({"name": n, "state": session_state(n),
                                        "owned": n.startswith(SCOPE_PFX)})
        live = len(names)
        if live >= MAX_SESSIONS:
            payload["guard"]["reason"] = (
                f"{live}/{MAX_SESSIONS} Colab GPU slots in use — a new lane "
                f"session will be refused until one stops (this protects the "
                f"running render from Colab reclaim)")
    except Exception as e:
        payload["error"] = f"{type(e).__name__}: {e}"

    harvest = Path("/tmp/harvest")
    try:
        payload["harvest"] = sorted(p.name for p in harvest.glob("*.mp3"))
    except Exception:
        pass

    if JOBS.exists():
        for jd in sorted(p for p in JOBS.iterdir() if p.is_dir()):
            tag = jd.name
            payload["scopes"][tag] = scope_for(tag)
            cf_p = CACHE / f"progress-{tag}.json"
            if _fresh(cf_p, STATUS_TTL * 4):
                try:
                    d = json.loads(cf_p.read_text(encoding="utf-8"))
                    payload["progress"][tag] = {
                        "completed": d.get("completed") or [],
                        "remain": d.get("remain") or [],
                        "alive": d.get("alive"),
                    }
                except Exception:
                    pass
            else:
                payload["progress"][tag] = {"completed": [], "remain": [],
                                            "alive": None}

    text = json.dumps(payload, ensure_ascii=False)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cf.write_text(text, encoding="utf-8")
    except OSError:
        pass
    sys.stdout.write(text)


def cmd_submit(tag: str) -> None:
    check_tag(tag)
    jd = JOBS / tag
    (jd / "out").mkdir(parents=True, exist_ok=True)
    for f in ("as_bundle.zip", "runner.py"):
        if not (jd / f).is_file():
            die(f"missing {f} in {jd} — the webapp pushes it before submit")
    if not PROBE.is_file() or not LAUNCH.is_file():
        die(f"lane_probe.py / lane_launch.py missing beside {HERE}")

    scope = scope_for(tag)
    (CACHE / f"progress-{tag}.json").unlink(missing_ok=True)
    try:
        names = list_sessions()
    except RuntimeError as e:
        die(f"cannot list sessions: {e}")

    if scope not in names:
        if len(names) >= MAX_SESSIONS:
            die(f"refusing to start {scope}: {len(names)} Colab GPU session(s) "
                f"already running and LANE_COLAB_MAX_SESSIONS={MAX_SESSIONS}. "
                f"Starting one risks Colab reclaiming a running render. Stop a "
                f"session first (lane_ctl.sh stop <tag>), or raise "
                f"LANE_COLAB_MAX_SESSIONS if the account tier allows it.")
        try:
            colab("new", "-s", scope, "--gpu", GPU, timeout=600)
        except RuntimeError as e:
            die(f"could not create {scope} ({GPU}): {e}")

    # Push the inputs the runner needs on the VM.
    try:
        colab("upload", "-s", scope, str(jd / "as_bundle.zip"),
              "/content/as_bundle.zip", timeout=1200)
        colab("upload", "-s", scope, str(jd / "runner.py"),
              "/content/runner.py", timeout=300)
        # Optional scope written by the webapp on a RESUBMIT: only the chapters not yet
        # banked, so a fresh VM never re-renders finished chapters.
        scope_slugs = None
        if (jd / "as_chapters.txt").is_file():
            colab("upload", "-s", scope, str(jd / "as_chapters.txt"),
                  "/content/as_chapters.txt", timeout=120)
            scope_slugs = {s.strip() for s in
                           (jd / "as_chapters.txt").read_text().split(",") if s.strip()}
        # Restore point for a replacement VM: every checkpointed chunk of the chapters still to render.
        for f in ckpts_to_upload(jd, scope_slugs):
            colab("upload", "-s", scope, str(f), f"/content/{f.name}", timeout=600)
    except RuntimeError as e:
        die(f"upload to {scope} failed: {e}")

    try:
        launch(scope)
    except RuntimeError as e:
        die(f"launch on {scope} failed: {e}")

    (jd / "scope").write_text(scope, encoding="utf-8")
    emit({"ok": True, "scope": scope, "gpu": GPU,
          "note": "runner started; cold start + dependency bootstrap ~5-10 min"})


def _summarise(payload: dict, job_dir: Path, tag: str) -> dict:
    """Apply the resume/dead policy to a probe result."""
    alive = bool(payload.get("alive"))
    remain = payload.get("remain") or []
    beat = int(payload.get("heartbeat_age") or 0)

    if not remain:
        payload["dead_permanent"] = False
        return payload

    payload["dead_permanent"] = False
    if alive or beat < HEARTBEAT_S:
        return payload

    # Runner stopped and the state has not moved: relaunch (state-resumable),
    # bounded, so a crash loop cannot spin forever.
    n = relaunch_count(job_dir)
    if n < MAX_RELAUNCH:
        try:
            scope = (job_dir / "scope").read_text().strip() or scope_for(tag)
            launch(scope)
            (job_dir / "relaunches").write_text(str(n + 1), encoding="utf-8")
            payload["relaunched"] = n + 1
            payload["log_tail"] = (payload.get("log_tail") or "") + (
                f"\n=== lane_ctl: runner gone with {len(remain)} chapter(s) "
                f"left, relaunched ({n + 1}/{MAX_RELAUNCH}) ===")
        except Exception as e:
            payload["dead_permanent"] = True
            payload["log_tail"] = (payload.get("log_tail") or "") + (
                f"\n=== lane_ctl: relaunch failed: {e} ===")
    else:
        payload["dead_permanent"] = True
        payload["log_tail"] = (payload.get("log_tail") or "") + (
            f"\n=== lane_ctl: runner dead after {MAX_RELAUNCH} relaunches; "
            f"giving up ===")
    return payload


def cmd_progress(tag: str) -> None:
    check_tag(tag)
    jd = JOBS / tag
    scope = scope_for(tag)
    cf = CACHE / f"progress-{tag}.json"
    if _fresh(cf, PROGRESS_TTL):
        sys.stdout.write(cf.read_text(encoding="utf-8"))
        return
    try:
        payload = exec_probe(scope)
    except Exception as e:
        # An unreachable bridge is reported as a probe error, not a crash. If the VM
        # itself is gone (Colab reclaimed / pruned it - seen 2026-10-06, exactly 1 h after
        # `colab new`) say so explicitly: the caller must RESUBMIT, not keep polling a
        # corpse. Before this, "gone" looked like a healthy probe with an empty state and
        # the webapp spun silently for 9 hours.
        gone = False
        try:
            gone = scope not in list_sessions()
        except Exception:
            pass
        out = {"state": {}, "remain": [], "alive": None, "dead_permanent": False,
               "error": f"{type(e).__name__}: {e}", "log_tail": ""}
        if gone:
            out["session_gone"] = True
            (CACHE / f"progress-{tag}.json").unlink(missing_ok=True)
        emit(out)
        return
    payload = _summarise(payload, jd, tag)
    try:
        pull_ckpts(tag, scope, payload)
    except Exception:
        pass   # never let checkpoint housekeeping break a progress reply
    text = json.dumps(payload, ensure_ascii=False)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cf.write_text(text, encoding="utf-8")
    except OSError:
        pass
    sys.stdout.write(text)


def cmd_fetch(tag: str, name: str) -> None:
    check_tag(tag)
    if not MP3_RE.match(name):
        die(f"refusing bad file name {name!r}")
    scope = scope_for(tag)
    dest = JOBS / tag / "out" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        colab("download", "-s", scope, f"/content/out/{name}", str(dest),
              timeout=600)
    except RuntimeError as e:
        die(f"download {name} from {scope} failed: {e}")
    if not dest.is_file() or dest.stat().st_size == 0:
        die(f"{name} not produced by {scope} yet")
    emit({"ok": True, "path": str(dest), "bytes": dest.stat().st_size})


def cmd_log(tag: str) -> None:
    check_tag(tag)
    try:
        payload = exec_probe(scope_for(tag))
        sys.stdout.write(payload.get("log_tail") or "")
    except Exception as e:
        die(f"log unavailable: {e}")


def _stop(tag: str, why: str) -> None:
    check_tag(tag)
    scope = scope_for(tag)
    try:
        names = list_sessions()
    except RuntimeError as e:
        die(f"cannot list sessions: {e}")
    if scope not in names:
        emit({"ok": True, "scope": scope, "note": "not running"})
        return
    try:
        colab("stop", "-s", scope, timeout=180)
    except RuntimeError as e:
        die(f"could not stop {scope}: {e}")
    (CACHE / f"progress-{tag}.json").unlink(missing_ok=True)
    emit({"ok": True, "scope": scope, "stopped": True, "reason": why})


def main(argv) -> int:
    if len(argv) < 1:
        die(__doc__ or "usage: lane_ctl.sh <command> [args]")
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "status":
            cmd_status()
        elif cmd == "submit" and len(rest) == 1:
            cmd_submit(rest[0])
        elif cmd == "progress" and len(rest) == 1:
            cmd_progress(rest[0])
        elif cmd == "fetch" and len(rest) == 2:
            cmd_fetch(rest[0], rest[1])
        elif cmd == "log" and len(rest) == 1:
            cmd_log(rest[0])
        elif cmd in ("done", "stop") and len(rest) == 1:
            _stop(rest[0], cmd)
        else:
            die(f"unknown/incomplete command: {' '.join(argv) or '(none)'}")
    except SystemExit:
        raise
    except Exception as e:
        # progress/status must stay machine-readable even when broken.
        if cmd in ("progress", "status"):
            emit({"state": {}, "remain": [], "alive": None,
                  "dead_permanent": False, "error": f"{type(e).__name__}: {e}",
                  "log_tail": ""})
            return 0
        die(f"{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
