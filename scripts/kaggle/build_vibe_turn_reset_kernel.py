#!/usr/bin/env python3
"""Stage a blind, free-Kaggle VibeVoice same-speaker-turn listening gate.

This gate changes only the placement of repeated ``Speaker 1:`` turns.  It
keeps the pinned official weights, audited community runtime, Arthur reference,
cfg, DDPM steps, seed and source words fixed.  The community runtime explicitly
recommends repeated turns with the same speaker label when speech becomes too
fast; this is the controlled test of that documented remedy.

Usage::

    python scripts/kaggle/build_vibe_turn_reset_kernel.py
    python -m kaggle kernels push -p scratch/vibe_turn_reset/kernel_A
    python -m kaggle kernels push -p scratch/vibe_turn_reset/kernel_B
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "vibe_turn_reset"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "yellow_wallpaper_turn_reset_78.txt"
RUNTIME_SHA = "07cb79feadd2d3fd7f47530d4c964a12857936a0"
REF_SHA = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
FULL_TEXT_SHA = "317e27c2769f23325e169bbbd0714fa462f063d601dc62c7fd6c003915714daa"
RAW_EXCERPT_SHA = "e27148a07d668355f99cbeab74635427e41f1c9ba245a10fdf14e58508827761"
FIXTURE_TEXT_SHA = "203787eef3b8dfdadcd5be9cf14af51f866d5020c527887f3ad683a26d6a0623"
SOURCE_SHA = "3b8808c4295c11cae751a33067a502452e3ebe4a10c7aaea5cadfe108625f0f4"
RUNTIME_DOCS = (
    "https://github.com/vibevoice-community/VibeVoice/blob/"
    f"{RUNTIME_SHA}/README.md"
)

# These groups are expressed as slices of the canonical Yellow Wallpaper
# paragraphs. Boundaries are the sole variable.
GROUPS = {
    "short_turns": [(0, 15), (15, 26), (26, 34), (34, 48),
                    (48, 60), (60, 68), (68, 78)],
    "long_turns": [(0, 23), (23, 40), (40, 61), (61, 78)],
}
EXPECTED_SCRIPT_SHA = {
    "short_turns": "433c52a91a8bd8440d5f661ef8c30b219dba85abf9a841fd64717c5434f40a49",
    "long_turns": "817a7ecaf8f6a69639cd43cdee9ea25f4fab7287a6e9bb4d5d7d25e7e7d3300c",
}


KERNEL = r"""import difflib
import gc
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

RUNTIME_SHA = __RUNTIME_SHA__
REF_SHA = __REF_SHA__
SOURCE_SHA = __SOURCE_SHA__
BUILDER_SHA = __BUILDER_SHA__
RUNTIME_DOCS = __RUNTIME_DOCS__
SOURCE_TEXT = json.loads(r'''__SOURCE_TEXT__''')
ARMS = json.loads(r'''__ARMS__''')
OUT = "/kaggle/working"
RUNTIME = "/tmp/VibeVoice"
REF = "/tmp/uk_male_minter.wav"
REF_URL = ("https://github.com/davedavedavenm/epub-to-audiobook/raw/master/"
           "chatterbox/voices/uk_male_minter.wav")


def sh(args, cwd=None, env=None):
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=cwd, env=env, check=True)


def norm(value):
    return re.sub(r"[^a-z0-9' ]+", " ", value.lower()).split()


def canonical(value):
    return re.sub(r"\s+", " ", value).strip()


assert hashlib.sha256(SOURCE_TEXT.encode()).hexdigest() == SOURCE_SHA
assert len(norm(SOURCE_TEXT)) == 1998
assert "draught ," not in SOURCE_TEXT and "draught, and" in SOURCE_TEXT
source_canonical = canonical(SOURCE_TEXT)
for arm in ARMS:
    assert canonical(" ".join(arm["groups"])) == source_canonical
    arm["script"] = "\n".join("Speaker 1: " + canonical(group)
                                for group in arm["groups"])
    arm["serialized_prompt_sha256"] = hashlib.sha256(
        arm["script"].encode()).hexdigest()

VENV = "/tmp/vibevoice-venv"
VENV_PY = VENV + "/bin/python"
if os.environ.get("VIBEVOICE_CLEAN_VENV") != "1":
    sh(["apt-get", "update", "-qq"])
    sh(["apt-get", "install", "-y", "-qq", "ffmpeg", "git"])
    if not shutil.which("uv"):
        sh([sys.executable, "-m", "pip", "install", "-q", "uv"])
    # Match the repository's already-proven CosyVoice Kaggle isolation pattern:
    # uv-managed Python 3.10, seeded venv, then ordinary pip inside that venv.
    sh(["uv", "python", "install", "3.10"])
    sh(["uv", "venv", "--python", "3.10", "--seed", VENV])
    clean_env = dict(os.environ)
    clean_env.pop("PYTHONPATH", None)
    clean_env["PYTHONNOUSERSITE"] = "1"
    sh([VENV_PY, "-m", "pip", "install", "-q",
        "torch==2.3.1", "torchvision==0.18.1", "torchaudio==2.3.1",
        "--index-url", "https://download.pytorch.org/whl/cu121"], env=clean_env)
    sh(["git", "clone", "https://github.com/vibevoice-community/VibeVoice.git", RUNTIME])
    sh(["git", "-C", RUNTIME, "checkout", "--detach", RUNTIME_SHA])
    assert subprocess.check_output(
        ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True).strip() == RUNTIME_SHA
    # Isolate this old pinned runtime from Kaggle's global NumPy-2 application
    # stack. One resolver transaction keeps the NumPy contract internally clean.
    sh([VENV_PY, "-m", "pip", "install", "-q", "--no-cache-dir",
        # SciPy 1.12 is the official branch supporting Python 3.9-3.12 with
        # NumPy >=1.22.4,<2.0.0. Pin the scientific stack instead of letting a
        # mid-2026 Kaggle image resolve future releases around this 2025 runtime.
        "numpy==1.26.4", "scipy==1.12.0", "scikit-learn==1.4.2",
        "-e", RUNTIME, "faster-whisper"], env=clean_env)
    sh([VENV_PY, "-c",
        "import numpy; from numpy.lib.stride_tricks import broadcast_to; "
        "print('numpy', numpy.__version__)"], env=clean_env)
    clean_env["VIBEVOICE_CLEAN_VENV"] = "1"
    os.execve(VENV_PY, [VENV_PY, __file__], clean_env)

assert os.environ.get("VIBEVOICE_CLEAN_VENV") == "1"
assert subprocess.check_output(
    ["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True).strip() == RUNTIME_SHA
urllib.request.urlretrieve(REF_URL, REF)
ref = open(REF, "rb").read()
assert ref[:4] == b"RIFF" and len(ref) == 864182
assert hashlib.sha256(ref).hexdigest() == REF_SHA

sys.path.insert(0, RUNTIME)
import numpy as np
import torch
from vibevoice.modular.modeling_vibevoice_inference import (
    VibeVoiceForConditionalGenerationInference,
)
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable; refusing CPU fallback")
print("gpu", torch.cuda.get_device_name(0), "torch", torch.__version__, flush=True)
processor = VibeVoiceProcessor.from_pretrained("microsoft/VibeVoice-1.5B")
model = VibeVoiceForConditionalGenerationInference.from_pretrained(
    "microsoft/VibeVoice-1.5B", torch_dtype=torch.float16,
    device_map="cuda", attn_implementation="sdpa").eval()
model.set_ddpm_inference_steps(num_steps=10)

from faster_whisper import WhisperModel
asr_model = WhisperModel("base.en", device="cpu", compute_type="int8")

summary = []
for arm in ARMS:
    label = arm["label"]
    print("\n===== BLIND ARM", label, "turns", len(arm["groups"]), "=====", flush=True)
    inputs = processor(text=[arm["script"]], voice_samples=[[REF]], padding=True,
                       return_tensors="pt", return_attention_mask=True)
    inputs = {key: (value.to("cuda") if torch.is_tensor(value) else value)
              for key, value in inputs.items()}
    torch.manual_seed(12345)
    torch.cuda.manual_seed_all(12345)
    torch.cuda.reset_peak_memory_stats()
    started = time.time()
    with torch.inference_mode():
        outputs = model.generate(
            **inputs, max_new_tokens=None, cfg_scale=2.0,
            tokenizer=processor.tokenizer,
            generation_config={"do_sample": False}, is_prefill=True, verbose=True)
    synth_seconds = time.time() - started
    if not outputs.speech_outputs or outputs.speech_outputs[0] is None:
        raise SystemExit("arm %s returned no audio" % label)
    audio = outputs.speech_outputs[0]
    wav = f"{OUT}/candidate_{label}.wav"
    mp3 = f"{OUT}/candidate_{label}.mp3"
    processor.save_audio(audio, output_path=wav)
    audio_seconds = audio.shape[-1] / 24000
    # A too-fast control is itself a test result; reject only truncation or an
    # implausibly long runaway generation here.
    assert 300 <= audio_seconds <= 780, (label, audio_seconds)
    sh(["ffmpeg", "-y", "-v", "error", "-i", wav,
        "-codec:a", "libmp3lame", "-b:a", "192k", mp3])
    sh(["ffmpeg", "-v", "error", "-i", mp3, "-f", "null", "-"])
    segments, _ = asr_model.transcribe(mp3, language="en", beam_size=5)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    expected, actual = norm(SOURCE_TEXT), norm(transcript)
    similarity = difflib.SequenceMatcher(None, expected, actual).ratio()
    word_ratio = len(actual) / len(expected)
    if similarity < 0.82 or not 0.85 <= word_ratio <= 1.15:
        raise SystemExit("arm %s completeness failed: similarity %.4f ratio %.4f"
                         % (label, similarity, word_ratio))
    row = {
        "label": label, "internal_id": arm["id"],
        "turn_count": len(arm["groups"]), "turn_words": arm["turn_words"],
        "official_weights": "microsoft/VibeVoice-1.5B",
        "runtime": "vibevoice-community/VibeVoice",
        "runtime_commit": RUNTIME_SHA,
        "runtime_docs": RUNTIME_DOCS,
        "harness_builder_sha256": BUILDER_SHA,
        "dtype": "float16", "attention": "sdpa",
        "cfg_scale": 2.0, "ddpm_steps": 10, "seed": 12345,
        "source_text_sha256": SOURCE_SHA,
        "serialized_prompt_sha256": arm["serialized_prompt_sha256"],
        "source_words": len(expected), "asr_words": len(actual),
        "asr_word_ratio": round(word_ratio, 4),
        "asr_similarity": round(similarity, 4),
        "audio_seconds": round(audio_seconds, 3),
        "synthesis_seconds": round(synth_seconds, 3),
        "rtf": round(synth_seconds / audio_seconds, 3),
        "mp3_bytes": os.path.getsize(mp3),
        "mp3_sha256": hashlib.sha256(open(mp3, "rb").read()).hexdigest(),
        "cuda_peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "cuda_peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
        "asr": transcript,
    }
    summary.append(row)
    print(json.dumps({k: v for k, v in row.items() if k != "asr"}, indent=2), flush=True)
    del outputs, audio, inputs
    gc.collect()
    torch.cuda.empty_cache()

open(f"{OUT}/source.txt", "w", encoding="utf-8").write(SOURCE_TEXT + "\n")
open(f"{OUT}/script.txt", "w", encoding="utf-8").write(ARMS[0]["script"] + "\n")
open(f"{OUT}/internal_manifest.json", "w", encoding="utf-8").write(
    json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
print("\nALL BLIND ARMS COMPLETE", flush=True)
"""


def _groups(paragraphs: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    return [" ".join(paragraphs[start:end]) for start, end in ranges]


def fixture_paragraphs() -> list[str]:
    """Load the committed, corrected excerpt used by clean CI and Kaggle."""
    text = FIXTURE.read_text(encoding="utf-8").strip()
    assert hashlib.sha256(text.encode()).hexdigest() == FIXTURE_TEXT_SHA
    paragraphs = text.split("\n\n")
    assert len(paragraphs) == 78
    return paragraphs


def main() -> int:
    builder_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    corrected_paragraphs = fixture_paragraphs()
    corrected = "\n\n".join(corrected_paragraphs)
    assert "draught , and" not in corrected
    assert corrected.count("draught, and") == 1
    source_text = re.sub(r"\s+", " ", corrected).strip()
    assert hashlib.sha256(source_text.encode()).hexdigest() == SOURCE_SHA
    assert len(re.sub(r"[^a-z0-9' ]+", " ", source_text.lower()).split()) == 1998
    # Each arm gets a separate private Kaggle job and therefore a fresh model
    # process. This prevents order or retained generation state becoming an
    # uncontrolled variable. The local ignored manifest preserves the blind map.
    blind_order = [("A", "long_turns"), ("B", "short_turns")]
    blind_map = {}
    for label, arm_id in blind_order:
        groups = _groups(
            corrected_paragraphs,
            GROUPS[arm_id],
        )
        arm = {
            "label": label,
            "id": arm_id,
            "groups": groups,
            "turn_words": [len(re.sub(r"[^a-z0-9' ]+", " ", group.lower()).split())
                           for group in groups],
        }
        script = "\n".join("Speaker 1: " + group for group in groups)
        assert hashlib.sha256(script.encode()).hexdigest() == EXPECTED_SCRIPT_SHA[arm_id]
        source = (KERNEL.replace("__RUNTIME_SHA__", repr(RUNTIME_SHA))
                  .replace("__REF_SHA__", repr(REF_SHA))
                  .replace("__SOURCE_SHA__", repr(SOURCE_SHA))
                  .replace("__BUILDER_SHA__", repr(builder_sha))
                  .replace("__RUNTIME_DOCS__", repr(RUNTIME_DOCS))
                  .replace("__SOURCE_TEXT__", json.dumps(source_text))
                  .replace("__ARMS__", json.dumps([arm])))
        compile(source, "run_vibe_turn_reset.py", "exec")
        kernel_out = OUT / f"kernel_{label}"
        kernel_out.mkdir(parents=True, exist_ok=True)
        (kernel_out / "run_vibe_turn_reset.py").write_text(
            source, encoding="utf-8", newline="\n")
        slug = f"vibevoice-arthur-turn-reset-{label.lower()}"
        metadata = {
            "id": f"davedavedavedavenm/{slug}", "title": slug,
            "code_file": "run_vibe_turn_reset.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
        }
        (kernel_out / "kernel-metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        blind_map[label] = arm_id
        print(f"kernel {label}: {kernel_out}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source.txt").write_text(source_text + "\n", encoding="utf-8")
    (OUT / "blind_map.json").write_text(
        json.dumps(blind_map, indent=2) + "\n", encoding="utf-8")
    print(f"source: 1998 words sha256={SOURCE_SHA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
