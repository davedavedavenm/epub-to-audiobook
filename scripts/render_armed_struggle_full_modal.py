"""
render_armed_struggle_full_modal.py — Resilient, Sub-Batched Full-Book Production
Rendering of "The Armed Struggle: The Story of the IRA" by Richard English.

Voice: Cillian Murphy (Studio Irish Narration, Breeze TTS 2 3.5B) on Modal L4 GPUs.

Architecture:
1. Chapters partitioned into 15-sentence sub-batches (~4-5 mins compute each).
2. Slices run across parallel Modal L4 workers (concurrency_limit=3) via .map().
3. Each sub-batch checkpoints immediately to local disk (output/armed_struggle_cillian/chunks/).
4. Fully resumable: skips already-banked sub-batches on restart.
5. Assembles and broadcast-masters (-20 LUFS) complete chapter MP3s upon batch completion.
6. Packages Armed Struggle.m4b and syncs to Audiobookshelf via scripts/sync_armed_struggle_abs.py.
"""

import io
import os
import re
import sys
import time
import wave
import subprocess
from pathlib import Path
import modal

app = modal.App("armed-struggle-full-book-render")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1", "sox", "libsox-fmt-all")
    .pip_install(
        "soundfile>=0.13",
        "huggingface_hub[cli]>=0.25",
        "transformers>=4.50.0,<5.0.0",
        "qwen-tts==0.1.1",
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


@app.cls(image=image, gpu="L4", timeout=900, scaledown_window=5, max_containers=3)
class FullBookBreezeProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from pathlib import Path
        from breeze_infer.runtime import load_runtime, resolve_device, update_generation_config_for_breeze
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        print("Initializing Breeze TTS 2 (3.5B) on Nvidia L4 GPU...")
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
        print("Breeze TTS 2 runtime ready.")

    @modal.method()
    def render_batch(self, item: dict) -> dict:
        import sys
        if "/root/breeze-tts" not in sys.path:
            sys.path.insert(0, "/root/breeze-tts")
        from breeze_infer.runtime import set_all_seeds
        from breeze_infer.templates import get_template, prepare_inputs
        import numpy as np
        import soundfile as sf
        import torch

        chapter_id = item["chapter_id"]
        batch_idx = item["batch_idx"]
        sentences = item["sentences"]
        ref_wav_bytes = item["ref_wav_bytes"]
        ref_text = item["ref_text"]

        ref_path = f"/tmp/cillian_{chapter_id}_ref.wav"
        if not Path(ref_path).exists():
            with open(ref_path, "wb") as f:
                f.write(ref_wav_bytes)

        t0 = time.time()
        sr = self.sample_rate
        LOCKED_SEED = 42
        pieces = []

        for s_item in sentences:
            sentence = s_item["text"]
            inst = s_item["instruction"]
            req_id = s_item["id"]

            req = {
                "id": req_id,
                "text": sentence,
                "instruction": inst,
                "speaker": "S0",
                "ref_audio_path": ref_path,
                "ref_text": ref_text,
            }

            try:
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
                for chunk in self.runtime.iter_audio_chunks(inputs, request_id=req_id, seed=LOCKED_SEED):
                    audio_parts.append(chunk.audio)
                del inputs
            except Exception as exc:
                torch.cuda.empty_cache()
                set_all_seeds(LOCKED_SEED)
                inputs = prepare_inputs(
                    self.tokenizer,
                    self.audio_tokenizer,
                    self.model,
                    [req],
                    get_template("ref_edit_tata"),
                    guidance_scale=1.5,
                    guidance_scale_ref=None,
                    guidance_scale_ins=None,
                )
                audio_parts = []
                for chunk in self.runtime.iter_audio_chunks(inputs, request_id=req_id, seed=LOCKED_SEED):
                    audio_parts.append(chunk.audio)
                del inputs

            if audio_parts:
                pieces.append(np.concatenate(audio_parts))
                # Natural inter-sentence pause (350ms)
                pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

            if s_item.get("is_para_end", False):
                # Extra 350ms pause (700ms total) at paragraph boundaries
                pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))

        if not pieces:
            raise RuntimeError(f"No audio produced for {chapter_id} batch {batch_idx}")

        batch_audio = np.concatenate(pieces)
        duration_sec = round(len(batch_audio) / sr, 2)
        elapsed_sec = round(time.time() - t0, 1)

        buf = io.BytesIO()
        sf.write(buf, batch_audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        return {
            "chapter_id": chapter_id,
            "batch_idx": batch_idx,
            "wav_bytes": wav_bytes,
            "duration": duration_sec,
            "sentence_count": len(sentences),
            "elapsed_gpu_sec": elapsed_sec,
        }


def chunk_paragraph(text: str) -> list[str]:
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.", "Capt.", "Gen.", "Col.", "Lt.", "RIC", "IRA", "UDA", "UVF", "SDLP", "GAA", "INLA"):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    return [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]


def partition_chapter(txt_path: Path, chapter_id: str, base_instruction: str, batch_size: int = 15):
    raw_text = txt_path.read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]

    all_sentences = []
    for p_idx, p in enumerate(paragraphs, 1):
        sents = chunk_paragraph(p)
        for s_idx, sentence in enumerate(sents, 1):
            is_para_end = (s_idx == len(sents))
            inst = base_instruction
            if "?" in sentence:
                inst += " Deliver with an inquisitive, rising inflection on the question."
            all_sentences.append({
                "id": f"{chapter_id}-p{p_idx}-s{s_idx}",
                "text": sentence,
                "instruction": inst,
                "is_para_end": is_para_end
            })

    batches = []
    for i in range(0, len(all_sentences), batch_size):
        b_idx = (i // batch_size) + 1
        b_slice = all_sentences[i:i + batch_size]
        batches.append({
            "chapter_id": chapter_id,
            "batch_idx": b_idx,
            "sentences": b_slice,
        })
    return all_sentences, batches


def concatenate_wav_files(chunk_files: list[Path], out_wav: Path):
    with wave.open(str(out_wav), "wb") as outfile:
        for i, f in enumerate(chunk_files):
            with wave.open(str(f), "rb") as infile:
                if i == 0:
                    outfile.setparams(infile.getparams())
                outfile.writeframes(infile.readframes(infile.getnframes()))


def master_and_encode(raw_wav: Path, mp3_path: Path, sample_rate: int = 24000):
    ffmpeg_exe = r"C:\Users\Dave\.local\bin\ffmpeg.exe"
    if not Path(ffmpeg_exe).exists():
        ffmpeg_exe = "ffmpeg"

    mastered_wav = raw_wav.with_name(f"{raw_wav.stem}_mastered.wav")
    af_filters = (
        "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
        "highshelf=f=7500:gain=-2.0:width=1.0,"
        "loudnorm=I=-20:TP=-2:LRA=11"
    )
    subprocess.run([
        ffmpeg_exe, "-y", "-i", str(raw_wav),
        "-af", af_filters,
        "-ar", str(sample_rate),
        str(mastered_wav)
    ], check=True, capture_output=True)

    subprocess.run([
        ffmpeg_exe, "-y", "-i", str(mastered_wav),
        "-codec:a", "libmp3lame", "-b:a", "192k",
        str(mp3_path)
    ], check=True, capture_output=True)

    if mastered_wav.exists():
        mastered_wav.unlink()


def get_billing_summary():
    try:
        proc = subprocess.run(["modal", "billing", "summary", "--json"], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            import json
            data = json.loads(proc.stdout)
            metered = float(data.get("metered_cost", 0.0))
            remaining = max(0.0, 30.00 - metered)
            return {"metered": metered, "remaining": remaining}
    except Exception:
        pass
    return None


@app.local_entrypoint()
def main():
    # Windows Sleep Prevention during long batch runs
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            print("[SYSTEM] Windows Sleep Prevention Active (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).")
        except Exception:
            pass

    root = Path(__file__).resolve().parents[1]
    chapters_dir = root / "fixtures" / "armed_struggle_chapters"
    out_dir = root / "output" / "armed_struggle_cillian"
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

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
    print(">>> ARMED STRUGGLE: RESILIENT FULL-BOOK PRODUCTION RENDER")
    print(">>> Voice: Cillian Murphy Studio Irish Clone (Breeze TTS 2 3.5B)")
    print(">>> Checkpoint Dir: output/armed_struggle_cillian/chunks/")
    print("===================================================================")

    bill = get_billing_summary()
    if bill:
        print(f"[BILLING] Metered Spend: ${bill['metered']:.2f} | Remaining Free Credit: ${bill['remaining']:.2f}")

    producer = FullBookBreezeProducer()

    for ch_idx, (cid, title) in enumerate(chapters, 1):
        mp3_path = out_dir / f"{title}.mp3"
        if mp3_path.exists() and mp3_path.stat().st_size > 50000:
            print(f"\n[{ch_idx}/{len(chapters)}] [BANKED] Chapter already completed: {title}.mp3 ({mp3_path.stat().st_size:,} bytes)")
            continue

        txt_file = chapters_dir / f"{title}.txt"
        if not txt_file.exists():
            print(f"[ERROR] Missing chapter text: {txt_file}")
            continue

        sents, batches = partition_chapter(txt_file, cid, instruction, batch_size=15)
        total_batches = len(batches)
        print(f"\n===================================================================")
        print(f"[{ch_idx}/{len(chapters)}] CHAPTER: {title}")
        print(f"Total Sentences: {len(sents)} | Sub-Batches (15 sents): {total_batches}")
        print(f"===================================================================")

        pending_batches = []
        for b in batches:
            b_idx = b["batch_idx"]
            chunk_file = chunks_dir / f"{cid}_batch_{b_idx:03d}.wav"
            if chunk_file.exists() and chunk_file.stat().st_size > 1000:
                continue
            b["ref_wav_bytes"] = ref_wav_bytes
            b["ref_text"] = ref_text
            pending_batches.append(b)

        completed_count = total_batches - len(pending_batches)
        if completed_count > 0:
            print(f"[{title}] Found {completed_count}/{total_batches} batches already banked on disk.")

        if pending_batches:
            print(f"[{title}] Dispatching {len(pending_batches)} batches across up to 3 parallel Modal L4 GPU workers...")
            t_start = time.time()
            for res in producer.render_batch.map(pending_batches, order_outputs=False):
                b_idx = res["batch_idx"]
                chunk_file = chunks_dir / f"{cid}_batch_{b_idx:03d}.wav"
                chunk_file.write_bytes(res["wav_bytes"])
                completed_count += 1
                elapsed = round(time.time() - t_start, 1)
                print(f"[{title}] Banked batch {b_idx:03d}/{total_batches:03d} ({res['duration']}s audio, {res['sentence_count']} sents in {res['elapsed_gpu_sec']}s GPU) [{completed_count}/{total_batches} done in {elapsed}s]")

        # Verify all batches are present on disk before assembly
        all_chunk_files = [chunks_dir / f"{cid}_batch_{b['batch_idx']:03d}.wav" for b in batches]
        missing = [f for f in all_chunk_files if not f.exists()]
        if missing:
            print(f"[ERROR] Chapter {title} has {len(missing)} missing batches. Cannot assemble.")
            continue

        print(f"[{title}] All {total_batches} batches verified on disk! Assembling & mastering to -20 LUFS...")
        raw_chapter_wav = out_dir / f"{cid}_raw.wav"
        concatenate_wav_files(all_chunk_files, raw_chapter_wav)
        master_and_encode(raw_chapter_wav, mp3_path, sample_rate=24000)
        if raw_chapter_wav.exists():
            raw_chapter_wav.unlink()

        print(f"✓✓✓ CHAPTER FULLY BANKED: {title}.mp3 ({mp3_path.stat().st_size:,} bytes)")

        bill = get_billing_summary()
        if bill:
            print(f"[BILLING UPDATE] Metered Spend: ${bill['metered']:.2f} | Remaining Free Credit: ${bill['remaining']:.2f}")

    print("\n===================================================================")
    print(">>> All chapters rendered! Generating M4B & syncing to ABS...")
    print("===================================================================")
    post_script = root / "scripts" / "sync_armed_struggle_abs.py"
    if post_script.exists():
        subprocess.run([sys.executable, str(post_script)], check=True)
