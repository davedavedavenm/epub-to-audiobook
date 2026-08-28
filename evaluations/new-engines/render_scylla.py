from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from shared import OUTPUT, corpus, finish


SOURCE_COMMIT = "ab5d38ad46eec64a8e02a56c38a6e4f3c0cfdeb8"
MODEL_REVISION = "1cc69363815254f6a19bd42534a66ee49fc0fae0"
MODELS = Path(os.environ.get("AUDITION_MODELS_ROOT", "/models")) / "scylla"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> None:
    _, prepared = corpus()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    text_file = OUTPUT / "scylla_prepared_input.txt"
    text_file.write_text(prepared, encoding="utf-8")
    for bundle_name in ("onnx-int8", "onnx"):
        bundle_dir = MODELS / "v2" / bundle_name
        if (bundle_dir / "manifest.json").is_file():
            run([
                sys.executable, "-m", "scyllasband", "validate-bundle", str(bundle_dir)
            ])
            continue
        run([
            sys.executable, "-m", "scyllasband", "download",
            "--models-dir", str(MODELS),
            "--model-version", "v2",
            "--bundle-subdir", bundle_name,
            "--revision", MODEL_REVISION,
            "--yes",
        ])
    for arm, bundle_name in (("int8", "onnx-int8"), ("fp32", "onnx")):
        stem = f"scylla_v2_ink_{arm}"
        wav = OUTPUT / f"{stem}.wav"
        metadata = OUTPUT / f"{stem}_upstream.json"
        timing = OUTPUT / f"{stem}.time.txt"
        time_binary = shutil.which("/usr/bin/time")
        timing_prefix = [time_binary, "-v", "-o", str(timing)] if time_binary else []
        command = [
            *timing_prefix, sys.executable, "-m", "scyllasband", "speak",
            str(MODELS / "v2" / bundle_name),
            "--file", str(text_file),
            "--voice", "ink",
            "--language", "en_gb",
            "--steps", "8",
            "--sampler", "heun",
            "--onnx-intra-op-threads", "4",
            "--onnx-inter-op-threads", "2",
            "--metadata", str(metadata),
            "-o", str(wav),
        ]
        started = time.perf_counter()
        run(command)
        upstream_metadata = json.loads(metadata.read_text())
        from shared import parse_peak_rss
        finish(
            stem=stem,
            wav=wav,
            input_text=prepared,
            wall_seconds=time.perf_counter() - started,
            peak_rss_mib=parse_peak_rss(timing) if time_binary else None,
            report={
                "engine": "Scylla's Band v2",
                "arm": arm,
                "runtime_commit": SOURCE_COMMIT,
                "model_revision": MODEL_REVISION,
                "voice": "ink (upstream managed en_gb label; authenticity unverified until heard)",
                "settings": {"steps": 8, "sampler": "heun", "intra_op_threads": 4, "inter_op_threads": 2},
                "input_path": "repository explicit preparation, then upstream default text normalization",
                "upstream_metadata": upstream_metadata,
            },
        )


if __name__ == "__main__":
    main()
