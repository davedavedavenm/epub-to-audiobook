"""Assemble the structurally repaired ZONOS2 audition without hiding the failed arm."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from render_zonos2 import MODEL_REVISION, SOURCE_COMMIT, SOURCE_RELEASE
from shared import OUTPUT, corpus, finish, sentence_chunks, verify_reference


SAMPLE_RATE = 44100


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _original_chunk(index: int) -> Path:
    explicit = OUTPUT / f"zonos2_arthur_q4_k_sentence_fixed_chunk_{index:02d}.wav"
    legacy = OUTPUT / f"zonos2_continuity_chunk_{index:02d}.wav"
    if explicit.is_file():
        return explicit
    if legacy.is_file():
        return legacy
    raise RuntimeError(f"missing retained ZONOS2 sentence chunk {index}")


def main() -> None:
    started = time.perf_counter()
    _, prepared = corpus()
    sentences = sentence_chunks(prepared)
    original_report = json.loads(
        (OUTPUT / "zonos2_arthur_q4_k_sentence_fixed.json").read_text(encoding="utf-8")
    )
    repair_report = json.loads(
        (OUTPUT / "zonos2_arthur_q4_k_iphone_split.json").read_text(encoding="utf-8")
    )
    if original_report["input_sha256"] != repair_report["input_sha256"]:
        original_sentence = next(
            chunk for chunk in sentences if chunk.startswith("Today the iPhone")
        )
        if _words(original_sentence) != _words(" ".join(repair_report["chunks"])):
            raise RuntimeError("ZONOS2 repair changed the source word content")

    pieces: list[np.ndarray] = []
    component_files: list[str] = []
    for index in range(1, 10):
        if index == 7:
            paths = [
                OUTPUT / "zonos2_arthur_q4_k_iphone_split_chunk_01.wav",
                OUTPUT / "zonos2_arthur_q4_k_iphone_split_chunk_02.wav",
            ]
        else:
            paths = [_original_chunk(index)]
        for path in paths:
            audio, rate = sf.read(path, dtype="float32")
            if rate != SAMPLE_RATE or audio.ndim != 1:
                raise RuntimeError(f"invalid ZONOS2 repair component: {path}")
            pieces.append(audio)
            component_files.append(path.name)

    wav = OUTPUT / "zonos2_arthur_q4_k_sentence_repaired.wav"
    sf.write(wav, np.concatenate(pieces), SAMPLE_RATE)
    finish(
        stem="zonos2_arthur_q4_k_sentence_repaired",
        wav=wav,
        input_text=prepared,
        wall_seconds=time.perf_counter() - started,
        report={
            "engine": "ZONOS2 official native GGUF",
            "arm": "q4_k_sentence_repaired",
            "runtime_release": SOURCE_RELEASE,
            "runtime_commit": SOURCE_COMMIT,
            "model_revision": MODEL_REVISION,
            "model_file": "zonos2-q4_k.gguf",
            "execution": (
                "reuse eight decoded chunks from the persistent full run; replace the "
                "truncated iPhone/App Store sentence with two decoded fixed-setting calls"
            ),
            "settings": original_report["settings"],
            "server_settings": original_report["server_settings"],
            "chunk_strategy": (
                "complete sentences; split only the failed compound sentence at its "
                "natural conjunction; fixed settings; no added join silence"
            ),
            "component_files": component_files,
            "failed_component_retained": _original_chunk(7).name,
            "join_silence_ms": 0,
            "input_path": "repository explicit preparation; native byte-tokenizer path",
            **verify_reference(),
        },
    )


if __name__ == "__main__":
    main()
