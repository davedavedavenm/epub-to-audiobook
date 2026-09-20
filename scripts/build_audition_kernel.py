import base64
import json
from pathlib import Path

root = Path(r"c:\Users\Dave\repos\epub-to-audiobook")
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

# Generate config payload
config = {
    "cillian_b64": cillian_b64,
    "ref_text": ref_text,
    "tough_irish_text": tough_irish_text,
}
(stage_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

# Generate standalone runner script
runner_content = """#!/usr/bin/env python3
import json
import base64
import subprocess
import sys
import time
from pathlib import Path
import soundfile as sf
import torch

print("=== Checking CUDA ===")
assert torch.cuda.is_available(), "CUDA required!"
device = torch.cuda.get_device_name(0)
print(f"GPU: {device}")

cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
ref_path = "/tmp/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode(cfg["cillian_b64"]))
ref_text = cfg["ref_text"]
eval_text = cfg["tough_irish_text"]

out_dir = Path("/kaggle/working/out")
out_dir.mkdir(parents=True, exist_ok=True)

def master(in_wav, out_mp3, sr=24000):
    af = "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11"
    subprocess.run(["ffmpeg", "-y", "-i", str(in_wav), "-af", af, "-ar", str(sr), "-codec:a", "libmp3lame", "-b:a", "192k", str(out_mp3)], check=True)
    print(f"Mastered: {out_mp3} ({Path(out_mp3).stat().st_size:,} bytes)")

# -------------------------------------------------------------
# ARM 1: OmniVoice
# -------------------------------------------------------------
print("\\n" + "="*50)
print(">>> ARM 1: OmniVoice Zero-Shot Reference Cloning")
print("="*50)
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "git+https://github.com/k2-fsa/OmniVoice.git@468e927ba3716cd8dd86421148dfb3046e9f9d7b", "soundfile>=0.13", "transformers>=4.45", "accelerate", "scipy"], check=True)
    from omnivoice.models.omnivoice import OmniVoice
    model_omni = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)
    print("OmniVoice loaded.")
    
    import re
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", eval_text) if s.strip()]
    pieces = []
    sr_omni = model_omni.sampling_rate
    t0 = time.time()
    for idx, s in enumerate(sents, 1):
        c_t0 = time.time()
        aud = model_omni.generate(text=s, ref_audio=ref_path, ref_text=ref_text, language="English", num_step=32, normalize_text=False)[0]
        pieces.append(aud)
        pieces.append(torch.zeros(int(0.35 * sr_omni)))
        dur = len(aud) / sr_omni
        print(f"  OmniVoice [{idx}/{len(sents)}]: {dur:.1f}s audio in {time.time()-c_t0:.1f}s")
    
    import numpy as np
    full_omni = np.concatenate([p.cpu().numpy() if hasattr(p, 'cpu') else np.asarray(p) for p in pieces])
    wav_omni = "/tmp/omni.wav"
    sf.write(wav_omni, full_omni, sr_omni)
    master(wav_omni, out_dir / "omnivoice_cillian_tough.mp3", sr_omni)
    del model_omni
    torch.cuda.empty_cache()
except Exception as e:
    print(f"OmniVoice error: {e}")

# -------------------------------------------------------------
# ARM 2: VoxCPM2
# -------------------------------------------------------------
print("\\n" + "="*50)
print(">>> ARM 2: VoxCPM2 Tokenizer-Free Continuous Cloning")
print("="*50)
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "voxcpm", "soundfile>=0.13", "accelerate"], check=True)
    from voxcpm import VoxCPM
    model_vox = VoxCPM.from_pretrained("openbmb/VoxCPM2")
    sr_vox = getattr(model_vox, "sample_rate", 24000)
    if hasattr(model_vox, "tts_model") and hasattr(model_vox.tts_model, "sample_rate"):
        sr_vox = model_vox.tts_model.sample_rate
    print(f"VoxCPM2 loaded (SR: {sr_vox}Hz).")
    
    import re
    import numpy as np
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", eval_text) if s.strip()]
    pieces = []
    t0 = time.time()
    for idx, s in enumerate(sents, 1):
        c_t0 = time.time()
        wav = model_vox.generate(text=s, reference_audio=ref_path, cfg_value=2.0, inference_timesteps=10)
        pieces.append(wav)
        pieces.append(np.zeros(int(0.35 * sr_vox), dtype=np.float32))
        dur = len(wav) / sr_vox
        print(f"  VoxCPM2 [{idx}/{len(sents)}]: {dur:.1f}s audio in {time.time()-c_t0:.1f}s")
    
    full_vox = np.concatenate(pieces)
    wav_vox = "/tmp/vox.wav"
    sf.write(wav_vox, full_vox, sr_vox)
    master(wav_vox, out_dir / "voxcpm2_cillian_tough.mp3", sr_vox)
    del model_vox
    torch.cuda.empty_cache()
except Exception as e:
    print(f"VoxCPM2 error: {e}")

print("\\n" + "="*50)
print("Kaggle Bakeoff Complete. Finished files:")
for f in out_dir.glob("*.mp3"):
    print(f"  - {f.name} ({f.stat().st_size:,} bytes)")
"""

(stage_dir / "run_kernel.py").write_text(runner_content, encoding="utf-8")

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

(stage_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print(f"✓ Successfully staged audition kernel at: {stage_dir}")
