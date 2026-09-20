"""
prepare_kaggle_audition_candidates.py — Stage OmniVoice and VoxCPM2
on the Tough Irish Words Challenge using Cillian Murphy's voice.
"""

import json
import base64
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

stage_dir = root / "scratch" / "kaggle_irish_bakeoff" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

# Main runner script
kernel_code = f'''#!/usr/bin/env python3
"""
Kaggle Audition Kernel: OmniVoice vs. VoxCPM2 on Tough Irish Words
Narrator Voice: Cillian Murphy (Studio Dry Reference)
"""

import io
import os
import sys
import time
import base64
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

print("=== GPU Hardware Detection ===")
assert torch.cuda.is_available(), "CUDA required!"
gpu_name = torch.cuda.get_device_name(0)
gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
print(f"GPU: {{gpu_name}} ({{gpu_mem:.1f}} GB VRAM)")

# Base ref audio & text
cillian_b64 = {repr(cillian_b64)}
ref_path = "/tmp/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode(cillian_b64))
ref_text = {repr(ref_text)}
eval_text = {repr(tough_irish_text)}

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)

def master_audio(in_wav: str, out_mp3: str, sr: int = 24000):
    af_filters = (
        "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
        "highshelf=f=7500:gain=-2.0:width=1.0,"
        "loudnorm=I=-20:TP=-2:LRA=11"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", in_wav,
        "-af", af_filters,
        "-ar", str(sr),
        "-codec:a", "libmp3lame", "-b:a", "192k",
        out_mp3
    ], check=True)
    print(f"✓ Mastered audio created: {{out_mp3}} ({{Path(out_mp3).stat().st_size:,}} bytes)")

# =========================================================================
# ARM 1: OmniVoice (k2-fsa/OmniVoice, 1.6B)
# =========================================================================
print("\\n" + "="*60)
print(">>> ARM 1: OmniVoice (1.6B) Zero-Shot Voice Cloning")
print("="*60)

arm1_code = """
import sys
import time
import subprocess
from pathlib import Path
import soundfile as sf
import torch

print("Installing OmniVoice...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "git+https://github.com/k2-fsa/OmniVoice.git@468e927ba3716cd8dd86421148dfb3046e9f9d7b",
    "soundfile>=0.13", "transformers>=4.45", "accelerate", "scipy"
], check=True)

from omnivoice.models.omnivoice import OmniVoice

print("Loading OmniVoice model onto cuda:0...")
model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)
print(f"OmniVoice loaded. Sample rate: {model.sampling_rate}Hz")

eval_text = \"\"\"""" + tough_irish_text + """\"\"\"
ref_path = "/tmp/cillian_ref.wav"
ref_text = \"\"\"""" + ref_text + """\"\"\"

print("Starting OmniVoice synthesis...")
t0 = time.time()
import re
sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip()]
pieces = []
sr = model.sampling_rate

for idx, s in enumerate(sents, 1):
    c_t0 = time.time()
    audio = model.generate(
        text=s,
        ref_audio=ref_path,
        ref_text=ref_text,
        language="English",
        num_step=32,
        normalize_text=False
    )[0]
    pieces.append(audio)
    pieces.append(torch.zeros(int(0.35 * sr)))
    c_dur = len(audio) / sr
    c_el = time.time() - c_t0
    print(f"  Chunk {idx}/{len(sents)}: {c_dur:.1f}s audio in {c_el:.1f}s (RTF {c_el/c_dur:.2f}x)")

import numpy as np
full_audio = np.concatenate([p.cpu().numpy() if hasattr(p, 'cpu') else np.asarray(p) for p in pieces])
dur = len(full_audio) / sr
el = time.time() - t0
print(f"OmniVoice Total: {dur:.1f}s audio in {el:.1f}s (RTF {el/dur:.2f}x)")

out_wav = "/kaggle/working/out/omnivoice_raw.wav"
sf.write(out_wav, full_audio, sr)
print(f"✓ Saved {out_wav}")
"""

Path("/tmp/run_omnivoice.py").write_text(arm1_code, encoding="utf-8")

try:
    subprocess.run([sys.executable, "/tmp/run_omnivoice.py"], check=True)
    if Path("/kaggle/working/out/omnivoice_raw.wav").exists():
        master_audio("/kaggle/working/out/omnivoice_raw.wav", "/kaggle/working/out/omnivoice_cillian_tough.mp3", 24000)
except Exception as exc:
    print(f"OmniVoice run failed: {{exc}}")

torch.cuda.empty_cache()

# =========================================================================
# ARM 2: VoxCPM2 (openbmb/VoxCPM2, 2.0B)
# =========================================================================
print("\\n" + "="*60)
print(">>> ARM 2: VoxCPM2 (2.0B) Tokenizer-Free Continuous Cloning")
print("="*60)

arm2_code = """
import sys
import time
import subprocess
from pathlib import Path
import soundfile as sf
import torch

print("Installing VoxCPM...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "voxcpm", "soundfile>=0.13", "accelerate"
], check=True)

from voxcpm import VoxCPM

print("Loading VoxCPM2 model onto GPU...")
model = VoxCPM.from_pretrained("openbmb/VoxCPM2")
sr = getattr(model, "sample_rate", 24000)
if hasattr(model, "tts_model") and hasattr(model.tts_model, "sample_rate"):
    sr = model.tts_model.sample_rate
print(f"VoxCPM2 loaded. Sample rate: {sr}Hz")

eval_text = \"\"\"""" + tough_irish_text + """\"\"\"
ref_path = "/tmp/cillian_ref.wav"

print("Starting VoxCPM2 synthesis...")
t0 = time.time()

import re
import numpy as np
sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip()]
pieces = []

for idx, s in enumerate(sents, 1):
    c_t0 = time.time()
    wav = model.generate(
        text=s,
        reference_audio=ref_path,
        cfg_value=2.0,
        inference_timesteps=10,
    )
    pieces.append(wav)
    pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
    c_dur = len(wav) / sr
    c_el = time.time() - c_t0
    print(f"  Chunk {idx}/{len(sents)}: {c_dur:.1f}s audio in {c_el:.1f}s (RTF {c_el/c_dur:.2f}x)")

full_audio = np.concatenate(pieces)
dur = len(full_audio) / sr
el = time.time() - t0
print(f"VoxCPM2 Total: {dur:.1f}s audio in {el:.1f}s (RTF {el/dur:.2f}x)")

out_wav = "/kaggle/working/out/voxcpm2_raw.wav"
sf.write(out_wav, full_audio, sr)
print(f"✓ Saved {out_wav}")
"""

Path("/tmp/run_voxcpm2.py").write_text(arm2_code, encoding="utf-8")

try:
    subprocess.run([sys.executable, "/tmp/run_voxcpm2.py"], check=True)
    if Path("/kaggle/working/out/voxcpm2_raw.wav").exists():
        master_audio("/kaggle/working/out/voxcpm2_raw.wav", "/kaggle/working/out/voxcpm2_cillian_tough.mp3", 24000)
except Exception as exc:
    print(f"VoxCPM2 run failed: {{exc}}")

print("\\n" + "="*60)
print("Audition Run Finished. Mastered Files in /kaggle/working/out:")
for p in Path("/kaggle/working/out").glob("*.mp3"):
    print(f"  - {{p.name}} ({{p.stat().st_size:,}} bytes)")
print("="*60)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"✓ Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/cillian-irish-omnivoice-voxcpm2",
    "title": "cillian-irish-omnivoice-voxcpm2",
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
    "model_sources": []
}

meta_file = stage_dir / "kernel-metadata.json"
meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"✓ Written {meta_file}")
