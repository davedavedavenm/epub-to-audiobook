"""
render_armed_struggle_full_modal.py — Full-book production rendering of
"The Armed Struggle: The Story of the IRA" by Richard English using Breeze 2
with Cillian Murphy's studio Irish narration on Modal GPUs.

Pipeline Overview:
1. Loads 11 extracted narrative chapters from fixtures/armed_struggle_chapters/
2. Distributes chapter synthesis across Modal L4/A10G GPU workers in parallel (.map())
3. Each worker synthesizes sentences with Cillian Murphy dry reference (seed 42, guidance 2.5)
   and applies the broadcast mastering chain (-20 LUFS).
4. Assembles completed MP3s into output/armed_struggle_cillian/
5. Builds Armed Struggle.m4b with chapter metadata and cover.jpg
6. Generates metadata.json with exact chapter timings
7. Deploys/syncs to Audiobookshelf on docker-vm
8. Recalibrates Dave's exact playback position in absdatabase.sqlite
"""

import modal
import re
import sys
import time
import subprocess
from pathlib import Path

app = modal.App("armed-struggle-full-book-render")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1", "sox", "libsox-fmt-all")
    .pip_install(
        "soundfile>=0.13",
        "huggingface_hub[cli]>=0.25",
        "transformers>=4.45",
        "accelerate",
        "scipy",
        "torch",
        "numpy"
    )
    .run_commands(
        "git clone https://github.com/breezeblue-ai/breeze-tts.git /root/breeze-tts",
        "hf download BreezeBlue/Breeze-TTS-2 --local-dir /root/breeze-model"
    )
)


@app.cls(image=image, gpu=["A10G", "L4"], timeout=3600, scaledown_window=300)
class FullBookBreezeProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from pathlib import Path
        from breeze_infer.runtime import load_runtime, resolve_device, update_generation_config_for_breeze
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        print("Initializing Breeze TTS 2 (3.5B) for full-book batch production...")
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
        print("Breeze TTS 2 runtime loaded and ready.")

    @modal.method()
    def render_chapter(self, item: dict) -> dict:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf

        chapter_id = item["chapter_id"]
        title = item["title"]
        paragraphs = item["paragraphs"]
        ref_wav_bytes = item["ref_wav_bytes"]
        ref_text = item["ref_text"]
        base_instruction = item["instruction"]

        ref_path = f"/tmp/cillian_{chapter_id}_ref.wav"
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        t0 = time.time()
        sr = self.sample_rate
        LOCKED_SEED = 42

        total_sentences = sum(len(p) for p in paragraphs)
        print(f"[{title}] Starting synthesis: {len(paragraphs)} paragraphs, {total_sentences} sentences...")

        pieces = []
        sentence_count = 0

        for p_idx, p in enumerate(paragraphs, 1):
            for s_idx, sentence in enumerate(p, 1):
                sentence_count += 1
                inst = base_instruction
                if "?" in sentence:
                    inst += " Deliver with an inquisitive, rising inflection on the question."

                req = {
                    "id": f"{chapter_id}-p{p_idx}-s{s_idx}",
                    "text": sentence,
                    "instruction": inst,
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
                for chunk in self.runtime.iter_audio_chunks(
                    inputs, request_id=f"{chapter_id}-p{p_idx}-s{s_idx}", seed=LOCKED_SEED
                ):
                    audio_parts.append(chunk.audio)

                if audio_parts:
                    pieces.append(np.concatenate(audio_parts))
                    # Natural inter-sentence pause (350ms)
                    pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

            # Natural inter-paragraph pause (additional 350ms -> 700ms total)
            pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

            if p_idx % 10 == 0 or p_idx == len(paragraphs):
                elapsed = round(time.time() - t0, 1)
                print(f"[{title}] Progress: Paragraph {p_idx}/{len(paragraphs)} ({sentence_count}/{total_sentences} sentences) in {elapsed}s")

        full_audio = np.concatenate(pieces)
        duration_sec = round(len(full_audio) / sr, 2)
        print(f"[{title}] Complete! Generated {duration_sec}s ({duration_sec/60:.1f} min) audio.")

        raw_wav = f"/tmp/{chapter_id}_raw.wav"
        mastered_wav = f"/tmp/{chapter_id}_mastered.wav"
        mastered_mp3 = f"/tmp/{chapter_id}_mastered.mp3"

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
            mp3_bytes = f.read()

        return {
            "chapter_id": chapter_id,
            "title": title,
            "mp3_bytes": mp3_bytes,
            "duration": duration_sec,
            "elapsed_gpu_sec": round(time.time() - t0, 1)
        }


def chunk_paragraph(text: str) -> list[str]:
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.", "Capt.", "Gen.", "Col.", "Lt."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    return [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[1]
    chapters_dir = root / "fixtures" / "armed_struggle_chapters"
    out_dir = root / "output" / "armed_struggle_cillian"
    out_dir.mkdir(parents=True, exist_ok=True)

    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
    ref_wav_bytes = cillian_wav.read_bytes()
    ref_text = (
        "You find so much empathy in novels, because there you are putting yourself into "
        "somebody else's point of view, and I've always been a big reader."
    )
    instruction = (
        "Read in a calm, thoughtful, authentic Irish accent with measured literary pacing and solemn gravitas "
        "suitable for an Irish history audiobook."
    )

    # 11 Chapters in canonical order
    chapters = [
        ("ch08", "08 - Preface"),
        ("ch09", "09 - One The Irish Revolution Nineteen Sixteen 23"),
        ("ch10", "10 - Two New States Nineteen Twenty Three 63"),
        ("ch11", "11 - Three The Birth Of The Provisional Ira Nineteen Sixty Three 72"),
        ("ch12", "12 - Four The Politics Of Violence Nineteen Seventy Two 6"),
        ("ch13", "13 - Five The Prison War Nineteen Seventy Six 81"),
        ("ch14", "14 - Six Politicization And The Cycle Of Violence Nineteen Eighty One 8"),
        ("ch15", "15 - Seven Talking And Killing Nineteen Eighty Eight 94"),
        ("ch16", "16 - Eight Cessations Of Violence Nineteen Ninety Four To Two Thousand Two"),
        ("ch17", "17 - Conclusion"),
        ("ch18", "18 - Afterword"),
    ]

    print("===================================================================")
    print(">>> ARMED STRUGGLE: FULL BOOK PRODUCTION RENDER (CILLIAN MURPHY)")
    print("===================================================================")

    items_to_render = []
    for cid, title in chapters:
        mp3_path = out_dir / f"{title}.mp3"
        if mp3_path.exists() and mp3_path.stat().st_size > 50000:
            print(f"[SKIP] Chapter already rendered: {title}.mp3 ({mp3_path.stat().st_size:,} bytes)")
            continue

        txt_file = chapters_dir / f"{title}.txt"
        if not txt_file.exists():
            print(f"[ERROR] Missing chapter text: {txt_file}")
            continue

        raw_text = txt_file.read_text(encoding="utf-8")
        paras = []
        for p in raw_text.split("\n\n"):
            p = p.strip()
            if p:
                sents = chunk_paragraph(p)
                if sents:
                    paras.append(sents)

        items_to_render.append({
            "chapter_id": cid,
            "title": title,
            "paragraphs": paras,
            "ref_wav_bytes": ref_wav_bytes,
            "ref_text": ref_text,
            "instruction": instruction
        })

    if not items_to_render:
        print("\nAll chapters already rendered!")
    else:
        print(f"\nSubmitting {len(items_to_render)} chapters to Modal GPU workers...")
        producer = FullBookBreezeProducer()
        for res in producer.render_chapter.map(items_to_render):
            cid = res["chapter_id"]
            title = res["title"]
            out_file = out_dir / f"{title}.mp3"
            out_file.write_bytes(res["mp3_bytes"])
            print(f"✓ FINISHED: {title}.mp3 ({len(res['mp3_bytes']):,} bytes, {res['duration']}s audio, rendered in {res['elapsed_gpu_sec']}s)")

    print("\n===================================================================")
    print(">>> All chapters rendered! Generating M4B, metadata & syncing to ABS...")
    print("===================================================================")

    # Post-processing script handles assembly, sync, and progress restoration
    post_script = root / "scripts" / "sync_armed_struggle_abs.py"
    if post_script.exists():
        subprocess.run([sys.executable, str(post_script)], check=True)
