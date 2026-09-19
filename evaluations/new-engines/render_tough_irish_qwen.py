"""
render_tough_irish_qwen.py — Qwen3-TTS 1.7B Evaluation on Tough Irish Words

Evaluates:
1. Qwen3-TTS 1.7B Base (Zero-Shot Clone of Cillian Murphy using cillian_irish_dry.wav)
2. Qwen3-TTS 1.7B CustomVoice Aiden (with scene-by-scene dynamic emotional direction)

Text: fixtures/tough_irish_words.txt (Taoiseach, Tánaiste, Dún Laoghaire, Portlaoise, Cathal Brugha, Cumann na mBan, etc.)
"""

import modal
import re
import subprocess
from pathlib import Path

app = modal.App("homelab-qwen3-tough-irish")

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

@app.cls(image=image, gpu=["A10G", "L4"], timeout=1200, scaledown_window=180)
class ToughIrishQwenProducer:
    @modal.enter()
    def setup(self):
        import torch
        from qwen_tts import Qwen3TTSModel

        print("Loading Qwen3-TTS models into GPU...")
        self.aiden_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map="cuda:0",
            dtype=torch.float16,
            attn_implementation="sdpa"
        )
        print("Qwen3-TTS CustomVoice loaded successfully!")

    @modal.method()
    def synthesize_aiden(self, items: list[dict]) -> dict:
        import numpy as np
        import soundfile as sf

        full_chunks = []
        sr = 24000

        print(f"[Aiden] Synthesizing {len(items)} chunks with dynamic LLM emotion steering...")
        for i, it in enumerate(items, 1):
            text = it["text"]
            instruct = it["instruction"]
            print(f"[Aiden][{i}/{len(items)}] ({len(text)} chars) Instruction: {instruct}")
            print(f"   Text: {text[:60]}...")
            wavs, gen_sr = self.aiden_model.generate_custom_voice(
                text=text,
                speaker="aiden",
                language="English",
                instruct=instruct,
                max_new_tokens=1024
            )
            audio = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            sr = gen_sr
            full_chunks.append(audio)
            pause_samples = int(0.35 * sr)
            full_chunks.append(np.zeros(pause_samples, dtype=np.float32))

        raw_audio = np.concatenate(full_chunks)
        duration = round(len(raw_audio) / sr, 2)

        raw_wav = "/tmp/qwen_aiden_raw.wav"
        mastered_wav = "/tmp/qwen_aiden_mastered.wav"
        mastered_mp3 = "/tmp/qwen_aiden_mastered.mp3"

        sf.write(raw_wav, raw_audio, sr)

        af_filters = (
            "equalizer=f=220:width_type=o:width=1.2:g=1.5,"
            "highshelf=f=7200:gain=-3.0:width=1.0,"
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
            "duration": duration
        }

    @modal.method()
    def synthesize_cillian_clone(self, chunks: list[str], ref_wav_bytes: bytes, ref_text: str) -> dict:
        import torch
        from qwen_tts import Qwen3TTSModel
        import numpy as np
        import soundfile as sf

        print("Loading Qwen3-TTS 1.7B Base model for Cillian Murphy zero-shot clone...")
        # Free CustomVoice VRAM if needed
        del self.aiden_model
        torch.cuda.empty_cache()

        base_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map="cuda:0",
            dtype=torch.float16,
            attn_implementation="sdpa"
        )

        ref_path = "/tmp/cillian_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        print(f"Building voice clone prompt from {ref_path} ({len(ref_text)} chars ref text)...")
        prompt = base_model.create_voice_clone_prompt(
            ref_audio=ref_path,
            ref_text=ref_text,
            x_vector_only_mode=False
        )

        full_chunks = []
        sr = 24000
        print(f"[Qwen Cillian Clone] Synthesizing {len(chunks)} chunks...")
        for i, text in enumerate(chunks, 1):
            print(f"[Qwen Cillian Clone][{i}/{len(chunks)}] ({len(text)} chars): {text[:60]}...")
            wavs, gen_sr = base_model.generate_voice_clone(
                text=text,
                language="English",
                voice_clone_prompt=prompt,
                max_new_tokens=1024
            )
            audio = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            sr = gen_sr
            full_chunks.append(audio)
            pause_samples = int(0.35 * sr)
            full_chunks.append(np.zeros(pause_samples, dtype=np.float32))

        raw_audio = np.concatenate(full_chunks)
        duration = round(len(raw_audio) / sr, 2)

        raw_wav = "/tmp/qwen_cillian_raw.wav"
        mastered_wav = "/tmp/qwen_cillian_mastered.wav"
        mastered_mp3 = "/tmp/qwen_cillian_mastered.mp3"

        sf.write(raw_wav, raw_audio, sr)

        af_filters = (
            "equalizer=f=220:width_type=o:width=1.2:g=1.5,"
            "highshelf=f=7200:gain=-3.0:width=1.0,"
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
            "duration": duration
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

    # Dynamic Scene-by-Scene Emotion Instructions for Aiden
    items = []
    for c in chunks:
        if "provisional government" in c or "Dublin" in c:
            inst = "Read with solemn historical gravitas and measured cadence."
        elif "Cathal Brugha" in c or "military garrison" in c:
            inst = "Read with steady narrative authority and subtle underlying tension."
        elif "?" in c:
            inst = "Speak with sharp inquisitive skepticism, with clear rising pitch at the end."
        else:
            inst = "Read with calm, authoritative conviction."
        items.append({"text": c, "instruction": inst})

    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
    cillian_ref_text = (
        "You find so much empathy in novels, because there you are putting yourself into "
        "somebody else's point of view, and I've always been a big reader."
    )

    producer = ToughIrishQwenProducer()

    print(f"\n>>> Running Qwen3-TTS Aiden on Tough Irish Words ({len(items)} chunks)...")
    res_aiden = producer.synthesize_aiden.remote(items)
    out_aiden = out_dir / "tough_irish_qwen_aiden_mastered.mp3"
    out_aiden.write_bytes(res_aiden["mastered_bytes"])
    print(f"✓ Aiden Output saved: {out_aiden} ({len(res_aiden['mastered_bytes']):,} bytes, {res_aiden['duration']}s audio)")

    print(f"\n>>> Running Qwen3-TTS Cillian Murphy Voice Clone on Tough Irish Words ({len(chunks)} chunks)...")
    res_cillian = producer.synthesize_cillian_clone.remote(
        chunks,
        cillian_wav.read_bytes(),
        cillian_ref_text
    )
    out_cillian = out_dir / "tough_irish_qwen_cillian_mastered.mp3"
    out_cillian.write_bytes(res_cillian["mastered_bytes"])
    print(f"✓ Qwen Cillian Output saved: {out_cillian} ({len(res_cillian['mastered_bytes']):,} bytes, {res_cillian['duration']}s audio)")
