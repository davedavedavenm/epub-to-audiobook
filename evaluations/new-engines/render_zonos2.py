from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from shared import ARTHUR, OUTPUT, corpus, finish, parse_peak_rss, verify_reference


SOURCE_COMMIT = "39a4d01558db86dca1219273992c77ebc8e03991"
SOURCE_RELEASE = "v0.5.1"
MODEL_REVISION = "75c877ec8ac86dda42bfc0e9968c87f29e10ef57"
MODELS = Path(
    os.environ.get(
        "ZONOS2_MODELS_DIR",
        str(Path(os.environ.get("AUDITION_MODELS_ROOT", "/models")) / "zonos2"),
    )
)


def cli_path() -> Path:
    configured = os.environ.get("ZONOS2_CLI")
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise RuntimeError(f"configured ZONOS2_CLI does not exist: {path}")
        return path
    matches = list(Path("/upstream/build").rglob("zonos2-cli"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one zonos2-cli build output, found: {matches}")
    return matches[0]


def main() -> None:
    prepared_path = os.environ.get("AUDITION_PREPARED_TEXT")
    if prepared_path:
        prepared = Path(prepared_path).read_text(encoding="utf-8")
    else:
        _, prepared = corpus()
    text_mode = os.environ.get("ZONOS2_TEXT_MODE", "full").strip().lower()
    if text_mode == "first_paragraph":
        prepared = prepared.split("\n\n", 1)[0]
    elif text_mode != "full":
        raise ValueError("ZONOS2_TEXT_MODE must be full or first_paragraph")
    reference = verify_reference()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    required = ["dac.gguf", "spk-encoder.gguf", "zonos2-q4_k.gguf", "zonos2-q8_0.gguf"]
    selected_arms = {
        item.strip() for item in os.environ.get("ZONOS2_ARMS", "q4_k,q8_0").split(",")
        if item.strip()
    }
    required = required[:2] + [
        filename for arm, filename in (("q4_k", required[2]), ("q8_0", required[3]))
        if arm in selected_arms
    ]
    if not all((MODELS / filename).is_file() for filename in required):
        from huggingface_hub import snapshot_download

        snapshot_download(
            "Zyphra/ZONOS2-GGUF",
            revision=MODEL_REVISION,
            allow_patterns=required,
            local_dir=MODELS,
        )
    binary = cli_path()
    for arm, filename in (("q4_k", "zonos2-q4_k.gguf"), ("q8_0", "zonos2-q8_0.gguf")):
        if arm not in selected_arms:
            continue
        suffix = "_short" if text_mode == "first_paragraph" else ""
        stem = f"zonos2_arthur_{arm}{suffix}"
        wav = OUTPUT / f"{stem}.wav"
        timing = OUTPUT / f"{stem}.time.txt"
        command = [
            "/usr/bin/time", "-v", "-o", str(timing),
            str(binary), str(MODELS / filename),
            "--tts", prepared, str(wav),
            "--dac", str(MODELS / "dac.gguf"),
            "--clone", str(ARTHUR),
            "--spk-encoder", str(MODELS / "spk-encoder.gguf"),
            "--cpu", "--seed", "42", "--max", "8000",
        ]
        started = time.perf_counter()
        subprocess.run(command, check=True)
        finish(
            stem=stem,
            wav=wav,
            input_text=prepared,
            wall_seconds=time.perf_counter() - started,
            peak_rss_mib=parse_peak_rss(timing),
            report={
                "engine": "ZONOS2 official native GGUF",
                "arm": arm,
                "runtime_release": SOURCE_RELEASE,
                "runtime_commit": SOURCE_COMMIT,
                "model_revision": MODEL_REVISION,
                "model_file": filename,
                "settings": {"backend": "CPU", "cpu_cap": 4, "seed": 42, "max_frames": 8000, "accurate_mode": True},
                "input_path": "repository explicit preparation; native byte-tokenizer path",
                "text_mode": text_mode,
                **reference,
            },
        )


if __name__ == "__main__":
    main()
