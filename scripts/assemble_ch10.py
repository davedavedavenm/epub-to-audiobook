"""
assemble_ch10.py — Concatenate contiguous batches 1-27 of Chapter 10,
apply broadcast mastering chain, and encode to MP3.
"""

import wave
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
chunks_dir = root / "output" / "armed_struggle_cillian" / "chunks"
out_dir = root / "output" / "armed_struggle_cillian"

contiguous_batches = []
for i in range(1, 35):
    p = chunks_dir / f"ch10_batch_{i:03d}.wav"
    if p.exists():
        contiguous_batches.append(p)
    else:
        break

print(f"Found {len(contiguous_batches)} contiguous batches for Chapter 10:")
print(f"From {contiguous_batches[0].name} to {contiguous_batches[-1].name}")

raw_wav = out_dir / "ch10_raw.wav"
print(f"Concatenating into {raw_wav}...")
with wave.open(str(raw_wav), "wb") as outfile:
    for i, f in enumerate(contiguous_batches):
        with wave.open(str(f), "rb") as infile:
            if i == 0:
                outfile.setparams(infile.getparams())
            outfile.writeframes(infile.readframes(infile.getnframes()))

print(f"Raw WAV created: {raw_wav.stat().st_size:,} bytes")

mastered_wav = out_dir / "ch10_mastered.wav"
af_filters = (
    "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
    "highshelf=f=7500:gain=-2.0:width=1.0,"
    "loudnorm=I=-20:TP=-2:LRA=11"
)
print("Applying broadcast mastering chain (-20 LUFS, EQ, highshelf)...")
subprocess.run([
    "ffmpeg", "-y", "-i", str(raw_wav),
    "-af", af_filters,
    "-ar", "24000",
    str(mastered_wav)
], check=True)

mp3_path = out_dir / "10 - Two New States Nineteen Twenty Three 63.mp3"
print(f"Encoding to 192k MP3: {mp3_path}...")
subprocess.run([
    "ffmpeg", "-y", "-i", str(mastered_wav),
    "-codec:a", "libmp3lame", "-b:a", "192k",
    str(mp3_path)
], check=True)

print("Cleaning up temporary WAVs...")
if raw_wav.exists():
    raw_wav.unlink()
if mastered_wav.exists():
    mastered_wav.unlink()

print(f"✓✓✓ CHAPTER 10 AUDIO ASSEMBLED: {mp3_path.name} ({mp3_path.stat().st_size:,} bytes)")
