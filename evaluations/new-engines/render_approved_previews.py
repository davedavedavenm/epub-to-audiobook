"""
render_approved_previews.py — Synthesize canonical SAMPLE_TEXT previews for all approved voices on Modal.

Voices rendered:
1. breeze_cillian_irish (Cillian Murphy, Irish Male, Studio Dry)
2. breeze_liam_au (Liam, Australian / Irish Male)
3. breeze_karen_savage (Karen Savage, British Female)
4. breeze_arthur (Arthur, British Male)
5. breeze_adrian (Adrian Praetzellis, British Male Scholar)
6. breeze_tadhg_clean (Tadhg Hynes, Restored Irish Male)
7. qwen3_aiden (Aiden, American / Non-Fiction Male)

All outputs are saved to data/previews/<voice_id>.mp3 with broadcast mastering (-20 LUFS).
"""

import modal
import re
import subprocess
from pathlib import Path

app = modal.App("homelab-render-approved-previews")

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
        "hf download BreezeBlue/Breeze-TTS-2 --local-dir /root/breeze-model",
        "hf download Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice --local-dir /root/qwen-customvoice"
    )
)

SAMPLE_TEXT = (
    "In the spring of 1997, Apple was nine weeks from bankruptcy. Its CEO had "
    "been ousted, Steve Jobs had returned, the share price had fallen 71 percent, "
    "and the company was burning through $1.2 billion a year. Few analysts at "
    "Goldman Sachs believed it would survive to see the year 2000.\n\n"
    "What changed was not one decision, but a thousand small ones. Scott Forstall, "
    "Jony Ive, and a young engineer named Nguyen worked eighteen-hour days, six "
    "days a week, for months on end. Between 2001 and 2007, Apple's partners in "
    "Shenzhen and Zhengzhou scaled from 3,400 workers to over 230,000; a single "
    "Foxconn campus drew 1.5 gigawatts.\n\n"
    "Today the iPhone accounts for roughly 52% of revenue, and the App Store for "
    "some £24.6 billion a year. Rivals — Huawei, Xiaomi, Samsung — circle "
    "constantly. Whether that dependence is a triumph or a trap, for the WTO, for "
    "the EU, and for a supply chain 7,000 miles long, is the question Dr. Wang has "
    "spent a decade trying to answer."
)


def chunk_text(text: str) -> list[str]:
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    return [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]


@app.cls(image=image, gpu=["A10G", "L4"], timeout=1200)
class PreviewProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from pathlib import Path
        from breeze_infer.runtime import load_runtime, resolve_device, update_generation_config_for_breeze
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        print("Loading Breeze TTS 2 (3.5B)...")
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

    @modal.method()
    def synthesize_breeze(self, voice_id: str, chunks: list[str], ref_wav_bytes: bytes, ref_text: str, instruction: str) -> bytes:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf

        ref_path = f"/tmp/{voice_id}_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        pieces = []
        sr = self.sample_rate
        LOCKED_SEED = 42

        print(f"[{voice_id}] Synthesizing {len(chunks)} chunks on Breeze 2...")
        for idx, c in enumerate(chunks, 1):
            chunk_inst = instruction
            if "?" in c:
                chunk_inst += " Deliver with an inquisitive, rising inflection on the question."
            req = {
                "id": f"{voice_id}-{idx}",
                "text": c,
                "instruction": chunk_inst,
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
                guidance_scale=2.5,
                guidance_scale_ref=None,
                guidance_scale_ins=None,
            )
            audio_parts = []
            for audio_chunk in self.runtime.iter_audio_chunks(
                inputs, request_id=f"{voice_id}-{idx}", seed=LOCKED_SEED
            ):
                audio_parts.append(audio_chunk.audio)
            if audio_parts:
                pieces.append(np.concatenate(audio_parts))
                pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

        full_audio = np.concatenate(pieces)
        raw_wav = f"/tmp/{voice_id}_raw.wav"
        mastered_wav = f"/tmp/{voice_id}_mastered.wav"
        mastered_mp3 = f"/tmp/{voice_id}_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
            "-ar", str(sr),
            mastered_wav
        ], check=True)
        subprocess.run([
            "ffmpeg", "-y", "-i", mastered_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            mastered_mp3
        ], check=True)
        with open(mastered_mp3, "rb") as f:
            return f.read()

    @modal.method()
    def synthesize_qwen_aiden(self, chunks: list[str]) -> bytes:
        import torch
        from qwen_tts import Qwen3TTSModel
        import numpy as np
        import soundfile as sf

        print("Loading Qwen3-TTS CustomVoice for Aiden...")
        # Free Breeze model if needed or load onto GPU
        qwen_model = Qwen3TTSModel.from_pretrained(
            "/root/qwen-customvoice",
            device_map="cuda:0",
            dtype=torch.float16,
            attn_implementation="sdpa"
        )
        pieces = []
        sr = 24000
        for idx, c in enumerate(chunks, 1):
            inst = "Read with clear, authoritative non-fiction narration, natural pacing, and expressive emphasis."
            if "?" in c:
                inst = "Speak with inquisitive skepticism, raising pitch clearly at the end of the question."
            wavs, gen_sr = qwen_model.generate_custom_voice(
                text=c,
                speaker="aiden",
                instruct=inst,
                max_new_tokens=1024
            )
            sr = gen_sr
            audio = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            pieces.append(audio)
            pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

        full_audio = np.concatenate(pieces)
        raw_wav = "/tmp/qwen_aiden_raw.wav"
        mastered_wav = "/tmp/qwen_aiden_mastered.wav"
        mastered_mp3 = "/tmp/qwen_aiden_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.5,highshelf=f=7200:gain=-3.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
            "-ar", str(sr),
            mastered_wav
        ], check=True)
        subprocess.run([
            "ffmpeg", "-y", "-i", mastered_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            mastered_mp3
        ], check=True)
        with open(mastered_mp3, "rb") as f:
            return f.read()


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[2]
    previews_dir = root / "data" / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    voices_dir = root / "chatterbox" / "voices"

    chunks = chunk_text(SAMPLE_TEXT)
    producer = PreviewProducer()

    breeze_configs = [
        {
            "id": "breeze_cillian_irish",
            "wav": voices_dir / "cillian_irish_dry.wav",
            "ref_text": "You find so much empathy in novels, because there you are putting yourself into somebody else's point of view, and I've always been a big reader.",
            "instruction": "Read in a calm, thoughtful, authentic Irish accent with measured literary pacing and solemn gravitas."
        },
        {
            "id": "breeze_liam_au",
            "wav": voices_dir / "vctk_australian_m_p374.wav",
            "ref_text": "Please call Stella. Ask her to bring these things with her from the store: six spoons of fresh snow peas, five thick slabs of blue cheese, and maybe a snack for her brother Bob.",
            "instruction": "Read in a warm, thoughtful Australian male accent with articulate literary narration."
        },
        {
            "id": "breeze_karen_savage",
            "wav": voices_dir / "karen_savage.wav",
            "ref_text": "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
            "instruction": "Read in an articulate, expressive British female accent with classic audiobook clarity."
        },
        {
            "id": "breeze_arthur",
            "wav": voices_dir / "uk_male_minter.wav",
            "ref_text": "The old lighthouse keeper climbed the spiral staircase, lantern in hand, listening to the crashing waves.",
            "instruction": "Read in a warm, distinguished British gentleman narrator voice with thoughtful cadence."
        },
        {
            "id": "breeze_adrian",
            "wav": voices_dir / "adrian_praetzellis.wav",
            "ref_text": "The archaeologist dusted off the ancient artifact, revealing intricate inscriptions from centuries ago.",
            "instruction": "Read in a scholarly, engaging British male voice with high presence and storytelling flair."
        },
        {
            "id": "breeze_tadhg_clean",
            "wav": voices_dir / "tadhg_hynes.wav",
            "ref_text": "The wind was blowing across the heather on the hillside as the evening shadows lengthened.",
            "instruction": "Read in a rich, warm, traditional Irish storytelling cadence."
        }
    ]

    print("\n=======================================================")
    print(">>> Generating Canonical Previews on Modal GPU...")
    print("=======================================================\n")

    for cfg in breeze_configs:
        vid = cfg["id"]
        out_file = previews_dir / f"{vid}.mp3"
        print(f">>> Rendering {vid}...")
        mp3_bytes = producer.synthesize_breeze.remote(
            vid,
            chunks,
            cfg["wav"].read_bytes(),
            cfg["ref_text"],
            cfg["instruction"]
        )
        out_file.write_bytes(mp3_bytes)
        print(f"✓ Saved: {out_file.name} ({len(mp3_bytes):,} bytes)")

    # Render Qwen3 Aiden
    print(">>> Rendering qwen3_aiden...")
    aiden_file = previews_dir / "qwen3_aiden.mp3"
    aiden_bytes = producer.synthesize_qwen_aiden.remote(chunks)
    aiden_file.write_bytes(aiden_bytes)
    print(f"✓ Saved: {aiden_file.name} ({len(aiden_bytes):,} bytes)")

    print("\n✓ ALL 7 APPROVED PREVIEWS GENERATED AND CACHED SUCCESSFULLY!")
