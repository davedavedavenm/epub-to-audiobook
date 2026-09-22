"""
prepare_kaggle_fish_fletter.py — render the single spoken letter F (fixes the
dropped 'F.' initial of 'F. L. Green' in the Armed Struggle ch2 render).
Tries several spellings; banks the first health-gated pass as f_letter.wav.
"""

import base64
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
cillian_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")

ref_text = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)

stage_dir = root / "scratch" / "kaggle_fish_fletter" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Render single letter 'F' (multiple spellings) - Fish S2 Pro, free T4."""
import base64, glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out"); OUT.mkdir(exist_ok=True)

ref_path = "/workspace/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
ref_text = {repr(ref_text)}
CANDIDATES = ["Ef.", "Eff.", "F.", "F"]

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
prompt_tokens = [encode_audio(ref_path, codec, CODEC_DEVICE).cpu()]
torch.manual_seed(42); torch.cuda.manual_seed(42)


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    return 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05, rms, d


results = []
got = None
for cand in CANDIDATES:
    try:
        gen = generate_long(
            model=model, device=DEVICE, decode_one_token=decode_one_token,
            text=cand, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
            temperature=1.0, compile=False, iterative_prompt=True, chunk_length=300,
            prompt_text=[ref_text], prompt_tokens=prompt_tokens,
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
        if wav is None or len(wav) < 0.15 * codec.sample_rate:
            print(f"{{cand!r}}: too short/none", flush=True)
            results.append({{"cand": cand, "ok": False, "why": "short"}})
            continue
        ok, rms, d = health(wav)
        secs = len(wav) / codec.sample_rate
        print(f"{{cand!r}}: {{secs:.2f}}s rms={{rms:.3f}} ok={{ok}}", flush=True)
        results.append({{"cand": cand, "ok": bool(ok), "sec": round(secs, 2), "rms": round(rms, 4)}})
        if ok and got is None:
            sf.write(str(OUT / "f_letter.wav"), wav, codec.sample_rate)
            got = cand
    except Exception as e:
        print(f"{{cand!r}} FAILED: {{str(e)[:120]}}", flush=True)
        results.append({{"cand": cand, "ok": False, "err": str(e)[:150]}})

(OUT / "manifest.json").write_text(json.dumps({{"got": got, "results": results}}, indent=1))
print(f"DONE got={{got}}", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-fletter-fix",
    "title": "fish-fletter-fix",
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
