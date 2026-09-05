#!/usr/bin/env python3
"""Stage the Qwen3-TTS 1.7B Breakneck Chapter 1 (Pages 1-2) Kaggle T4 evaluation gate.

Builds a self-contained Kaggle kernel directory under scratch/qwen3_breakneck/kernel/
that evaluates Qwen3-TTS 1.7B Base with Arthur reference clone on the exact
2-page normalized excerpt of Breakneck Chapter 1.
Outputs WAV, 128k MP3, and JSON evidence.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "qwen3_breakneck" / "kernel"
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
ARTHUR_URL = "https://media.githubusercontent.com/media/davedavedavenm/epub-to-audiobook/master/chatterbox/voices/uk_male_minter.wav"
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
vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
print(f"Total VRAM: {vram_gb:.2f} GB")

print("=== Downloading Reference Audio ===")
urllib.request.urlretrieve(ARTHUR_URL, str(REF_WAV))
raw_ref = REF_WAV.read_bytes()
assert hashlib.sha256(raw_ref).hexdigest() == ARTHUR_SHA256, "Reference WAV hash mismatch"
print(f"Reference WAV verified ({len(raw_ref):,} bytes)")

print("=== Installing Dependencies ===")
RUNTIME_SHA = "022e286b98fbec7e1e916cb940cdf532cd9f488e"
sh([sys.executable, "-m", "pip", "install", "-q",
    "soundfile>=0.13", "transformers>=4.45", "accelerate", "scipy",
    f"qwen-tts @ git+https://github.com/QwenLM/Qwen3-TTS.git@{RUNTIME_SHA}"])

print("=== Loading Qwen3-TTS Model ===")
from qwen_tts import Qwen3TTSModel
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
model = Qwen3TTSModel.from_pretrained(
    MODEL_ID, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
)
print("Model loaded.")

prompt = model.create_voice_clone_prompt(
    ref_audio=str(REF_WAV), ref_text=ARTHUR_TRANSCRIPT, x_vector_only_mode=False
)
print("Voice clone prompt created.")

def sentence_chunks(text: str) -> list[str]:
    protected = text
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?])\s+", protected)
        if item.strip()
    ]
    return chunks

chunks = sentence_chunks(BREAKNECK_TEXT)
print(f"Total sentence chunks: {len(chunks)}")
for i, c in enumerate(chunks, 1):
    print(f"  [{i}/{len(chunks)}] ({len(c)} chars) {c[:60]}...")

print(f"\n==========================================")
print(f"Starting Qwen3-TTS 1.7B Arthur Render")
print(f"==========================================")
started = time.perf_counter()
pieces = []
chunk_timings = []
sample_rate = 24000

for idx, c in enumerate(chunks, 1):
    c_start = time.perf_counter()
    torch.manual_seed(12345 + idx)
    torch.cuda.manual_seed_all(12345 + idx)
    wavs, sr = model.generate_voice_clone(
        text=c, language="English", voice_clone_prompt=prompt,
        max_new_tokens=4096, do_sample=True, top_k=50, top_p=1.0,
        temperature=0.9, repetition_penalty=1.05,
        subtalker_dosample=True, subtalker_top_k=50, subtalker_top_p=1.0,
        subtalker_temperature=0.9
    )
    sample_rate = sr
    audio = np.asarray(wavs[0], dtype="float32").reshape(-1)
    del wavs
    gc.collect()
    torch.cuda.empty_cache()

    pieces.append(audio)
    c_elapsed = time.perf_counter() - c_start
    c_dur = len(audio) / sample_rate
    chunk_timings.append({"chunk": idx, "wall_s": round(c_elapsed, 2), "duration_s": round(c_dur, 2)})
    print(f"  Chunk {idx}/{len(chunks)} rendered in {c_elapsed:.2f}s (audio: {c_dur:.2f}s, RTF: {c_elapsed/c_dur:.2f})")

full_audio = np.concatenate(pieces)
total_dur = len(full_audio) / sample_rate
wall_total = time.perf_counter() - started
overall_rtf = wall_total / total_dur

wav_out = OUT_DIR / "qwen3_breakneck_ch1_arthur.wav"
mp3_out = OUT_DIR / "qwen3_breakneck_ch1_arthur.mp3"
sf.write(str(wav_out), full_audio, sample_rate)

# Encode 128k MP3 via ffmpeg
sh(["ffmpeg", "-y", "-i", str(wav_out), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3_out)])

report = {
    "engine": "Qwen3-TTS 12Hz 1.7B Base",
    "arm": "qwen3_breakneck_ch1_arthur",
    "voice": "arthur",
    "sample_rate": sample_rate,
    "total_duration_s": round(total_dur, 2),
    "wall_time_s": round(wall_total, 2),
    "overall_rtf": round(overall_rtf, 3),
    "chunk_count": len(chunks),
    "chunk_timings": chunk_timings,
    "vram_allocated_mb": round(torch.cuda.memory_allocated() / (1024**2), 1),
    "vram_reserved_mb": round(torch.cuda.memory_reserved() / (1024**2), 1),
}
(OUT_DIR / "qwen3_breakneck_ch1_arthur.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Finished Qwen3: audio={total_dur:.2f}s, wall={wall_total:.2f}s, RTF={overall_rtf:.3f}")

print("\n=== All Done ===")
for f in sorted(OUT_DIR.iterdir()):
    print(f"  {f.name} ({f.stat().st_size:,} bytes)")
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
    (OUT / "run_qwen3.py").write_text(kernel_code, encoding="utf-8")

    meta = {
        "id": "davedavedavedavenm/qwen3-breakneck-audition",
        "title": "qwen3-breakneck-audition",
        "code_file": "run_qwen3.py",
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
    print(f"Staged Qwen3-TTS Kaggle kernel at {OUT}")
    print(f"Kernel code size: {len(kernel_code):,} characters")


if __name__ == "__main__":
    main()
