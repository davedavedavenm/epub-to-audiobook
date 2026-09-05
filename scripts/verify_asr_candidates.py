from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
OUTPUT_DIR = ROOT / "evaluations" / "new-engines" / "output"

def clean(t: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]+", "", t.lower()).split()

def compute_wer(ref_words: list[str], hyp_words: list[str]) -> float:
    # Standard dynamic programming Levenshtein distance for WER
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = min(
                    d[i - 1][j] + 1,      # deletion
                    d[i][j - 1] + 1,      # insertion
                    d[i - 1][j - 1] + 1,  # substitution
                )
    return d[len(ref_words)][len(hyp_words)] / max(1, len(ref_words))

def main():
    ref_text = TEXT_FILE.read_text(encoding="utf-8").strip()
    ref_words = clean(ref_text)
    print(f"Reference text words: {len(ref_words)}")

    print("Loading faster-whisper base model on CPU...")
    model = WhisperModel("base", device="cpu", compute_type="int8")

    files = [
        ("Breeze TTS 2 (Voice Design: UK Male)", OUTPUT_DIR / "breeze_voice_design_uk_male.mp3"),
        ("Breeze TTS 2 (Voice Direction: Arthur)", OUTPUT_DIR / "breeze_voice_direction_arthur.mp3"),
    ]

    for label, audio_path in files:
        if not audio_path.exists():
            print(f"Skipping {label} (missing {audio_path.name})")
            continue
        print(f"\n==========================================")
        print(f"Verifying: {label}")
        print(f"File: {audio_path.name} ({audio_path.stat().st_size:,} bytes)")
        print(f"==========================================")
        segments, info = model.transcribe(str(audio_path), beam_size=5)
        asr_segments = list(segments)
        asr_text = " ".join([seg.text.strip() for seg in asr_segments])
        asr_words = clean(asr_text)

        wer = compute_wer(ref_words, asr_words)
        matcher = difflib.SequenceMatcher(None, ref_words, asr_words)
        similarity = matcher.ratio()

        print(f"Audio duration: {info.duration:.2f}s ({info.duration/60:.2f}m)")
        print(f"ASR word count: {len(asr_words)} (vs {len(ref_words)} ref)")
        print(f"WER: {wer:.4f} ({wer*100:.1f}%)")
        print(f"Word Similarity: {similarity:.4f} ({similarity*100:.1f}%)")
        print(f"Snippet: {asr_text[:200]}...")

        # Save ASR report
        asr_report = {
            "label": label,
            "file": audio_path.name,
            "duration_s": round(info.duration, 2),
            "ref_words": len(ref_words),
            "asr_words": len(asr_words),
            "wer": round(wer, 4),
            "similarity": round(similarity, 4),
            "transcript": asr_text,
        }
        (OUTPUT_DIR / f"{audio_path.stem}.asr.json").write_text(
            json.dumps(asr_report, indent=2), encoding="utf-8"
        )

if __name__ == "__main__":
    main()
