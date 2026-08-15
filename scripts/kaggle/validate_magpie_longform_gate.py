#!/usr/bin/env python3
"""Independently validate downloaded Magpie v2607 gate outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.kaggle import build_magpie_longform_gate as gate  # noqa: E402


EXPECTED_ARMS = {
    "magpie_aria": ("Aria", 0, False),
    "magpie_jason": ("Jason", 1, False),
    "magpie_john": ("John", 2, False),
    "magpie_leo": ("Leo", 3, False),
    "magpie_sofia": ("Sofia", 4, False),
    "magpie_john_longform": ("John", 2, True),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path, ffprobe: str | None) -> dict:
    if ffprobe is None:
        from mutagen.mp3 import MP3

        info = MP3(path).info
        return {
            "codec_name": "mp3",
            "sample_rate": int(info.sample_rate),
            "channels": int(info.channels),
            "duration": float(info.length),
        }
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(result.stdout)
    streams = [stream for stream in metadata["streams"] if stream["codec_type"] == "audio"]
    assert len(streams) == 1
    stream = streams[0]
    return {
        "codec_name": stream["codec_name"],
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration": float(metadata["format"]["duration"]),
    }


def validate(output: Path, *, ffmpeg: str, ffprobe: str | None = None) -> dict:
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["official_runtime_commit"] == gate.NEMO_SPEECH_COMMIT
    assert manifest["official_model_revision"] == gate.MODEL_REVISION
    assert manifest["model_bytes"] == gate.MODEL_BYTES
    assert manifest["model_sha256"] == gate.MODEL_SHA256
    assert manifest["paid_compute"] is False
    assert manifest["hosted_api_used"] is False
    assert manifest["officially_supported_gpu"] is False
    assert manifest["asr_used"] is False
    assert manifest["quality_verdict"] == "human listening required"
    assert manifest["sample_rate"] == 22050
    assert manifest["speakers"] == gate.SPEAKERS

    hard = (output / "hard_source.txt").read_text(encoding="utf-8").rstrip("\n")
    long = (output / "longform_source.txt").read_text(encoding="utf-8").rstrip("\n")
    assert hashlib.sha256(hard.encode()).hexdigest() == gate.HARD_SHA256
    assert hashlib.sha256(long.encode()).hexdigest() == gate.LONG_SHA256
    assert len(hard.split()) == 202 and len(long.split()) == 1470
    assert manifest["hard_text"]["sha256"] == gate.HARD_SHA256
    assert manifest["long_text"]["sha256"] == gate.LONG_SHA256
    assert manifest["hard_text"]["longform_chunks"] > 1
    assert manifest["long_text"]["longform_chunks"] > 1

    arms = {item["label"]: item for item in manifest["arms"]}
    assert set(arms) == set(EXPECTED_ARMS)
    hashes: set[str] = set()
    for label, (speaker, speaker_index, is_long) in EXPECTED_ARMS.items():
        item = arms[label]
        assert item["speaker"] == speaker
        assert item["speaker_index"] == speaker_index
        assert item["input_sha256"] == (gate.LONG_SHA256 if is_long else gate.HARD_SHA256)
        duration = float(item["duration_seconds"])
        assert (360.0 <= duration <= 900.0) if is_long else (30.0 <= duration <= 240.0)
        path = output / f"{label}.mp3"
        assert path.stat().st_size == item["mp3_bytes"] and path.stat().st_size > 100_000
        digest = sha256(path)
        assert digest == item["mp3_sha256"] and digest not in hashes
        hashes.add(digest)
        metadata = probe(path, ffprobe)
        assert metadata["codec_name"] == "mp3"
        assert metadata["sample_rate"] == 22050
        assert metadata["channels"] == 1
        probed_duration = metadata["duration"]
        assert abs(probed_duration - duration) < 0.2
        subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
            check=True,
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe"))
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("ffmpeg is required; pass --ffmpeg PATH")
    manifest = validate(args.output.resolve(), ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    summary = {
        item["label"]: {
            "speaker": item["speaker"],
            "duration_seconds": item["duration_seconds"],
            "mp3_bytes": item["mp3_bytes"],
            "rtf": item["rtf"],
        }
        for item in manifest["arms"]
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
