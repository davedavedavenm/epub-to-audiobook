"""
render_tough_irish_supertonic3.py - Supertonic-3 (99M ONNX, local CPU) on Tough Irish Words

CPU-only audition of Supertone/supertonic-3 preset voices on the notorious Irish
names & terms challenge (Dail Eireann, Padraig Pearse, Dualdhaire etc). No GPU, no
cloud quota: the whole point of the engine is free on-device inference.

Preset voices only: the open-weight release ships fixed styles; zero-shot custom
voices require the paid Voice Builder and are out of scope.

Audio mastered to EBU R128 (-20 LUFS) to match the Breeze/F5/Qwen audition suite.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from supertonic import TTS

FFMPEG = r"C:\Users\Dave\.local\bin\ffmpeg.exe"
VOICES = ["M1", "M2", "M3"]
SENTENCE_JOIN_S = 0.35

MASTER_FILTER = (
    "equalizer=f=250:width_type=o:width=1.2:g=2.2,"
    "highshelf=f=7200:gain=-3.5:width=1.0,"
    "loudnorm=I=-20:TP=-2:LRA=11"
)


def chunk_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.?!])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def master_to_mp3(raw_wav: Path, out_mp3: Path) -> None:
    subprocess.run(
        [
            FFMPEG, "-y", "-loglevel", "error", "-i", str(raw_wav),
            "-af", MASTER_FILTER, "-b:a", "192k", str(out_mp3),
        ],
        check=True,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    text = (root / "fixtures" / "tough_irish_words.txt").read_text(encoding="utf-8")
    sentences = chunk_sentences(text)
    print(f"Source: {len(sentences)} sentences, {len(text)} chars")

    tts = TTS(auto_download=True)
    sr = tts.sample_rate

    for voice in VOICES:
        t0 = time.time()
        style = tts.get_voice_style(voice_name=voice)
        pieces: list[np.ndarray] = []
        gap = np.zeros(int(SENTENCE_JOIN_S * sr), dtype=np.float32)
        for idx, sent in enumerate(sentences, 1):
            wav, _ = tts.synthesize(sent, voice_style=style, lang="en")
            wav = np.asarray(wav, dtype=np.float32)
            if wav.ndim > 1:
                wav = wav.mean(axis=0)
            pieces.append(wav)
            pieces.append(gap)
            print(f"  [{voice} {idx}/{len(sentences)}] {len(wav) / sr:.1f}s audio", flush=True)
        full = np.concatenate(pieces)
        raw = out_dir / f"supertonic3_tough_irish_{voice}_raw.wav"
        sf.write(raw, full, sr)
        mp3 = out_dir / f"supertonic3_tough_irish_{voice}_mastered.mp3"
        master_to_mp3(raw, mp3)
        elapsed = time.time() - t0
        audio_s = len(full) / sr
        print(
            f"OK {voice}: {audio_s:.1f}s audio in {elapsed:.1f}s (RTF {elapsed / audio_s:.2f}) "
            f"-> {mp3.name} ({mp3.stat().st_size:,} bytes)"
        )


if __name__ == "__main__":
    sys.exit(main())
