#!/usr/bin/env python3
"""Stage the FireRedTTS3 Base Breakneck Chapter 1 (Pages 1-2) Kaggle T4 evaluation gate.

Builds a self-contained Kaggle kernel directory under scratch/firered_breakneck/kernel/
that evaluates FireRedTTS3 Base with Arthur reference clone on the exact
2-page normalized excerpt of Breakneck Chapter 1.
Outputs WAV, 128k MP3, and JSON evidence.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "firered_breakneck" / "kernel"
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
ARTHUR_URL = "https://media.githubusercontent.com/media/davedavedavenm/epub-to-audiobook/master/chatterbox/voices/uk_male_minter.wav"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
ARTHUR_TRANSCRIPT = (
    '"I know that," snapped Bertram. "Not that it would make any difference if she stayed," '
    'pursued the relentless George. "She flies higher than the paper trade, my boy." '
    '"Hang her!" said Bertram. "It would make it more interesting for me," I ventured to observe.'
)

KERNEL_TEMPLATE = r'''import base64
import gc
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

BREAKNECK_TEXT = base64.b64decode(__TEXT_B64__).decode("utf-8")
ARTHUR_URL = __ARTHUR_URL__
ARTHUR_SHA256 = __ARTHUR_SHA256__
ARTHUR_TRANSCRIPT = __ARTHUR_TRANSCRIPT__
WORK = Path("/kaggle/working")
OUT_DIR = WORK / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
REF_WAV = WORK / "arthur.wav"

def sh(cmd, cwd=None):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=True)

print("=== Checking CUDA ===")
assert torch.cuda.is_available(), "CUDA is not available on this Kaggle runner!"
device_name = torch.cuda.get_device_name(0)
print(f"CUDA Device: {device_name}")

print("=== Fetching Arthur Reference Audio ===")
if not REF_WAV.exists():
    urllib.request.urlretrieve(ARTHUR_URL, REF_WAV)

h = hashlib.sha256(REF_WAV.read_bytes()).hexdigest()
assert h == ARTHUR_SHA256, f"Checksum mismatch: {h} != {ARTHUR_SHA256}"
print("Arthur reference audio verified.")

print("=== Installing Dependencies & Cloning FireRedTTS3 ===")
REPO_DIR = WORK / "FireRedTTS3"
if not REPO_DIR.exists():
    sh(["git", "clone", "https://github.com/FireRedTeam/FireRedTTS3.git", str(REPO_DIR)])

sh([sys.executable, "-m", "pip", "install", "-q", "-r", str(REPO_DIR / "requirements.txt")])
sh([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub[cli]"])

MODEL_DIR = WORK / "pretrained_models"
if not MODEL_DIR.exists():
    print("=== Downloading FireRedTTS3 Model Weights ===")
    sh(["huggingface-cli", "download", "FireRedTeam/FireRedTTS3", "--local-dir", str(MODEL_DIR)])

sys.path.insert(0, str(REPO_DIR))
from fireredtts3.core import FireRedTTS3

print("=== Loading FireRedTTS3 Model ===")
t0_load = time.time()
tts = FireRedTTS3(str(MODEL_DIR), use_wetext=True, use_llm_tn=False)
t_load = time.time() - t0_load
print(f"FireRedTTS3 loaded in {t_load:.2f}s")

# Load reference prompt
prompt_audio, prompt_sr = torchaudio.load(str(REF_WAV))

# Split Breakneck text into sentence chunks
def split_sentences(text: str) -> list[str]:
    raw_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    chunks = []
    curr = ""
    for s in raw_sents:
        if len(curr) + len(s) + 1 < 300:
            curr = f"{curr} {s}".strip()
        else:
            if curr:
                chunks.append(curr)
            curr = s
    if curr:
        chunks.append(curr)
    return chunks

chunks = split_sentences(BREAKNECK_TEXT)
print(f"Synthesizing {len(chunks)} text chunks with Arthur clone...")

audio_segments = []
t0_gen = time.time()

for idx, chunk in enumerate(chunks):
    print(f"[{idx+1}/{len(chunks)}] Synthesizing: {chunk[:60]}...")
    gen_audio, gen_sr = tts.generate(
        text=chunk,
        language="English",
        prompt_text=ARTHUR_TRANSCRIPT,
        prompt_audio=prompt_audio
    )
    if isinstance(gen_audio, torch.Tensor):
        gen_audio = gen_audio.squeeze().cpu().numpy()
    audio_segments.append(gen_audio)
    # 350ms pause between chunks
    pause_samples = int(gen_sr * 0.35)
    audio_segments.append(np.zeros(pause_samples, dtype=np.float32))

t_gen = time.time() - t0_gen
full_audio = np.concatenate(audio_segments)
duration = len(full_audio) / gen_sr
rtf = t_gen / duration if duration > 0 else 0

print(f"Generated {duration:.2f}s audio in {t_gen:.2f}s (RTF: {rtf:.3f})")

# Save WAV and MP3
wav_path = OUT_DIR / "firered_breakneck_ch1_arthur.wav"
mp3_path = OUT_DIR / "firered_breakneck_ch1_arthur.mp3"
sf.write(str(wav_path), full_audio, gen_sr)

sh(["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)])

evidence = {
    "model": "FireRedTeam/FireRedTTS3",
    "hardware": device_name,
    "duration_sec": round(duration, 3),
    "wall_time_sec": round(t_gen, 3),
    "load_time_sec": round(t_load, 3),
    "rtf": round(rtf, 3),
    "chunks_count": len(chunks),
}
(OUT_DIR / "firered_breakneck_ch1_arthur.json").write_text(json.dumps(evidence, indent=2))
print("Finished FireRedTTS3 evaluation run.")
'''

def main():
    assert TEXT_FILE.exists(), f"Text file missing: {TEXT_FILE}"

    text_content = TEXT_FILE.read_text(encoding="utf-8")
    text_b64 = repr(base64.b64encode(text_content.encode("utf-8")).decode("ascii"))
    arthur_url = repr(ARTHUR_URL)
    arthur_sha256 = repr(ARTHUR_SHA256)
    arthur_transcript = repr(ARTHUR_TRANSCRIPT)

    kernel_code = KERNEL_TEMPLATE.replace("__TEXT_B64__", text_b64)
    kernel_code = kernel_code.replace("__ARTHUR_URL__", arthur_url)
    kernel_code = kernel_code.replace("__ARTHUR_SHA256__", arthur_sha256)
    kernel_code = kernel_code.replace("__ARTHUR_TRANSCRIPT__", arthur_transcript)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run_firered.py").write_text(kernel_code, encoding="utf-8")

    meta = {
        "id": "davedavedavenm/firered-breakneck-audition",
        "title": "firered-breakneck-audition",
        "code_file": "run_firered.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (OUT / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Staged FireRedTTS3 Kaggle kernel at {OUT}")
    print(f"Kernel code size: {len(kernel_code):,} characters")


if __name__ == "__main__":
    main()
