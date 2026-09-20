"""
prepare_kaggle_higgs3.py — Stage Higgs TTS 3 (bosonai/higgs-tts-3-4b) on the
Tough Irish Words Challenge using Cillian Murphy's studio dry reference.

Free Kaggle T4 only. NO Modal, NO paid GPU (Dave: zero remaining Modal credit).

ARM 1: vLLM-Omni OpenAI-compatible /v1/audio/speech (vendor-recommended serving)
ARM 2: transformers-native fallback if vLLM cannot run on T4 (sm_75)
Either arm producing a mastered MP3 is a valid audition result.
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

stage_dir = root / "scratch" / "kaggle_higgs3" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""
Kaggle Audition Kernel: Higgs TTS 3 (Boson, 4B) on Tough Irish Words
Narrator Voice: Cillian Murphy (Studio Dry Reference), zero-shot clone.
ARM 1 vLLM-Omni -> ARM 2 transformers-native fallback. Free T4 only.
"""

import base64
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

assert torch.cuda.is_available(), "CUDA required!"
gpu_name = torch.cuda.get_device_name(0)
gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
print(f"GPU: {{gpu_name}} ({{gpu_mem:.1f}} GB VRAM)")

ref_path = "/tmp/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
ref_text = {repr(ref_text)}
eval_text = {repr(tough_irish_text)}

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)

sents = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", eval_text) if s.strip()]
print(f"{{len(sents)}} sentences staged.")


def master_audio(in_wav: str, out_mp3: str, sr: int):
    af_filters = (
        "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
        "highshelf=f=7500:gain=-2.0:width=1.0,"
        "loudnorm=I=-20:TP=-2:LRA=11"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", in_wav,
        "-af", af_filters, "-ar", str(sr),
        "-codec:a", "libmp3lame", "-b:a", "192k", out_mp3,
    ], check=True)
    print(f"Mastered: {{out_mp3}} ({{Path(out_mp3).stat().st_size:,}} bytes)")


def join_and_save(pieces, sr, raw_wav, out_mp3):
    full = np.concatenate(pieces)
    sf.write(raw_wav, full, sr)
    master_audio(raw_wav, out_mp3, sr)
    return len(full) / sr


# ===================== ARM 1: vLLM-Omni serving =====================
arm1_ok = False
try:
    print("=" * 60)
    print(">>> ARM 1: Higgs TTS 3 via vLLM-Omni (fp16 on T4)")
    print("=" * 60)
    subprocess.run([sys.executable, "-m", "pip", "install",
                    "vllm==0.22.*", "vllm-omni==0.22.*", "requests"], check=True)
    env = dict(__import__("os").environ,
               VLLM_ATTENTION_BACKEND="XFORMERS", DTYPE="float16")
    srv = subprocess.Popen(
        ["vllm-omni", "serve", "bosonai/higgs-tts-3-4b",
         "--host", "127.0.0.1", "--port", "8095",
         "--trust-remote-code", "--omni",
         "--dtype", "float16", "--gpu-memory-utilization", "0.85",
         "--max-model-len", "4096"],
        env=env)
    import requests
    ready = False
    for _ in range(180):
        time.sleep(10)
        try:
            if requests.get("http://127.0.0.1:8095/v1/models", timeout=5).ok:
                ready = True
                break
        except Exception:
            if srv.poll() is not None:
                break
    if not ready:
        raise RuntimeError("vLLM-Omni server never became ready")
    print("vLLM-Omni server is up.")

    t0 = time.time()
    pieces = []
    sr = 24000
    for idx, s in enumerate(sents, 1):
        c_t0 = time.time()
        resp = requests.post("http://127.0.0.1:8095/v1/audio/speech", json={{
            "input": s,
            "references": [{{"audio_path": ref_path, "text": ref_text}}],
            "temperature": 0.8, "top_k": 50, "max_new_tokens": 1024,
        }}, timeout=600)
        resp.raise_for_status()
        wav, sr = sf.read(__import__("io").BytesIO(resp.content), dtype="float32")
        pieces.append(wav)
        pieces.append(np.zeros(int(0.35 * sr), dtype=np.float32))
        c_dur = len(wav) / sr
        c_el = time.time() - c_t0
        print(f"  [Higgs3/vllm {{idx}}/{{len(sents)}}] {{c_dur:.1f}}s audio in {{c_el:.1f}}s (RTF {{c_el / c_dur:.2f}}x)")
    dur = join_and_save(pieces, sr, "/kaggle/working/out/higgs3_raw.wav",
                        "/kaggle/working/out/higgs3_cillian_tough.mp3")
    el = time.time() - t0
    print(f"ARM 1 TOTAL: {{dur:.1f}}s audio in {{el:.1f}}s (RTF {{el / dur:.2f}}x)")
    srv.terminate()
    arm1_ok = True
except Exception as exc:
    print(f"ARM 1 FAILED: {{exc}}")

# transformers-native support for higgs_multimodal_qwen3 is not in main yet
# (verified failing on v2); vLLM-Omni is the only runnable public runtime.
if not arm1_ok:
    raise RuntimeError("ARM 1 (vLLM-Omni) failed; no supported runtime remains")

print("=" * 60)
print("Kaggle Execution Finished. Outputs:")
for p in sorted(out_dir.glob("*.mp3")):
    print(f"  {{p.name}} ({{p.stat().st_size:,}} bytes)")
print("=" * 60)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/higgs3-tough-irish-cillian",
    "title": "higgs3-tough-irish-cillian",
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
