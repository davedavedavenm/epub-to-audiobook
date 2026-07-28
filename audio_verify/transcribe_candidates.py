#!/usr/bin/env python3
"""Transcribe the local accent-candidate samples against their exact input."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from faster_whisper import WhisperModel


def words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9']+", " ", text.lower()).split()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", type=Path)
    parser.add_argument("--source", default="/source")
    parser.add_argument("--model", default="base")
    args = parser.parse_args()

    sys.path.insert(0, args.source)
    from voice_sample import sample_text_for

    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=4)
    results = []
    for audio in sorted(args.samples.glob("*.mp3")):
        if not audio.name.startswith(("me_", "ov_", "cv3_")):
            continue
        if audio.name.startswith("me_"):
            engine = "melotts"
        elif audio.name.startswith("ov_"):
            engine = "omnivoice"
        else:
            engine = "chatterbox"
        expected = words(sample_text_for(engine))
        segments, info = model.transcribe(str(audio), language="en", beam_size=1, vad_filter=True)
        transcript = " ".join((segment.text or "").strip() for segment in segments).strip()
        actual = words(transcript)
        expected_counts = Counter(expected)
        actual_counts = Counter(actual)
        overlap = sum(min(count, actual_counts.get(word, 0)) for word, count in expected_counts.items())
        results.append({
            "file": audio.name,
            "expected_words": len(expected),
            "asr_words": len(actual),
            "word_overlap_of_expected": round(overlap / max(1, len(expected)), 4),
            "word_overlap_of_asr": round(overlap / max(1, len(actual)), 4),
            "sequence_ratio": round(SequenceMatcher(None, expected, actual).ratio(), 4),
            "detected_language": info.language,
            "transcript": transcript,
        })
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
