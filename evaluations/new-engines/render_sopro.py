"""Sopro v2 turbo CPU audition — cloned Arthur, offline path, one call per arm.

Upstream splits long text into segments itself (`--max-seconds` caps a segment,
total length is unbounded), so this harness deliberately passes the whole
prepared passage in a single call. Pre-chunking here would test our splitter,
not Sopro's.

Upstream also states the streaming path is not bit-exact with the offline path
and recommends offline for best quality, so only the offline path is auditioned.
The int8 arm is the same-text numeric control, in the same role Scylla's FP32
control played: if both arms fail the same way, quantisation is not the cause.
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


SOURCE_COMMIT = "cb2b2a1949cd70cca469d689416906a6d181fa22"
PACKAGE_VERSION = "2.0.5"
MODEL_ID = "samuel-vitorino/sopro-v2-turbo"
MODEL_REVISION = "0abc5561e8ffd7b582b8aea2eb9e5f3bf7637c26"

# Upstream documented defaults for the offline path, pinned here so the arms
# differ only in the numeric precision of the AR weights.
STEPS = 2
TEMPERATURE = 0.7
TOP_P = 0.9
SEED = 42


def main() -> None:
    import torch

    _, prepared = corpus()
    reference = verify_reference()
    torch.set_num_threads(4)

    selected = {
        item.strip()
        for item in os.environ.get("SOPRO_ARMS", "fp32,int8").split(",")
        if item.strip()
    }
    unknown = selected - {"fp32", "int8"}
    if unknown:
        raise ValueError(f"unknown SOPRO_ARMS: {sorted(unknown)}")

    from sopro import SoproTTS

    for arm in ("fp32", "int8"):
        if arm not in selected:
            continue
        tts = SoproTTS.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            device="cpu",
            quantization="int8" if arm == "int8" else None,
        )
        stem = f"sopro_v2_arthur_{arm}"
        wav = OUTPUT / f"{stem}.wav"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(SEED)
        started = time.perf_counter()
        audio = tts.synthesize(
            prepared,
            ref_audio_path=str(ARTHUR),
            lang="en",
            steps=STEPS,
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        wall = time.perf_counter() - started
        tts.save_wav(str(wav), audio)
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
                "engine": "Sopro v2 turbo (120M)",
                "arm": arm,
                "runtime_commit": SOURCE_COMMIT,
                "runtime_package": f"sopro=={PACKAGE_VERSION}",
                "model_revision": MODEL_REVISION,
                "path": "offline (upstream states streaming is not bit-exact and prefers offline)",
                "voice": "cloned from the authentic user-authorized Arthur reference",
                "settings": {
                    "threads": 4,
                    "steps": STEPS,
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "seed": 42,
                    "int8_ar_weights": arm == "int8",
                },
                "chunking": (
                    "engine-internal: upstream splits long text into segments itself, "
                    "so the whole prepared passage is one call"
                ),
                "join_silence_ms": 0,
                "input_path": "repository explicit preparation; upstream text frontend is minimal and prefers words over symbols",
                **reference,
            },
        )


if __name__ == "__main__":
    main()
