from __future__ import annotations

import io
import json
import os
import re
import subprocess
import time
import wave
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
OUT_DIR = ROOT / "evaluations" / "new-engines" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_DIR = Path(r"C:\Users\Dave\.gemini\antigravity\brain\e7f9f1a0-6096-4e36-a931-750eafb29d67")

POCKET_URL = os.environ.get("POCKET_URL", "http://192.168.1.41:8012")
KITTEN_URL = os.environ.get("KITTEN_URL", "http://192.168.1.41:8013")


def parse_chunks(text: str) -> list[dict]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    marker = "\ue000"

    def split_sentences(p: str) -> list[str]:
        protected = p
        for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs."):
            protected = protected.replace(abbrev, abbrev[:-1] + marker)
        return [
            s.replace(marker, ".").strip()
            for s in re.split(r"(?<=[.!?])\s+", protected)
            if s.strip()
        ]

    chunks = []
    for p_idx, p in enumerate(paragraphs, 1):
        sents = split_sentences(p)
        for s_idx, s in enumerate(sents):
            is_last_in_para = s_idx == len(sents) - 1
            is_chapter_title = p_idx == 1 and s_idx == 0
            chunks.append({
                "text": s,
                "p_idx": p_idx,
                "is_last_in_para": is_last_in_para,
                "is_chapter_title": is_chapter_title,
            })
    return chunks


def render_engine_wav(
    name: str,
    base_url: str,
    voice: str,
    chunks: list[dict],
    out_mp3: Path,
) -> dict:
    print(f"\n=== Rendering {name} ({voice}) ===")
    started = time.perf_counter()
    speech_url = f"{base_url.rstrip('/')}/v1/audio/speech"

    combined_frames = bytearray()
    audio_params = None
    chunk_metrics = []

    for idx, item in enumerate(chunks, 1):
        c_text = item["text"]
        c_start = time.perf_counter()
        resp = requests.post(
            speech_url,
            json={"input": c_text, "voice": voice, "response_format": "wav"},
            timeout=120,
        )
        resp.raise_for_status()
        c_dur = time.perf_counter() - c_start

        # Read WAV data via standard library wave
        with wave.open(io.BytesIO(resp.content), "rb") as r:
            params = r.getparams()
            if audio_params is None:
                audio_params = params
            elif (params.nchannels != audio_params.nchannels or
                  params.sampwidth != audio_params.sampwidth or
                  params.framerate != audio_params.framerate):
                raise ValueError(f"WAV format mismatch: expected {audio_params}, got {params}")
            frames = r.readframes(r.getnframes())

        combined_frames.extend(frames)
        seg_dur = len(frames) / (audio_params.sampwidth * audio_params.nchannels * audio_params.framerate)

        # Silence insertion based on structure
        if idx < len(chunks):
            if item["is_chapter_title"]:
                silence_sec = 0.85
            elif item["is_last_in_para"]:
                silence_sec = 0.50
            else:
                silence_sec = 0.22
            silence_bytes = b"\x00" * (audio_params.sampwidth * audio_params.nchannels * int(audio_params.framerate * silence_sec))
            combined_frames.extend(silence_bytes)

        chunk_metrics.append({
            "idx": idx,
            "text": c_text[:40] + "...",
            "duration": round(seg_dur, 2),
            "infer_sec": round(c_dur, 2),
        })
        print(f"  [{idx}/{len(chunks)}] {seg_dur:.2f}s audio generated in {c_dur:.2f}s")

    total_audio_dur = len(combined_frames) / (audio_params.sampwidth * audio_params.nchannels * audio_params.framerate)

    # Save temporary wav
    temp_wav = out_mp3.with_suffix(".wav")
    with wave.open(str(temp_wav), "wb") as w:
        w.setparams(audio_params)
        w.writeframes(combined_frames)

    # Encode to MP3 via ffmpeg (192k CBR)
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(temp_wav),
        "-b:a", "192k",
        str(out_mp3),
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    temp_wav.unlink(missing_ok=True)

    wall = time.perf_counter() - started
    rtf = wall / total_audio_dur if total_audio_dur > 0 else 0
    print(f"Complete: {out_mp3.name} ({out_mp3.stat().st_size:,} bytes, {total_audio_dur:.1f}s audio in {wall:.1f}s wall, RTF: {rtf:.2f}x)")

    # Copy to artifacts dir if accessible
    if ARTIFACT_DIR.exists():
        art_copy = ARTIFACT_DIR / out_mp3.name
        art_copy.write_bytes(out_mp3.read_bytes())
        print(f"  Copied to artifact dir: {art_copy.name}")

    return {
        "engine": name,
        "voice": voice,
        "audio_seconds": round(total_audio_dur, 2),
        "wall_seconds": round(wall, 2),
        "rtf": round(rtf, 3),
        "file": str(out_mp3),
        "bytes": out_mp3.stat().st_size,
    }


def main():
    text = TEXT_FILE.read_text(encoding="utf-8").strip()
    chunks = parse_chunks(text)
    words = len(text.split())
    print(f"Loaded {TEXT_FILE.name}: {words} words, {len(chunks)} chunks across {chunks[-1]['p_idx']} paragraphs.")

    results = []

    # 1. Pocket TTS (Peter Yearsley)
    try:
        r = requests.get(f"{POCKET_URL}/health", timeout=5)
        if r.ok:
            res = render_engine_wav(
                "Pocket TTS",
                POCKET_URL,
                "peter_yearsley",
                chunks,
                OUT_DIR / "pocket_breakneck_ch1_peter.mp3",
            )
            results.append(res)
    except Exception as e:
        print(f"Pocket TTS error: {e}")

    # 2. KittenTTS (Rosie)
    try:
        r = requests.get(f"{KITTEN_URL}/health", timeout=5)
        if r.ok:
            res_rosie = render_engine_wav(
                "KittenTTS",
                KITTEN_URL,
                "Rosie",
                chunks,
                OUT_DIR / "kitten_breakneck_ch1_rosie.mp3",
            )
            results.append(res_rosie)

            # 3. KittenTTS (Jasper)
            res_jasper = render_engine_wav(
                "KittenTTS",
                KITTEN_URL,
                "Jasper",
                chunks,
                OUT_DIR / "kitten_breakneck_ch1_jasper.mp3",
            )
            results.append(res_jasper)
    except Exception as e:
        print(f"KittenTTS error: {e}")

    summary_file = OUT_DIR / "cpu_candidates_summary.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved summary to {summary_file}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
