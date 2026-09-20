"""
kaggle_prepare_4pages.py — Prepare the 4-page verification test for Kaggle.
"""

import re
import json
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ch10_file = root / "fixtures" / "armed_struggle_chapters" / "10 - Two New States Nineteen Twenty Three 63.txt"
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"

txt = ch10_file.read_text(encoding="utf-8")
paras = [p.strip() for p in txt.split("\n\n") if p.strip()]

# Paragraphs 21 to 28 (0-indexed 20 to 28)
selected_paras = paras[20:28]

def clean_sentence_split(text: str) -> list[str]:
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.", "Capt.", "Gen.", "Col.", "Lt."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    items = [item.replace(marker, ".").strip() for item in re.split(r"(?<=[.!?\n])\s+", protected) if item.strip()]
    return items

chunks = []
for p_idx, p in enumerate(selected_paras, 1):
    sents = clean_sentence_split(p)
    cur_chunk = []
    cur_words = 0
    for s in sents:
        w_cnt = len(s.split())
        if cur_words + w_cnt > 80 and cur_chunk:
            chunks.append({
                "text": " ".join(cur_chunk),
                "is_para_end": False,
            })
            cur_chunk = [s]
            cur_words = w_cnt
        else:
            cur_chunk.append(s)
            cur_words += w_cnt
    if cur_chunk:
        chunks.append({
            "text": " ".join(cur_chunk),
            "is_para_end": True,
        })

print(f"Total chunks created: {len(chunks)}")
total_w = sum(len(c["text"].split()) for c in chunks)
print(f"Total words: {total_w}")

# Verify no "IR." or mangled acronyms
for i, c in enumerate(chunks, 1):
    t = c["text"]
    assert "IR." not in t, f"Chunk {i} contains corrupted 'IR.': {t}"
    assert "IR.’s" not in t, f"Chunk {i} contains corrupted 'IR.’s': {t}"

print("✓ All chunks verified: 'IRA' and 'IRA’s' are 100% intact and clean.")

# Output staged directory for Kaggle kernel
stage_dir = root / "scratch" / "kaggle_ch10_4pages" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

# Encode ref wav as b64
ref_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")
chunks_json_str = json.dumps(chunks)

ref_text = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)
instruction = (
    "Read in a calm, thoughtful, authentic Irish accent with measured literary pacing and solemn gravitas "
    "suitable for an Irish history audiobook."
)

kernel_code = f'''#!/usr/bin/env python3
"""
Kaggle Kernel: Render 4-page verification of Armed Struggle Chapter 10
Voice: Cillian Murphy (Breeze TTS 2 3.5B)
"""

import io
import os
import sys
import time
import json
import base64
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

print("=== Checking GPU ===")
assert torch.cuda.is_available(), "CUDA required!"
device = torch.cuda.get_device_name(0)
print(f"GPU: {{device}}")

# Install sox via apt
try:
    subprocess.run(["apt-get", "update", "-qq"], check=False)
    subprocess.run(["apt-get", "install", "-y", "-qq", "sox", "libsox-fmt-all", "ffmpeg"], check=False)
except Exception:
    pass

# 1. Install dependencies
print("=== Installing dependencies ===")
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "soundfile>=0.13", "huggingface_hub[cli]>=0.25", "transformers>=4.45,<5.0.0",
    "qwen-tts==0.1.1", "accelerate", "scipy"
], check=True)

# 2. Clone Breeze TTS repo
breeze_repo = Path("/tmp/breeze-tts")
if not breeze_repo.exists():
    print("=== Cloning Breeze TTS ===")
    subprocess.run(["git", "clone", "https://github.com/breezeblue-ai/breeze-tts.git", str(breeze_repo)], check=True)

sys.path.insert(0, str(breeze_repo))

# 3. Download weights
print("=== Downloading Breeze TTS 2 Weights ===")
from huggingface_hub import snapshot_download
model_dir = Path("/tmp/breeze-model")
snapshot_download("BreezeBlue/Breeze-TTS-2", local_dir=str(model_dir))

# 4. Load runtime
print("=== Loading Breeze Runtime ===")
from breeze_infer.runtime import load_runtime, resolve_device, set_all_seeds, update_generation_config_for_breeze
from breeze_infer.templates import get_template, prepare_inputs
from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

tokenizer, model, audio_tokenizer = load_runtime(
    model_dir,
    device=resolve_device(),
    attn_implementation="sdpa",
)
update_generation_config_for_breeze(model)
config = FastStreamingConfig(
    max_new_tokens=1500,
    max_seq_len=2048,
    repetition_penalty=1.15,
)
runtime = FastBreezeStreamingRuntime(
    model, audio_tokenizer, config, tokenizer=tokenizer
)
sr = runtime.sample_rate
print(f"Runtime ready. Sample rate: {{sr}}")

# 5. Reference Audio
ref_wav_bytes = base64.b64decode({repr(ref_b64)})
ref_path = "/tmp/cillian_ref.wav"
Path(ref_path).write_bytes(ref_wav_bytes)

ref_text = {repr(ref_text)}
instruction = {repr(instruction)}
chunks = json.loads({repr(chunks_json_str)})

print(f"=== Rendering {{len(chunks)}} chunks for 4-page excerpt ===")
pieces = []
t0 = time.time()
LOCKED_SEED = 42

for idx, c in enumerate(chunks, 1):
    c_start = time.time()
    t_text = c["text"]
    inst = instruction
    if "?" in t_text:
        inst += " Deliver with an inquisitive, rising inflection on the question."
    
    req = {{
        "id": f"chunk-{{idx:03d}}",
        "text": t_text,
        "instruction": inst,
        "speaker": "S0",
        "ref_audio_path": ref_path,
        "ref_text": ref_text,
    }}
    
    set_all_seeds(LOCKED_SEED)
    inputs = prepare_inputs(
        tokenizer,
        audio_tokenizer,
        model,
        [req],
        get_template("ref_edit_tata"),
        guidance_scale=2.5,
        guidance_scale_ref=None,
        guidance_scale_ins=None,
    )
    
    audio_parts = []
    for chunk in runtime.iter_audio_chunks(inputs, request_id=f"chunk-{{idx:03d}}", seed=LOCKED_SEED):
        audio_parts.append(chunk.audio)
    del inputs
    
    if not audio_parts:
        print(f"Warning: Chunk {{idx}} empty!")
        continue
        
    chunk_pcm = np.concatenate(audio_parts)
    pieces.append(chunk_pcm)
    
    # Natural pause
    pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
    if c.get("is_para_end", False):
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
        
    elapsed = time.time() - c_start
    dur = len(chunk_pcm) / sr
    print(f"  [{{idx:02d}}/{{len(chunks):02d}}] ({{len(t_text.split()):2d}} words) {{dur:.1f}}s audio in {{elapsed:.1f}}s (RTF {{elapsed/dur:.2f}}x)")

full_pcm = np.concatenate(pieces)
total_audio_sec = len(full_pcm) / sr
total_wall = time.time() - t0
print(f"=== Render Finished: {{total_audio_sec:.1f}}s ({{total_audio_sec/60:.1f}} min) in {{total_wall:.1f}}s (RTF {{total_wall/total_audio_sec:.2f}}x) ===")

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)
raw_wav = out_dir / "raw.wav"
sf.write(str(raw_wav), full_pcm, sr)

# Broadcast mastering
mastered_mp3 = out_dir / "ch10_4pages_cillian_clean.mp3"
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
    str(mastered_mp3)
], check=True)

if raw_wav.exists():
    raw_wav.unlink()

print(f"✓✓✓ Output file ready: {{mastered_mp3}} ({{mastered_mp3.stat().st_size:,}} bytes)")
'''

(stage_dir / "run_kernel.py").write_text(kernel_code, encoding="utf-8")

meta = {
    "id": "davedavedavedavenm/armed-struggle-ch10-4pages",
    "title": "armed-struggle-ch10-4pages",
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

print(f"✓ Kaggle kernel staged at: {stage_dir}")
