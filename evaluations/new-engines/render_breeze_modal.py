"""
render_breeze_modal.py — Breeze TTS 2 (3.5B) Voice Direction on Modal GPU

Model: BreezeBlue/Breeze-TTS-2 (3.5B)
Voice Direction: Cloned Arthur (uk_male_minter.wav)
Hardware: Nvidia L4 GPU (24GB VRAM) on Modal Cloud
Outputs:
1. Raw Breeze Arthur 192k MP3
2. Broadcast Mastered Breeze Arthur 192k MP3 (+2.2 dB @ 250Hz Warmth EQ, -3.5 dB @ 7.2kHz De-Esser, EBU R128 -20 LUFS)
"""

import modal
import os
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-breeze2-arthur-breakneck")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "soundfile>=0.13",
        "huggingface_hub[cli]>=0.25",
        "transformers>=4.45",
        "qwen-tts==0.1.1",
        "accelerate",
        "scipy",
        "torch",
        "numpy"
    )
    .run_commands(
        "git clone https://github.com/breezeblue-ai/breeze-tts.git /root/breeze-tts",
        "huggingface-cli download BreezeBlue/Breeze-TTS-2 --local-dir /root/breeze-model"
    )
)

@app.cls(image=image, gpu="L4", timeout=900, scaledown_window=2)
class BreezeArthurProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import load_runtime, resolve_device, update_generation_config_for_breeze
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        print("Loading Breeze TTS 2 (3.5B) into GPU memory...")
        self.tokenizer, self.model, self.audio_tokenizer = load_runtime(
            "/root/breeze-model",
            device=resolve_device(),
            attn_implementation="sdpa",
        )
        update_generation_config_for_breeze(self.model)
        config = FastStreamingConfig(
            max_new_tokens=1500,
            max_seq_len=2048,
            repetition_penalty=1.1,
        )
        self.runtime = FastBreezeStreamingRuntime(
            self.model, self.audio_tokenizer, config, tokenizer=self.tokenizer
        )
        self.sample_rate = self.runtime.sample_rate
        print(f"Breeze TTS 2 runtime ready (Sample Rate: {self.sample_rate}Hz)!")

    @modal.method()
    def synthesize(self, chunks: list[str], ref_wav_bytes: bytes, ref_text: str, instruction: str) -> dict:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf
        import time

        ref_path = "/tmp/arthur_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        t0 = time.time()
        pieces = []
        sr = self.sample_rate

        print(f"Synthesizing {len(chunks)} chunks with Breeze 2 Voice Direction (Arthur)...")
        for idx, c in enumerate(chunks, 1):
            print(f"[{idx}/{len(chunks)}] ({len(c)} chars): {c[:60]}...")
            req = {
                "id": f"chunk-{idx}",
                "text": c,
                "instruction": instruction,
                "speaker": "S0",
                "ref_audio_path": ref_path,
                "ref_text": ref_text,
            }
            set_all_seeds(42)
            inputs = prepare_inputs(
                self.tokenizer,
                self.audio_tokenizer,
                self.model,
                [req],
                get_template("ref_edit_tata"),
                guidance_scale=4.0,
                guidance_scale_ref=None,
                guidance_scale_ins=None,
            )

            audio_parts = []
            for audio_chunk in self.runtime.iter_audio_chunks(
                inputs, request_id=f"chunk-{idx}", seed=42
            ):
                audio_parts.append(audio_chunk.audio)

            if audio_parts:
                chunk_pcm = np.concatenate(audio_parts)
                pieces.append(chunk_pcm)
                pause_samples = int(0.35 * sr)
                pieces.append(np.zeros(pause_samples, dtype=np.float32))

        full_audio = np.concatenate(pieces)
        duration_sec = round(len(full_audio) / sr, 2)
        gpu_time = round(time.time() - t0, 2)
        print(f"Generated {duration_sec}s audio in {gpu_time}s GPU compute!")

        raw_wav = "/tmp/breeze_raw.wav"
        mastered_wav = "/tmp/breeze_mastered.wav"
        raw_mp3 = "/tmp/breeze_raw.mp3"
        mastered_mp3 = "/tmp/breeze_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)

        # 1. Raw MP3
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            raw_mp3
        ], check=True)

        # 2. Mastered MP3
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

    ref_wav_file = root / "chatterbox" / "voices" / "uk_male_minter.wav"
    assert ref_wav_file.exists(), f"Missing reference WAV: {ref_wav_file}"
    ref_wav_bytes = ref_wav_file.read_bytes()

    ref_text = (
        '"I know that," snapped Bertram. "Not that it would make any difference if she stayed," '
        'pursued the relentless George. "She flies higher than the paper trade, my boy." '
        '"Hang her!" said Bertram. "It would make it more interesting for me," I ventured to observe.'
    )

    instruction = "Read in an intelligent, clear British accent at a measured, engaging pace for an analytical non-fiction audiobook."

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

    print(f"Submitting Breeze 2 Arthur production job ({len(chunks)} chunks) to Modal L4 GPU...")
    res = BreezeArthurProducer().synthesize.remote(chunks, ref_wav_bytes, ref_text, instruction)

    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "breakneck_ch1_breeze_arthur_modal_raw.mp3"
    mastered_path = out_dir / "breakneck_ch1_breeze_arthur_modal_mastered.mp3"

    raw_path.write_bytes(res["raw_bytes"])
    mastered_path.write_bytes(res["mastered_bytes"])

    print(f"\nSUCCESS!")
    print(f"Raw MP3: {raw_path} ({len(res['raw_bytes']):,} bytes)")
    print(f"Mastered MP3: {mastered_path} ({len(res['mastered_bytes']):,} bytes)")
    print(f"Audio Duration: {res['duration']}s | GPU Wall Time: {res['gpu_time']}s")
