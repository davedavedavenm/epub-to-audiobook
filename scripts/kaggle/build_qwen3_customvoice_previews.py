from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "qwen3_customvoice_previews" / "kernel"
OUT.mkdir(parents=True, exist_ok=True)

KERNEL_CODE = r'''import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

WORK = Path("/kaggle/working")
OUT_DIR = WORK / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def sh(cmd):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True)

print("=== Checking CUDA ===")
assert torch.cuda.is_available(), "CUDA unavailable"
print(f"CUDA Device: {torch.cuda.get_device_name(0)}")

print("=== Installing Dependencies ===")
RUNTIME_SHA = "022e286b98fbec7e1e916cb940cdf532cd9f488e"
sh([sys.executable, "-m", "pip", "install", "-q",
    "soundfile>=0.13", "transformers>=4.45", "accelerate", "scipy",
    f"qwen-tts @ git+https://github.com/QwenLM/Qwen3-TTS.git@{RUNTIME_SHA}"])

print("=== Loading Qwen3-TTS 1.7B CustomVoice ===")
from qwen_tts import Qwen3TTSModel
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
model = Qwen3TTSModel.from_pretrained(
    MODEL_ID, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
)

supported_speakers = model.get_supported_speakers()
print("Supported speakers:", supported_speakers)

TEST_TEXT = (
    "Silicon Valley can be an amazingly drab place. "
    "The peninsula south of San Francisco has natural beauty, with rolling hills and coastal views, "
    "but you strain to see them beyond so many corporate parking lots. "
    "Mountain View and Menlo Park are bizarrely full of rug shops."
)

INSTRUCT = "Speak in a thoughtful, engaging, and measured tone suitable for an analytical non-fiction audiobook."

SPEAKERS_TO_TEST = ["ryan", "aiden", "uncle_fu", "vivian"]

for spk in SPEAKERS_TO_TEST:
    if spk not in supported_speakers:
        print(f"Speaker {spk} not in supported speakers, skipping")
        continue
    print(f"\n--- Generating CustomVoice Preview: {spk} ---")
    start = time.perf_counter()
    wavs, sr = model.generate_custom_voice(
        text=TEST_TEXT,
        speaker=spk,
        language="English",
        instruct=INSTRUCT,
        max_new_tokens=1024,
    )
    audio = np.asarray(wavs[0], dtype="float32").reshape(-1)
    dur = len(audio) / sr
    elapsed = time.perf_counter() - start
    print(f"Rendered {spk}: {dur:.2f}s audio in {elapsed:.2f}s (RTF {elapsed/dur:.2f})")
    
    wav_path = OUT_DIR / f"qwen3_customvoice_{spk.lower()}.wav"
    mp3_path = OUT_DIR / f"qwen3_customvoice_{spk.lower()}.mp3"
    sf.write(str(wav_path), audio, sr)
    sh(["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3_path)])

print("\n=== Previews Complete ===")
for f in sorted(OUT_DIR.iterdir()):
    print(f"  {f.name} ({f.stat().st_size:,} bytes)")
'''

def main():
    (OUT / "run_previews.py").write_text(KERNEL_CODE, encoding="utf-8")
    meta = {
        "id": "davedavedavedavenm/qwen3-customvoice-previews",
        "title": "qwen3-customvoice-previews",
        "code_file": "run_previews.py",
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
    print(f"Staged Qwen3 CustomVoice preview kernel at {OUT}")

if __name__ == "__main__":
    main()
