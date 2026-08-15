#!/usr/bin/env python3
"""Stage the bounded IndexTTS-2.5 free-Kaggle T4 audition gate.

The generated private kernel follows the exact upstream release and model
snapshot.  It loads the model once and renders only two short, same-reference
arms: Index's native normalizer and the repo's explicit number/currency text.
No ASR is used and no production defaults are changed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "indextts25_gate" / "kernel"
APP_COMMIT = "c33442e356e908cdee49cb08d89c25c8f9f5dcec"
INDEX_COMMIT = "39207d91c30899cad1e7c1b9eb678c241f678e55"
MODEL_REVISION = "c39ce5ba981572cb187443877ff559dfb246ce63"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
ARTHUR_BYTES = 864_182
RAW_SHA256 = "f6294d0b3a9257277f26cf505f6814933500da641f826d3e6ca3cc1e28c45a0f"
PREPARED_SHA256 = "57b51dd4df3795dda2e1dab04c68d25c7eea97f5b160dfd8b65537bd5ee2389c"
SEED = 20_260_815

# Byte-pinned output of the deployed explicit number/currency profile.  Keep it
# literal: importing the production normalizer from an incomplete local Python
# environment can silently take its documented fallback path and stage the
# wrong comparison text.
PREPARED_TEXT = (
    "In the spring of nineteen ninety-seven, Apple was nine weeks from bankruptcy. Its C E O had "
    "been ousted, Steve Jobs had returned, the share price had fallen seventy-one percent, and the "
    "company was burning through one point two billion dollars a year. Few analysts at Goldman Sachs "
    "believed it would survive to see the year two thousand.\n\n"
    "What changed was not one decision, but a thousand small ones. Scott Forstall, Jony Ive, and a "
    "young engineer named Nguyen worked eighteen-hour days, six days a week, for months on end. "
    "Between two thousand one and two thousand seven, Apple's partners in Shenzhen and Zhengzhou "
    "scaled from three thousand four hundred workers to over two hundred and thirty thousand; a "
    "single Foxconn campus drew 1.5 gigawatts.\n\n"
    "Today the iPhone accounts for roughly fifty-two percent of revenue, and the App Store for some "
    "twenty-four point six billion pounds a year. Rivals — Huawei, Xiaomi, Samsung — circle constantly. "
    "Whether that dependence is a triumph or a trap, for the W T O, for the E U, and for a supply "
    "chain seven thousand miles long, is the question Doctor Wang has spent a decade trying to answer."
)


KERNEL = r'''import base64
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.request
import wave

APP_COMMIT = __APP_COMMIT__
INDEX_COMMIT = __INDEX_COMMIT__
MODEL_REVISION = __MODEL_REVISION__
ARTHUR_SHA256 = __ARTHUR_SHA256__
ARTHUR_BYTES = __ARTHUR_BYTES__
RAW_TEXT = base64.b64decode(__RAW_B64__).decode("utf-8")
PREPARED_TEXT = base64.b64decode(__PREPARED_B64__).decode("utf-8")
RAW_SHA256 = __RAW_SHA256__
PREPARED_SHA256 = __PREPARED_SHA256__
SEED = __SEED__
RUNTIME = "/tmp/index-tts"
CHECKPOINTS = "/tmp/index-checkpoints"
REFERENCE = "/tmp/arthur.wav"
OUT = "/kaggle/working/out"


def sh(args, cwd=None, env=None):
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd, env=env, check=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


assert hashlib.sha256(RAW_TEXT.encode()).hexdigest() == RAW_SHA256
assert hashlib.sha256(PREPARED_TEXT.encode()).hexdigest() == PREPARED_SHA256
os.makedirs(OUT, exist_ok=True)

if os.environ.get("INDEX_GATE_ENV") != "1":
    sh(["apt-get", "update", "-qq"])
    sh(["apt-get", "install", "-y", "-qq", "ffmpeg", "git"])
    sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    sh(["git", "clone", "https://github.com/index-tts/index-tts.git", RUNTIME])
    sh(["git", "-C", RUNTIME, "checkout", "--detach", INDEX_COMMIT])
    actual = subprocess.check_output(
        ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual == INDEX_COMMIT
    env = dict(os.environ)
    env["UV_CACHE_DIR"] = "/tmp/index-uv-cache"
    sh(["uv", "sync", "--frozen", "--no-dev"], cwd=RUNTIME, env=env)
    sh(["uv", "cache", "clean"], cwd=RUNTIME, env=env)
    env["INDEX_GATE_ENV"] = "1"
    env["PYTHONPATH"] = RUNTIME
    os.execve(
        RUNTIME + "/.venv/bin/python",
        [RUNTIME + "/.venv/bin/python", __file__],
        env,
    )

assert subprocess.check_output(
    ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True
).strip() == INDEX_COMMIT

import numpy as np
import torch
from huggingface_hub import snapshot_download

if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable; refusing CPU fallback")
gpu_name = torch.cuda.get_device_name(0)
if "T4" not in gpu_name:
    raise SystemExit(f"Expected Kaggle Tesla T4, got {gpu_name!r}")

snapshot_download(
    repo_id="IndexTeam/IndexTTS-2.5",
    revision=MODEL_REVISION,
    local_dir=CHECKPOINTS,
    ignore_patterns=["qwen0.6bemo4-merge/*"],
)
expected_weights = {
    "codec.pth": (607_290_935, "d15cbed16a40f478438c961fb043f68dfa6353bf56c966761315db3433e9722c"),
    "gpt.pth": (3_259_599_833, "43a8f4c30eccdf201958d3b9713511482c19d56dc20b0b1c4ee1e6b080b19d85"),
    "s2mel.pth": (414_908_601, "9b1b0003fc189c94cc349758d7ebc25f903b7eb2de4602879959cc64ce816456"),
}
weight_evidence = {}
for name, (expected_bytes, expected_sha) in expected_weights.items():
    path = os.path.join(CHECKPOINTS, name)
    actual = (os.path.getsize(path), sha256(path))
    assert actual == (expected_bytes, expected_sha), (name, actual)
    weight_evidence[name] = {"bytes": actual[0], "sha256": actual[1]}

urllib.request.urlretrieve(
    "https://github.com/davedavedavenm/epub-to-audiobook/raw/"
    + APP_COMMIT + "/chatterbox/voices/uk_male_minter.wav",
    REFERENCE,
)
assert os.path.getsize(REFERENCE) == ARTHUR_BYTES
assert sha256(REFERENCE) == ARTHUR_SHA256
with wave.open(REFERENCE, "rb") as ref:
    reference_evidence = {
        "sha256": ARTHUR_SHA256,
        "bytes": ARTHUR_BYTES,
        "channels": ref.getnchannels(),
        "sample_rate": ref.getframerate(),
        "sample_width": ref.getsampwidth(),
        "frames": ref.getnframes(),
        "input_seconds": ref.getnframes() / ref.getframerate(),
        "upstream_seconds_used": 15.0,
    }
assert reference_evidence["channels"] == 1
assert reference_evidence["sample_rate"] == 24000
assert reference_evidence["sample_width"] == 2

sys.path.insert(0, RUNTIME)
from indextts.infer_v2_5 import IndexTTS2

torch.cuda.reset_peak_memory_stats()
load_started = time.monotonic()
try:
    tts = IndexTTS2(
        cfg_path=os.path.join(CHECKPOINTS, "config.yaml"),
        model_dir=CHECKPOINTS,
        device="cuda:0",
        use_bf16=False,
        use_cuda_kernel=False,
        use_deepspeed=False,
        use_accel=False,
        use_torch_compile=False,
        use_qwen_emo=False,
    )
except torch.cuda.OutOfMemoryError as exc:
    failure = {
        "status": "capacity_failed",
        "error": type(exc).__name__,
        "gpu": gpu_name,
        "repo_commit": INDEX_COMMIT,
        "model_revision": MODEL_REVISION,
        "cuda_peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "cuda_peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
    }
    open(os.path.join(OUT, "manifest.json"), "w").write(json.dumps(failure, indent=2) + "\n")
    raise
load_seconds = time.monotonic() - load_started


def normalized_text(text, enabled):
    value = tts.text_process.clean_pattern.sub(
        lambda match: tts.text_process.char_rep_map[match.group()], text
    )
    return tts.text_process.normalize(value) if enabled else value


arms = [
    ("native", RAW_TEXT, True),
    ("prepared", PREPARED_TEXT, False),
]
manifest_arms = []
for label, text, text_normalization in arms:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.cuda.reset_peak_memory_stats()
    output_wav = os.path.join(OUT, label + ".wav")
    started = time.monotonic()
    result = tts.infer(
        spk_audio_prompt=REFERENCE,
        text=text,
        output_path=output_wav,
        lang="EN",
        use_random=False,
        interval_silence=200,
        max_text_tokens_per_segment=120,
        duration_factor=1.0,
        text_normalization=text_normalization,
        verbose=True,
        top_p=0.8,
        top_k=30,
        temperature=0.8,
        num_beams=3,
        repetition_penalty=10.0,
        max_mel_tokens=1500,
    )
    synth_seconds = time.monotonic() - started
    assert result == output_wav and os.path.getsize(output_wav) > 250_000
    with wave.open(output_wav, "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 22050
        duration = audio.getnframes() / audio.getframerate()
    assert 25.0 <= duration <= 150.0, (label, duration)
    sh(["ffmpeg", "-v", "error", "-i", output_wav, "-f", "null", "-"])
    output_mp3 = os.path.join(OUT, label + ".mp3")
    sh(["ffmpeg", "-y", "-v", "error", "-i", output_wav,
        "-codec:a", "libmp3lame", "-b:a", "192k", output_mp3])
    sh(["ffmpeg", "-v", "error", "-i", output_mp3, "-f", "null", "-"])
    normalized = normalized_text(text, text_normalization)
    open(os.path.join(OUT, label + "_source.txt"), "w", encoding="utf-8").write(text + "\n")
    open(os.path.join(OUT, label + "_normalized.txt"), "w", encoding="utf-8").write(normalized + "\n")
    manifest_arms.append({
        "label": label,
        "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "input_chars": len(text),
        "input_words": len(text.split()),
        "text_normalization": text_normalization,
        "normalized_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "normalized_text": normalized,
        "duration_seconds": round(duration, 3),
        "synthesis_seconds": round(synth_seconds, 3),
        "rtf": round(synth_seconds / duration, 3),
        "wav_bytes": os.path.getsize(output_wav),
        "wav_sha256": sha256(output_wav),
        "mp3_bytes": os.path.getsize(output_mp3),
        "mp3_sha256": sha256(output_mp3),
        "cuda_peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "cuda_peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
        "full_decode": "passed",
    })

manifest = {
    "status": "complete",
    "official_docs": "https://github.com/index-tts/index-tts/blob/" + INDEX_COMMIT + "/README.md",
    "official_runtime_commit": INDEX_COMMIT,
    "official_model": "IndexTeam/IndexTTS-2.5",
    "official_model_revision": MODEL_REVISION,
    "license": "Bilibili Model Use License",
    "kaggle_machine_shape": "NvidiaTeslaT4",
    "paid_compute": False,
    "gpu": gpu_name,
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "seed": SEED,
    "load_seconds": round(load_seconds, 3),
    "precision": "FP32",
    "qwen_emotion_loaded": False,
    "reference": reference_evidence,
    "weights": weight_evidence,
    "settings": {
        "top_p": 0.8, "top_k": 30, "temperature": 0.8,
        "num_beams": 3, "repetition_penalty": 10.0,
        "max_mel_tokens": 1500, "max_text_tokens_per_segment": 120,
        "interval_silence_ms": 200, "duration_factor": 1.0,
    },
    "arms": manifest_arms,
    "asr_used": False,
}
open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8").write(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
)
print("INDEXTTS25_GATE_COMPLETE", json.dumps(manifest, ensure_ascii=False), flush=True)
'''


def source_texts() -> tuple[str, str]:
    sys.path.insert(0, str(ROOT / "webapp"))
    try:
        from voice_sample import SAMPLE_TEXT

        return SAMPLE_TEXT, PREPARED_TEXT
    finally:
        sys.path.remove(str(ROOT / "webapp"))


def main() -> int:
    raw, prepared = source_texts()
    assert hashlib.sha256(raw.encode()).hexdigest() == RAW_SHA256
    assert hashlib.sha256(prepared.encode()).hexdigest() == PREPARED_SHA256
    source = (
        KERNEL.replace("__APP_COMMIT__", repr(APP_COMMIT))
        .replace("__INDEX_COMMIT__", repr(INDEX_COMMIT))
        .replace("__MODEL_REVISION__", repr(MODEL_REVISION))
        .replace("__ARTHUR_SHA256__", repr(ARTHUR_SHA256))
        .replace("__ARTHUR_BYTES__", repr(ARTHUR_BYTES))
        .replace("__RAW_B64__", repr(base64.b64encode(raw.encode()).decode()))
        .replace("__PREPARED_B64__", repr(base64.b64encode(prepared.encode()).decode()))
        .replace("__RAW_SHA256__", repr(RAW_SHA256))
        .replace("__PREPARED_SHA256__", repr(PREPARED_SHA256))
        .replace("__SEED__", repr(SEED))
    )
    compile(source, "run_indextts25_gate.py", "exec")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run_indextts25_gate.py").write_text(source, encoding="utf-8", newline="\n")
    metadata = {
        "id": "davedavedavedavenm/indextts25-arthur-focused-gate",
        "title": "indextts25-arthur-focused-gate",
        "code_file": "run_indextts25_gate.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (OUT / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"staged {OUT}")
    print(f"raw={RAW_SHA256} prepared={PREPARED_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
