"""
prepare_kaggle_fish_as_book_chapter.py — Production chapter renderer for the
Armed Struggle Cillian audiobook (LOCKED recipe, see CILLIAN-RECIPE.md).

Usage: python prepare_kaggle_fish_as_book_chapter.py <slug>
  e.g. preface | ch1 .. ch8 | conclusion
Reads scratch/as_book/<slug>.json (prepared by prepare_armed_struggle_chapters.py).
"""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
slug = sys.argv[1] if len(sys.argv) > 1 else "preface"
payload_path = root / "scratch" / "as_book" / f"{slug}.json"
payload = json.loads(payload_path.read_text(encoding="utf-8"))
title = payload["title"]
sents = payload["sents"]
print(f"Chapter {slug}: {title} — {len(sents)} sentences")

stage_dir = root / "scratch" / "as_book_kernels" / slug
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Armed Struggle — {title} — locked Cillian recipe (Fish S2 Pro, free T4x2)."""
import glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out")
(OUT / "wavs").mkdir(parents=True, exist_ok=True)

hits = sorted(Path("/kaggle/input").rglob("refs.json"))
if not hits:
    print("INPUT MOUNTS:", [str(p) for p in Path("/kaggle/input").rglob("*")][:40], flush=True)
    raise SystemExit("refs dataset not mounted")
REFDIR = hits[0].parent
REFS = json.loads((REFDIR / "refs.json").read_text(encoding="utf-8"))
PAYLOAD = json.loads({repr(json.dumps(payload, ensure_ascii=False))})
sents = PAYLOAD["sents"]
print(f"{{len(sents)}} sentences", flush=True)

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
REFS_READY = {{}}
def get_ref_tokens(ref_key):
    if ref_key not in REFS_READY:
        REFS_READY[ref_key] = [encode_audio(str(REFDIR / f"{{ref_key}}.wav"), codec, CODEC_DEVICE).cpu()]
    return REFS_READY[ref_key]

torch.manual_seed(42); torch.cuda.manual_seed(42)


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    return 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05, rms, d


def synth(text, ref_key, temp, seed):
    torch.manual_seed(seed); torch.cuda.manual_seed(seed)
    gen = generate_long(
        model=model, device=DEVICE, decode_one_token=decode_one_token,
        text=text, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
        temperature=temp, compile=False, iterative_prompt=True, chunk_length=300,
        prompt_text=[REFS[ref_key + "_text"]], prompt_tokens=get_ref_tokens(ref_key),
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
    return wav


t0 = time.time()
audio_secs = 0.0
n_fail = 0
manifest = []
for i, item in enumerate(sents, 1):
    ref_key = "crop_expressive_tail" if item["quote"] else "cillian_irish"
    c_t0 = time.time()
    ok = False
    for attempt, seed in enumerate((42, 43, 44), 1):
        try:
            wav = synth(item["text"], ref_key, 0.85, seed)
            if wav is None or len(wav) < 0.6 * codec.sample_rate:
                raise RuntimeError("no/short audio")
            h_ok, rms, d = health(wav)
            if not h_ok:
                raise RuntimeError(f"health rms={{rms:.4f}} diff={{d:.5f}}")
            if attempt > 1:
                print(f"  [{{i}}] re-roll {{attempt}} ok", flush=True)
            sf.write(str(OUT / "wavs" / f"{{i:04d}}.wav"), wav, codec.sample_rate)
            secs = len(wav) / codec.sample_rate
            audio_secs += secs
            manifest.append({{"idx": i, "para": item["para"], "quote": item["quote"],
                              "ref": ref_key, "seed": seed, "sec": round(secs, 2), "ok": True}})
            ok = True
            if i % 25 == 0 or i == len(sents):
                el = time.time() - t0
                print(f"[{{i}}/{{len(sents)}}] RTF {{el / max(audio_secs, 1):.2f}}x ({{n_fail}} failed)", flush=True)
                (OUT / "manifest.json").write_text(json.dumps({{"elapsed": round(el, 1), "audio_secs": round(audio_secs, 1), "n_fail": n_fail, "done": i, "sents": manifest}}, indent=1))
            break
        except Exception as e:
            if attempt == 3:
                n_fail += 1
                manifest.append({{"idx": i, "para": item["para"], "ok": False, "err": str(e)[:200]}})
                print(f"[{{i}}/{{len(sents)}}] FAILED: {{str(e)[:150]}}", flush=True)

gen_wall = time.time() - t0
rtf = gen_wall / max(audio_secs, 1.0)
print(f"GEN DONE: {{audio_secs:.0f}}s audio in {{gen_wall:.0f}}s -> RTF {{rtf:.2f}}x ({{n_fail}} failed)", flush=True)

SR = codec.sample_rate
TRIM_FRAME = int(0.02 * SR)


def load_trim(p):
    w, s = sf.read(p, dtype="float32")
    if w.ndim > 1:
        w = w.mean(axis=1)
    n = len(w)
    if n < TRIM_FRAME * 3:
        return w
    rms = np.array([float(np.sqrt(np.mean(w[i:i + TRIM_FRAME] ** 2))) for i in range(0, n - TRIM_FRAME, TRIM_FRAME)])
    loud = np.where(rms > 0.004)[0]
    if len(loud) == 0:
        return w
    return w[max(0, loud[0] * TRIM_FRAME - int(0.08 * SR)): min(n, (loud[-1] + 1) * TRIM_FRAME + int(0.08 * SR))]


pieces = []
prev_para = None
for item in manifest:
    if not item.get("ok"):
        continue
    p = OUT / "wavs" / f"{{item['idx']:04d}}.wav"
    if not p.exists():
        continue
    w = load_trim(p)
    if prev_para is not None:
        gap = 0.50 if item["para"] != prev_para else 0.18
        pieces.append(np.zeros(int(gap * SR), dtype=np.float32))
    pieces.append(w)
    prev_para = item["para"]
full = np.concatenate(pieces)
sf.write("/workspace/chapter_raw.wav", full, SR)
OUTMP3 = OUT / "armed_struggle_{slug}_cillian.mp3"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/workspace/chapter_raw.wav",
                "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", "192k", str(OUTMP3)], check=True)
a, sra = sf.read("/workspace/chapter_raw.wav", dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
ok, rms, d = health(a)
total = len(a) / sra
print(f"FINAL: {{total:.1f}}s rms={{rms:.4f}} diff={{d:.5f}} pass={{ok}}")
print(f"MANIFEST: rtf={{rtf:.2f}} n_fail={{n_fail}} total={{total:.1f}}", flush=True)
(OUT / "manifest.json").write_text(json.dumps({{"rtf": round(rtf, 2), "n_fail": n_fail, "total_sec": round(total, 1), "sents": manifest}}, indent=1))
if not ok:
    OUTMP3.rename(OUT / ("armed_struggle_{slug}_cillian_UNHEALTHY.mp3"))
print("CHAPTER COMPLETE", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": f"davedavedavedavenm/fish-as-book-{slug}",
    "title": f"fish-as-book-{slug}",
    "code_file": "run_kernel.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,
    "machine_shape": "NvidiaTeslaT4",
    "dataset_sources": ["davedavedavedavenm/cillian-refs"],
    "competition_sources": [],
    "kernel_sources": [],
    "model_sources": [],
}
(stage_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("metadata written")
