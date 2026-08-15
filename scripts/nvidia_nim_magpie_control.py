#!/usr/bin/env python3
"""Make exactly one focused request to NVIDIA's hosted Magpie NIM.

This is a diagnostic, not an app integration or audiobook renderer.  It exists
to compare NVIDIA's hosted Riva/NIM path with the rejected raw NeMo path at the
first sentence boundary.  The client has no retry loop and refuses to overwrite
an earlier result.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import wave

import requests


ENDPOINT = (
    "https://877104f7-e885-42b9-8de8-f6e4c6303969."
    "invocation.api.nvcf.nvidia.com/v1/audio/synthesize"
)
VOICE = "Magpie-Multilingual.EN-US.Aria"
TEXT = (
    "In the spring of 1997, Apple was nine weeks from bankruptcy. "
    "Its CEO had been ousted, Steve Jobs had returned, and the share price "
    "had fallen 71 percent."
)


def validate_wav(path: Path) -> dict[str, int | str]:
    if path.stat().st_size < 10_000:
        raise RuntimeError(f"NVIDIA response is too small to be audio: {path.stat().st_size} bytes")
    with wave.open(str(path), "rb") as audio:
        details: dict[str, int | str] = {
            "channels": audio.getnchannels(),
            "sample_width": audio.getsampwidth(),
            "sample_rate": audio.getframerate(),
            "frames": audio.getnframes(),
        }
    if details["channels"] != 1 or details["sample_width"] != 2:
        raise RuntimeError(f"Unexpected NVIDIA WAV format: {details}")
    if details["sample_rate"] not in (22_050, 44_100):
        raise RuntimeError(f"Unexpected NVIDIA sample rate: {details}")
    details["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scratch/nvidia_nim_magpie_control/magpie_nim_aria.wav"),
    )
    parser.add_argument(
        "--confirm-single-free-prototype-request",
        action="store_true",
        help="Required acknowledgement that this sends one developer/prototype request.",
    )
    args = parser.parse_args()
    if not args.confirm_single_free_prototype_request:
        parser.error("--confirm-single-free-prototype-request is required")
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        parser.error("NVIDIA_API_KEY is not set")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")

    response = requests.post(
        ENDPOINT,
        headers={"Authorization": f"Bearer {key}"},
        files={
            "text": (None, TEXT),
            "language": (None, "en-US"),
            "voice": (None, VOICE),
            "encoding": (None, "LINEAR_PCM"),
            "sample_rate_hz": (None, "44100"),
        },
        timeout=(15, 180),
    )
    if response.status_code != 200:
        summary = (response.text or "").replace("\n", " ")[:300]
        raise RuntimeError(f"NVIDIA NIM returned HTTP {response.status_code}: {summary}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    part = args.output.with_suffix(args.output.suffix + ".part")
    part.write_bytes(response.content)
    try:
        details = validate_wav(part)
        part.replace(args.output)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    print(f"Wrote {args.output} ({details})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
