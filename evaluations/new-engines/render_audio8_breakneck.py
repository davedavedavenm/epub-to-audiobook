from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from huggingface_hub import snapshot_download

from arktts_runtime.registration import VoiceRegistration
from arktts_runtime.runtime import ArkTtsRuntime

from shared import (
    ARTHUR,
    ARTHUR_TRANSCRIPT,
    OUTPUT,
    finish,
    sentence_chunks,
    verify_reference,
)

try:
    import resource
except ImportError:
    resource = None

SOURCE_COMMIT = "421f71559848572431bd6229af3e1a73f25986a7"
MODEL_REVISION = "818569c6b832118ad68d61bbd873abe250fcd68a"
MODEL_ROOT = Path(os.environ.get("AUDITION_MODELS_ROOT", "/models"))
MODEL_DIR = MODEL_ROOT / "audio8"
VOICES_DIR = MODEL_ROOT / "audio8-voices"

TEXT_FILE = Path(__file__).resolve().parents[2] / "fixtures" / "breakneck_ch1_2pages_norm.txt"


def main() -> None:
    if not TEXT_FILE.exists():
        raise FileNotFoundError(f"Missing text file: {TEXT_FILE}")
    text = TEXT_FILE.read_text(encoding="utf-8").strip()
    reference = verify_reference()

    print("=== Downloading Audio8 ONNX INT4 Checkpoint ===")
    snapshot_download(
        "Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4",
        revision=MODEL_REVISION,
        local_dir=MODEL_DIR,
    )
    manifest = json.loads((MODEL_DIR / "runtime_manifest.json").read_text())
    registration = VoiceRegistration(
        MODEL_DIR / "registration", VOICES_DIR, manifest["model_fingerprint"]
    )
    registration.register(
        ARTHUR.read_bytes(), ARTHUR.name, ARTHUR_TRANSCRIPT, "arthur", overwrite=True
    )
    runtime = ArkTtsRuntime(MODEL_DIR, VOICES_DIR, "int4", "fp16", 4)

    chunks = sentence_chunks(text)
    print(f"=== Audio8 Synthesizing Breakneck (Pages 1-2): {len(chunks)} sentence chunks ===")
    started = time.perf_counter()
    pieces = []
    chunk_durations = []

    for index, chunk in enumerate(chunks, 1):
        c_start = time.perf_counter()
        audio, _ = runtime.synthesize(
            text=chunk,
            voice="arthur",
            max_new_tokens=1024,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            seed=42,  # Fixed seed for continuity
        )
        duration = len(audio) / int(manifest["sample_rate"])
        if duration < 0.5:
            raise RuntimeError(f"Audio8 chunk {index}/{len(chunks)} truncated")
        pieces.append(np.asarray(audio, dtype=np.float32))
        chunk_durations.append(round(duration, 3))
        c_elapsed = time.perf_counter() - c_start
        print(f"  Chunk {index}/{len(chunks)} rendered in {c_elapsed:.2f}s (audio: {duration:.2f}s, RTF: {c_elapsed/duration:.2f})")

    wav = OUTPUT / "audio8_breakneck_ch1_arthur.wav"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    full_audio = np.concatenate(pieces)
    sf.write(wav, full_audio, int(manifest["sample_rate"]))

    finish(
        stem="audio8_breakneck_ch1_arthur",
        wav=wav,
        input_text=text,
        wall_seconds=time.perf_counter() - started,
        peak_rss_mib=(
            round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
            if resource is not None else None
        ),
        report={
            "engine": "Audio8 TTS Preview 0.6B ONNX INT4",
            "book": "Breakneck - Dan Wang",
            "chapter": "Chapter 1 (Pages 1-2 Preview)",
            "voice": "arthur",
            "runtime_commit": SOURCE_COMMIT,
            "model_revision": MODEL_REVISION,
            "model_fingerprint": manifest["model_fingerprint"],
            "settings": {
                "threads": 4,
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 50,
                "seed": 42,
            },
            "chunk_strategy": "exact complete sentences; fixed seed 42; no added join silence",
            "chunk_count": len(chunks),
            "chunk_durations_seconds": chunk_durations,
            **reference,
        },
    )
    print("=== Audio8 Render Complete ===")


if __name__ == "__main__":
    main()
