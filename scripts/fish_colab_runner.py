"""runner.py — Armed Struggle full-book production render on Colab GPU (headless).
Locked recipe: Fish S2 Pro, dual-ref routing (narration=cillian_irish.wav,
quotes=crop_expressive_tail.wav), temp 0.85, per-sentence bank + health gate +
reroll seeds, per-chapter silence-trim + natural-gap assembly + mastering.
Resumable via /content/as_state.json."""

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

VENV = "/content/fishenv"
if not sys.prefix.startswith(VENV):
    vp = Path(VENV) / "bin" / "python"
    pyv = Path(VENV, "PYVER")
    if not vp.exists() or not pyv.exists() or pyv.read_text() != "3.10":
        subprocess.run(["rm", "-rf", VENV], check=False)
        r = subprocess.run(["uv", "venv", VENV, "--python", "3.10"])
        if r.returncode != 0:
            subprocess.run(["python3.10", "-m", "venv", VENV], check=True)
        Path(VENV, "PYVER").write_text("3.10")
    subprocess.run(["uv", "pip", "install", "-p", str(vp), "-q", "numpy", "soundfile"], check=False)
    print("bootstrapping into venv python", flush=True)
    os.execv(str(vp), [str(vp), str(Path(__file__).resolve())])

import numpy as np
import soundfile as sf


BASE = Path("/content")
OUT = BASE / "out"
OUT.mkdir(exist_ok=True)
(WAVS := BASE / "wavs").mkdir(exist_ok=True)
STATE_PATH = BASE / "as_state.json"
BUNDLE = BASE / "as_bundle.zip"
ORDER = ["preface", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7", "ch8", "conclusion"]

print("=== install runtime ===", flush=True)


def pip_install(*args):
    r = subprocess.run(["uv", "pip", "install", "-p", sys.executable, "-q", *args])
    if r.returncode != 0:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade", "--default-pip"], check=False)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *args], check=True)


subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
if not (BASE / "fish-speech").exists():
    subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", str(BASE / "fish-speech")], check=True)
pip_install("-e", str(BASE / "fish-speech"))
pip_install("huggingface_hub", "soundfile")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "protobuf>=6.31.1"], check=False)

for path in glob.glob("/content/fishenv/lib/python3.*/site-packages/audiotools/ml/decorators.py") + \
            glob.glob("/usr/local/lib/python3.*/dist-packages/audiotools/ml/decorators.py") + \
            glob.glob("/usr/lib/python3.*/dist-packages/audiotools/ml/decorators.py"):
    try:
        c = Path(path).read_text()
        if "from torch.utils.tensorboard import SummaryWriter" in c:
            Path(path).write_text(c.replace("from torch.utils.tensorboard import SummaryWriter", "SummaryWriter = None"))
    except Exception:
        pass

if not BUNDLE.exists():
    raise SystemExit("as_bundle.zip missing at /content")
import zipfile
with zipfile.ZipFile(BUNDLE) as zf:
    zf.extractall(BASE)
print("bundle extracted", flush=True)

inf_path = BASE / "fish-speech/fish_speech/models/text2semantic/inference.py"
src = inf_path.read_text()
if "CODEC_DEVICE" not in src:
    src = 'import os as _os\nCODEC_DEVICE = _os.environ.get("FISH_CODEC_DEVICE", "")\n' + src
src = src.replace("codec = load_codec_model(codec_checkpoint, device, precision)",
                  "codec = load_codec_model(codec_checkpoint, CODEC_DEVICE or device, precision)")
src = src.replace("encode_audio(p, codec, device)", "encode_audio(p, codec, CODEC_DEVICE or device)")
src = src.replace("decode_to_audio(merged_codes.to(device), codec)",
                  "decode_to_audio(merged_codes.to(CODEC_DEVICE or device), codec)")
assert src.count("CODEC_DEVICE or device") == 4
inf_path.write_text(src)

import torch

assert torch.cuda.is_available(), "no GPU"
print("GPU:", torch.cuda.get_device_name(0), flush=True)
DEVICE = "cuda:0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

if not (BASE / "s2-pro/codec.pth").exists():
    from huggingface_hub import snapshot_download
    print("=== downloading s2-pro weights ===", flush=True)
    t_w = time.time()
    snapshot_download("fishaudio/s2-pro", local_dir="/content/s2-pro")
    print(f"weights done in {time.time() - t_w:.0f}s", flush=True)

sys.path.insert(0, str(BASE / "fish-speech"))
from fish_speech.models.text2semantic.inference import (
    decode_to_audio, encode_audio, generate_long, init_model, load_codec_model,
)

precision = torch.half if torch.cuda.get_device_capability(0) < (8, 0) else torch.bfloat16
print("precision:", precision, flush=True)
model, decode_one_token = init_model("/content/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/content/s2-pro/codec.pth", DEVICE, precision)
REFS = json.loads((BASE / "refs/refs.json").read_text(encoding="utf-8"))
REFS.setdefault("cillian_irish_text", REFS["ref_full_text"])
REFS.setdefault("crop_expressive_tail_text", REFS["crop_expressive_tail_text"])
TOKENS = {
    "cillian_irish": [encode_audio(str(BASE / "refs/cillian_irish.wav"), codec, DEVICE).cpu()],
    "crop_expressive_tail": [encode_audio(str(BASE / "refs/crop_expressive_tail.wav"), codec, DEVICE).cpu()],
}
SR = codec.sample_rate

torch.manual_seed(42)
torch.cuda.manual_seed(42)


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    return 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05, rms, d


def synth(text, ref_key, temp, seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    gen = generate_long(
        model=model, device=DEVICE, decode_one_token=decode_one_token,
        text=text, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
        temperature=temp, compile=False, iterative_prompt=True, chunk_length=300,
        prompt_text=[REFS[ref_key + "_text"]], prompt_tokens=TOKENS[ref_key],
    )
    codes = []
    wav = None
    for response in gen:
        if response.action == "sample":
            codes.append(response.codes)
        elif response.action == "next" and codes:
            merged = torch.cat(codes, dim=1)
            wav = decode_to_audio(merged.to(DEVICE), codec).cpu().float().numpy()
            codes = []
    if codes:
        merged = torch.cat(codes, dim=1)
        wav = decode_to_audio(merged.to(DEVICE), codec).cpu().float().numpy()
    return wav


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


def state_load():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"completed": [], "progress": {}}


def state_save(st):
    STATE_PATH.write_text(json.dumps(st, indent=1))


st = state_load()
t_start = time.time()
for slug in ORDER:
    if slug in st["completed"]:
        continue
    payload = json.loads((BASE / "payloads" / f"{slug}.json").read_text(encoding="utf-8"))
    sents = payload["sents"]
    wdir = (WAVS / slug)
    wdir.mkdir(exist_ok=True, parents=True)
    start_idx = st["progress"].get(slug, 0)
    print(f"=== {slug}: {len(sents)} sents, resuming at {start_idx} ===", flush=True)
    for i in range(start_idx + 1, len(sents) + 1):
        item = sents[i - 1]
        wp = wdir / f"{i:04d}.wav"
        if wp.exists():
            st["progress"][slug] = i
            continue
        ref_key = "crop_expressive_tail" if item["quote"] else "cillian_irish"
        ok = False
        for attempt, seed in enumerate((42, 43, 44), 1):
            try:
                wav = synth(item["text"], ref_key, 0.85, seed)
                if wav is None or len(wav) < 0.6 * SR:
                    raise RuntimeError("short/none")
                good, rms, d = health(wav)
                if not good:
                    raise RuntimeError(f"health rms={rms:.4f}")
                sf.write(str(wp), wav, SR)
                ok = True
                break
            except Exception as e:
                if attempt == 3:
                    (wdir / f"{i:04d}.FAIL").write_text(str(e)[:200])
                    ok = True
                    print(f"  [{slug} {i}] FAILED PERMANENTLY: {str(e)[:120]}", flush=True)
        st["progress"][slug] = i
        if i % 20 == 0 or i == len(sents):
            state_save(st)
            el = time.time() - t_start
            print(f"  [{slug} {i}/{len(sents)}] elapsed {el/60:.0f}m", flush=True)
        if time.time() - t_start > 10 * 3600:
            state_save(st)
            print("=== 10h budget, exiting clean ===", flush=True)
            sys.exit(0)

    done = sorted(wdir.glob("*.wav"))
    fails = len(list(wdir.glob("*.FAIL")))
    prev_para = None
    pieces = []
    for wp in done:
        i = int(wp.stem)
        para = sents[i - 1]["para"]
        if prev_para is not None:
            gap = 0.50 if para != prev_para else 0.18
            pieces.append(np.zeros(int(gap * SR), dtype=np.float32))
        pieces.append(load_trim(wp))
        prev_para = para
    full = np.concatenate(pieces)
    raw = BASE / f"{slug}_raw.wav"
    sf.write(raw, full, SR)
    mp3 = OUT / f"armed_struggle_{slug}_cillian.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                    "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                    "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
    raw.unlink()
    st["completed"].append(slug)
    st.setdefault("meta", {})[slug] = {"sec": round(len(full) / SR, 1), "sents": len(done), "fails": fails}
    state_save(st)
    print(f"=== CHAPTER DONE: {slug} {len(full)/SR/60:.1f} min, {fails} failed sents ===", flush=True)

print("ALL CHAPTERS COMPLETE", flush=True)
