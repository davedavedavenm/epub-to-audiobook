"""
prepare_kaggle_fish_pilot.py — Fish S2 Pro full-chapter PILOT on free Kaggle T4×2.

Chapter under test: Sophie's World, Chapter 6 "Fate" (the chapter Dave is
listening to right now; 16.4 min audio in ABS). Voice: flat Cillian studio ref
(Dave's verdict 2026-09-20: "voice is perfect"). Pronunciation: book glossary
respellings (Delphi, Pythia) per the accepted lexicon approach.

Optimisations vs the audition harness (RTF 15x):
- single process: 4.4B model + caches load ONCE (the audition reloaded per sentence)
- codec split to 2nd GPU (S2 Pro stack > 16 GB)
- per-sentence banking in /kaggle/working/out/wavs + done-index → resumable
- waveform health gate per sentence + final mastered gate + manifest with RTF
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
# strip extraction artefacts
chapter_text = chapter_text.replace('filepos104331">', "").strip()
cut = chapter_text.rfind("<")
if cut > len(chapter_text) - 60:
    chapter_text = chapter_text[:cut]
chapter_text = chapter_text.rstrip().rstrip('"').rstrip()

# book glossary (accepted approach: exact-match, longest-first, TTS-input only)
glossary = {
    "Delphi": "Del-fye",
    "Pythia": "Pith-ee-a",
}
for key in sorted(glossary, key=len, reverse=True):
    chapter_text = chapter_text.replace(key, glossary[key])

stage_dir = root / "scratch" / "kaggle_fish_pilot" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Fish S2 Pro pilot - Sophie's World ch6 "Fate" - single-process, dual-T4, banked."""
import base64, glob, json, os, re, subprocess, sys, time
from pathlib import Path

import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out"); (OUT / "wavs").mkdir(parents=True, exist_ok=True)
DONE = OUT / "wavs" / "done.json"
done = json.loads(DONE.read_text()) if DONE.exists() else {{"sent": {{}}, "meta": {{}}}}

ref_path = "/workspace/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
ref_text = {repr(ref_text)}
eval_text = {repr(chapter_text)}
sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip() and len(s.strip()) > 1]
print(f"{{len(sents)}} sentences")

# ---------- runtime install FIRST (so the torch/torchaudio pair on disk is
# consistent before this process imports torch - ABI mismatch otherwise) ----------
subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", "/workspace/fish-speech"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "/workspace/fish-speech"], check=True)
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
inf_path.write_text(src)

# ---------- NOW import torch (post-install) ----------
import torch

assert torch.cuda.is_available()
NGPU = torch.cuda.device_count()
print(f"GPU: {{torch.cuda.get_device_name(0)}} x{{NGPU}}")
DEVICE = "cuda:0"
CODEC_DEVICE = "cuda:1" if NGPU > 1 else DEVICE
os.environ["FISH_CODEC_DEVICE"] = CODEC_DEVICE
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# ---------- in-process driver ----------
sys.path.insert(0, "/workspace/fish-speech")
from fish_speech.models.text2semantic.inference import (
    init_model, load_codec_model, encode_audio, decode_to_audio, generate_long,
)

t_setup = time.time()
precision = torch.half
model, decode_one_token = init_model("/workspace/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/workspace/s2-pro/codec.pth", CODEC_DEVICE, precision)
prompt_tokens = [encode_audio(ref_path, codec, CODEC_DEVICE).cpu()]
torch.manual_seed(42); torch.cuda.manual_seed(42)
print(f"Setup done in {{time.time()-t_setup:.0f}}s (model + codec resident)")

def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    ok = 0.005 < rms < 0.5 and d > 0.001 and float(np.abs(a).max()) > 0.05
    return ok, rms, d

t0 = time.time()
n_new = n_skip = n_fail = 0
audio_secs_new = 0.0
for idx, s in enumerate(sents, 1):
    key = str(idx)
    if key in done["sent"]:
        n_skip += 1
        continue
    c_t0 = time.time()
    try:
        gen = generate_long(model=model, device=DEVICE, decode_one_token=decode_one_token,
                            text=s, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
                            temperature=1.0, compile=False, iterative_prompt=True,
                            chunk_length=300, prompt_text=[ref_text], prompt_tokens=prompt_tokens)
        codes = []
        wav = None
        sr = codec.sample_rate
        for response in gen:
            if response.action == "sample":
                codes.append(response.codes)
            elif response.action == "next" and codes:
                merged = torch.cat(codes, dim=1)
                audio = decode_to_audio(merged.to(CODEC_DEVICE), codec)
                wav = audio.cpu().float().numpy()
                codes = []
        if wav is None or len(wav) < sr * 0.5:
            raise RuntimeError("no audio produced")
        ok, rms, d = health(wav)
        if not ok:
            raise RuntimeError(f"health FAIL rms={{rms:.4f}} diff={{d:.5f}}")
        sf.write(str(OUT / "wavs" / f"sent_{{idx:04d}}.wav"), wav, sr)
        done["sent"][key] = {{"sec": round(len(wav) / sr, 2), "rms": round(rms, 4)}}
        DONE.write_text(json.dumps(done))
        n_new += 1
        audio_secs_new += len(wav) / sr
        print(f"  [{{idx}}/{{len(sents)}}] {{len(wav)/sr:.1f}}s in {{time.time()-c_t0:.0f}}s rms={{rms:.3f}}", flush=True)
    except Exception as e:
        n_fail += 1
        done["sent"][key] = {{"error": str(e)[:200]}}
        DONE.write_text(json.dumps(done))
        print(f"  [{{idx}}/{{len(sents)}}] FAILED: {{str(e)[:150]}}", flush=True)

gen_wall = time.time() - t0
done["meta"] = {{"gen_wall_s": round(gen_wall, 1), "n_new": n_new, "n_fail": n_fail, "audio_new_s": round(audio_secs_new, 1)}}
DONE.write_text(json.dumps(done))
print(f"Generation: {{n_new}} new, {{n_skip}} skipped, {{n_fail}} failed, {{audio_secs_new:.0f}}s audio in {{gen_wall:.0f}}s")

# ---------- assemble + master ----------
pieces = []
sr = codec.sample_rate
for idx in range(1, len(sents) + 1):
    p = OUT / "wavs" / f"sent_{{idx:04d}}.wav"
    if p.exists():
        w, s0 = sf.read(p, dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        sr = s0
        pieces.append(w)
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
if not pieces:
    raise SystemExit("no banked audio to assemble")
full = np.concatenate(pieces)
sf.write("/workspace/pilot_raw.wav", full, sr)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/workspace/pilot_raw.wav",
                "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", "192k", str(OUT / "fish_pilot_fate_cillian.mp3")], check=True)
dec = "/workspace/final_check.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "fish_pilot_fate_cillian.mp3"), dec], check=True)
a, sra = sf.read(dec, dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
ok, rms, d = health(a)
total_audio = len(a) / sra
print(f"FINAL: {{total_audio:.1f}}s rms={{rms:.4f}} diff={{d:.5f}} pass={{ok}}")
print(f"MANIFEST RTF: {{gen_wall / max(audio_secs_new, 1):.2f}}x (new audio only, model-resident)")
if not ok:
    (OUT / "fish_pilot_fate_cillian.mp3").rename(OUT / "fish_pilot_fate_cillian_UNHEALTHY.mp3")
print("Pilot complete.")
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-pilot-sophies-fate",
    "title": "fish-pilot-sophies-fate",
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
