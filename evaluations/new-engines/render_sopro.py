"""Sopro v2 turbo CPU audition — Beatrice reference, offline path, upstream defaults.

Sopro ships **no native voices**: `--ref` is a required CLI argument and the
model repository contains no voice profiles, so every render needs a reference
clip. Dave chose Beatrice (`uk_female_samuel`), the repository's shipped default
narrator, on 2026-08-28. Nothing here picks a reference on its own.

Sampling is left at upstream's own defaults — temperature 0.8, top_p 0.9,
top_k 25 — by passing nothing. An earlier run of this gate passed
temperature 0.7, a value copied from the Audio8 harness and not documented
anywhere by Sopro; those files were not upstream-default renders.

`steps` is Sopro's acoustic solver step count and its documented default is 2.
That is the only setting varied here, because it is the obvious quality knob on
a flow-matching decoder and leaving it unexplored would say nothing about the
engine's ceiling.

Upstream splits long text into segments itself (`max_segment_chars` 300,
`max_seconds` 30) and carries `prompt_tokens` across the join, so the whole
prepared passage is passed in one call. Pre-chunking would test our splitter.

The streaming path is excluded: upstream states it is not bit-exact with the
offline path and recommends offline for quality.
"""

from __future__ import annotations

import os
import time

from shared import BEATRICE, OUTPUT, corpus, finish, verify_beatrice

try:
    import resource
except ImportError:  # Windows native audition; Docker/Linux records peak RSS.
    resource = None


SOURCE_COMMIT = "cb2b2a1949cd70cca469d689416906a6d181fa22"
PACKAGE_VERSION = "2.0.5"
MODEL_ID = "samuel-vitorino/sopro-v2-turbo"
MODEL_REVISION = "0abc5561e8ffd7b582b8aea2eb9e5f3bf7637c26"

SEED = 42
UPSTREAM_DEFAULT_STEPS = 2

# arm name -> steps. None means "pass nothing", i.e. upstream's own default.
ARMS = {
    "default": None,
    "steps16": 16,
}


def main() -> None:
    import torch

    _, prepared = corpus()
    reference = verify_beatrice()
    torch.set_num_threads(4)

    selected = {
        item.strip()
        for item in os.environ.get("SOPRO_ARMS", ",".join(ARMS)).split(",")
        if item.strip()
    }
    unknown = selected - set(ARMS)
    if unknown:
        raise ValueError(f"unknown SOPRO_ARMS: {sorted(unknown)}")

    from sopro import SoproTTS

    tts = SoproTTS.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, device="cpu"
    )
    defaults = tts.generation

    for arm, steps in ARMS.items():
        if arm not in selected:
            continue
        stem = f"sopro_v2_beatrice_{arm}"
        wav = OUTPUT / f"{stem}.wav"
        OUTPUT.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(SEED)
        started = time.perf_counter()
        # Only `steps` is ever passed. Everything else resolves to the values
        # in tts.generation, which are upstream's, not ours.
        extra = {} if steps is None else {"steps": steps}
        audio = tts.synthesize(
            prepared,
            ref_audio_path=str(BEATRICE),
            lang="en",
            **extra,
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
                "native_voices": "none — Sopro ships no voice profiles; --ref is required",
                "voice": "Beatrice reference, chosen by Dave 2026-08-28",
                "settings": {
                    "threads": 4,
                    "seed": 42,
                    "steps": steps if steps is not None else defaults.steps,
                    "steps_is_upstream_default": steps is None,
                    "temperature": defaults.temperature,
                    "top_p": defaults.top_p,
                    "top_k": defaults.top_k,
                    "max_seconds": defaults.max_seconds,
                    "max_segment_chars": defaults.max_segment_chars,
                    "prompt_tokens_carried": defaults.prompt_tokens,
                    "sampling_source": "upstream GenerationConfig defaults; nothing overridden but steps",
                },
                "chunking": (
                    "engine-internal: upstream splits on max_segment_chars and carries "
                    "prompt_tokens across the join, so the whole prepared passage is one call"
                ),
                "join_silence_ms": 0,
                "input_path": "repository explicit preparation; upstream text frontend is minimal and prefers words over symbols",
                **reference,
            },
        )


if __name__ == "__main__":
    main()
