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

app = modal.App("homelab-breeze2-voices-breakneck")

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

@app.cls(image=image, gpu="L4", timeout=1200, scaledown_window=180)
class BreezeProducer:
    @modal.enter()
    def setup(self):
        import sys
        from pathlib import Path
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
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
    def synthesize(
        self,
        voice_id: str,
        chunks: list[str],
        ref_wav_bytes: bytes,
        ref_text: str,
        instruction: str,
        denoise_ref: bool = False,
        eq_profile: str = "warmth"
    ) -> dict:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf
        import time
        import re

        ref_path = f"/tmp/{voice_id}_ref.wav"
        raw_ref_path = f"/tmp/{voice_id}_raw_ref.wav"
        with open(raw_ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        if denoise_ref:
            print(f"[{voice_id}] Denoising reference audio and removing boxy telephone resonance...")
            # afftdn removes room hiss; equalizer dips 600Hz boxiness; highshelf restores air
            ref_filter = "afftdn=nf=-35,equalizer=f=600:width_type=o:width=1.5:g=-4.0,highshelf=f=5500:gain=+4.0:width=1.0"
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_ref_path,
                "-af", ref_filter,
                ref_path
            ], check=True)
        else:
            ref_path = raw_ref_path

        t0 = time.time()
        pieces = []
        sr = self.sample_rate

        print(f"Synthesizing {len(chunks)} chunks with Breeze 2 Voice Direction ({voice_id})...")
        for idx, c in enumerate(chunks, 1):
            chunk_instruction = instruction
            # Robust question detection: ends in '?' or contains a question before closing quote
            if re.search(r'\?[’”"\'\s]*$', c):
                chunk_instruction = instruction + " Deliver with an inquisitive, engaging cadence, lifting your pitch in a natural rising inflection at the end of the question."
            elif c.strip().startswith(('“', '"')) and c.strip().endswith(('”', '"')):
                chunk_instruction = instruction + " Deliver as direct spoken speech with natural expressive phrasing."

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
        print(f"[{voice_id}] Generated {duration_sec}s audio in {gpu_time}s GPU compute!")

        raw_wav = f"/tmp/{voice_id}_raw.wav"
        mastered_wav = f"/tmp/{voice_id}_mastered.wav"
        raw_mp3 = f"/tmp/{voice_id}_raw.mp3"
        mastered_mp3 = f"/tmp/{voice_id}_mastered.mp3"

        sf.write(raw_wav, full_audio, sr)

        # 1. Raw MP3
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            raw_mp3
        ], check=True)

        # 2. Mastered MP3 (Warmth EQ / Air EQ + De-Esser + EBU R128 Loudnorm)
        if eq_profile == "air":
            af_filters = (
                "equalizer=f=200:width_type=o:width=1.0:g=-1.0,"
                "equalizer=f=3500:width_type=o:width=1.2:g=1.5,"
                "highshelf=f=8000:gain=2.0:width=1.0,"
                "loudnorm=I=-20:TP=-2:LRA=11"
            )
        else:
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
def main(voice: str = "all"):
    root = Path(__file__).resolve().parents[2]
    text_file = root / "fixtures" / "breakneck_ch1_2pages_norm.txt"
    text = text_file.read_text(encoding="utf-8")

    # Robust quotation clause splitting: isolate dialogue/thought quotes
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]

    all_voices = [
        {
            "id": "karen",
            "name": "Karen Savage (UK Female)",
            "wav_file": root / "chatterbox" / "voices" / "karen_savage.wav",
            "ref_text": (
                "Those who best knew the easiness of his temper, whether he might not spend the remainder of his days at Netherfield, "
                "and leave the next generation to purchase. His sisters were anxious for his having an estate of his own, "
                "but though he was now only established as a tenant, Miss Bingley was by no means unwilling to preside at his table,"
            ),
            "instruction": "Read in an articulate, expressive British female accent with warm, engaging pacing for a narrative non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
        {
            "id": "yearsley",
            "name": "Peter Yearsley (UK Male Baritone)",
            "wav_file": root / "chatterbox" / "voices" / "uk_male_yearsley.wav",
            "ref_text": (
                "will say, Yes, when you say, Will you? But, as I say, my legacy almost put Mildred out of my head, "
                "especially as she was staying with friends in the country just then. Before the first gloss was off my new mourning, I was"
            ),
            "instruction": "Read in a deep, distinguished British baritone accent with a measured, authoritative cadence for an analytical non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
        {
            "id": "adrian",
            "name": "Adrian Praetzellis (UK Male Conversational)",
            "wav_file": root / "chatterbox" / "voices" / "adrian_praetzellis.wav",
            "ref_text": (
                "she took hold of both hands at once. The next moment they were dancing round in a ring. This seemed quite natural, "
                "she remembered afterwards, and she was not even surprised to hear music playing. It seemed to come from the tree under which they were dancing, and it"
            ),
            "instruction": "Read in a warm, scholarly, conversational British male accent with natural, thoughtful cadence for an analytical non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
        {
            "id": "tadhg_clean",
            "name": "Tadhg Hynes (Irish Male - Studio Restored)",
            "wav_file": root / "chatterbox" / "voices" / "tadhg_hynes.wav",
            "ref_text": (
                "crib framing and copseware manufacturer in general, opposite where the wagon sheds where Marty had deposited her spars. "
                "Here Winterborne had remained after the girls had booked a departure to see that the wagon loads were properly made up. "
                "Winterborne was connected with the Melbury family in various ways."
            ),
            "instruction": "Read in a warm, melodic, intelligent Irish accent with measured, engaging pacing for an analytical non-fiction audiobook.",
            "denoise_ref": True,
            "eq_profile": "air"
        },
        {
            "id": "arthur",
            "name": "Arthur (UK Male)",
            "wav_file": root / "chatterbox" / "voices" / "uk_male_minter.wav",
            "ref_text": (
                '"I know that," snapped Bertram. "Not that it would make any difference if she stayed," '
                'pursued the relentless George. "She flies higher than the paper trade, my boy." '
                '"Hang her!" said Bertram. "It would make it more interesting for me," I ventured to observe.'
            ),
            "instruction": "Read in an intelligent, clear British accent at a measured, engaging pace for an analytical non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
        {
            "id": "beatrice",
            "name": "Beatrice (UK Female)",
            "wav_file": root / "chatterbox" / "voices" / "uk_female_samuel.wav",
            "ref_text": (
                "Letter the second: Laura to Isabel. Although I cannot agree with you in supposing that "
                "I shall never again be exposed to misfortunes as unmerited as those I have already experienced, "
                "yet to avoid the imputation of obstinacy"
            ),
            "instruction": "Read in an intelligent, warm British accent at a measured, engaging pace for an analytical non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
        {
            "id": "liam_au",
            "name": "Liam (Australian Male)",
            "wav_file": root / "chatterbox" / "voices" / "vctk_australian_m_p374.wav",
            "ref_text": (
                "We also need a small plastic snake and a big toy frog for the kids. She can scoop these things into three red bags "
                "and we will go meet her Wednesday at the train station. When the sunlight strikes, raindrops"
            ),
            "instruction": "Read in a clear, natural, engaging Australian accent at a steady, thoughtful pace for an analytical non-fiction audiobook.",
            "denoise_ref": False,
            "eq_profile": "warmth"
        },
    ]

    if voice != "all":
        targets = [v for v in all_voices if v["id"] == voice.lower()]
        if not targets:
            raise ValueError(f"Unknown voice '{voice}'. Choose from: {[v['id'] for v in all_voices]}")
    else:
        targets = all_voices

    producer = BreezeProducer()
    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n==========================================")
    print(f"Breeze TTS 2 Modal Production Runner")
    print(f"Voices to synthesize: {[v['name'] for v in targets]}")
    print(f"Total Chunks: {len(chunks)} ({len(text)} chars)")
    print(f"==========================================\n")

    for v in targets:
        v_id = v["id"]
        v_name = v["name"]
        print(f"\n>>> Processing {v_name} ({v_id})...")
        assert v["wav_file"].exists(), f"Missing WAV: {v['wav_file']}"
        wav_bytes = v["wav_file"].read_bytes()

        res = producer.synthesize.remote(
            v_id,
            chunks,
            wav_bytes,
            v["ref_text"],
            v["instruction"],
            denoise_ref=v.get("denoise_ref", False),
            eq_profile=v.get("eq_profile", "warmth")
        )

        raw_path = out_dir / f"breakneck_ch1_breeze_{v_id}_modal_raw.mp3"
        mastered_path = out_dir / f"breakneck_ch1_breeze_{v_id}_modal_mastered.mp3"

        raw_path.write_bytes(res["raw_bytes"])
        mastered_path.write_bytes(res["mastered_bytes"])

        print(f"✓ {v_name} Finished!")
        print(f"  Raw: {raw_path} ({len(res['raw_bytes']):,} bytes)")
        print(f"  Mastered: {mastered_path} ({len(res['mastered_bytes']):,} bytes)")
        print(f"  Duration: {res['duration']}s | GPU Time: {res['gpu_time']}s")
