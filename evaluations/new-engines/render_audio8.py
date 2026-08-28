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
    bounded_chunks,
    corpus,
    finish,
    sentence_chunks,
    verify_reference,
)

try:
    import resource
except ImportError:  # Windows native audition; Docker/Linux records peak RSS.
    resource = None


SOURCE_COMMIT = "421f71559848572431bd6229af3e1a73f25986a7"
MODEL_REVISION = "818569c6b832118ad68d61bbd873abe250fcd68a"
MODEL_ROOT = Path(os.environ.get("AUDITION_MODELS_ROOT", "/models"))
MODEL_DIR = MODEL_ROOT / "audio8"
VOICES_DIR = MODEL_ROOT / "audio8-voices"


def main() -> None:
    raw, prepared = corpus()
    reference = verify_reference()
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
    selected_arms = {
        item.strip()
        for item in os.environ.get("AUDIO8_ARMS", "raw,prepared").split(",")
        if item.strip()
    }
    arm_specs = {
        "raw": (raw, bounded_chunks(raw, 150), False, 200),
        "prepared": (prepared, bounded_chunks(prepared, 150), False, 200),
        "prepared_sentence_fixed": (prepared, sentence_chunks(prepared), True, 0),
    }
    unknown = selected_arms - arm_specs.keys()
    if unknown:
        raise ValueError(f"unknown AUDIO8_ARMS: {sorted(unknown)}")
    for arm, (text, chunks, fixed_seed, join_silence_ms) in arm_specs.items():
        if arm not in selected_arms:
            continue
        started = time.perf_counter()
        pieces = []
        chunk_durations = []
        for index, chunk in enumerate(chunks):
            audio, _ = runtime.synthesize(
                text=chunk,
                voice="arthur",
                max_new_tokens=1024,
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                seed=42 if fixed_seed else 42 + index,
            )
            duration = len(audio) / int(manifest["sample_rate"])
            if duration < 0.5:
                raise RuntimeError(f"Audio8 chunk {index + 1}/{len(chunks)} truncated")
            if pieces and join_silence_ms:
                pieces.append(
                    np.zeros(
                        int(manifest["sample_rate"]) * join_silence_ms // 1000,
                        dtype=np.float32,
                    )
                )
            pieces.append(np.asarray(audio, dtype=np.float32))
            chunk_durations.append(round(duration, 3))
        wav = OUTPUT / f"audio8_arthur_{arm}.wav"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        sf.write(wav, np.concatenate(pieces), int(manifest["sample_rate"]))
        finish(
            stem=f"audio8_arthur_{arm}",
            wav=wav,
            input_text=text,
            wall_seconds=time.perf_counter() - started,
            peak_rss_mib=(
                round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
                if resource is not None else None
            ),
            report={
                "engine": "Audio8 TTS Preview 0.6B ONNX INT4",
                "arm": arm,
                "runtime_commit": SOURCE_COMMIT,
                "model_revision": MODEL_REVISION,
                "model_fingerprint": manifest["model_fingerprint"],
                "settings": {
                    "threads": 4,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 50,
                    "seed": 42 if fixed_seed else None,
                    "seed_base": None if fixed_seed else 42,
                },
                "chunk_strategy": (
                    "exact complete sentences; fixed seed; no added join silence"
                    if fixed_seed
                    else "upstream-recommended maximum 150 characters"
                ),
                "upstream_recommended_characters": 150,
                "chunk_lengths": [len(chunk) for chunk in chunks],
                "chunks_over_recommendation": [
                    len(chunk) for chunk in chunks if len(chunk) > 150
                ],
                "join_silence_ms": join_silence_ms,
                "chunks": chunks,
                "chunk_durations_seconds": chunk_durations,
                **reference,
            },
        )


if __name__ == "__main__":
    main()
