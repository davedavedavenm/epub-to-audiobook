#!/usr/bin/env python3
"""Local delivery arm for the Armed Struggle lane render.

The khpi5 harvest loop copies each finished chapter into /tmp/harvest. This
script is the Windows-side half of the pipeline (CILLIAN-RECIPE.md "Windows-side
pull"): poll the harvest dir, pull every new chapter ATOMICALLY (scp to
<name>.part, then rename — a half-transferred file can never be mistaken for a
chapter), and gate it with scripts/gate_book_chapter.py (waveform health + ASR
completeness against the exact payload the lane rendered).

Exit codes:
  0  ALLDONE — all 10 sections have gate verdicts and every one PASSed
  2  ALLDONE but at least one gate FAILED — do not assemble the book
  1  operational error (ssh/scp/gate could not run)

Idempotent and resumable: a section is downloaded and gated only until its
.gate.json exists, so re-running after an interruption never re-pulls or
re-gates a finished chapter. A gate FAIL is kept on disk (it is evidence), the
run ends loudly, and nothing is deleted.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REMOTE = os.environ.get("AS_HARVEST_HOST", "khpi5")
HARVEST_DIR = os.environ.get("AS_HARVEST_DIR", "/tmp/harvest")
POLL_SECONDS = int(os.environ.get("AS_POLL_SECONDS", "300"))
SLUGS = ["preface"] + [f"ch{i}" for i in range(1, 9)] + ["conclusion"]
PREFIX = "armed_struggle_"
SUFFIX = "_cillian.mp3"

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluations" / "new-engines" / "output"
GATE = ROOT / "scripts" / "gate_book_chapter.py"


def log(msg: str) -> None:
    print(time.strftime("[%Y-%m-%d %H:%M:%S] "), msg, flush=True)


def mp3_for(slug: str) -> Path:
    return OUT / f"{PREFIX}{slug}{SUFFIX}"


def gate_for(slug: str) -> Path:
    """The gate tool writes <mp3-stem>.gate.json, i.e. …_cillian.gate.json."""
    return OUT / f"{PREFIX}{slug}_cillian.gate.json"


def remote_listing() -> set:
    """Filenames (not paths) currently in the harvest dir; empty on ssh failure."""
    r = subprocess.run(
        ["ssh", REMOTE, f"ls -1 {HARVEST_DIR}/*.mp3 2>/dev/null"],
        capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        log(f"ssh listing failed rc={r.returncode}: {(r.stderr or '').strip()[:200]}")
        return set()
    return {Line.rsplit("/", 1)[-1] for Line in r.stdout.splitlines() if Line.strip()}


def pull(slug: str) -> bool:
    """scp to <name>.part then rename. Returns True when the full file is in place."""
    name = f"{PREFIX}{slug}{SUFFIX}"
    dst = mp3_for(slug)
    part = dst.parent / (dst.name + ".part")
    dst.parent.mkdir(parents=True, exist_ok=True)
    log(f"pulling {name} …")
    t0 = time.time()
    r = subprocess.run(
        ["scp", f"{REMOTE}:{HARVEST_DIR}/{name}", str(part)],
        capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        log(f"scp FAILED rc={r.returncode}: {(r.stderr or '').strip()[:300]}")
        part.unlink(missing_ok=True)
        return False
    got, want = part.stat().st_size, None
    # size sanity against the remote copy before adopting it
    r2 = subprocess.run(
        ["ssh", REMOTE, f"stat -c %s {HARVEST_DIR}/{name} 2>/dev/null"],
        capture_output=True, text=True, timeout=60)
    if r2.returncode == 0 and r2.stdout.strip().isdigit():
        want = int(r2.stdout.strip())
        if got != want:
            log(f"size mismatch remote={want} local={got} — NOT adopting; will retry next cycle")
            part.unlink(missing_ok=True)
            return False
    os.replace(part, dst)
    log(f"pulled {name} ({got / 1e6:.1f} MB in {time.time() - t0:.0f}s)"
        + ("" if want is None else " — size matches remote"))
    return True


def gate(slug: str) -> dict | None:
    """Run the completeness gate; returns its verdict dict (FAILED gates included)."""
    log(f"gating {slug} …")
    r = subprocess.run(
        [sys.executable, str(GATE), str(mp3_for(slug)), "--slug", slug],
        capture_output=True, text=True, timeout=3600)
    tail = "\n".join((r.stdout or "").strip().splitlines()[-6:])
    log(f"gate rc={r.returncode}\n{tail}")
    gp = gate_for(slug)
    if gp.exists():
        return json.loads(gp.read_text())
    return None


def summary(verdicts: dict) -> int:
    log("=========== ALL GATED — VERDICT SUMMARY ===========")
    fails = 0
    for slug in SLUGS:
        v = verdicts.get(slug)
        if not v:
            log(f"  {slug:<10} NO VERDICT")
            fails += 1
            continue
        w, a = v.get("waveform", {}), v.get("asr", {})
        log(f"  {slug:<10} {v.get('verdict')}  word={a.get('word_ratio')} "
            f"cov={a.get('coverage')} rms={w.get('rms')} dur={w.get('duration_sec', 0) / 60:.1f}min")
        if v.get("verdict") != "PASS":
            fails += 1
    if fails:
        log(f"ALLDONE WITH {fails} PROBLEM(S) — do NOT assemble the book")
        return 2
    log("ALLDONE — all 10 sections PASS; ready for chaptered M4B + ABS replace")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true",
                    help="run a single poll/pull/gate cycle and exit (0 = all gated)")
    args = ap.parse_args()
    verdicts = {}
    while True:
        listing = remote_listing()
        for slug in SLUGS:
            if gate_for(slug).exists():
                try:
                    verdicts[slug] = json.loads(gate_for(slug).read_text())
                except Exception as e:
                    log(f"{slug}: unreadable gate json ({e})")
                continue
            if f"{PREFIX}{slug}{SUFFIX}" in listing:
                if pull(slug):
                    v = gate(slug)
                    if v:
                        verdicts[slug] = v
                        if v.get("verdict") != "PASS":
                            log(f"{slug}: GATE FAILED — keeping evidence, stopping the run")
                            return summary(verdicts)
            else:
                log(f"{slug}: not harvested yet")
        if all(gate_for(s).exists() for s in SLUGS):
            return summary(verdicts)
        if args.once:
            log("--once: cycle done, exiting")
            return 1
        log(f"cycle complete — {sum(gate_for(s).exists() for s in SLUGS)}/10 gated; "
            f"sleeping {POLL_SECONDS}s")
        try:
            time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            log("interrupted — resume by re-running; gated chapters are never redone")
            return 130


if __name__ == "__main__":
    sys.exit(main())
