"""
prepare_kaggle_fish_as_newstates_v2.py — Armed Struggle ch2 "New States 1923-63",
v2 fixing Dave's 2026-09-22 verdict on v1:
  1. year ranges read digit-wise  -> full year expansion (ranges, short forms, standalone)
  2. pacing runs on / no breathing -> paragraph-aware gaps (0.65s) + abbrev-safe
     sentence splitting (initials no longer shatter: F. L. Green)
  3. occasional American drift    -> temperature 1.0 -> 0.7 (vendor fixed default)
Free Kaggle T4 x2, same single-process banked harness.
"""

import base64
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
cillian_b64 = base64.b64encode(cillian_wav.read_bytes()).decode("ascii")

ref_text = (
    "You find so much empathy in novels, because there you are putting yourself into "
    "somebody else's point of view, and I've always been a big reader."
)

# ---------------- text preparation ----------------
raw = Path(r"C:\Users\Dave\AppData\Local\Temp\opencode\as_ch2_newstates.txt").read_text(encoding="utf-8")

lex = json.loads(
    (root / "fixtures" / "irish_pronunciation_lexicon.json").read_text(encoding="utf-8")
)
chapter_glossary = {
    "Fianna Fáil": "Fee-na Fawl",
    "Fianna Fail": "Fee-na Fawl",
    "Fáil": "Fawl",
    "Fianna": "Fee-na",
    "Dáil": "Dawl",
    "Éireann": "Air-inn",
    "Eireann": "Air-inn",
    "Sean": "Shawn",
    "Eamon": "Aymun",
    "IRA": "I-R-A",
}
for key in sorted((k for k in lex if not k.startswith("_")), key=len, reverse=True):
    raw = raw.replace(key, lex[key])
for key in sorted(chapter_glossary, key=len, reverse=True):
    raw = raw.replace(key, chapter_glossary[key])

_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TENS = ["", "ten", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def year_words(y: int) -> str:
    if 1900 <= y <= 1999:
        rest = y - 1900
        if rest == 0:
            return "nineteen hundred"
        if rest < 10:
            return f"nineteen oh {_ONES[rest]}"
        return f"nineteen {_TENS[rest // 10]}-{_ONES[rest % 10]}"
    if 2000 <= y <= 2099:
        rest = y - 2000
        if rest == 0:
            return "two thousand"
        if rest < 10:
            return f"two thousand and {_ONES[rest]}"
        return f"two thousand and {_TENS[rest // 10]}-{_ONES[rest % 10]}"
    return str(y)


def two_digit_words(d: str) -> str:
    n = int(d)
    if n == 0:
        return "hundred"
    if n < 10:
        return f"oh {_ONES[n]}"
    return f"{_TENS[n // 10]}-{_ONES[n % 10]}"


# ranges first: "1911-1921" and short-form "1923-63"
def range_repl(m: re.Match) -> str:
    y1 = int(m.group(1))
    tail = m.group(2)
    if len(tail) == 4:
        return f"{year_words(y1)} to {year_words(int(tail))}"
    return f"{year_words(y1)} to {two_digit_words(tail)}"


raw = re.sub(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|\d{2})\b", range_repl, raw)
# standalone years
raw = re.sub(r"\b((?:19|20)\d{2})\b", lambda m: year_words(int(m.group(1))), raw)

# ---------------- abbrev-safe sentence splitting with paragraph structure ----------------
PLACEHOLDER = "\ue000"
ABBR = ["Mr", "Mrs", "Ms", "Dr", "Prof", "St", "Sr", "Jr", "Col", "Gen", "Lt", "Cpt",
        "Capt", "Sgt", "Rev", "Hon", "Sinn", "Vol", "No", "fig"]


def protect(text: str) -> str:
    for a in ABBR:
        text = text.replace(a + ".", a + PLACEHOLDER)
    # letter initials: "F. L." and trailing "L. Green"
    text = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", r"\1" + PLACEHOLDER, text)
    return text


paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip() and not re.fullmatch(r"\d{1,3}", p.strip())]
sents: list[dict] = []
for pid, para in enumerate(paras):
    guarded = protect(para)
    for s in re.split(r"(?<=[.!?])\s+", guarded):
        s = s.replace(PLACEHOLDER, ".").strip()
        if s and len(s) > 1:
            sents.append({"text": s, "para": pid})

print(f"{len(paras)} paragraphs, {len(sents)} sentences")
for s in sents[:3]:
    print("  ", s)

payload = {"ref_text": ref_text, "sents": sents}
text_json = json.dumps(payload, ensure_ascii=False)

stage_dir = root / "scratch" / "kaggle_fish_as_newstates_v2" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Fish S2 Pro AS ch2 v2: years expanded, paragraph gaps, temp 0.7."""
import base64, glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out")
(OUT / "wavs").mkdir(parents=True, exist_ok=True)

ref_path = "/workspace/cillian_ref.wav"
Path(ref_path).write_bytes(base64.b64decode({repr(cillian_b64)}))
PAYLOAD = json.loads({repr(text_json)})
ref_text = PAYLOAD["ref_text"]
sents = PAYLOAD["sents"]  # list of {{"text", "para"}}
print(f"{{len(sents)}} sentences / {{max(s['para'] for s in sents) + 1}} paragraphs", flush=True)

subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", "/workspace/fish-speech"], check=False)
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "/workspace/fish-speech"])
print("pip -e exit:", r.returncode, flush=True)
for path in glob.glob("/usr/local/lib/python3.*/dist-packages/audiotools/ml/decorators.py"):
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
assert src.count("CODEC_DEVICE or device") == 4, "codec device patch incomplete"
inf_path.write_text(src)

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
precision = torch.half
model, decode_one_token = init_model("/workspace/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/workspace/s2-pro/codec.pth", CODEC_DEVICE, precision)
prompt_tokens_list = [encode_audio(ref_path, codec, CODEC_DEVICE).cpu()]
torch.manual_seed(42)
torch.cuda.manual_seed(42)
print(f"Setup {{time.time()-t_setup:.0f}}s", flush=True)


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
for i, item in enumerate(sents, 1):
    s = item["text"]
    c_t0 = time.time()
    try:
        gen = generate_long(
            model=model, device=DEVICE, decode_one_token=decode_one_token,
            text=s, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
            temperature=0.7, compile=False, iterative_prompt=True, chunk_length=300,
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
        if wav is None or len(wav) < 0.3 * codec.sample_rate:
            raise RuntimeError("no usable audio returned")
        ok, rms, d, peak = health(wav)
        if not ok:
            raise RuntimeError(f"health FAIL rms={{rms:.4f}} diff={{d:.5f}} peak={{peak:.3f}}")
        sf.write(str(OUT / "wavs" / f"{{i:04d}}.wav"), wav, codec.sample_rate)
        secs = len(wav) / codec.sample_rate
        audio_secs += secs
        manifest.append({{"idx": i, "para": item["para"], "sec": round(secs, 2), "ok": True}})
        if i % 25 == 0 or i == len(sents):
            el = time.time() - t0
            print(f"[{{i}}/{{len(sents)}}] RTF {{el / max(audio_secs, 1):.2f}}x ({{n_fail}} failed)", flush=True)
            (OUT / "manifest.json").write_text(json.dumps({{"elapsed": round(el, 1), "audio_secs": round(audio_secs, 1), "n_fail": n_fail, "done": i, "sents": manifest}}, indent=1))
    except Exception as e:
        n_fail += 1
        manifest.append({{"idx": i, "para": item["para"], "ok": False, "err": str(e)[:200]}})
        print(f"[{{i}}/{{len(sents)}}] FAILED: {{str(e)[:150]}}", flush=True)

gen_wall = time.time() - t0
rtf = gen_wall / max(audio_secs, 1.0)
print(f"GEN DONE: {{audio_secs:.0f}}s audio in {{gen_wall:.0f}}s -> RTF {{rtf:.2f}}x ({{n_fail}} failed)", flush=True)

pieces = []
prev_para = None
sr = codec.sample_rate
for item in manifest:
    if not item.get("ok"):
        continue
    p = OUT / "wavs" / f"{{item['idx']:04d}}.wav"
    if p.exists():
        w, s0 = sf.read(p, dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        sr = s0
        if prev_para is not None:
            gap = 0.65 if item["para"] != prev_para else 0.35
            pieces.append(np.zeros(int(gap * sr), dtype=np.float32))
        pieces.append(w)
        prev_para = item["para"]
if not pieces:
    raise SystemExit("no banked audio")
full = np.concatenate(pieces)
sf.write("/workspace/as_ch2_v2_raw.wav", full, sr)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/workspace/as_ch2_v2_raw.wav",
                "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", "192k", str(OUT / "armed_struggle_ch2_newstates_cillian_v2.mp3")], check=True)
a, sra = sf.read("/workspace/as_ch2_v2_raw.wav", dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
ok, rms, d, peak = health(a)
total = len(a) / sra
print(f"FINAL: {{total:.1f}}s rms={{rms:.4f}} diff={{d:.5f}} pass={{ok}}")
print(f"MANIFEST: rtf={{rtf:.2f}} n_fail={{n_fail}}", flush=True)
(OUT / "manifest.json").write_text(json.dumps({{"rtf": round(rtf, 2), "n_fail": n_fail, "total_sec": round(total, 1), "sents": manifest}}, indent=1))
if not ok:
    (OUT / "armed_struggle_ch2_newstates_cillian_v2.mp3").rename(OUT / "armed_struggle_ch2_newstates_cillian_v2_UNHEALTHY.mp3")
print("CHAPTER V2 COMPLETE", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-as-newstates-cillian-v2",
    "title": "fish-as-newstates-cillian-v2",
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
