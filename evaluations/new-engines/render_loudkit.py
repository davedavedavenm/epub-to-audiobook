"""LoudKit 0.1.0 / loudr-1 CPU audition — the engine's own native voices.

This renders loudr-1 as shipped: its managed voice profiles, upstream defaults,
no cloning and no reference clip. The roster's only English profiles are `joe`
and `kathleen`, both CC0 OHF-Voice donations; their accents are whatever they
are and that is for Dave to judge, not for this harness to pre-filter.

Backend: ONNX Runtime CPU, the path with a published faster-than-realtime CPU
figure. The PyTorch CPU reference measured RTF 7.564 here and is not a viable
book path, so it is available (`LOUDKIT_BACKEND=torch`) but not a default arm.

Passage API: `Engine.synthesize()` renders exactly one window and is documented
as such — calling it returned 10.2 s for this 1,142-character corpus.
`Engine.synthesize_long()` splits across windows and conditions each chunk on
its predecessor, which is the join behaviour under test.

Token cap: upstream's SamplingConfig.max_new_tokens and
WindowConfig.max_speech_tokens both default to 255, and the default-config runs
of 2026-08-28 reported hit_token_cap with chunks landing on exactly 255. The
`cap512` arm raises both so the dropped-content question can be answered
against a setting rather than assumed to be a property of the model.
"""

from __future__ import annotations

import dataclasses
import os
import time
from pathlib import Path

from shared import OUTPUT, corpus, finish

try:
    import resource
except ImportError:  # Windows native audition; Docker/Linux records peak RSS.
    resource = None


SOURCE_COMMIT = "58fd4a58de8980b42c1021492728876d67ea2718"  # tag v0.1.0
PACKAGE_VERSION = "0.1.0"
MODEL_ID = "loudreader/loudr-1"
MODEL_REVISION = "0fe297e449ba4f31113977f6c7f8c438fdfd1be3"

SEED = 42
RAISED_CAP = 512

# arm -> (native voice name, raised token cap or None for upstream defaults)
ARMS = {
    "joe": ("joe", None),
    "kathleen": ("kathleen", None),
    "kathleen_cap512": ("kathleen", RAISED_CAP),
}


def main() -> None:
    import loudkit as lk

    _, prepared = corpus()
    backend = os.environ.get("LOUDKIT_BACKEND", "onnx")
    device = {"onnx": "onnx", "torch": "cpu"}[backend]

    selected = {
        item.strip()
        for item in os.environ.get("LOUDKIT_ARMS", "joe,kathleen").split(",")
        if item.strip()
    }
    unknown = selected - set(ARMS)
    if unknown:
        raise ValueError(f"unknown LOUDKIT_ARMS: {sorted(unknown)}")

    for arm, (voice_name, cap) in ARMS.items():
        if arm not in selected:
            continue
        algorithm = None
        if cap is not None:
            base = lk.DEFAULT_ALGORITHM
            algorithm = dataclasses.replace(
                base,
                sampling=dataclasses.replace(base.sampling, max_new_tokens=cap),
                window=dataclasses.replace(base.window, max_speech_tokens=cap),
            )
        engine = lk.load(
            MODEL_ID,
            device=device,
            execution=lk.ExecutionOverrides(num_threads=4, onnx_provider="cpu"),
            algorithm=algorithm,
            revision=MODEL_REVISION,
        )
        voice = lk.voice(voice_name, repo=MODEL_ID, revision=MODEL_REVISION)
        stem = f"loudkit_{arm}_{backend}"
        wav = OUTPUT / f"{stem}.wav"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        result = engine.synthesize_long(prepared, voice, seed=SEED)
        wall = time.perf_counter() - started
        # Refuse only on structural truncation. hit_token_cap is surfaced, not
        # used to reject: upstream calls it "worth surfacing", and the quality
        # verdict is Dave's.
        if len(result.chunks) < 2 or result.duration < 60:
            raise RuntimeError(
                f"LoudKit {arm} arm did not window the passage: "
                f"chunks={len(result.chunks)} duration={result.duration:.3f}s "
                "— refusing to write a truncated audition"
            )
        result.save(str(wav), voice=voice_name, language="en")
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
                "voice": f"native shipped profile '{voice_name}' — no cloning, no reference clip",
                "voice_provenance": "roster lists joe and kathleen as the only English profiles, both CC0 OHF-Voice donations",
                "settings": {
                    "threads": 4,
                    "seed": 42,
                    "backend": backend,
                    "device": device,
                    "onnx_provider": "cpu",
                    "max_new_tokens": cap if cap is not None else lk.DEFAULT_ALGORITHM.sampling.max_new_tokens,
                    "max_speech_tokens": cap if cap is not None else lk.DEFAULT_ALGORITHM.window.max_speech_tokens,
                    "token_cap_is_upstream_default": cap is None,
                    "temperature": lk.DEFAULT_ALGORITHM.sampling.temperature,
                    "min_p": lk.DEFAULT_ALGORITHM.sampling.min_p,
                    "repetition_penalty": lk.DEFAULT_ALGORITHM.sampling.repetition_penalty,
                    "euler_steps": lk.DEFAULT_ALGORITHM.euler_steps,
                    "speed": 1.0,
                    "sampling_source": "upstream DEFAULT_ALGORITHM; only the token cap is varied, and only in the cap512 arm",
                },
                "chunking": (
                    "engine-internal: upstream manifest declares max_tokens 255 with "
                    "prefix_tokens 6 carry-over, so the whole prepared passage is one "
                    "synthesize_long call"
                ),
                "join_silence_ms": 0,
                "input_path": "repository explicit preparation; upstream warns difficult punctuation, numbers and abbreviations can shift prosody",
                # Upstream's own instrumentation, not an external transcript check.
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
            },
        )


if __name__ == "__main__":
    main()
