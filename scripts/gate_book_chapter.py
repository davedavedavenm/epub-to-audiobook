"""gate_book_chapter.py — the delivery gate for locked-recipe book chapters.

A chapter may NOT be described as done, packed into the M4B, or pushed to
Audiobookshelf without PASSing here. This is the enforcement half of
CILLIAN-RECIPE.md / the verification discipline: waveform health + ASR
completeness measured against the EXACT prepped source that the lane spoke
(scratch/as_book/<slug>.json — the same payloads whose sentence count the
runner banked, so a truncated or misplaced render cannot pass).

Thresholds (as recorded for the preface gate, TTS-WATCH-FINDINGS 2026-09-24):
  word ratio = n_heard / n_source  >= 0.93   (qa_asr normalises years/digits
                                              and curly apostrophes both sides)
  coverage   = n_match  / n_source  >= 0.90
  waveform   : RMS in [0.02, 0.30], mean|diff| > 0.002 (no DC collapse),
               no full-scale run >= 2 s, no dead 30 s window.

Usage:
  python scripts/gate_book_chapter.py <chapter.mp3> [--slug ch1] [--wave-only]

Writes <chapter>.gate.json next to the audio. Exit code 0 = PASS, 1 = FAIL.
Running it against the already-gated preface must reproduce the recorded
numbers (0.977 ratio / 95.5% coverage) — that reproduction is the tool's own
validation before it is trusted on new chapters.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

THRESHOLDS = {
    "word_ratio_min": 0.93,
    "coverage_min": 0.90,
    "rms_min": 0.02,
    "rms_max": 0.30,
    "mean_abs_diff_min": 0.002,
    "plateau_sec_max": 2.0,
    "quiet_window_rms": 0.005,
    "quiet_window_sec": 30.0,
}


def slug_from_filename(mp3: Path) -> str:
    m = re.match(r"armed_struggle_(.+)_cillian$", mp3.stem)
    if not m:
        raise SystemExit(f"cannot derive slug from {mp3.name}; pass --slug")
    return m.group(1)


def source_for(slug: str) -> tuple[str, int]:
    """(joined prepped source text, sentence count) from the payload the lane
    actually rendered — not the raw epub, so year-spelling etc. compare equal."""
    p = ROOT / "scratch" / "as_book" / f"{slug}.json"
    if not p.exists():
        raise SystemExit(f"source payload missing: {p}")
    d = json.loads(p.read_text(encoding="utf-8"))
    sents = [s["text"] for s in d["sents"]]
    return " ".join(sents), len(sents)


def probe(path: Path) -> dict:
    # No ffprobe on this box — mutagen parses MP3 frame headers directly.
    from mutagen.mp3 import MP3
    info = MP3(str(path)).info
    return {"sample_rate": int(info.sample_rate),
            "duration": float(info.length)}


def waveform_gate(path: Path) -> dict:
    """Streaming decode -> health stats. Reads raw f32le from ffmpeg's stdout,
    so a 100-minute chapter never materialises as a temp wav on disk."""
    info = probe(path)
    sr = info["sample_rate"]
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
         "-f", "f32le", "-"],
        stdout=subprocess.PIPE)
    total_sq = 0.0
    n = 0
    max_abs = 0.0
    absdiff_sum = 0.0
    absdiff_n = 0
    prev = None                     # last sample of the previous chunk
    run = 0                         # current consecutive full-scale run (samples)
    plateau_max = 0                 # longest full-scale run (samples)
    win_sq = 0.0
    win_n = 0
    quiet_windows = 0
    win_len = int(sr * THRESHOLDS["quiet_window_sec"])
    rem = b""
    while True:
        buf = proc.stdout.read(1 << 22)
        if not buf:
            break
        data = rem + buf
        usable = len(data) - (len(data) % 4)
        rem = data[usable:]
        x = np.frombuffer(data[:usable], dtype=np.float32)
        if x.size == 0:
            continue
        ax = np.abs(x)
        total_sq += float(np.dot(x, x))
        n += int(x.size)
        max_abs = max(max_abs, float(ax.max()))

        # mean |diff| with a single-sample carry across chunk boundaries
        full = x if prev is None else np.concatenate((np.array([prev], dtype=np.float32), x))
        d = np.abs(np.diff(full))
        absdiff_sum += float(d.sum())
        absdiff_n += int(d.size)
        prev = x[-1]

        # full-scale plateau runs (>=0.99 FS), vectorised segment scan
        fs = ax >= 0.99
        if fs.size:
            changes = np.flatnonzero(fs[1:] != fs[:-1]) + 1
            starts = np.concatenate((np.array([0]), changes))
            ends = np.concatenate((changes, np.array([fs.size])))
            seg_len = ends - starts
            seg_val = fs[starts]
            if run and fs[0]:                 # chunk starts mid-run
                seg_len = seg_len.copy()
                seg_len[0] += run
            if seg_val.any():
                plateau_max = max(plateau_max, int(seg_len[seg_val].max()))
            run = int(seg_len[-1]) if seg_val[-1] else 0

        # dead 30 s windows
        win_sq += float(np.dot(x, x))
        win_n += int(x.size)
        if win_n >= win_len:
            if (win_sq / win_n) ** 0.5 < THRESHOLDS["quiet_window_rms"]:
                quiet_windows += 1
            win_sq = 0.0
            win_n = 0
    proc.stdout.close()
    proc.wait()
    if win_n > sr * 5:  # trailing partial window counts if >= 5 s
        if (win_sq / win_n) ** 0.5 < THRESHOLDS["quiet_window_rms"]:
            quiet_windows += 1
    if not n:
        raise SystemExit("ffmpeg produced no samples — audio unreadable")
    return {
        "duration_sec": round(n / sr, 2),
        "ffprobe_duration_sec": round(info["duration"], 2),
        "sample_rate": sr,
        "rms": round((total_sq / n) ** 0.5, 4),
        "max_abs": round(max_abs, 4),
        "mean_abs_diff": round(absdiff_sum / absdiff_n, 5) if absdiff_n else 0.0,
        "plateau_max_sec": round(plateau_max / sr, 3),
        "quiet_windows": quiet_windows,
    }


def boundary_check(source_text: str, transcript: str, k: int = 15) -> dict:
    """Informational: do the first/last k normalised words match? (The preface
    gate recorded 'first/last lines verbatim' — this makes it repeatable.)"""
    import difflib
    from qa_asr import normalize_words
    s, h = normalize_words(source_text), normalize_words(transcript)
    def ratio(a, b):
        if not a or not b:
            return 0.0
        return round(difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio(), 3)
    return {
        "first_words_ratio": ratio(s[:k], h[:k]),
        "last_words_ratio": ratio(s[-k:], h[-k:]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Delivery gate for a book chapter mp3")
    ap.add_argument("mp3")
    ap.add_argument("--slug", help="source payload slug (default: from filename)")
    ap.add_argument("--wave-only", action="store_true", help="skip the ASR pass")
    ap.add_argument("--model", default="base", help="whisper model size")
    a = ap.parse_args()

    mp3 = Path(a.mp3).resolve()
    if not mp3.exists():
        raise SystemExit(f"missing audio: {mp3}")
    slug = a.slug or slug_from_filename(mp3)
    source_text, n_sents = source_for(slug)
    t0 = time.time()

    print(f"[gate] {mp3.name}  slug={slug}  source={n_sents} sents", flush=True)
    wave = waveform_gate(mp3)
    print(f"[gate] waveform: {wave['duration_sec']/60:.1f} min  RMS {wave['rms']}  "
          f"mean|diff| {wave['mean_abs_diff']}  plateau_max {wave['plateau_max_sec']}s  "
          f"quiet_windows {wave['quiet_windows']}", flush=True)

    checks = {
        "rms_in_band": THRESHOLDS["rms_min"] <= wave["rms"] <= THRESHOLDS["rms_max"],
        "mean_abs_diff_ok": wave["mean_abs_diff"] > THRESHOLDS["mean_abs_diff_min"],
        "no_plateau": wave["plateau_max_sec"] < THRESHOLDS["plateau_sec_max"],
        "no_quiet_window": wave["quiet_windows"] == 0,
    }

    asr = None
    if not a.wave_only:
        os.environ.setdefault(
            "WHISPER_MODEL_DIR",
            str(ROOT / "evaluations" / "new-engines" / "output" / ".whisper"))
        from qa_asr import diff_report, transcribe
        print(f"[gate] ASR ({a.model}) transcribing — this is the slow part…",
              flush=True)
        transcript = transcribe(mp3, model_size=a.model)
        rep = diff_report(source_text, transcript)
        word_ratio = rep["n_heard"] / max(1, rep["n_source"])
        coverage = rep["n_match"] / max(1, rep["n_source"])
        asr = {
            "model": a.model,
            "n_source": rep["n_source"],
            "n_heard": rep["n_heard"],
            "word_ratio": round(word_ratio, 4),
            "coverage": round(coverage, 4),
            "wer": rep["wer"],
            "n_divergences": len(rep["divergences"]),
            "divergences": rep["divergences"][:60],
            "transcript_chars": len(transcript),
        }
        checks["word_ratio"] = word_ratio >= THRESHOLDS["word_ratio_min"]
        checks["coverage"] = coverage >= THRESHOLDS["coverage_min"]
        print(f"[gate] ASR: SRC {rep['n_source']} vs {rep['n_heard']} words "
              f"({word_ratio:.3f}), coverage {coverage*100:.1f}%, "
              f"WER {rep['wer']:.3f}", flush=True)
        if not a.wave_only:
            b = boundary_check(source_text, transcript)
            asr.update(b)
            print(f"[gate] boundary: first {b['first_words_ratio']} / "
                  f"last {b['last_words_ratio']}", flush=True)

    verdict = all(checks.values())
    report = {
        "audio": mp3.name,
        "slug": slug,
        "gate": "book-chapter",
        "thresholds": THRESHOLDS,
        "waveform": wave,
        "source_sents": n_sents,
        "asr": asr,
        "checks": checks,
        "verdict": "PASS" if verdict else "FAIL",
        "elapsed_sec": round(time.time() - t0, 1),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    out = mp3.with_suffix(".gate.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    failed = [k for k, v in checks.items() if not v]
    print(f"[gate] VERDICT: {'PASS' if verdict else 'FAIL ' + str(failed)}  "
          f"-> {out.name}", flush=True)
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
