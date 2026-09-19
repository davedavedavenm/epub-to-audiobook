"""
render_tough_irish_cosyvoice.py — FunAudioLLM CosyVoice 3 (0.5B) Evaluation on Tough Irish Words

Evaluates Fun-CosyVoice3-0.5B-2512 on notorious Irish names & terms
using Cillian Murphy (Studio Dry reference):
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

app = modal.App("homelab-cosyvoice3-tough-irish")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1", "sox", "libsox-dev")
    .pip_install(
        "modelscope>=1.20.0",
        "torch",
        "torchaudio",
        "torchcodec",
        "setuptools<80.0.0",
        "openai-whisper",
        "soundfile>=0.13",
        "conformer==0.3.2",
        "gdown",
        "wget",
        "diffusers==0.29.0",
        "hydra-core==1.3.2",
        "HyperPyYAML==1.2.3",
        "inflect==7.3.1",
        "librosa==0.10.2",
        "lightning==2.2.4",
        "networkx==3.1",
        "omegaconf==2.3.0",
        "onnx>=1.16.0",
        "onnxruntime-gpu",
        "huggingface_hub>=0.25",
        "transformers>=4.45",
        "x-transformers",
        "pyworld",
        "wetext",
        "matplotlib",
        "pyarrow",
        "pydantic",
        "scipy",
        "numpy"
    )
    .run_commands(
        "git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /root/CosyVoice",
        "python3 -c \"from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir='/root/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B')\""
    )
)


@app.cls(image=image, gpu="T4", timeout=600, scaledown_window=2)
class ToughIrishCosyProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/CosyVoice" not in sys.path:
            sys.path.insert(0, "/root/CosyVoice")
        if "/root/CosyVoice/third_party/Matcha-TTS" not in sys.path:
            sys.path.insert(0, "/root/CosyVoice/third_party/Matcha-TTS")
        import torch
        from cosyvoice.cli.cosyvoice import AutoModel

        print(f"Loading CosyVoice 3 (0.5B) on {torch.cuda.get_device_name(0)}...")
        self.model = AutoModel(model_dir="/root/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B")
        # Ensure all submodules (especially Qwen2 backbone which defaults to bfloat16) are cast to float32
        self.model.model.llm.to(torch.float32)
        self.model.model.flow.to(torch.float32)
        self.model.model.hift.to(torch.float32)
        self.sample_rate = self.model.sample_rate
        print(f"CosyVoice 3 runtime ready (Sample Rate: {self.sample_rate}Hz)!")

    @modal.method()
    def synthesize_chunks(
        self,
        label: str,
        chunks: list[str],
        ref_wav_bytes: bytes,
        ref_text: str,
        speed: float = 1.0
    ) -> dict:
        import numpy as np
        import soundfile as sf
        import os

        t0 = time.time()
        ref_path = f"/tmp/{label}_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        prompt_text = "You are a helpful assistant.<|endofprompt|>" + ref_text
        sr = self.sample_rate
        full_pieces = []

        print(f"[{label}] Synthesizing {len(chunks)} chunks with CosyVoice 3...")
        for idx, chunk_text in enumerate(chunks, 1):
            print(f"[{label}][{idx}/{len(chunks)}] ({len(chunk_text)} chars): {chunk_text[:60]}...")
            
            chunk_audio_parts = []
            for out in self.model.inference_zero_shot(chunk_text, prompt_text, ref_path, stream=False, speed=speed):
                tts_speech = out["tts_speech"].squeeze().cpu().numpy()
                chunk_audio_parts.append(tts_speech)

            if chunk_audio_parts:
                chunk_pcm = np.concatenate(chunk_audio_parts)
                full_pieces.append(chunk_pcm)

                # Insert natural pause (0.35s) between sentences
                pause_samples = int(0.35 * sr)
                full_pieces.append(np.zeros(pause_samples, dtype=np.float32))

        if not full_pieces:
            raise RuntimeError(f"CosyVoice 3 produced no audio for {label}")

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

        if os.path.exists(ref_path):
            os.remove(ref_path)

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

    producer = ToughIrishCosyProducer()
    print(f"\n>>> Running CosyVoice 3 Cillian Murphy on Tough Irish Words ({len(chunks)} chunks)...")
    res = producer.synthesize_chunks.remote(
        label="tough_irish_cosyvoice3_cillian",
        chunks=chunks,
        ref_wav_bytes=cillian_wav.read_bytes(),
        ref_text=cillian_ref_text,
        speed=1.0
    )

    out_file = out_dir / "tough_irish_cosyvoice3_cillian_mastered.mp3"
    out_file.write_bytes(res["mastered_bytes"])
    print(f"✓ CosyVoice 3 Output saved: {out_file} ({len(res['mastered_bytes']):,} bytes, {res['duration']}s audio)")
    print(f"  GPU Time: {res['gpu_time']}s | RTF: {res['rtf']}")
