#!/usr/bin/env python3
"""Kaggle GPU kernel: convert EPUB chapters with the CosyVoice 3 engine via the
repo's cosyvoice/server.py + scripts/convert_book.py — the faithful full-book
path (same contract as run_chatterbox.py / run.py).

CosyVoice needs Python 3.10 + pinned deps (unpinned on 3.12 => multilingual
babble; see TTS-LANDSCAPE §Verified). So the SERVER runs in a uv-built 3.10
venv, while convert_book.py runs in Kaggle's base python and just POSTs to it
over HTTP — the two decouple cleanly through the OpenAI-compatible endpoint.

Reusable: change START/END/VOICE below and re-push. Per-chapter MP3s -> /kaggle/working.
"""
import glob
import os
import shutil
import subprocess
import sys
import time

# ---- knobs -----------------------------------------------------------------
REPO = "https://github.com/davedavedavenm/epub-to-audiobook.git"
BRANCH = "master"
VOICE = "uk_male_minter"      # ref stem; the server also accepts *_cosyvoice
START = 1
END = 0                        # 0 = to end of book
PROGRESS_URL = ""
# ---------------------------------------------------------------------------

os.environ["USE_TF"] = "0"     # keep transformers off Kaggle's mismatched TF
os.environ["USE_TENSORFLOW"] = "0"

WORK = "/kaggle/working"
SCRATCH = "/tmp/cv3"
REPO_DIR = f"{WORK}/repo"
CV_DIR = f"{SCRATCH}/CosyVoice"
VENV = f"{SCRATCH}/venv"
PY = f"{VENV}/bin/python"
MODEL_DIR = f"{CV_DIR}/pretrained_models/Fun-CosyVoice3-0.5B"
OUT = f"{WORK}/out"
T0 = time.time()


def sh(cmd, check=True, **kw):
    print("+", cmd if isinstance(cmd, str) else " ".join(cmd), flush=True)
    # string commands use the shell (they contain && / pipes / --flags);
    # list commands run directly.
    return subprocess.run(cmd, check=check, shell=isinstance(cmd, str), **kw)


def stage(m):
    print(f"\n{'='*70}\n[{time.time()-T0:6.0f}s] {m}\n{'='*70}", flush=True)


os.makedirs(OUT, exist_ok=True)
os.makedirs(SCRATCH, exist_ok=True)

# 1. system deps + both repos ------------------------------------------------
stage("System deps + clone repos")
sh("apt-get update -qq && apt-get install -y -qq sox libsox-dev ffmpeg", check=False)
if not os.path.isdir(REPO_DIR):
    sh(["git", "clone", "--depth", "1", "-b", BRANCH, REPO, REPO_DIR])
if not os.path.isdir(CV_DIR):
    sh(["git", "clone", "--recursive",
        "https://github.com/FunAudioLLM/CosyVoice.git", CV_DIR])

# 2. py3.10 venv + pinned CosyVoice deps + server deps -----------------------
stage("Python 3.10 venv + pinned deps (the load-bearing part)")
sh("pip install -q uv")
sh("uv python install 3.10")
sh(f"uv venv --python 3.10 --seed {VENV}")
with open(f"{SCRATCH}/constraints.txt", "w") as f:
    f.write("setuptools<81\n")
os.environ["PIP_CONSTRAINT"] = f"{SCRATCH}/constraints.txt"
sh(f"{PY} -m pip install -q 'setuptools<81' wheel")
# T4 is sm_75 -> cu121 build of the pinned torch
sh(f"{PY} -m pip install -q torch==2.3.1 torchaudio==2.3.1 numpy==1.26.4 "
   "--extra-index-url https://download.pytorch.org/whl/cu121")
sh(f"{PY} -m pip install -r requirements.txt", cwd=CV_DIR)
# server.py deps (fastapi/uvicorn/soundfile) + faster-whisper for ref transcript
sh(f"{PY} -m pip install -q fastapi uvicorn soundfile faster-whisper huggingface_hub")

# 3. model download ----------------------------------------------------------
stage("Download Fun-CosyVoice3-0.5B-2512")
dl = f"{SCRATCH}/dl.py"
with open(dl, "w") as f:
    f.write('from huggingface_hub import snapshot_download\n'
            f'snapshot_download("FunAudioLLM/Fun-CosyVoice3-0.5B-2512",'
            f' local_dir="{MODEL_DIR}", max_workers=4)\nprint("model ready")\n')
sh(f"{PY} {dl}")

# 4. drop the repo's server.py + voices into the CosyVoice tree --------------
stage("Stage server.py + voices")
shutil.copy(f"{REPO_DIR}/cosyvoice/server.py", f"{CV_DIR}/server.py")
VOICES_DIR = f"{REPO_DIR}/chatterbox/voices"    # reuse the same UK ref wavs

# 5. start the CosyVoice server in the venv ----------------------------------
stage("Start cosyvoice/server.py (venv, GPU)")
senv = dict(os.environ)
senv["VOICES_DIR"] = VOICES_DIR
senv["COSYVOICE_MODEL_DIR"] = MODEL_DIR
senv["MATCHA_PATH"] = f"{CV_DIR}/third_party/Matcha-TTS"
LOG = f"{WORK}/server.log"
srv = subprocess.Popen(
    [PY, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8004"],
    cwd=CV_DIR, env=senv, stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

import urllib.request
import json as _json
healthy = False
for i in range(120):                               # model load is slow (~1 min)
    time.sleep(5)
    if srv.poll() is not None:
        print("SERVER DIED — log tail:\n", open(LOG).read()[-3000:], flush=True)
        raise SystemExit("cosyvoice server failed to start")
    try:
        h = _json.loads(urllib.request.urlopen("http://127.0.0.1:8004/health", timeout=5).read())
        print(f"health[{i}]", h, flush=True)
        if h.get("status") == "ok":
            assert h.get("device") == "cuda", "server not on GPU — refusing CPU run"
            healthy = True
            break
    except Exception as e:
        print(f"waiting[{i}] {str(e)[:60]}", flush=True)
assert healthy, "server never became healthy"

# 5b. SMOKE TEST — synthesise one short sentence before committing to the book.
#     /health only proves the process is up; the first real request is what
#     loads Whisper for the reference transcript and runs the model. A render
#     died 20 min in on exactly that gap (bf6d5335, 2026-07-24). Fail in 30s
#     with a clear message instead.
stage("Smoke test: one sentence through /v1/audio/speech")
_req = urllib.request.Request(
    "http://127.0.0.1:8004/v1/audio/speech",
    data=_json.dumps({"model": "tts-1", "input": "Testing one two three.",
                      "voice": VOICE, "response_format": "wav"}).encode(),
    headers={"Content-Type": "application/json"})
try:
    _wav = urllib.request.urlopen(_req, timeout=900).read()
except Exception as e:
    print("SMOKE TEST FAILED — server log tail:\n", open(LOG).read()[-3000:], flush=True)
    raise SystemExit(f"smoke test failed: {e}")
if len(_wav) < 8000 or _wav[:4] != b"RIFF":
    print("server log tail:\n", open(LOG).read()[-2000:], flush=True)
    raise SystemExit(f"smoke test returned {len(_wav)} bytes, not a usable WAV")
print(f"smoke test OK: {len(_wav)} bytes of WAV", flush=True)

# 6. convert (base python + its deps) ----------------------------------------
stage("Install convert_book deps (base python) + convert")
sh([sys.executable, "-m", "pip", "install", "-q",
    "ebooklib", "beautifulsoup4", "lxml", "num2words", "requests",
    "soundfile", "openai-whisper"])
epubs = glob.glob("/kaggle/input/**/*.epub", recursive=True)
assert epubs, "no .epub under /kaggle/input — attach the epub dataset"
print("epub:", epubs[0], flush=True)
args = [sys.executable, f"{REPO_DIR}/scripts/convert_book.py",
        "--epub", epubs[0], "--engine-url", "http://127.0.0.1:8004/v1",
        "--voice", VOICE, "--out", OUT, "--start", str(START),
        "--chunk-chars", "300", "--qa", "--qa-model", "base"]
if END and int(END) > 0:
    args += ["--end", str(END)]
if PROGRESS_URL:
    args += ["--progress-url", PROGRESS_URL]
t1 = time.time()
sh(args)
print(f"conversion wall: {time.time()-t1:.0f}s", flush=True)

# 7. surface outputs ---------------------------------------------------------
for f in sorted(glob.glob(f"{OUT}/*.mp3")) + sorted(glob.glob(f"{OUT}/*.json")):
    shutil.copy(f, os.path.join(WORK, os.path.basename(f)))
    print("OUTPUT:", os.path.basename(f), os.path.getsize(f), "bytes", flush=True)
print(f"ALL DONE in {time.time()-T0:.0f}s", flush=True)
