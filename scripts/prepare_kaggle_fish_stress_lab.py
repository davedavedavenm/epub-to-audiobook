"""
prepare_kaggle_fish_stress_lab.py — LOCKED-RECIPE stress test on made-up hard text.

2 dense paragraphs: Irish names, year ranges, ordinal dates, currency, thousands,
em-dashes, curly apostrophes, and a dramatic quote mid-flow.

Recipe under test (locked from Dave's verdicts 2026-09-22):
  - narration sentences: full 28s ref, temp 0.85
  - quote sentences:      expressive-tail crop ref, temp 0.85
  - curly apostrophes kept; years/ordinals/numbers expanded to words
  - orphan merge; per-sentence banking; health gate; auto re-roll (seed+1) on fail
  - assembly: silence-trim + 0.18s sentence / 0.50s paragraph gaps; mastered
"""

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]

lex = json.loads((root / "fixtures" / "irish_pronunciation_lexicon.json").read_text(encoding="utf-8"))

raw = (
    "On the morning of 12 July 1921, Dáil Éireann convened in Dublin’s Mansion House, where "
    "Cathal Brugha and Austin Chamberlain argued for three hours about the Treaty’s wording. "
    "By 1923, Cumann na mBan had 4,500 members; the National Army, by contrast, numbered "
    "roughly 55,000, and the cost of the Civil War — some £15 million — had ruined the "
    "exchequer. In Dún Laoghaire, Portlaoise and Westport, families still spoke of the burns "
    "and the raiders as if the ambulances had left only that week. Caoimhghín Ó Caoláin walked "
    "from Glounthaune to Cnoc na Gaoithe to vote.\n\n"
    "The inquest heard what happened next. ‘We started shooting from the car, then getting out "
    "of the car we continued to shoot. We all shot at him; he didn’t have a chance,’ the "
    "volunteer admitted, before adding that the plan, such as it was, had been improvised on "
    "the road. When the news reached Dublin, Eamon de Valera said nothing at all; Sinn Féin’s "
    "statement ran to exactly one line, and on 10 August 1927 an envelope arrived at "
    "Bóthar na gCloch addressed simply to ‘the Tánaiste, le cúnamh Dé.’"
)

# ---------------- lexicon ----------------
for key in sorted((k for k in lex if not k.startswith("_")), key=len, reverse=True):
    raw = raw.replace(key, lex[key])

# ---------------- years, ranges, ordinals, numbers ----------------
_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


def under100(n):
    return _ONES[n] if n < 20 else f"{_TENS[n // 10]}-{_ONES[n % 10]}"


def under1000(n):
    if n < 100:
        return under100(n)
    h = f"{_ONES[n // 100]} hundred"
    r = n % 100
    return h if r == 0 else f"{h} and {under100(r)}"


def year_words(y):
    if 1900 <= y <= 1999:
        rest = y - 1900
        if rest == 0:
            return "nineteen hundred"
        if rest < 10:
            return f"nineteen oh {_ONES[rest]}"
        return f"nineteen {under100(rest)}"
    if 2000 <= y <= 2099:
        rest = y - 2000
        if rest == 0:
            return "two thousand"
        if rest < 10:
            return f"two thousand and {_ONES[rest]}"
        return f"two thousand and {under100(rest)}"
    return under1000(y)


def num_words(n):
    if n >= 1_000_000:
        m, r = divmod(n, 1_000_000)
        return f"{num_words(m)} million" + (f" {num_words(r)}" if r else "")
    if n >= 1000:
        t, r = divmod(n, 1000)
        return f"{under1000(t)} thousand" + (f" {num_words(r)}" if r else "")
    return under1000(n)


_ORD_SPECIAL = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth",
                9: "ninth", 12: "twelfth"}


def ordinal_words(n):
    if n in _ORD_SPECIAL:
        return _ORD_SPECIAL[n]
    if n % 100 in (11, 12, 13):
        return under100(n) + "th"
    return under100(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


# dates: "12 July 1921" / "10 August 1927" (also tolerate 12th July 1921)
def date_repl(m):
    day, mon, yr = int(m.group(1)), m.group(2), int(m.group(3))
    return f"the {ordinal_words(day)} of {mon} {year_words(yr)}"


raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\s+((?:19|20)\d{2})\b",
             date_repl, raw)
# year ranges then standalone years
raw = re.sub(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|\d{2})\b",
             lambda m: f"{year_words(int(m.group(1)))} to {year_words(int(m.group(2))) if len(m.group(2)) == 4 else under100(int(m.group(2)))}",
             raw)
raw = re.sub(r"\b((?:19|20)\d{2})\b", lambda m: year_words(int(m.group(1))), raw)
# currency and big numbers
raw = re.sub(r"£(\d+) million", lambda m: f"{num_words(int(m.group(1)))} million pounds", raw)
raw = re.sub(r"\b(\d{1,3}(?:,\d{3})+|\d{3,})\b", lambda m: num_words(int(m.group(1).replace(",", ""))), raw)

# ---------------- orphan merge + sentence split with quote tracking ----------------
paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
PLACEHOLDER = "\ue000"
ABBR = ["Mr", "Mrs", "Ms", "Dr", "Prof", "St", "Sr", "Jr", "Col", "Gen", "Lt", "Cpt",
        "Capt", "Sgt", "Rev", "Hon", "Sinn", "Vol", "No"]


def protect(text):
    for a in ABBR:
        text = text.replace(a + ".", a + PLACEHOLDER)
    text = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", r"\1" + PLACEHOLDER, text)
    return text


flat: list[dict] = []
for pid, para in enumerate(paras):
    guarded = protect(para)
    pieces = re.split(r"(?<=[.!?])\s+", guarded)
    pieces = [p.replace(PLACEHOLDER, ".").strip() for p in pieces]
    pieces = [p for p in pieces if p]
    # merge orphans: fragment without terminal punctuation joins the next piece
    merged = []
    buf = ""
    for p in pieces:
        buf = (buf + " " + p).strip() if buf else p
        if re.search(r"[.!?][”’\"']?$", buf) and len(buf.split()) >= 3:
            merged.append(buf)
            buf = ""
        else:
            buf = buf  # keep accumulating
    if buf:
        if merged:
            merged[-1] = merged[-1] + " " + buf
        else:
            merged.append(buf)
    for s in merged:
        in_quote = ("‘" in s) or ("’ " in s and s.rstrip().endswith(("’", "'"))) or ("chance,’" in s)
        in_quote = "‘" in s
        flat.append({"text": s, "para": pid, "quote": in_quote})

# propagate/open quote detection: ’ that is NOT a letter apostrophe (didn’t)
# i.e. a close-quote after punctuation/space, or a sentence-initial/opening ‘
for i in range(1, len(flat)):
    if not flat[i]["quote"]:
        t = flat[i]["text"]
        if re.search(r"(?<![A-Za-z])’", t):
            flat[i]["quote"] = True

print(f"{len(paras)} paragraphs, {len(flat)} sentences")
for s in flat:
    print(("Q " if s["quote"] else "  ") + s["text"][:110])

payload = {"sents": flat}
stage_dir = root / "scratch" / "kaggle_fish_stress_lab" / "kernel"
stage_dir.mkdir(parents=True, exist_ok=True)

kernel_code = f'''#!/usr/bin/env python3
"""Stress test: locked recipe (dual-ref, years/ordinals/numbers expanded)."""
import glob, json, os, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

WORK = Path("/workspace"); WORK.mkdir(exist_ok=True)
OUT = Path("/kaggle/working/out")
(OUT / "wavs").mkdir(parents=True, exist_ok=True)

hits = sorted(Path("/kaggle/input").rglob("refs.json"))
if not hits:
    print("INPUT MOUNTS:", [str(p) for p in Path("/kaggle/input").rglob("*")][:40], flush=True)
    raise SystemExit("refs dataset not mounted")
REFDIR = hits[0].parent
REFS = json.loads((REFDIR / "refs.json").read_text(encoding="utf-8"))
PAYLOAD = json.loads({repr(json.dumps(payload, ensure_ascii=False))})
sents = PAYLOAD["sents"]
print(f"{{len(sents)}} sentences", flush=True)

subprocess.run(["apt-get", "update", "-q"], check=False)
subprocess.run(["apt-get", "install", "-y", "-q", "portaudio19-dev", "libsox-dev", "libsndfile1", "ffmpeg"], check=False)
subprocess.run(["git", "clone", "-q", "https://github.com/fishaudio/fish-speech.git", "/workspace/fish-speech"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "/workspace/fish-speech"], check=True)
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
assert src.count("CODEC_DEVICE or device") == 4
inf_path.write_text(src)

import torch

assert torch.cuda.is_available()
DEVICE = "cuda:0"
CODEC_DEVICE = "cuda:1" if torch.cuda.device_count() > 1 else DEVICE
os.environ["FISH_CODEC_DEVICE"] = CODEC_DEVICE
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

sys.path.insert(0, "/workspace/fish-speech")
from fish_speech.models.text2semantic.inference import (
    decode_to_audio, encode_audio, generate_long, init_model, load_codec_model,
)

precision = torch.half
model, decode_one_token = init_model("/workspace/s2-pro", DEVICE, precision, compile=False)
with torch.device(DEVICE):
    model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                       dtype=next(model.parameters()).dtype)
codec = load_codec_model("/workspace/s2-pro/codec.pth", CODEC_DEVICE, precision)
REFS_READY = {{}}
def get_ref_tokens(ref_key):
    if ref_key not in REFS_READY:
        wav_path = REFDIR / f"{{ref_key}}.wav"
        REFS_READY[ref_key] = [encode_audio(str(wav_path), codec, CODEC_DEVICE).cpu()]
    return REFS_READY[ref_key]

torch.manual_seed(42); torch.cuda.manual_seed(42)


def health(a):
    rms = float(np.sqrt(np.mean(a ** 2)))
    d = float(np.abs(np.diff(a)).mean())
    peak = float(np.abs(a).max())
    return 0.005 < rms < 0.5 and d > 0.001 and peak > 0.05, rms, d


def synth(text, ref_key, temp, seed):
    torch.manual_seed(seed); torch.cuda.manual_seed(seed)
    ref_tokens = get_ref_tokens(ref_key)
    gen = generate_long(
        model=model, device=DEVICE, decode_one_token=decode_one_token,
        text=text, num_samples=1, max_new_tokens=0, top_p=0.9, top_k=30,
        temperature=temp, compile=False, iterative_prompt=True, chunk_length=300,
        prompt_text=[REFS[ref_key + "_text"]], prompt_tokens=ref_tokens,
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
    return wav


t0 = time.time()
audio_secs = 0.0
n_fail = 0
manifest = []
for i, item in enumerate(sents, 1):
    ref_key = "crop_expressive_tail" if item["quote"] else "cillian_irish"
    temp = 0.85
    c_t0 = time.time()
    ok = False
    for attempt, seed in enumerate((42, 43, 44), 1):
        try:
            wav = synth(item["text"], ref_key, temp, seed)
            if wav is None or len(wav) < 0.6 * codec.sample_rate:
                raise RuntimeError("no/short audio")
            h_ok, rms, d = health(wav)
            if not h_ok:
                raise RuntimeError(f"health rms={{rms:.4f}} diff={{d:.5f}}")
            if attempt > 1:
                print(f"  [{{i}}] re-roll attempt {{attempt}} succeeded", flush=True)
            sf.write(str(OUT / "wavs" / f"{{i:04d}}.wav"), wav, codec.sample_rate)
            secs = len(wav) / codec.sample_rate
            audio_secs += secs
            manifest.append({{"idx": i, "para": item["para"], "quote": item["quote"],
                              "ref": ref_key, "seed": seed, "sec": round(secs, 2), "ok": True}})
            ok = True
            print(f"[{{i}}/{{len(sents)}}] {{'Q' if item['quote'] else ' '}} {{secs:.1f}}s ({{time.time()-c_t0:.0f}}s)", flush=True)
            break
        except Exception as e:
            if attempt == 3:
                n_fail += 1
                manifest.append({{"idx": i, "para": item["para"], "ok": False, "err": str(e)[:200]}})
                print(f"[{{i}}/{{len(sents)}}] FAILED after re-rolls: {{str(e)[:150]}}", flush=True)
    (OUT / "manifest.json").write_text(json.dumps({{"elapsed": round(time.time()-t0, 1), "audio_secs": round(audio_secs, 1), "n_fail": n_fail, "sents": manifest}}, indent=1))

gen_wall = time.time() - t0
rtf = gen_wall / max(audio_secs, 1.0)
print(f"GEN DONE: {{audio_secs:.0f}}s audio in {{gen_wall:.0f}}s -> RTF {{rtf:.2f}}x ({{n_fail}} failed)", flush=True)

# assemble with silence trim + natural gaps
SR = codec.sample_rate
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


pieces = []
prev_para = None
for item in manifest:
    if not item.get("ok"):
        continue
    p = OUT / "wavs" / f"{{item['idx']:04d}}.wav"
    if not p.exists():
        continue
    w = load_trim(p)
    if prev_para is not None:
        gap = 0.50 if item["para"] != prev_para else 0.18
        pieces.append(np.zeros(int(gap * SR), dtype=np.float32))
    pieces.append(w)
    prev_para = item["para"]
full = np.concatenate(pieces)
sf.write("/workspace/stress_raw.wav", full, SR)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/workspace/stress_raw.wav",
                "-af", "equalizer=f=220:width_type=o:width=1.2:g=1.0,highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", "192k", str(OUT / "stress_test_locked_recipe.mp3")], check=True)
a, sra = sf.read("/workspace/stress_raw.wav", dtype="float32")
if a.ndim > 1:
    a = a.mean(axis=1)
ok, rms, d = health(a)
total = len(a) / sra
print(f"FINAL: {{total:.1f}}s rms={{rms:.4f}} diff={{d:.5f}} pass={{ok}}")
print(f"MANIFEST: rtf={{rtf:.2f}} n_fail={{n_fail}}", flush=True)
if not ok:
    (OUT / "stress_test_locked_recipe.mp3").rename(OUT / "stress_test_locked_recipe_UNHEALTHY.mp3")
print("STRESS COMPLETE", flush=True)
'''

run_file = stage_dir / "run_kernel.py"
run_file.write_text(kernel_code, encoding="utf-8")
print(f"Written {run_file} ({run_file.stat().st_size:,} bytes)")

meta = {
    "id": "davedavedavedavenm/fish-stress-lab",
    "title": "fish-stress-lab",
    "code_file": "run_kernel.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,
    "machine_shape": "NvidiaTeslaT4",
    "dataset_sources": ["davedavedavedavenm/cillian-refs"],
    "competition_sources": [],
    "kernel_sources": [],
    "model_sources": [],
}
(stage_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("metadata written")
