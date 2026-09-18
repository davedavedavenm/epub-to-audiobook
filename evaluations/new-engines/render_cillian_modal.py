"""
render_cillian_modal.py — Breeze TTS 2 (3.5B) Cillian Murphy Irish Narration on Modal L4 GPU

Clones Cillian Murphy from a CBS broadcast interview (chatterbox/voices/cillian_irish.wav).
Synthesizes the First Dail excerpt from Armed Struggle: The Story of the IRA:
- Raw Irish proper nouns: Dáil Éireann, Cathal Brugha, Sinn Féin
- Hyphenated years: nineteen-seventeen, nineteen-sixteen, nineteen-nineteen to twenty-one
- Quizzical uptalk on rhetorical question: "then where did that leave British legitimacy?"
- Broadcast mastering: Warmth EQ + De-Esser + EBU R128 (-20 LUFS)
"""

import modal
import os
import re
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-breeze-cillian-armed-struggle")

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
class CillianBreezeProducer:
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
        import re

        ref_path = "/tmp/cillian_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        t0 = time.time()
        pieces = []
        sr = self.sample_rate

        print(f"Synthesizing {len(chunks)} chunks with Cillian Murphy Voice Direction...")
        for idx, c in enumerate(chunks, 1):
            chunk_instruction = instruction
            # Robust interrogative uptalk steering
            if re.search(r'\?[’”"\'\s]*$', c):
                chunk_instruction = instruction + " Deliver with an inquisitive, skeptical tone, raising pitch in an uptalk inflection at the end of the question."
            
            print(f"[{idx}/{len(chunks)}] ({len(c)} chars): {c[:60]}...")
            req = {
                "id": f"chunk-{idx}",
                "text": c,
                "instruction": chunk_instruction,
                "speaker": "S0",
                "ref_audio_path": ref_path,
                "ref_text": ref_text,
            }
            set_all_seeds(42 + idx)
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
                inputs, request_id=f"chunk-{idx}", seed=42 + idx
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

        raw_wav = "/tmp/cillian_raw.wav"
        mastered_wav = "/tmp/cillian_mastered.wav"
        mastered_mp3 = "/tmp/cillian_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)

        # Broadcast Mastering Chain (Warmth EQ + De-Esser + EBU R128)
        af_filters = (
            "equalizer=f=220:width_type=o:width=1.2:g=1.5,"
            "highshelf=f=7500:gain=-2.5:width=1.0,"
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

    text = (root / "fixtures" / "armed_struggle_hybrid_best.txt").read_text(encoding="utf-8")
    chunks = chunk_text(text)

    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish.wav"
    cillian_ref_text = (
        "You find so much empathy in novels, you know, because there you are putting yourself into "
        "somebody else's point of view and I've always been a big reader. When a movie can connect with someone "
        "and they feel seen or feel heard or a novel can change somebody's life or piece of music and album can "
        "change someone's life and I've had all that happen to me and that's the power of good art I think."
    )
    instruction = (
        "Read in a calm, thoughtful, authentic Irish accent with measured literary pacing and solemn gravitas "
        "suitable for an Irish history audiobook."
    )

    producer = CillianBreezeProducer()
    print(f"\n>>> Running Cillian Murphy (Breeze 2) on Armed Struggle ({len(chunks)} chunks)...")
    res = producer.synthesize.remote(
        chunks,
        cillian_wav.read_bytes(),
        cillian_ref_text,
        instruction
    )

    out_path = out_dir / "armed_struggle_breeze_cillian_irish_mastered.mp3"
    out_path.write_bytes(res["mastered_bytes"])
    print(f"✓ Output saved: {out_path} ({len(res['mastered_bytes']):,} bytes, {res['duration']}s audio)")
