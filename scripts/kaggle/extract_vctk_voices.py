"""Kaggle kernel: extract accent-diverse voice-clone references from VCTK.

VCTK (CSTR) is 110 English speakers labelled BY ACCENT (Australian, Scottish,
Irish, NorthernIrish, English regions, ...) in clean studio audio — exactly the
non-US accent variety we want, and impossible to mis-source (accent is labelled,
not guessed). This runs on Kaggle so the 11GB corpus is attached instantly.

For each chosen speaker it concatenates a few consecutive utterances into a
~16s continuous clip, loudness-normalises, 24kHz mono — matching our vetted
reference spec — and writes it named by accent+gender to /kaggle/working.

Attach dataset: kynthesis/vctk-corpus  (v0.92)
"""
import os
import glob
import subprocess
import sys
import random

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "soundfile", "numpy"], check=False)
import soundfile as sf
import numpy as np

ROOT = "/kaggle/input"
# locate speaker-info.txt and the wav/flac tree wherever the dataset mounted it
info = next((p for p in glob.glob(f"{ROOT}/**/speaker-info.txt", recursive=True)), None)
assert info, "speaker-info.txt not found under /kaggle/input"
base = os.path.dirname(info)
print("dataset base:", base, flush=True)

# parse: ID  AGE  GENDER  ACCENT  REGION  (ID is a bare number like "225",
# the directories are p225; handle both "225" and "p225")
speakers = {}
for line in open(info, encoding="utf-8", errors="ignore"):
    parts = line.split()
    if len(parts) < 4:
        continue
    raw = parts[0]
    if raw.isdigit():
        sid = "p" + raw
    elif raw[0].lower() == "p" and raw[1:].isdigit():
        sid = raw
    else:
        continue
    speakers[sid] = {"gender": parts[2], "accent": parts[3]}
print(f"parsed {len(speakers)} speakers; accents: {sorted(set(v['accent'] for v in speakers.values()))}", flush=True)

# which accents we want, and how many speakers each (M/F if available)
WANT = ["Australian", "Scottish", "Irish", "NorthernIrish", "Welsh",
        "English", "Canadian"]
picked = []
for accent in WANT:
    cands = [(s, v) for s, v in speakers.items() if v["accent"].lower() == accent.lower()]
    random.Random(42).shuffle(cands)
    m = next((c for c in cands if c[1]["gender"] == "M"), None)
    f = next((c for c in cands if c[1]["gender"] == "F"), None)
    for c in (m, f):
        if c:
            picked.append((c[0], accent, c[1]["gender"]))
print(f"selected {len(picked)} speakers across accents", flush=True)


def load_speaker_clip(sid, target_s=16.0):
    """Concatenate consecutive utterances into ~target_s of continuous speech."""
    files = sorted(glob.glob(f"{base}/**/{sid}/{sid}_*_mic1.flac", recursive=True) or
                   glob.glob(f"{base}/**/{sid}/{sid}_*.flac", recursive=True) or
                   glob.glob(f"{base}/**/{sid}/{sid}_*.wav", recursive=True))
    if not files:
        return None, None
    # skip the first couple (often "Please call Stella" calibration) — use mid ones
    files = files[3:] if len(files) > 6 else files
    chunks, total, sr = [], 0.0, None
    for fp in files:
        try:
            a, s = sf.read(fp)
        except Exception:
            continue
        if a.ndim > 1:
            a = a.mean(axis=1)
        if sr is None:
            sr = s
        if s != sr:
            continue
        # trim leading/trailing near-silence
        thr = 0.01 * np.max(np.abs(a)) if a.size else 0
        idx = np.where(np.abs(a) > thr)[0]
        if idx.size:
            a = a[idx[0]:idx[-1] + 1]
        chunks.append(a)
        chunks.append(np.zeros(int(sr * 0.12)))  # small natural gap
        total += len(a) / sr
        if total >= target_s:
            break
    if not chunks:
        return None, None
    return np.concatenate(chunks), sr


os.makedirs("/kaggle/working", exist_ok=True)
manifest = []
for sid, accent, gender in picked:
    audio, sr = load_speaker_clip(sid)
    if audio is None:
        print("  no audio for", sid, flush=True)
        continue
    name = f"vctk_{accent.lower()}_{gender.lower()}_{sid.lower()}"
    raw = f"/tmp/{name}.wav"
    sf.write(raw, audio, sr)
    out = f"/kaggle/working/{name}.wav"
    # loudnorm + 24kHz mono, matching our vetted spec
    subprocess.run(["ffmpeg", "-v", "error", "-i", raw,
                    "-af", "loudnorm=I=-18:TP=-1.5:LRA=11,highpass=f=70",
                    "-ar", "24000", "-ac", "1", "-t", "18", out, "-y"], check=False)
    if os.path.exists(out):
        manifest.append((name, accent, gender, sid))
        print("OUTPUT:", name, accent, gender, flush=True)

open("/kaggle/working/manifest.txt", "w").write(
    "\n".join(f"{n}\t{a}\t{g}\t{s}" for n, a, g, s in manifest))
print("DONE:", len(manifest), "voices", flush=True)
