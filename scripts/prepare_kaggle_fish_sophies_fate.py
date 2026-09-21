"""
prepare_kaggle_fish_sophies_fate.py — Fish S2 Pro chapter pilot (optimized harness).

Chapter: Sophie's World Ch 6 "Fate" (the chapter Dave is listening to; 16.4 min
in ABS). Voice: Fish S2 Pro + flat Cillian studio ref (verdict: "voice is
perfect"). Glossary: Delphi/Pythia respelled.

Optimizations vs the RTF-15x audition harness:
- single process: 4.4B AR + caches + codec load ONCE
- AR on cuda:0, DAC codec split to cuda:1 (S2 Pro stack > 16 GB on one T4)
- per-sentence WAVs banked into /kaggle/working/out/wavs (survives crashes and
  are downloadable even on failure), manifest.json, per-sentence + final gates
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

chapter_text = Path(r"C:\Users\Dave\AppData\Local\Temp\opencode\fate_chapter.txt").read_text(encoding="utf-8")
# clean extraction artefacts
chapter_text = chapter_text.replace('filepos104331">', "")
cut = chapter_text.rfind("<")
if cut > len(chapter_text) - 80:
    chapter_text = chapter_text[:cut]
chapter_text = chapter_text.rstrip().rstrip('">').rstrip()

glossary = {
    "Delphi": "Dell-fye",
    "Pythia": "Pith-ee-a",
}
for key in sorted(glossary, key=len, reverse=True):
    chapter_text = chapter_text.replace(key, glossary[key])

stage_dir = root / "scratch" / "kaggle_fish_sophies_fate" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Fish S2 Pro pilot: Sophie's World ch6 'Fate'. Single-process, dual-T4, banked."""
import base64, glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out")
(OUT / "wavs").mkdir(parents=True, exist_ok=True)

ref_path = "/workspace/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
ref_text = {repr(ref_text)}
eval_text = {repr(chapter_text)}
sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip() and len(s.strip()) > 1]
print(f"{{len(sents)}} sentences", flush=True)

# ---------- runtime install FIRST (torch/torchaudio pair consistent on disk
# before this process imports torch - ABI mismatch otherwise) ----------
subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", "/workspace/fish-speech"], check=False)
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "/workspace/fish-speech"])
print("pip -e exit:", r.returncode, flush=True)
for path in glob.glob("/usr/local/lib/python3.*/dist-packages/audiotools/ml/decorators.py") + glob.glob("/usr/local/lib/python3.*/site-packages/audiotools/ml/decorators.py"):
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

# split codec to 2nd GPU (S2 Pro stack > 16 GB on a single T4)
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
assert src.count("CODEC_DEVICE or device") == 4, "codec device patch incomplete"
inf_path.write_text(src)

# ---------- NOW import torch (post-install) ----------
import torch

assert torch.cuda.is_available()
NGPU = torch.cuda.device_count()
print(f"GPU: {{torch.cuda.get_device_name(0)}} x{{NGPU}}", flush=True)
DEVICE = "cuda:0"
CODEC_DEVICE = "cuda:1" if NGPU > 1 else DEVICE
os.environ["FISH_CODEC_DEVICE"] = CODEC_DEVICE
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

sys.path.insert(0, "/workspace/fish-speech")
from fish_speech.models.text2semantic.inference import (
    decode_to_audio, encode_audio, generate_long, init_model, load_codec_model,
)

t_setup = time.time()
precision = torch.half  # T4 has no bf16
model, decode_one_token = init_model("/workspace/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/workspace/s2-pro/codec.pth", CODEC_DEVICE, precision)
prompt_tokens_list = [encode_audio(ref_path, codec, CODEC_DEVICE).cpu()]
torch.manual_seed(42)
torch.cuda.manual_seed(42)
print(f"Setup {{time.time()-t_setup:.0f}}s: model on {{DEVICE}}, codec on {{CODEC_DEVICE}}", flush=True)


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    ok = 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05
    return ok, rms, d, peak


t0 = time.time()
audio_secs = 0.0
n_fail = 0
manifest = []
for idx, s in enumerate(sents, 1):
    c_t0 = time.time()
    try:
        gen = generate_long(
            model=model, device=DEVICE, decode_one_token=decode_one_token,
            text=s, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
            temperature=1.0, compile=False, iterative_prompt=True, chunk_length=300,
            prompt_text=[ref_text], prompt_tokens=prompt_tokens_list,
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
            raise RuntimeError("no usable audio returned")
        ok, rms, d, peak = health(wav)
        if not ok:
            raise RuntimeError(f"health FAIL rms={{rms:.4f}} diff={{d:.5f}} peak={{peak:.3f}}")
        sf.write(str(OUT / "wavs" / f"{{idx:04d}}.wav"), wav, codec.sample_rate)
        secs = len(wav) / codec.sample_rate
        audio_secs += secs
        manifest.append({{"idx": idx, "sec": round(secs, 2), "rms": round(rms, 4), "ok": True}})
        print(f"[{{idx}}/{{len(sents)}}] {{secs:.1f}}s in {{time.time()-c_t0:.0f}}s rms={{rms:.3f}}", flush=True)
    except Exception as e:
        n_fail += 1
        manifest.append({{"idx": idx, "ok": False, "err": str(e)[:200]}})
        print(f"[{{idx}}/{{len(sents)}}] FAILED: {{str(e)[:150]}}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps({{"elapsed": round(time.time()-t0, 1), "audio_secs": round(audio_secs, 1), "n_fail": n_fail, "sents": manifest}}, indent=1))

gen_wall = time.time() - t0
rtf = gen_wall / max(audio_secs, 1.0)
print(f"GEN DONE: {{audio_secs:.0f}}s audio in {{gen_wall:.0f}}s -> RTF {{rtf:.2f}}x ({{n_fail}} failed)", flush=True)

# ---------- assemble + master ----------
pieces = []
for idx in range(1, len(sents) + 1):
    p = OUT / "wavs" / f"{{idx:04d}}.wav"
    if p.exists():
        w, sr = sf.read(p, dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        pieces.append(w)
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
if not pieces:
    raise SystemExit("no banked audio")
full = np.concatenate(pieces)
sf.write("/workspace/pilot_raw.wav", full, sr)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/workspace/pilot_raw.wav",
                "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", "192k", str(OUT / "fish_sophies_fate_cillian.mp3")], check=True)
a, sra = sf.read("/workspace/pilot_raw.wav", dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
ok, rms, d, peak = health(a)
total = len(a) / sra
print(f"FINAL: {{total:.1f}}s rms={{rms:.4f}} diff={{d:.5f}} pass={{ok}}")
print(f"MANIFEST: rtf={{rtf:.2f}} n_fail={{n_fail}}", flush=True)
(OUT / "manifest.json").write_text(json.dumps({{"rtf": round(rtf, 2), "n_fail": n_fail, "total_sec": round(total, 1), "sents": manifest}}, indent=1))
if not ok:
    (OUT / "fish_sophies_fate_cillian.mp3").rename(OUT / "fish_sophies_fate_cillian_UNHEALTHY.mp3")
print("PILOT COMPLETE", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-sophies-fate-cillian",
    "title": "fish-sophies-fate-cillian",
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
