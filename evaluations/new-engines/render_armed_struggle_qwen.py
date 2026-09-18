"""
render_armed_struggle_qwen.py — Qwen3-TTS 1.7B CustomVoice Aiden with LLM Emotional Direction

Tests Aiden on Armed Struggle: The Story of the IRA
Evaluates:
1. Dynamic LLM Emotional Direction per chunk (gravitas, dramatic tension, sharp inquisitive uptalk)
2. Irish phonetics and hyphenated year normalization
3. Broadcast mastering chain (Warmth EQ + De-Esser + EBU R128)
"""

import modal
import os
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-qwen3-armed-struggle")

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
class ArmedStruggleQwenProducer:
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
    def synthesize(self, items: list[dict]) -> dict:
        import numpy as np
        import soundfile as sf
        import time

        full_chunks = []
        sr = 24000
        t0 = time.time()

        print(f"Synthesizing {len(items)} chunks with Aiden LLM Emotional Direction...")
        for i, it in enumerate(items, 1):
            text = it["text"]
            instruct = it["instruction"]
            print(f"[{i}/{len(items)}] ({len(text)} chars) Instruction: {instruct}")
            print(f"   Text: {text[:60]}...")
            wavs, gen_sr = self.model.generate_custom_voice(
                text=text,
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

        raw_wav = "/tmp/qwen_armed_raw.wav"
        mastered_wav = "/tmp/qwen_armed_mastered.wav"
        mastered_mp3 = "/tmp/qwen_armed_mastered.mp3"

        sf.write(raw_wav, raw_audio, sr)

        # Broadcast Mastering Chain (Warmth EQ + De-Esser + EBU R128)
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

        with open(mastered_mp3, "rb") as f:
            mastered_bytes = f.read()

        return {
            "mastered_bytes": mastered_bytes,
            "duration": duration_sec,
            "gpu_time": gpu_time
        }


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    llm_text = (root / "fixtures" / "armed_struggle_llm_norm.txt").read_text(encoding="utf-8")

    # Segment sentences
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', llm_text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.", "IPP's", "RIC"):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]

    # LLM Emotional Direction Mapping
    items = []
    for c in chunks:
        if c.endswith("?"):
            inst = "Deliver with an intense, skeptical tone and an inquisitive uptalk inflection at the end of the question."
        elif "rebel government" in c or "war against the British" in c:
            inst = "Speak with dramatic tension, dark solemnity, and restrained historical power."
        elif "Doyle Air-un" in c or "First Doyle" in c:
            inst = "Deliver with authoritative historical gravitas and clear, dignified cadence."
        elif "Shin Fane" in c or "nineteen-sixteen" in c:
            inst = "Speak in a compelling, measured storytelling voice with rich vocal texture."
        else:
            inst = "Speak in an intelligent, engaging, and measured tone suitable for a serious historical audiobook."
        items.append({"text": c, "instruction": inst})

    producer = ArmedStruggleQwenProducer()
    print(f"\n>>> Running Aiden Qwen3-TTS with LLM Emotional Direction ({len(items)} chunks)...")
    res = producer.synthesize.remote(items)

    out_path = out_dir / "armed_struggle_qwen3_aiden_emotive_mastered.mp3"
    out_path.write_bytes(res["mastered_bytes"])
    print(f"✓ Output saved: {out_path} ({len(res['mastered_bytes']):,} bytes, {res['duration']}s audio)")
