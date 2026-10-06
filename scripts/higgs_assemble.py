"""higgs_assemble.py - join Higgs chunk audio into a chapter (pure numpy; no GPU).

Join style "V3", chosen by Dave on 2026-10-06 over the original (0.3 s silence + 15 ms fade after
every chunk, which sounded abrupt) and over V2 (shorter gaps + soft tail):
  * each chunk: silence-trimmed (-55 dB, 150 ms pad), 20 ms fade-in, 90 ms fade-out
  * inside a paragraph: chunks OVERLAP by a 70 ms crossfade - no silence at all
  * across paragraphs / after a heading: 0.45 s of silence
Then a single gain to ~-20 LUFS with sample peak <= -2 dBFS (gain-only: no EQ, no compression).
"""
from __future__ import annotations

import numpy as np

TRIM_DB = -55.0
TRIM_PAD_S = 0.15
FADE_IN_S = 0.02
FADE_OUT_S = 0.09
XFADE_S = 0.07
PARA_GAP_S = 0.45


def trim(w: np.ndarray, sr: int, thr_db: float = TRIM_DB, pad_s: float = TRIM_PAD_S) -> np.ndarray:
    idx = np.where(np.abs(w) > 10 ** (thr_db / 20))[0]
    if not len(idx):
        return w
    return w[max(0, idx[0] - int(pad_s * sr)): min(len(w), idx[-1] + int(pad_s * sr))]


def shape(w: np.ndarray, sr: int) -> np.ndarray:
    w = trim(np.asarray(w, dtype=np.float32), sr).copy()
    fi, fo = int(FADE_IN_S * sr), int(FADE_OUT_S * sr)
    if len(w) > fi + fo:
        w[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
        w[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    return w


def joins_inside_paragraph(prev: dict, cur: dict) -> bool:
    """Overlap only between two prose chunks of the same paragraph."""
    return (not prev.get("heading") and not cur.get("heading")
            and prev.get("para") == cur.get("para"))


def assemble(wavs: list, chunks: list, sr: int) -> np.ndarray:
    """``wavs[i]`` is the audio of ``chunks[i]`` (None = missing chunk, skipped)."""
    out = None
    prev = None
    for w, c in zip(wavs, chunks):
        if w is None or len(w) == 0:
            continue
        w = shape(w, sr)
        if out is None:
            out, prev = w, c
            continue
        if joins_inside_paragraph(prev, c):
            k = min(int(XFADE_S * sr), len(out), len(w))
            out[-k:] = out[-k:] * np.linspace(1.0, 0.0, k, dtype=np.float32) + \
                w[:k] * np.linspace(0.0, 1.0, k, dtype=np.float32)
            out = np.concatenate([out, w[k:]])
        else:
            out = np.concatenate([out, np.zeros(int(PARA_GAP_S * sr), dtype=np.float32), w])
        prev = c
    return out if out is not None else np.zeros(0, dtype=np.float32)


def loudness_gain_db(integrated_lufs: float | None, sample_peak_dbfs: float | None,
                     target_lufs: float = -20.0, peak_ceiling_dbfs: float = -2.0) -> float:
    """Gain that reaches the loudness target without pushing the sample peak over the ceiling."""
    gain = 0.0 if integrated_lufs is None else target_lufs - integrated_lufs
    if sample_peak_dbfs is not None:
        gain = min(gain, peak_ceiling_dbfs - sample_peak_dbfs)
    return max(-12.0, min(12.0, gain))
