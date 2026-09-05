#!/usr/bin/env python3
"""Stage the Breeze TTS 2 Breakneck Chapter 1 (Pages 1-2) Kaggle T4 evaluation gate.

Builds a self-contained Kaggle kernel directory under scratch/breeze_breakneck/kernel/
that evaluates Breeze TTS 2 (3.5B) across two arms:
1. Voice Design: British male narrator prompt (CFG 4)
2. Voice Direction: Arthur clone + natural instruction (CFG 4)

Both arms render the exact 2-page normalized excerpt of Breakneck Chapter 1.
Outputs WAV, 128k MP3, and JSON evidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "breeze_breakneck" / "kernel"
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
ARTHUR_URL = "https://media.githubusercontent.com/media/davedavedavenm/epub-to-audiobook/master/chatterbox/voices/uk_male_minter.wav"
ARTHUR_TRANSCRIPT = (
    '"I know that," snapped Bertram. "Not that it would make any difference if she stayed," '
    'pursued the relentless George. "She flies higher than the paper trade, my boy." '
    '"Hang her!" said Bertram. "It would make it more interesting for me," I ventured to observe.'
)

KERNEL_TEMPLATE = r'''import base64
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
REF_WAV = Path("/tmp/arthur.wav")

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
sh([sys.executable, "-m", "pip", "install", "-q",
    "soundfile>=0.13", "huggingface_hub>=0.25", "transformers>=4.45",
    "qwen-tts==0.1.1", "accelerate", "scipy"])

print("=== Cloning Breeze TTS 2 Repo ===")
BREEZE_REPO = Path("/tmp/breeze-tts")
if not BREEZE_REPO.exists():
    sh(["git", "clone", "https://github.com/breezeblue-ai/breeze-tts.git", str(BREEZE_REPO)])

sys.path.insert(0, str(BREEZE_REPO))

print("=== Downloading Breeze TTS 2 Model Weights ===")
from huggingface_hub import snapshot_download
MODEL_DIR = Path("/tmp/breeze-model")
snapshot_download("BreezeBlue/Breeze-TTS-2", local_dir=str(MODEL_DIR))

print("=== Loading Breeze Runtime ===")
from breeze_infer.runtime import (
    load_runtime,
    resolve_device,
    set_all_seeds,
    update_generation_config_for_breeze,
)
from breeze_infer.templates import get_template, prepare_inputs
from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

tokenizer, model, audio_tokenizer = load_runtime(
    MODEL_DIR,
    device=resolve_device(),
    attn_implementation="eager",
)
update_generation_config_for_breeze(model)

config = FastStreamingConfig(
    max_new_tokens=1500,
    max_seq_len=2048,
    repetition_penalty=1.1,
)
runtime = FastBreezeStreamingRuntime(
    model, audio_tokenizer, config, tokenizer=tokenizer
)
sample_rate = runtime.sample_rate
print(f"Breeze runtime initialized. Sample rate: {sample_rate}")

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

arms = [
    {
        "name": "breeze_voice_design_uk_male",
        "label": "Breeze TTS 2 — Voice Design (British Male Narrator)",
        "instruction": "A British male narrator with an intelligent, clear voice, speaking thoughtfully at a measured, engaging pace for a non-fiction book.",
        "ref_audio": None,
        "ref_text": None,
        "cfg_scale": 4.0,
        "seed": 42,
    },
    {
        "name": "breeze_voice_direction_arthur",
        "label": "Breeze TTS 2 — Voice Direction (Arthur Clone)",
        "instruction": "Speak clearly and naturally with measured pace and thoughtful delivery.",
        "ref_audio": str(REF_WAV),
        "ref_text": ARTHUR_TRANSCRIPT,
        "cfg_scale": 4.0,
        "seed": 42,
    }
]

for arm in arms:
    print(f"\n==========================================")
    print(f"Starting Arm: {arm['name']} ({arm['label']})")
    print(f"==========================================")
    started = time.perf_counter()
    pieces = []
    chunk_timings = []

    for idx, c in enumerate(chunks, 1):
        c_start = time.perf_counter()
        req = {
            "id": f"chunk-{idx}",
            "text": c,
            "instruction": arm["instruction"],
            "speaker": "S0",
        }
        template_name = "tts_instruction"
        if arm["ref_audio"]:
            req["ref_audio_path"] = arm["ref_audio"]
            req["ref_text"] = arm["ref_text"]
            template_name = "ref_edit_tata"

        set_all_seeds(arm["seed"])
        inputs = prepare_inputs(
            tokenizer,
            audio_tokenizer,
            model,
            [req],
            get_template(template_name),
            guidance_scale=arm["cfg_scale"],
            guidance_scale_ref=None,
            guidance_scale_ins=None,
        )

        audio_parts = []
        for audio_chunk in runtime.iter_audio_chunks(
            inputs, request_id=f"chunk-{idx}", seed=arm["seed"]
        ):
            audio_parts.append(audio_chunk.audio)

        if not audio_parts:
            print(f"  Warning: chunk {idx} generated empty audio!")
            continue

        chunk_pcm = np.concatenate(audio_parts)
        pieces.append(chunk_pcm)
        c_elapsed = time.perf_counter() - c_start
        c_dur = len(chunk_pcm) / sample_rate
        chunk_timings.append({"chunk": idx, "wall_s": round(c_elapsed, 2), "duration_s": round(c_dur, 2)})
        print(f"  Chunk {idx}/{len(chunks)} rendered in {c_elapsed:.2f}s (audio: {c_dur:.2f}s, RTF: {c_elapsed/c_dur:.2f})")

    full_audio = np.concatenate(pieces)
    total_dur = len(full_audio) / sample_rate
    wall_total = time.perf_counter() - started
    overall_rtf = wall_total / total_dur

    wav_out = OUT_DIR / f"{arm['name']}.wav"
    mp3_out = OUT_DIR / f"{arm['name']}.mp3"
    sf.write(str(wav_out), full_audio, sample_rate)

    # Encode 128k MP3 via ffmpeg
    sh(["ffmpeg", "-y", "-i", str(wav_out), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3_out)])

    report = {
        "arm": arm["name"],
        "label": arm["label"],
        "instruction": arm["instruction"],
        "cfg_scale": arm["cfg_scale"],
        "seed": arm["seed"],
        "sample_rate": sample_rate,
        "total_duration_s": round(total_dur, 2),
        "wall_time_s": round(wall_total, 2),
        "overall_rtf": round(overall_rtf, 3),
        "chunk_count": len(chunks),
        "chunk_timings": chunk_timings,
        "vram_allocated_mb": round(torch.cuda.memory_allocated() / (1024**2), 1),
        "vram_reserved_mb": round(torch.cuda.memory_reserved() / (1024**2), 1),
    }
    (OUT_DIR / f"{arm['name']}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Finished {arm['name']}: audio={total_dur:.2f}s, wall={wall_total:.2f}s, RTF={overall_rtf:.3f}")

print("\n=== All Arms Complete ===")
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
    (OUT / "run_breeze.py").write_text(kernel_code, encoding="utf-8")

    meta = {
        "id": "davedavedavedavenm/breeze2-breakneck-audition",
        "title": "breeze2-breakneck-audition",
        "code_file": "run_breeze.py",
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
    print(f"Staged Breeze TTS 2 Kaggle kernel at {OUT}")
    print(f"Kernel code size: {len(kernel_code):,} characters")


if __name__ == "__main__":
    main()
