"""
render_qwen3_aiden_modal.py — Qwen3-TTS 1.7B CustomVoice Aiden Production on Modal

Model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
Speaker: "aiden" (Approved by Dave on 2026-09-18)
Steering Instruction: "Speak in a calm, thoughtful, engaging, and measured tone suitable for an analytical non-fiction audiobook."
Hardware: Nvidia L4 GPU (24GB VRAM) on Modal Cloud
Outputs:
1. Raw Aiden 192k MP3
2. Broadcast Mastered Aiden 192k MP3 (+2.2 dB @ 250Hz Warmth EQ, -3.5 dB @ 7.2kHz De-Esser, EBU R128 -20 LUFS)
"""

import modal
import os
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-qwen3-aiden-breakneck")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "soundfile>=0.13",
        "transformers>=4.45",
        "accelerate",
        "scipy",
        "torch",
        "numpy",
        "huggingface_hub"
    )
    .run_commands(
        "git clone https://github.com/QwenLM/Qwen3-TTS.git /root/Qwen3-TTS",
        "cd /root/Qwen3-TTS && pip install -e ."
    )
)

@app.cls(image=image, gpu="L4", timeout=600, scaledown_window=2)
class Qwen3AidenProducer:
    @modal.enter()
    def setup(self):
        import torch
        from qwen_tts import Qwen3TTSModel

        print("Loading Qwen3-TTS 1.7B CustomVoice into GPU...")
        self.model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map="cuda:0",
            dtype=torch.float16,
            attn_implementation="sdpa"
        )
        print("Qwen3-TTS CustomVoice loaded successfully!")

    @modal.method()
    def synthesize(self, chunks: list[str], instruct: str) -> dict:
        import numpy as np
        import soundfile as sf
        import time

        full_chunks = []
        sr = 24000
        t0 = time.time()

        print(f"Synthesizing {len(chunks)} chunks with Aiden (Instruction: {instruct[:50]}...)...")
        for i, chunk in enumerate(chunks):
            print(f"[{i+1}/{len(chunks)}] ({len(chunk)} chars): {chunk[:60]}...")
            wavs, gen_sr = self.model.generate_custom_voice(
                text=chunk,
                speaker="aiden",
                language="English",
                instruct=instruct,
                max_new_tokens=1024
            )
            audio = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            sr = gen_sr
            full_chunks.append(audio)

            # 350ms join pause between sentences
            pause_samples = int(0.35 * sr)
            full_chunks.append(np.zeros(pause_samples, dtype=np.float32))

        raw_audio = np.concatenate(full_chunks)
        duration_sec = round(len(raw_audio) / sr, 2)
        gpu_time = round(time.time() - t0, 2)
        print(f"Generated {duration_sec}s audio in {gpu_time}s GPU compute!")

        raw_wav = "/tmp/aiden_raw.wav"
        mastered_wav = "/tmp/aiden_mastered.wav"
        raw_mp3 = "/tmp/aiden_raw.mp3"
        mastered_mp3 = "/tmp/aiden_mastered.mp3"

        sf.write(raw_wav, raw_audio, sr)

        # 1. Encode Raw MP3 (192kbps)
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            raw_mp3
        ], check=True)

        # 2. Apply Broadcast Mastering Chain (Warmth EQ + De-Esser + EBU R128)
        af_filters = (
            "equalizer=f=250:width_type=o:width=1.2:g=2.2,"
            "highshelf=f=7200:gain=-3.5:width=1.0,"
            "loudnorm=I=-20:TP=-2:LRA=11"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-af", af_filters,
            "-ar", str(sr),
            mastered_wav
        ], check=True)

        subprocess.run([
            "ffmpeg", "-y", "-i", mastered_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            mastered_mp3
        ], check=True)

        with open(raw_mp3, "rb") as f:
            raw_bytes = f.read()
        with open(mastered_mp3, "rb") as f:
            mastered_bytes = f.read()

        return {
            "raw_bytes": raw_bytes,
            "mastered_bytes": mastered_bytes,
            "duration": duration_sec,
            "gpu_time": gpu_time
        }


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[2]
    text_file = root / "fixtures" / "breakneck_ch1_2pages_norm.txt"
    text = text_file.read_text(encoding="utf-8")

    # Split into clean sentence chunks
    protected = text
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?])\s+", protected)
        if item.strip()
    ]

    instruct = "Speak in a calm, thoughtful, engaging, and measured tone suitable for an analytical non-fiction audiobook."

    print(f"Submitting Qwen3 Aiden production job ({len(chunks)} chunks) to Modal L4 GPU...")
    res = Qwen3AidenProducer().synthesize.remote(chunks, instruct)

    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "breakneck_ch1_qwen3_aiden_raw.mp3"
    mastered_path = out_dir / "breakneck_ch1_qwen3_aiden_mastered.mp3"

    raw_path.write_bytes(res["raw_bytes"])
    mastered_path.write_bytes(res["mastered_bytes"])

    print(f"\nSUCCESS!")
    print(f"Raw MP3: {raw_path} ({len(res['raw_bytes']):,} bytes)")
    print(f"Mastered MP3: {mastered_path} ({len(res['mastered_bytes']):,} bytes)")
    print(f"Audio Duration: {res['duration']}s | GPU Wall Time: {res['gpu_time']}s")
