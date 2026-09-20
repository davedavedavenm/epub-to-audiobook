"""
kaggle_prepare_qwen3_tough_irish.py — Stage Qwen3-TTS 1.7B Cillian Murphy clone
on the Tough Irish Words challenge for fast Kaggle T4 evaluation.
"""

import base64
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
ref_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")

raw_text = (
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

phonetic_text = (
    "In Dublin, the leaders of the new republic assembled to challenge the authority of the Crown. "
    "Paw-drig Pearse and Shawn Mac-Deer-muh-duh had proclaimed the provisional government in nineteen-sixteen, "
    "but it was the First Doyle Air-in that solidified the republican mandate. "
    "A-mon de Valera was chosen as Preev-Arra, while Cah-hal Broo-ha took charge of the Ministry of Defence, "
    "supported by the dedicated volunteers of Coo-man na mBawn. "
    "From the coastal redoubts of Doon Leer-ee to the military garrison at Port-leesh, British forces struggled to contain the rising tide. "
    "When the office of Tee-shukh and Taw-nish-tuh were debated decades later by leaders like Rory O-Braw-dee, "
    "Shin Fain insisted that true legitimacy had already been won in the crucible of war. "
    "If the imperial parliament in Westminster could be so thoroughly rejected across the island, then where did that leave the moral standing of British rule?"
)

ref_text = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)

kernel_code = f'''#!/usr/bin/env python3
"""
Qwen3-TTS 1.7B Cillian Murphy Clone on Tough Irish Words Challenge
Evaluates:
Arm 1: Raw Irish Text
Arm 2: Phonetically Steered Text
"""

import gc
import os
import sys
import time
import base64
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

print("=== Checking CUDA ===")
assert torch.cuda.is_available(), "CUDA required!"
device = torch.cuda.get_device_name(0)
print(f"GPU: {{device}}")

# 1. Install Qwen3-TTS
print("=== Installing Dependencies ===")
RUNTIME_SHA = "022e286b98fbec7e1e916cb940cdf532cd9f488e"
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "soundfile>=0.13", "transformers>=4.45", "accelerate", "scipy",
    f"qwen-tts @ git+https://github.com/QwenLM/Qwen3-TTS.git@{{RUNTIME_SHA}}"
], check=True)

# 2. Reference Audio
ref_wav_bytes = base64.b64decode({repr(ref_b64)})
ref_path = "/tmp/cillian_ref.wav"
Path(ref_path).write_bytes(ref_wav_bytes)
ref_text = {repr(ref_text)}

# 3. Load Qwen3-TTS Model
print("=== Loading Qwen3-TTS 1.7B Base Model ===")
from qwen_tts import Qwen3TTSModel
model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="cuda:0",
    dtype=torch.float16,
    attn_implementation="sdpa",
)
print("Model loaded. Creating Cillian Murphy voice clone prompt...")
prompt = model.create_voice_clone_prompt(
    ref_audio=ref_path, ref_text=ref_text, x_vector_only_mode=False
)
print("Voice clone prompt created!")

arms = [
    ("qwen3_cillian_raw", {repr(raw_text)}),
    ("qwen3_cillian_phonetic", {repr(phonetic_text)})
]

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)

import re
def sentence_chunks(text: str) -> list[str]:
    protected = text
    marker = "\\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?])\\s+", protected)
        if item.strip()
    ]
    return chunks

for name, text in arms:
    print(f"\\n==========================================")
    print(f"Starting Arm: {{name}}")
    print(f"==========================================")
    chunks = sentence_chunks(text)
    pieces = []
    t_start = time.time()
    sr = 24000
    
    for idx, c in enumerate(chunks, 1):
        c_t0 = time.time()
        torch.manual_seed(42 + idx)
        torch.cuda.manual_seed_all(42 + idx)
        
        wavs, sample_rate = model.generate_voice_clone(
            text=c,
            language="English",
            voice_clone_prompt=prompt,
            max_new_tokens=4096,
            do_sample=True,
            top_k=50,
            top_p=1.0,
            temperature=0.85,
            repetition_penalty=1.05,
            subtalker_dosample=True,
            subtalker_top_k=50,
            subtalker_top_p=1.0,
            subtalker_temperature=0.85
        )
        sr = sample_rate
        audio = np.asarray(wavs[0], dtype="float32").reshape(-1)
        del wavs
        gc.collect()
        torch.cuda.empty_cache()
        
        pieces.append(audio)
        # Natural pause
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
        c_dur = len(audio) / sr
        c_el = time.time() - c_t0
        print(f"  Chunk {{idx}}/{{len(chunks)}} ({{len(c.split())}} words): {{c_dur:.1f}}s audio in {{c_el:.1f}}s (RTF {{c_el/c_dur:.2f}}x)")
        
    full_pcm = np.concatenate(pieces)
    tot_dur = len(full_pcm) / sr
    tot_wall = time.time() - t_start
    print(f"Arm {{name}} complete: {{tot_dur:.1f}}s audio in {{tot_wall:.1f}}s (RTF {{tot_wall/tot_dur:.2f}}x)")
    
    raw_wav = out_dir / f"{{name}}_raw.wav"
    sf.write(str(raw_wav), full_pcm, sr)
    
    # Broadcast mastering
    mp3_path = out_dir / f"{{name}}.mp3"
    af_filters = (
        "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
        "highshelf=f=7500:gain=-2.0:width=1.0,"
        "loudnorm=I=-20:TP=-2:LRA=11"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw_wav),
        "-af", af_filters,
        "-ar", "24000",
        "-codec:a", "libmp3lame", "-b:a", "192k",
        str(mp3_path)
    ], check=True)
    if raw_wav.exists():
        raw_wav.unlink()
    print(f"✓ Created: {{mp3_path.name}} ({{mp3_path.stat().st_size:,}} bytes)")

print("\\n✓✓✓ All arms rendered and mastered successfully!")
'''

stage_dir = root / "scratch" / "kaggle_qwen3_tough_irish" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)
(stage_dir / "run_qwen3.py").write_text(kernel_code, encoding="utf-8")

meta = {
    "id": "davedavedavedavenm/qwen3-tough-irish-cillian",
    "title": "qwen3-tough-irish-cillian",
    "code_file": "run_qwen3.py",
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
print(f"✓ Staged Qwen3 Tough Irish kernel at: {stage_dir}")
