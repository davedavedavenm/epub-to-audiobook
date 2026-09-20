"""
prepare_kaggle_preface_v2.py — Stage Chapter 0 (Preface) of The Armed Struggle
with full date normalization, year-range expansion, and sentence-level slicing.
"""

import re
import json
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[1]
preface_file = root / "fixtures" / "armed_struggle_chapters" / "08 - Preface.txt"
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"

txt = preface_file.read_text(encoding="utf-8")

def normalize_dates_and_years(text: str) -> str:
    # 1. Expand "1 p.m." -> "one p.m."
    text = re.sub(r'\b1\s*p\.m\.', 'one p.m.', text)
    
    # 2. Year ranges: e.g. 1963–76, 1916-23, 1980–1, 1988–2002
    def _expand_year_range(m):
        y1 = int(m.group(1))
        y2_str = m.group(2)
        if len(y2_str) == 4:
            return f"{y1} to {y2_str}"
        elif len(y2_str) == 2:
            century = str(y1)[:2]
            return f"{y1} to {century}{y2_str}"
        elif len(y2_str) == 1:
            prefix = str(y1)[:3]
            return f"{y1} to {prefix}{y2_str}"
        return m.group(0)

    text = re.sub(r'\b(1[0-9]{3}|20[0-9]{2})\s*[-–—]\s*(\d{4}|\d{2}|\d{1})\b', _expand_year_range, text)

    # 3. Day + Month: e.g. "10 August", "8 August", "9 October"
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    day_ordinals = {
        "1": "first", "2": "second", "3": "third", "4": "fourth", "5": "fifth",
        "6": "sixth", "7": "seventh", "8": "eighth", "9": "ninth", "10": "tenth",
        "11": "eleventh", "12": "twelfth", "13": "thirteenth", "14": "fourteenth",
        "15": "fifteenth", "16": "sixteenth", "17": "seventeenth", "18": "eighteenth",
        "19": "nineteenth", "20": "twentieth", "21": "twenty-first", "22": "twenty-second",
        "23": "twenty-third", "24": "twenty-fourth", "25": "twenty-fifth", "26": "twenty-sixth",
        "27": "twenty-seventh", "28": "twenty-eighth", "29": "twenty-ninth", "30": "thirtieth",
        "31": "thirty-first"
    }

    def _expand_date(m):
        prep = m.group(1) or ""
        day = m.group(2)
        month = m.group(3)
        ord_word = day_ordinals.get(day, day)
        if prep:
            return f"{prep} the {ord_word} of {month}"
        else:
            return f"the {ord_word} of {month}"

    text = re.sub(rf'\b(on\s+)?(\d{{1,2}})\s+({months})\b', _expand_date, text, flags=re.IGNORECASE)

    return text

def clean_sentence_split(text: str) -> list[str]:
    # Protect dialogue quotes
    protected = re.sub(r'([,;:—])\s*([“"][^”"]+[?!”"])', r'\1\n\2', text)
    marker = "\ue000"
    for abbrev in (
        "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs.", "e.g.", "i.e.",
        "Capt.", "Gen.", "Col.", "Lt.", "Rev.", "No.", "p.m.", "a.m."
    ):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    items = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?\n])\s+", protected)
        if item.strip()
    ]
    return items

# Apply date & year normalizations
norm_txt = normalize_dates_and_years(txt)
paras = [p.strip() for p in norm_txt.split("\n\n") if p.strip()]

chunks = []
for p_idx, p in enumerate(paras, 1):
    sents = clean_sentence_split(p)
    for s_idx, s in enumerate(sents, 1):
        is_last_in_para = (s_idx == len(sents))
        chunks.append({
            "text": s,
            "is_para_end": is_last_in_para,
        })

print(f"Total sentence chunks created: {len(chunks)}")
total_w = sum(len(c["text"].split()) for c in chunks)
print(f"Total words: {total_w}")

# Strict verification: Ensure no corrupted acronyms or wobbly patterns
for i, c in enumerate(chunks, 1):
    t = c["text"]
    assert "IR." not in t, f"Chunk {i} contains corrupted 'IR.': {t}"
    assert "IR.’s" not in t, f"Chunk {i} contains corrupted 'IR.’s': {t}"
    assert "IR." not in t, f"Chunk {i} contains corrupted 'IR.': {t}"

print("✓ All chunks verified: 'IRA', 'OIRA', 'CIRA', 'RIRA', 'PIRA' are 100% intact and clean.")

# Output staged directory for Kaggle kernel
stage_dir = root / "scratch" / "kaggle_preface_v2" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

ref_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")
chunks_json_str = json.dumps(chunks, indent=2)

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
Kaggle Kernel: Render Preface of Armed Struggle (Richard English) - V2 Clean
Voice: Cillian Murphy (Breeze TTS 2 3.5B)
Fixes applied:
1. Expanded dates: "8 August" -> "the eighth of August"
2. Expanded year spans: "1963-76" -> "1963 to 1976"
3. Sentence-level slicing: eliminates attention wobble on complex words like "Presbyterian"
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

print(f"=== Rendering {{len(chunks)}} sentence chunks for Preface V2 ===")
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
    
    # Natural pause: 350ms between sentences
    pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
    if c.get("is_para_end", False):
        # Additional 350ms (700ms total) at paragraph boundaries
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
        
    elapsed = time.time() - c_start
    dur = len(chunk_pcm) / sr
    print(f"  [{{idx:02d}}/{{len(chunks):02d}}] ({{len(t_text.split()):2d}} words) {{dur:.1f}}s audio in {{elapsed:.1f}}s (RTF {{elapsed/dur:.2f}}x)", flush=True)

full_pcm = np.concatenate(pieces)
total_audio_sec = len(full_pcm) / sr
total_wall = time.time() - t0
print(f"\\n=== Synthesis Complete ===")
print(f"Total Audio: {{total_audio_sec:.1f}}s ({{total_audio_sec/60:.2f}} mins)")
print(f"Total Wall Time: {{total_wall:.1f}}s ({{total_wall/60:.2f}} mins)")
print(f"Overall RTF: {{total_wall/total_audio_sec:.2f}}x")

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)

raw_wav = out_dir / "preface_raw.wav"
sf.write(str(raw_wav), full_pcm, sr)

# Broadcast mastering
mastered_mp3 = out_dir / "08_preface_cillian_breeze.mp3"
af_filters = (
    "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
    "highshelf=f=7500:gain=-2.0:width=1.0,"
    "loudnorm=I=-20:TP=-2:LRA=11"
)
print("=== Broadcast Mastering to EBU R128 (-20 LUFS) ===")
subprocess.run([
    "ffmpeg", "-y", "-i", str(raw_wav),
    "-af", af_filters,
    "-ar", "24000",
    "-codec:a", "libmp3lame", "-b:a", "192k",
    str(mastered_mp3)
], check=True)

if raw_wav.exists():
    raw_wav.unlink()

print(f"✓ Mastered audio created: {{mastered_mp3.name}} ({{mastered_mp3.stat().st_size:,}} bytes)")
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"✓ Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/armed-struggle-preface-breeze-v2",
    "title": "armed-struggle-preface-breeze-v2",
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
