"""
render_tough_irish_breeze.py — Breeze TTS 2 (3.5B) Tough Irish Words Evaluation

Evaluates Cillian Murphy (Studio Dry, Seed-Locked) and Liam on notorious Irish Gaelic names & terms:
- Pádraig Pearse, Seán MacDiarmada, nineteen-sixteen
- Dáil Éireann, Eamon de Valera, Priomh-Aire
- Cathal Brugha, Cumann na mBan
- Dún Laoghaire, Portlaoise
- Taoiseach, Tánaiste, Ruairí Ó Brádaigh, Sinn Féin
- Rhetorical Question with Inquisitive Uptalk

Fixes applied based on Dave's listening feedback:
1. FIXED SEED (seed=42): Eliminates voice timbre and pitch drift across sentences.
2. DRY REFERENCE (cillian_irish_dry.wav): Sliced & filtered to remove boxy room slap-back and room echo.
3. CALIBRATED GUIDANCE (guidance_scale=2.5): Eliminates latent warbling and oversaturation.
"""

import modal
import os
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-breeze-tough-irish")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1", "sox", "libsox-fmt-all")
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

@app.cls(image=image, gpu=["A10G", "L4"], timeout=1200, scaledown_window=180)
class ToughIrishBreezeProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from pathlib import Path
        from breeze_infer.runtime import load_runtime, resolve_device, update_generation_config_for_breeze
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        print("Loading Breeze TTS 2 (3.5B) into GPU memory...")
        self.tokenizer, self.model, self.audio_tokenizer = load_runtime(
            Path("/root/breeze-model"),
            device=resolve_device(),
            attn_implementation="sdpa",
        )
        update_generation_config_for_breeze(self.model)
        config = FastStreamingConfig(
            max_new_tokens=1500,
            max_seq_len=2048,
            repetition_penalty=1.15,
        )
        self.runtime = FastBreezeStreamingRuntime(
            self.model, self.audio_tokenizer, config, tokenizer=self.tokenizer
        )
        self.sample_rate = self.runtime.sample_rate
        print(f"Breeze TTS 2 runtime ready (Sample Rate: {self.sample_rate}Hz)!")

    @modal.method()
    def synthesize(self, label: str, chunks: list[str], ref_wav_bytes: bytes, ref_text: str, instruction: str) -> dict:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf
        import time
        import re

        ref_path = f"/tmp/{label}_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        t0 = time.time()
        pieces = []
        sr = self.sample_rate

        # Fixed seed=42 locks vocal identity across ALL sentences
        LOCKED_SEED = 42

        print(f"[{label}] Synthesizing {len(chunks)} chunks (seed locked to {LOCKED_SEED})...")
        for idx, c in enumerate(chunks, 1):
            chunk_instruction = instruction
            if re.search(r'\?[’”"\'\s]*$', c):
                chunk_instruction = instruction + " Deliver with an inquisitive, skeptical tone, raising pitch in an uptalk inflection at the end of the question."
            
            print(f"[{label}][{idx}/{len(chunks)}] ({len(c)} chars): {c[:60]}...")
            req = {
                "id": f"{label}-chunk-{idx}",
                "text": c,
                "instruction": chunk_instruction,
                "speaker": "S0",
                "ref_audio_path": ref_path,
                "ref_text": ref_text,
            }
            set_all_seeds(LOCKED_SEED)
            inputs = prepare_inputs(
                self.tokenizer,
                self.audio_tokenizer,
                self.model,
                [req],
                get_template("ref_edit_tata"),
                guidance_scale=2.5,  # Calibrated for natural speech without warble
                guidance_scale_ref=None,
                guidance_scale_ins=None,
            )

            audio_parts = []
            for audio_chunk in self.runtime.iter_audio_chunks(
                inputs, request_id=f"{label}-chunk-{idx}", seed=LOCKED_SEED
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
        print(f"[{label}] Generated {duration_sec}s audio in {gpu_time}s GPU compute!")

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

    text = (root / "fixtures" / "tough_irish_words.txt").read_text(encoding="utf-8")
    chunks = chunk_text(text)

    # 1. Cillian Murphy (Studio Dry, Seed-Locked)
    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
    cillian_ref_text = (
        "You find so much empathy in novels, because there you are putting yourself into "
        "somebody else's point of view, and I've always been a big reader."
    )
    cillian_instruction = (
        "Read in a calm, thoughtful, authentic Irish accent with measured literary pacing and solemn gravitas "
        "suitable for an Irish history audiobook."
    )

    producer = ToughIrishBreezeProducer()
    print(f"\n>>> Running Breeze 2 Cillian Murphy (Studio Dry & Seed-Locked) on Tough Irish Words ({len(chunks)} chunks)...")
    res_cillian = producer.synthesize.remote(
        "tough_irish_breeze_cillian",
        chunks,
        cillian_wav.read_bytes(),
        cillian_ref_text,
        cillian_instruction
    )

    out_cillian = out_dir / "tough_irish_breeze_cillian_mastered.mp3"
    out_cillian.write_bytes(res_cillian["mastered_bytes"])
    print(f"✓ Cillian Output saved: {out_cillian} ({len(res_cillian['mastered_bytes']):,} bytes, {res_cillian['duration']}s audio)")
