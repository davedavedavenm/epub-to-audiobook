#!/usr/bin/env python3
"""Stage a free-T4 NVIDIA MagpieTTS v2607 listening gate.

The generated private Kaggle job uses NVIDIA's official NeMo Speech release,
the exact public v2607 checkpoint, its five baked English speakers, and the
model's own stateful sentence-chunk long-form path.  It never calls a hosted
NIM endpoint and deliberately performs no ASR quality ranking.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.kaggle.build_indextts25_gate import PREPARED_TEXT  # noqa: E402


OUT = ROOT / "scratch" / "magpie_longform" / "kernel"
FIXTURE = ROOT / "scripts" / "kaggle" / "fixtures" / "yellow_wallpaper_turn_reset_78.txt"

NEMO_SPEECH_COMMIT = "fd6a877539710e2b98f28c43272ff81312f83417"  # official v3.0.0 tag
MODEL_REVISION = "5023df68bd3f5b5ce6d666a50979bc501af145cc"  # official v2607 branch
MODEL_BYTES = 1_470_208_000
MODEL_SHA256 = "ec675fa8c02b9c1d5382c5c2b5a6acec6492c1e8344866c07cf3892185d18953"
FIXTURE_SHA256 = "80cafecf62a6a86ad30f39464f3b2792b136f2e797fc11cde723970a3ab697e1"
HARD_SHA256 = "8ccd447f2890e5f7cb7b9f8d41bb77cf4fe08a5cb40de2320a76559715afac1e"
LONG_SHA256 = "f8f21118f48ba6130438a8d3af3ef7c957b75599c4f5a158baa0635ac7545982"
SEED = 20_260_815
SPEAKERS = {"Aria": 0, "Jason": 1, "John": 2, "Leo": 3, "Sofia": 4}


def listening_text() -> str:
    raw = FIXTURE.read_text(encoding="utf-8").strip()
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", raw))
    chosen: list[str] = []
    words = 0
    for sentence in sentences:
        count = len(sentence.split())
        if chosen and words + count > 1_500:
            break
        chosen.append(sentence)
        words += count
    text = " ".join(chosen)
    assert words == 1_470
    assert len(chosen) == 79
    assert hashlib.sha256(text.encode()).hexdigest() == LONG_SHA256
    return text


KERNEL = r'''import base64
import dataclasses
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import wave

HARD_TEXT = base64.b64decode(__HARD_TEXT_B64__).decode("utf-8")
LONG_TEXT = base64.b64decode(__LONG_TEXT_B64__).decode("utf-8")
HARD_SHA256 = __HARD_SHA256__
LONG_SHA256 = __LONG_SHA256__
NEMO_SPEECH_COMMIT = __NEMO_SPEECH_COMMIT__
MODEL_REVISION = __MODEL_REVISION__
MODEL_BYTES = __MODEL_BYTES__
MODEL_SHA256 = __MODEL_SHA256__
SPEAKERS = __SPEAKERS__
SEED = __SEED__
RUNTIME = "/tmp/nemo-speech"
MODEL_DIR = "/tmp/magpie-model"
OUT = "/kaggle/working/out"


def sh(args, cwd=None, env=None):
    print("+", " ".join(str(item) for item in args), flush=True)
    return subprocess.run(args, cwd=cwd, env=env, check=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail_manifest(status, **details):
    os.makedirs(OUT, exist_ok=True)
    payload = {
        "status": status,
        "official_runtime_commit": NEMO_SPEECH_COMMIT,
        "official_model_revision": MODEL_REVISION,
        "paid_compute": False,
        **details,
    }
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


assert hashlib.sha256(HARD_TEXT.encode()).hexdigest() == HARD_SHA256
assert hashlib.sha256(LONG_TEXT.encode()).hexdigest() == LONG_SHA256
assert len(HARD_TEXT.split()) == 202
assert len(LONG_TEXT.split()) == 1470
assert not any(char.isdigit() for char in HARD_TEXT), "hard text must be explicit spoken wording"
os.makedirs(OUT, exist_ok=True)

if os.environ.get("MAGPIE_GATE_ENV") != "1":
    sh(["apt-get", "update", "-qq"])
    sh(["apt-get", "install", "-y", "-qq", "ffmpeg", "git"])
    sh(["git", "clone", "https://github.com/NVIDIA-NeMo/Speech.git", RUNTIME])
    sh(["git", "-C", RUNTIME, "checkout", "--detach", NEMO_SPEECH_COMMIT])
    actual = subprocess.check_output(
        ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual == NEMO_SPEECH_COMMIT
    # NVIDIA's model card says to install NeMo Speech with the TTS extra, plus
    # kaldialign.  Install the exact official release checkout rather than an
    # unpinned wheel or a community wrapper.
    sh([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-q", "-e", RUNTIME + "[tts]"])
    sh([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-q", "kaldialign"])
    env = dict(os.environ)
    env["MAGPIE_GATE_ENV"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = RUNTIME
    os.execve(sys.executable, [sys.executable, __file__], env)

assert subprocess.check_output(
    ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True
).strip() == NEMO_SPEECH_COMMIT

import numpy as np
import soundfile as sf
import torch
from huggingface_hub import hf_hub_download
from nemo.collections.tts.models import MagpieTTSModel
from nemo.collections.tts.parts.utils.tts_dataset_utils import (
    chunk_text_for_inference,
    get_tokenizer_for_language,
)

if not torch.cuda.is_available():
    fail_manifest("capacity_failed", error="CUDA unavailable; CPU fallback refused")
    raise SystemExit("CUDA unavailable; refusing CPU fallback")
gpu_name = torch.cuda.get_device_name(0)
if "T4" not in gpu_name:
    fail_manifest("capacity_failed", error=f"Expected Kaggle Tesla T4, got {gpu_name}")
    raise SystemExit(f"Expected Kaggle Tesla T4, got {gpu_name!r}")

model_path = hf_hub_download(
    repo_id="nvidia/magpie_tts_multilingual_357m",
    filename="magpie_tts_multilingual_357m.nemo",
    revision=MODEL_REVISION,
    local_dir=MODEL_DIR,
)
actual_model = (os.path.getsize(model_path), sha256(model_path))
assert actual_model == (MODEL_BYTES, MODEL_SHA256), actual_model

torch.cuda.reset_peak_memory_stats()
load_started = time.monotonic()
try:
    model = MagpieTTSModel.restore_from(model_path, map_location="cpu")
    model.eval()
    model.cuda()
except torch.cuda.OutOfMemoryError as exc:
    fail_manifest(
        "capacity_failed",
        error=type(exc).__name__,
        gpu=gpu_name,
        cuda_peak_allocated_gib=round(torch.cuda.max_memory_allocated() / 2**30, 3),
        cuda_peak_reserved_gib=round(torch.cuda.max_memory_reserved() / 2**30, 3),
    )
    raise
load_seconds = time.monotonic() - load_started


def chunk_count(text):
    available = list(model.tokenizer.tokenizers.keys())
    tokenizer_name = get_tokenizer_for_language(
        "en",
        available,
    )
    chunks, lengths, _ = chunk_text_for_inference(
        text=text,
        language="en",
        tokenizer_name=tokenizer_name,
        text_tokenizer=model.tokenizer,
        eos_token_id=model.eos_id,
    )
    assert len(chunks) == len(lengths) and len(chunks) > 1
    return len(chunks), [int(item) for item in lengths]


hard_chunks, hard_chunk_lengths = chunk_count(HARD_TEXT)
long_chunks, long_chunk_lengths = chunk_count(LONG_TEXT)


def render(label, text, speaker, speaker_index, expected_range):
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    with torch.inference_mode():
        audio, audio_len = model.do_tts(
            text,
            language="en",
            apply_TN=False,
            use_cfg=True,
            speaker_index=speaker_index,
        )
    synth_seconds = time.monotonic() - started
    frames = int(audio_len[0].item())
    samples = audio[0, :frames].detach().float().cpu().numpy()
    assert samples.size == frames and np.isfinite(samples).all()
    duration = frames / 22050
    assert expected_range[0] <= duration <= expected_range[1], duration
    rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))
    peak = float(np.max(np.abs(samples)))
    assert rms > 0.001 and peak > 0.01, (rms, peak)
    wav_path = os.path.join(OUT, label + ".wav")
    mp3_path = os.path.join(OUT, label + ".mp3")
    sf.write(wav_path, samples, 22050, subtype="PCM_16")
    with wave.open(wav_path, "rb") as check:
        assert check.getnchannels() == 1
        assert check.getsampwidth() == 2
        assert check.getframerate() == 22050
        assert check.getnframes() == frames
    sh(["ffmpeg", "-v", "error", "-i", wav_path, "-f", "null", "-"])
    sh(["ffmpeg", "-y", "-v", "error", "-i", wav_path,
        "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path])
    sh(["ffmpeg", "-v", "error", "-i", mp3_path, "-f", "null", "-"])
    evidence = {
        "label": label,
        "speaker": speaker,
        "speaker_index": speaker_index,
        "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "input_chars": len(text),
        "input_words": len(text.split()),
        "duration_seconds": round(duration, 3),
        "synthesis_seconds": round(synth_seconds, 3),
        "rtf": round(synth_seconds / duration, 3),
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "wav_bytes": os.path.getsize(wav_path),
        "wav_sha256": sha256(wav_path),
        "mp3_bytes": os.path.getsize(mp3_path),
        "mp3_sha256": sha256(mp3_path),
        "cuda_peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "cuda_peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
        "full_decode": "passed",
    }
    os.remove(wav_path)
    return evidence


arms = []
for speaker, index in SPEAKERS.items():
    arms.append(render("magpie_" + speaker.lower(), HARD_TEXT, speaker, index, (30.0, 240.0)))

# John is the release's public LibriVox-derived narrator, so he gets the bounded
# first 8-10 minute continuity gate.  Other voices advance only after listening.
arms.append(render("magpie_john_longform", LONG_TEXT, "John", SPEAKERS["John"], (360.0, 900.0)))
assert len({arm["mp3_sha256"] for arm in arms}) == len(arms)

params = model.inference_parameters
if dataclasses.is_dataclass(params):
    settings = dataclasses.asdict(params)
else:
    settings = {key: value for key, value in vars(params).items() if isinstance(value, (str, int, float, bool, type(None)))}

with open(os.path.join(OUT, "hard_source.txt"), "w", encoding="utf-8") as handle:
    handle.write(HARD_TEXT + "\n")
with open(os.path.join(OUT, "longform_source.txt"), "w", encoding="utf-8") as handle:
    handle.write(LONG_TEXT + "\n")

manifest = {
    "status": "complete",
    "official_docs": "https://docs.nvidia.com/nemo/speech/nightly/tts/magpietts-longform.html",
    "official_model_card": "https://huggingface.co/nvidia/magpie_tts_multilingual_357m",
    "official_runtime_repo": "https://github.com/NVIDIA-NeMo/Speech",
    "official_runtime_commit": NEMO_SPEECH_COMMIT,
    "official_runtime_release": "v3.0.0",
    "official_model": "nvidia/magpie_tts_multilingual_357m",
    "official_model_release": "v2607",
    "official_model_revision": MODEL_REVISION,
    "model_bytes": MODEL_BYTES,
    "model_sha256": MODEL_SHA256,
    "license": "NVIDIA Open Model License",
    "kaggle_machine_shape": "NvidiaTeslaT4",
    "officially_supported_gpu": False,
    "paid_compute": False,
    "hosted_api_used": False,
    "gpu": gpu_name,
    "python": sys.version,
    "torch": torch.__version__,
    "cuda": torch.version.cuda,
    "seed": SEED,
    "sample_rate": 22050,
    "load_seconds": round(load_seconds, 3),
    "speakers": SPEAKERS,
    "settings": settings,
    "hard_text": {
        "sha256": HARD_SHA256,
        "words": len(HARD_TEXT.split()),
        "longform_chunks": hard_chunks,
        "chunk_token_lengths": hard_chunk_lengths,
        "text_normalization": "repo explicit spoken wording; model TN disabled",
    },
    "long_text": {
        "sha256": LONG_SHA256,
        "words": len(LONG_TEXT.split()),
        "longform_chunks": long_chunks,
        "chunk_token_lengths": long_chunk_lengths,
        "text_normalization": "not required; public-domain prose contains no numeric test tokens",
    },
    "arms": arms,
    "asr_used": False,
    "quality_verdict": "human listening required",
}
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, ensure_ascii=False, default=str)
    handle.write("\n")
print("MAGPIE_GATE_COMPLETE", json.dumps(manifest, ensure_ascii=False, default=str), flush=True)
'''


def main() -> int:
    long_text = listening_text()
    assert hashlib.sha256(PREPARED_TEXT.encode()).hexdigest() == HARD_SHA256
    source = (
        KERNEL.replace(
            "__HARD_TEXT_B64__",
            repr(base64.b64encode(PREPARED_TEXT.encode("utf-8")).decode("ascii")),
        )
        .replace(
            "__LONG_TEXT_B64__",
            repr(base64.b64encode(long_text.encode("utf-8")).decode("ascii")),
        )
        .replace("__HARD_SHA256__", repr(HARD_SHA256))
        .replace("__LONG_SHA256__", repr(LONG_SHA256))
        .replace("__NEMO_SPEECH_COMMIT__", repr(NEMO_SPEECH_COMMIT))
        .replace("__MODEL_REVISION__", repr(MODEL_REVISION))
        .replace("__MODEL_BYTES__", repr(MODEL_BYTES))
        .replace("__MODEL_SHA256__", repr(MODEL_SHA256))
        .replace("__SPEAKERS__", repr(SPEAKERS))
        .replace("__SEED__", repr(SEED))
    )
    compile(source, "run_magpie_longform_gate.py", "exec")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run_magpie_longform_gate.py").write_text(source, encoding="utf-8", newline="\n")
    metadata = {
        "id": "davedavedavedavenm/nvidia-magpie-v2607-longform-gate",
        "title": "nvidia-magpie-v2607-longform-gate",
        "code_file": "run_magpie_longform_gate.py",
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
    print(f"hard={HARD_SHA256} long={LONG_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
