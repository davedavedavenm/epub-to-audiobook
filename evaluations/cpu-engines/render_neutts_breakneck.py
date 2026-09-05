from __future__ import annotations

import io
import json
import re
import subprocess
import time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from neutts import NeuTTS

torch.set_num_threads(4)

ROOT = Path("/repo")
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
OUT_DIR = Path("/output")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("Initializing NeuTTS Air (backbone=neuphonic/neutts-air-q4-gguf, codec=neuphonic/neucodec-onnx-decoder)...")
tts = NeuTTS(
    backbone_repo="neuphonic/neutts-air-q4-gguf",
    backbone_device="cpu",
    codec_repo="neuphonic/neucodec-onnx-decoder",
    codec_device="cpu",
    seed=42,
)

print("Loading Jo reference codes and transcript...")
ref_codes = torch.load("/upstream/samples/jo.pt", map_location="cpu")
ref_text = Path("/upstream/samples/jo.txt").read_text().strip()

text = TEXT_FILE.read_text(encoding="utf-8").strip()
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

print(f"NeuTTS rendering {len(chunks)} chunks for Breakneck Ch 1 (temperature=0.75, top_k=40)...")
started = time.perf_counter()
rendered_segments = []

for idx, item in enumerate(chunks, 1):
    c_text = item["text"]
    c_start = time.perf_counter()
    audio = np.asarray(tts.infer(c_text, ref_codes, ref_text, temperature=0.75, top_k=40))
    dur = len(audio) / 24000
    c_infer = time.perf_counter() - c_start
    print(f"  [{idx}/{len(chunks)}] {dur:.2f}s audio generated in {c_infer:.2f}s ({c_text[:35]}...)")
    rendered_segments.append(audio)

    if idx < len(chunks):
        if item["is_chapter_title"]:
            silence_sec = 0.85
        elif item["is_last_in_para"]:
            silence_sec = 0.50
        else:
            silence_sec = 0.22
        silence_samples = int(24000 * silence_sec)
        rendered_segments.append(np.zeros(silence_samples, dtype=np.float32))

full_audio = np.concatenate(rendered_segments)
wav_out = OUT_DIR / "neutts_breakneck_ch1_jo.wav"
sf.write(str(wav_out), full_audio, 24000)

mp3_out = OUT_DIR / "neutts_breakneck_ch1_jo.mp3"
subprocess.run([
    "ffmpeg", "-y", "-v", "error",
    "-i", str(wav_out),
    "-b:a", "192k",
    str(mp3_out),
], check=True)
wav_out.unlink(missing_ok=True)

total_audio_dur = len(full_audio) / 24000
wall = time.perf_counter() - started
rtf = wall / total_audio_dur if total_audio_dur > 0 else 0
print(f"NeuTTS complete: {mp3_out.name} ({mp3_out.stat().st_size:,} bytes, {total_audio_dur:.1f}s audio in {wall:.1f}s wall, RTF: {rtf:.2f}x)")
