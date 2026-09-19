"""
render_tough_irish_f5tts.py — F5-TTS Evaluation on Tough Irish Words

Evaluates F5-TTS (300M non-autoregressive flow-matching diffusion) on notorious Irish names & terms
using Cillian Murphy (Studio Dry reference, seed-locked):
- Pádraig Pearse, Seán MacDiarmada, nineteen-sixteen
- First Dáil Éireann, Eamon de Valera, Priomh-Aire
- Cathal Brugha, Cumann na mBan
- Dún Laoghaire, Portlaoise
- Taoiseach, Tánaiste, Ruairí Ó Brádaigh, Sinn Féin
- Westminster question inflection

Audio is mastered to EBU R128 (-20 LUFS) standard to match the Breeze and Qwen audition suite.
"""

import modal
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-f5tts-tough-irish")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "f5-tts>=0.1.0",
        "torch",
        "torchaudio",
        "soundfile>=0.13",
        "numpy"
    )
)


@app.cls(image=image, gpu="T4", timeout=600, scaledown_window=2)
class ToughIrishF5Producer:
    @modal.enter()
    def setup(self):
        import torch
        from f5_tts.api import F5TTS

        print(f"Loading F5-TTS on {torch.cuda.get_device_name(0)}...")
        self.f5 = F5TTS(device="cuda")
        self.sample_rate = 24000
        print("F5-TTS model loaded successfully!")

    @modal.method()
    def synthesize_chunks(
        self,
        label: str,
        chunks: list[str],
        ref_wav_bytes: bytes,
        ref_text: str,
        seed: int = 42
    ) -> dict:
        import numpy as np
        import soundfile as sf
        import os

        t0 = time.time()
        ref_path = f"/tmp/{label}_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        sr = self.sample_rate
        full_pieces = []

        print(f"[{label}] Synthesizing {len(chunks)} chunks with F5-TTS (seed={seed})...")
        for idx, chunk_text in enumerate(chunks, 1):
            print(f"[{label}][{idx}/{len(chunks)}] ({len(chunk_text)} chars): {chunk_text[:60]}...")
            chunk_wav_path = f"/tmp/{label}_chunk_{idx}.wav"

            wav, gen_sr, _ = self.f5.infer(
                ref_file=ref_path,
                ref_text=ref_text,
                gen_text=chunk_text,
                file_wave=chunk_wav_path,
                seed=seed
            )

            audio_data, file_sr = sf.read(chunk_wav_path)
            sr = file_sr
            full_pieces.append(audio_data)

            # Insert natural speech cadence pause (0.35s) between sentences
            pause_samples = int(0.35 * sr)
            full_pieces.append(np.zeros(pause_samples, dtype=np.float32))

            if os.path.exists(chunk_wav_path):
                os.remove(chunk_wav_path)

        full_audio = np.concatenate(full_pieces)
        duration_sec = round(len(full_audio) / sr, 2)
        gpu_time = round(time.time() - t0, 2)
        rtf = round(gpu_time / max(duration_sec, 0.01), 3)
        print(f"[{label}] Generated {duration_sec}s audio in {gpu_time}s GPU compute (RTF: {rtf})!")

        raw_wav = f"/tmp/{label}_raw.wav"
        mastered_wav = f"/tmp/{label}_mastered.wav"
        mastered_mp3 = f"/tmp/{label}_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)

        # Broadcast Mastering Chain: Clean lower mids, smooth highs, EBU R128 (-20 LUFS)
        af_filters = (
            "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
            "highshelf=f=7500:gain=-2.0:width=1.0,"
            "loudnorm=I=-20:TP=-2:LRA=11"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-af", af_filters,
            "-ar", str(sr),
            mastered_wav
        ], check=True, capture_output=True)

        subprocess.run([
            "ffmpeg", "-y", "-i", mastered_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            mastered_mp3
        ], check=True, capture_output=True)

        with open(mastered_mp3, "rb") as f:
            mastered_bytes = f.read()

        return {
            "mastered_bytes": mastered_bytes,
            "duration": duration_sec,
            "gpu_time": gpu_time,
            "rtf": rtf
        }


def chunk_text(text: str) -> list[str]:
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.", "IPP's", "RIC"):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    return [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    text_file = root / "fixtures" / "tough_irish_words.txt"
    text = text_file.read_text(encoding="utf-8")
    chunks = chunk_text(text)

    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
    cillian_ref_text = (
        "You find so much empathy in novels, because there you are putting yourself into "
        "somebody else's point of view, and I've always been a big reader."
    )

    producer = ToughIrishF5Producer()
    print(f"\n>>> Running F5-TTS Cillian Murphy on Tough Irish Words ({len(chunks)} chunks)...")
    res = producer.synthesize_chunks.remote(
        label="tough_irish_f5tts_cillian",
        chunks=chunks,
        ref_wav_bytes=cillian_wav.read_bytes(),
        ref_text=cillian_ref_text,
        seed=42
    )

    out_file = out_dir / "tough_irish_f5tts_cillian_mastered.mp3"
    out_file.write_bytes(res["mastered_bytes"])
    print(f"✓ F5-TTS Output saved: {out_file} ({len(res['mastered_bytes']):,} bytes, {res['duration']}s audio)")
    print(f"  GPU Time: {res['gpu_time']}s | RTF: {res['rtf']}")
