"""LoudKit 0.1.0 / loudr-1 CPU audition — cloned Arthur, ONNX and PyTorch arms.

Why the cloned reference is the only project-relevant arm: loudr-1 ships twenty
managed voices, but its own roster lists exactly two English profiles (`joe`,
`kathleen`), both CC0 donations from the OHF-Voice/Nabu Casa set — no shipped
English voice is British, so a managed-voice arm could not clear this project's
authentic-accent gate whatever it sounded like. Arthur is enrolled instead.

Why one call per arm: upstream's own `manifest.json` declares the chunking
(`max_tokens` 255, `prefix_tokens` 6, split on sentence and clause marks), so
LoudKit's windowing and its six-token carry-over are exactly what is under test.
Pre-chunking here would substitute our splitter for theirs and measure nothing.

Why two arms: ONNX Runtime CPU is the path with a published faster-than-realtime
CPU figure (1.21x on an M3 Pro, against 0.33x for the PyTorch CPU reference on
the same machine). The PyTorch arm is the same-text runtime control. Upstream
promises token-stream parity but not byte-identical waveforms across backends,
so if both arms fail the same way the runtime is not the explanation — the same
logic Scylla's FP32 control used to clear INT8.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from shared import ARTHUR, OUTPUT, corpus, finish, verify_reference

try:
    import resource
except ImportError:  # Windows native audition; Docker/Linux records peak RSS.
    resource = None


SOURCE_COMMIT = "58fd4a58de8980b42c1021492728876d67ea2718"  # tag v0.1.0
PACKAGE_VERSION = "0.1.0"
MODEL_ID = "loudreader/loudr-1"
MODEL_REVISION = "0fe297e449ba4f31113977f6c7f8c438fdfd1be3"
PROFILES = Path(os.environ.get("AUDITION_MODELS_ROOT", "/models")) / "loudkit-voices"

SEED = 42


def main() -> None:
    import loudkit as lk

    _, prepared = corpus()
    reference = verify_reference()

    selected = {
        item.strip()
        for item in os.environ.get("LOUDKIT_ARMS", "onnx,torch").split(",")
        if item.strip()
    }
    unknown = selected - {"onnx", "torch"}
    if unknown:
        raise ValueError(f"unknown LOUDKIT_ARMS: {sorted(unknown)}")

    PROFILES.mkdir(parents=True, exist_ok=True)
    profile_path = PROFILES / "arthur.safetensors"
    if not profile_path.is_file():
        enrolled = lk.enroll(
            str(ARTHUR), MODEL_ID, name="arthur", language="en",
            device="cpu", revision=MODEL_REVISION,
        )
        enrolled.save(str(profile_path))

    # loudkit selects the backend through the device literal: "onnx" runs ONNX
    # Runtime, "cpu" runs the PyTorch CPU reference path.
    devices = {"onnx": "onnx", "torch": "cpu"}
    for arm in ("onnx", "torch"):
        if arm not in selected:
            continue
        engine = lk.load(
            MODEL_ID,
            device=devices[arm],
            execution=lk.ExecutionOverrides(num_threads=4, onnx_provider="cpu"),
            revision=MODEL_REVISION,
        )
        voice = lk.voice(str(profile_path))
        stem = f"loudkit_arthur_{arm}"
        wav = OUTPUT / f"{stem}.wav"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        # synthesize() renders exactly one window and is documented as such;
        # synthesize_long() is the passage API that splits across windows and
        # conditions each chunk on its predecessor. Calling the single-window
        # form here silently returned 10.2 s for this 1,142-character passage.
        result = engine.synthesize_long(prepared, voice, seed=SEED)
        wall = time.perf_counter() - started
        # Refuse only on structural truncation. hit_token_cap means some chunk
        # stopped at the cap rather than at a stop token — upstream's words:
        # "usually a sign of a broken EOS path, and always worth surfacing".
        # Surfacing is not rejecting: it is recorded below and judged by the
        # ASR pass and by ear, not by this guard.
        if len(result.chunks) < 2 or result.duration < 60:
            raise RuntimeError(
                f"LoudKit {arm} arm did not window the passage: "
                f"chunks={len(result.chunks)} duration={result.duration:.3f}s "
                "— refusing to write a truncated audition"
            )
        result.save(str(wav), voice="arthur", language="en")
        finish(
            stem=stem,
            wav=wav,
            input_text=prepared,
            wall_seconds=wall,
            peak_rss_mib=(
                round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
                if resource is not None
                else None
            ),
            report={
                "engine": "LoudKit 0.1.0 / loudr-1",
                "arm": arm,
                "runtime_commit": SOURCE_COMMIT,
                "runtime_package": f"loudkit=={PACKAGE_VERSION}",
                "model_revision": MODEL_REVISION,
                "lineage": "derived from MIT-licensed Chatterbox (Resemble AI); Nano is this project's current default narrator",
                "voice": "cloned from the authentic user-authorized Arthur reference",
                "managed_voice_note": (
                    "not used: no shipped English voice is British — the roster lists "
                    "joe and kathleen as the only English profiles, both CC0 OHF-Voice donations"
                ),
                "settings": {
                    "threads": 4,
                    "seed": 42,
                    "backend": arm,
                    "device": devices[arm],
                    "onnx_provider": "cpu",
                },
                # Upstream's own truncation/repetition flags. hit_token_cap is the
                # exact failure class that ended the ZONOS2 arm (early EOS losing
                # the tail), so it is recorded whether or not it fires.
                "upstream_backend": getattr(result, "backend", None),
                "upstream_hit_token_cap": getattr(result, "hit_token_cap", None),
                "upstream_suspect": getattr(result, "suspect", None),
                "upstream_chunk_count": len(getattr(result, "chunks", []) or []),
                "upstream_inspections": [
                    str(item) for item in (getattr(result, "inspections", ()) or ())
                ],
                "upstream_duration_seconds": round(float(getattr(result, "duration", 0.0)), 3),
                "checkpoint_sha256": getattr(result, "checkpoint_sha256", None),
                "voice_sha256": getattr(result, "voice_sha256", None),
                "chunking": (
                    "engine-internal: upstream manifest declares max_tokens 255 with "
                    "prefix_tokens 6 carry-over, so the whole prepared passage is one call"
                ),
                "join_silence_ms": 0,
                "input_path": "repository explicit preparation; upstream warns difficult punctuation, numbers and abbreviations can shift prosody",
                **reference,
            },
        )


if __name__ == "__main__":
    main()
