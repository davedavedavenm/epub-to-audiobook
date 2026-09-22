"""
prepare_kaggle_fish_emotion_lab.py — Emotion lab: temperature x reference choice.

Dave wants more emotion without losing the Cillian accent. Levers tested:
  - temperature 0.7 / 0.85 / 1.0 (1.0 = the audition he called perfect; drift
    only appeared over long-form, which does not apply per-sentence)
  - reference: dry 5s cut vs full 28s clip (more expressive range) vs BOTH
One dramatic sentence (killer's quote) + one neutral narrative sentence.
Each arm health-gated, mastered, banked as its own mp3.
"""

import base64
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dry_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
full_wav = root / "chatterbox" / "voices" / "cillian_irish.wav"
dry_b64 = base64.b64encode(dry_wav.read_bytes()).decode("ascii")
full_b64 = base64.b64encode(full_wav.read_bytes()).decode("ascii")

DRY_TEXT = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)
FULL_TEXT = (
    "You find so much empathy in novels, you know, because there you are putting yourself "
    "into somebody else's point of view and I've always been a big reader. When a movie can "
    "connect with someone and they feel seen or feel heard or a novel can change somebody's "
    "life or a music and album can change someone's life and I've had all that happen to me. "
    "And that's the power of good art, I think."
)

D = ("We started shooting from the car, then getting out of the car we continued to shoot. "
     "We all shot at him; he didn't have a chance.")
N = ("This was spectacularly so with the killing of Kevin O'Higgins, one of the most talented "
     "and important figures in the Free State regime.")

arms = []
for label, text, temp, ref in [
    ("D_t07_dry", D, 0.7, "dry"),
    ("D_t085_dry", D, 0.85, "dry"),
    ("D_t10_dry", D, 1.0, "dry"),
    ("N_t07_dry", N, 0.7, "dry"),
    ("N_t085_dry", N, 0.85, "dry"),
    ("N_t10_dry", N, 1.0, "dry"),
    ("D_t085_full", D, 0.85, "full"),
    ("N_t085_full", N, 0.85, "full"),
    ("D_t085_both", D, 0.85, "both"),
    ("N_t085_both", N, 0.85, "both"),
]:
    arms.append({"label": label, "text": text, "temp": temp, "ref": ref})

stage_dir = root / "scratch" / "kaggle_fish_emotion_lab" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Emotion lab: temperature x reference - Fish S2 Pro, free T4."""
import base64, glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out"); OUT.mkdir(exist_ok=True)

DRY_TEXT = {repr(DRY_TEXT)}
FULL_TEXT = {repr(FULL_TEXT)}
ARMS = json.loads({repr(json.dumps(arms, ensure_ascii=False))})

Path("/workspace/ref_dry.wav").write_bytes(base64.b64decode({repr(dry_b64)}))
Path("/workspace/ref_full.wav").write_bytes(base64.b64decode({repr(full_b64)}))

subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", "/workspace/fish-speech"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "/workspace/fish-speech"], check=True)
for path in glob.glob("/usr/local/lib/python3.*/dist-packages/audiotools/ml/decorators.py"):
    try:
        c = Path(path).read_text()
        if "from torch.utils.tensorboard import SummaryWriter" in c:
            Path(path).write_text(c.replace("from torch.utils.tensorboard import SummaryWriter", "SummaryWriter = None"))
    except Exception:
        pass
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "protobuf>=6.31.1"], check=False)
subprocess.run([sys.executable, "-c",
                "from huggingface_hub import snapshot_download; "
                "snapshot_download('fishaudio/s2-pro', local_dir='/workspace/s2-pro')"], check=True)

inf_path = Path("/workspace/fish-speech/fish_speech/models/text2semantic/inference.py")
src = inf_path.read_text()
if "CODEC_DEVICE" not in src:
    src = 'import os as _os\\nCODEC_DEVICE = _os.environ.get("FISH_CODEC_DEVICE", "")\\n' + src
src = src.replace("codec = load_codec_model(codec_checkpoint, device, precision)",
                  "codec = load_codec_model(codec_checkpoint, CODEC_DEVICE or device, precision)")
src = src.replace("encode_audio(p, codec, device)",
                  "encode_audio(p, codec, CODEC_DEVICE or device)")
src = src.replace("decode_to_audio(merged_codes.to(device), codec)",
                  "decode_to_audio(merged_codes.to(CODEC_DEVICE or device), codec)")
assert src.count("CODEC_DEVICE or device") == 4
inf_path.write_text(src)

import torch

assert torch.cuda.is_available()
DEVICE = "cuda:0"
CODEC_DEVICE = "cuda:1" if torch.cuda.device_count() > 1 else DEVICE
os.environ["FISH_CODEC_DEVICE"] = CODEC_DEVICE
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

sys.path.insert(0, "/workspace/fish-speech")
from fish_speech.models.text2semantic.inference import (
    decode_to_audio, encode_audio, generate_long, init_model, load_codec_model,
)

precision = torch.half
model, decode_one_token = init_model("/workspace/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/workspace/s2-pro/codec.pth", CODEC_DEVICE, precision)
tok_dry = [encode_audio("/workspace/ref_dry.wav", codec, CODEC_DEVICE).cpu()]
tok_full = [encode_audio("/workspace/ref_full.wav", codec, CODEC_DEVICE).cpu()]
torch.manual_seed(42); torch.cuda.manual_seed(42)

REFS = {{
    "dry": (DRY_TEXT, tok_dry),
    "full": (FULL_TEXT, tok_full),
    "both": ([DRY_TEXT, FULL_TEXT], tok_dry + tok_full),
}}


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    return 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05, rms, d


results = []
for arm in ARMS:
    label, temp, ref = arm["label"], arm["temp"], arm["ref"]
    ref_text, ref_tokens = REFS[ref]
    c_t0 = time.time()
    try:
        gen = generate_long(
            model=model, device=DEVICE, decode_one_token=decode_one_token,
            text=arm["text"], num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
            temperature=temp, compile=False, iterative_prompt=True, chunk_length=300,
            prompt_text=ref_text if isinstance(ref_text, list) else [ref_text],
            prompt_tokens=ref_tokens,
        )
        codes = []
        wav = None
        for response in gen:
            if response.action == "sample":
                codes.append(response.codes)
            elif response.action == "next" and codes:
                merged = torch.cat(codes, dim=1)
                audio = decode_to_audio(merged.to(CODEC_DEVICE), codec)
                wav = audio.cpu().float().numpy()
                codes = []
        if codes:
            merged = torch.cat(codes, dim=1)
            audio = decode_to_audio(merged.to(CODEC_DEVICE), codec)
            wav = audio.cpu().float().numpy()
        if wav is None or len(wav) < 0.5 * codec.sample_rate:
            raise RuntimeError("no usable audio")
        ok, rms, d = health(wav)
        raw_wav = WORK / f"{{label}}.wav"
        sf.write(str(raw_wav), wav, codec.sample_rate)
        mp3 = OUT / f"lab_{{label}}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_wav),
                        "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
        secs = len(wav) / codec.sample_rate
        results.append({{"label": label, "ok": bool(ok), "sec": round(secs, 2), "rms": round(rms, 4)}})
        print(f"{{label}}: {{secs:.1f}}s ok={{ok}} ({{time.time()-c_t0:.0f}}s)", flush=True)
    except Exception as e:
        results.append({{"label": label, "ok": False, "err": str(e)[:200]}})
        print(f"{{label}} FAILED: {{str(e)[:150]}}", flush=True)

(OUT / "manifest.json").write_text(json.dumps({{"results": results}}, indent=1))
print("LAB COMPLETE", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-emotion-lab",
    "title": "fish-emotion-lab",
    "code_file": "run_kernel.py",
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
(stage_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("metadata written")
