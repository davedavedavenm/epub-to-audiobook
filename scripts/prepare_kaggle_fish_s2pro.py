"""
prepare_kaggle_fish_s2pro.py — Bounded Fish Speech S2 Pro retry on free Kaggle T4.

Hypothesis (per 2026-09-18 rejection boundary): the S2 Pro failure was theatrical
prompt prosody transfer, not the engine. New controlled input: flat, dry studio
Cillian reference (cillian_irish_dry.wav) + its transcript, tough-Irish paragraph.

Runtime mirrors the proven A10G Modal recipe (render_fish_speech_s2.py) with
--precision float16 for T4 (no bf16). HARD HEALTH GATE: every sentence and the
final file must pass waveform checks or the audition mp3 is NOT written.
"""

import base64
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
cillian_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")

tough_irish_text = (
    "In Dublin, the leaders of the new republic assembled to challenge the authority of the Crown. "
    "Pádraig Pearse and Seán MacDiarmada had proclaimed the provisional government in nineteen-sixteen, "
    "but it was the First Dáil Éireann that solidified the republican mandate. "
    "Eamon de Valera was chosen as Priomh-Aire, while Cathal Brugha took charge of the Ministry of Defence, "
    "supported by the dedicated volunteers of Cumann na mBan. "
    "From the coastal redoubts of Dún Laoghaire to the military garrison at Portlaoise, British forces struggled to contain the rising tide. "
    "When the office of Taoiseach and Tánaiste were debated decades later by leaders like Ruairí Ó Brádaigh, "
    "Sinn Féin insisted that true legitimacy had already been won in the crucible of war. "
    "If the imperial parliament in Westminster could be so thoroughly rejected across the island, then where did that leave the moral standing of British rule?"
)

ref_text = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)

stage_dir = root / "scratch" / "kaggle_fish_s2pro" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Fish Speech S2 Pro (flat Cillian ref) on Tough Irish Words - free Kaggle T4.
Waveform-health-gated: refuses to emit the audition mp3 on silent/saturated audio."""

import base64
import glob
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

assert torch.cuda.is_available(), "CUDA required"
print(f"GPU: {{torch.cuda.get_device_name(0)}}")

WORK = Path("/workspace")
WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out")
OUT.mkdir(exist_ok=True)

ref_path = "/workspace/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
ref_text = {repr(ref_text)}
eval_text = {repr(tough_irish_text)}
sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip()]

# ---------- install runtime (proven A10G recipe) ----------
print("Installing fish-speech runtime...")
subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev",
                "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git",
                "/workspace/fish-speech"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e",
                "/workspace/fish-speech"], check=True)

for path in glob.glob("/usr/local/lib/python3.*/dist-packages/audiotools/ml/decorators.py") + \\
            glob.glob("/usr/local/lib/python3.*/site-packages/audiotools/ml/decorators.py"):
    try:
        content = Path(path).read_text()
        if "from torch.utils.tensorboard import SummaryWriter" in content:
            content = content.replace("from torch.utils.tensorboard import SummaryWriter",
                                      "SummaryWriter = None")
            Path(path).write_text(content)
    except Exception as e:
        print(f"audiotools patch skipped ({{path}}): {{e}}")

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "protobuf>=6.31.1"],
               check=False)

print("Downloading fishaudio/s2-pro weights...")
subprocess.run([sys.executable, "-m", "huggingface_hub.cli", "download",
                "fishaudio/s2-pro", "--local-dir", "/workspace/s2-pro"], check=True)

# ---------- health gate ----------
def health(label, a, sr):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    plateau = bool(np.any(np.abs(a) > 0.99)) and d < 0.001
    ok = 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05 and not plateau
    print(f"  HEALTH {{label}}: rms={{rms:.4f}} mean|diff|={{d:.5f}} peak={{peak:.3f}} -> {{'PASS' if ok else 'FAIL'}}")
    return ok

def run_infer(text, sent_dir, idx):
    sent_dir.mkdir(exist_ok=True, parents=True)
    cmd = [sys.executable, "fish_speech/models/text2semantic/inference.py",
           "--text", text,
           "--prompt-text", ref_text,
           "--prompt-audio", ref_path,
           "--checkpoint-path", "/workspace/s2-pro",
           "--output", str(sent_dir / "output.wav"),
           "--output-dir", str(sent_dir),
           "--num-samples", "1",
           "--precision", "float16"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "/workspace/fish-speech:" + env.get("PYTHONPATH", "")
    r = subprocess.run(cmd, cwd="/workspace/fish-speech", env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"sentence {{idx}} inference failed:\\n{{r.stderr[-1500:]}}")
        return None
    cands = [sent_dir / "output.wav"] + sorted(sent_dir.rglob("*.wav"))
    for c in cands:
        if c.exists() and c.stat().st_size > 10000:
            wav, sr = sf.read(c, dtype="float32")
            if wav.ndim > 1:
                wav = wav.mean(axis=1)
            return wav, sr
    print(f"sentence {{idx}}: no usable wav produced")
    return None

# ---------- synthesize ----------
t0 = time.time()
pieces = []
sr_final = 24000
n_fail = 0
for idx, s in enumerate(sents, 1):
    c_t0 = time.time()
    got = run_infer(s, WORK / f"sent_{{idx:02d}}", idx)
    if got is None:
        n_fail += 1
        continue
    wav, sr = got
    sr_final = sr
    if not health(f"sent {{idx}}", wav, sr):
        n_fail += 1
        continue
    pieces.append(wav)
    pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
    print(f"  [Fish {{idx}}/{{len(sents)}}] {{len(wav) / sr:.1f}}s audio in {{time.time() - c_t0:.1f}}s")

if n_fail:
    print(f"HEALTH-GATE ABORT: {{n_fail}}/{{len(sents)}} sentences failed; audition mp3 NOT written.")
    # still save raw join for diagnosis, clearly named
    if pieces:
        full = np.concatenate(pieces)
        sf.write(OUT / "fish_s2pro_RAW_unhealthy.wav", full, sr_final)
    raise SystemExit(1)

full = np.concatenate(pieces)
raw_wav = "/workspace/fish_s2pro_raw.wav"
sf.write(raw_wav, full, sr_final)

mp3 = OUT / "fish_s2pro_cillian_tough.mp3"
af = ("equalizer=f=220:width_type=o:width=1.2:g=1.0,"
      "highshelf=f=7500:gain=-2.0:width=1.0,"
      "loudnorm=I=-20:TP=-2:LRA=11")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw_wav,
                "-af", af, "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)],
               check=True)

# final gate on the master: decode via ffmpeg and re-check waveform
dec = "/workspace/final_check.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), dec], check=True)
a, sr_a = sf.read(dec, dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
el = time.time() - t0
dur = len(a) / sr_a
if health("FINAL_MP3", a, sr_a):
    print(f"FISH OK: {{dur:.1f}}s audio in {{el:.1f}}s (RTF {{el / dur:.2f}}x) -> {{mp3.name}} ({{mp3.stat().st_size:,}} bytes)")
else:
    print("HEALTH-GATE ABORT: final mp3 failed; renaming to UNHEALTHY.")
    mp3.rename(OUT / "fish_s2pro_cillian_tough_UNHEALTHY.mp3")
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-s2pro-tough-irish-cillian",
    "title": "fish-s2pro-tough-irish-cillian",
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
meta_file = stage_dir / "kernel-metadata.json"
meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"Written {meta_file}")
