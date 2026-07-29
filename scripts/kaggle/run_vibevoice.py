#!/usr/bin/env python3
"""Kaggle P100 full-book kernel for VibeVoice 1.5B.

The app checkout is pinned to APP_REF by webapp/kaggle_render.py. The model
runtime is the audited community fork because Microsoft's official TTS
inference is disabled; weights remain the official microsoft/VibeVoice-1.5B.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import requests

REPO = "https://github.com/davedavedavenm/epub-to-audiobook.git"
APP_REF = ""
VOICE = "uk_male_minter_vibevoice"
START = 1
END = 0
PROGRESS_URL = ""
RUNTIME_REPO = "https://github.com/vibevoice-community/VibeVoice.git"
RUNTIME_SHA = "07cb79feadd2d3fd7f47530d4c964a12857936a0"

WORK = "/kaggle/working"
REPO_DIR = f"{WORK}/repo"
RUNTIME_DIR = "/tmp/VibeVoice"
OUT = f"{WORK}/out"
LOG = f"{WORK}/server.log"
os.environ.update({"USE_TF": "0", "USE_TENSORFLOW": "0",
                   "TRANSCRIPTS_DIR": f"{WORK}/transcripts"})


def sh(cmd, **kwargs):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


assert re.fullmatch(r"[0-9a-fA-F]{40}", APP_REF), "APP_REF must be the deployed full commit"
sh(["apt-get", "update"])
sh(["apt-get", "install", "-y", "git-lfs"])
sh(["git", "lfs", "install"])
sh(["git", "clone", "--filter=blob:none", "--no-checkout", REPO, REPO_DIR])
sh(["git", "-C", REPO_DIR, "fetch", "origin", APP_REF])
sh(["git", "-C", REPO_DIR, "checkout", "--detach", APP_REF])
assert subprocess.check_output(["git", "-C", REPO_DIR, "rev-parse", "HEAD"], text=True).strip() == APP_REF
sh(["git", "-C", REPO_DIR, "lfs", "pull", "--include",
    "chatterbox/voices/uk_male_minter.wav"])
ref = f"{REPO_DIR}/chatterbox/voices/uk_male_minter.wav"
raw = open(ref, "rb").read()
assert raw[:4] == b"RIFF", "Arthur reference is a Git-LFS pointer, not WAV"
assert len(raw) == 864182, f"Arthur reference has wrong size: {len(raw)}"
assert hashlib.sha256(raw).hexdigest() == "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"

sh(["git", "clone", RUNTIME_REPO, RUNTIME_DIR])
sh(["git", "-C", RUNTIME_DIR, "checkout", "--detach", RUNTIME_SHA])
assert subprocess.check_output(["git", "-C", RUNTIME_DIR, "rev-parse", "HEAD"], text=True).strip() == RUNTIME_SHA

# P100 (sm_60) needs the cu121 wheel set used by the accepted audition; bf16
# and FlashAttention are not supported there, so the server pins fp16 + SDPA.
sh([sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
    "torch==2.3.1", "torchvision==0.18.1", "torchaudio==2.3.1",
    "--index-url", "https://download.pytorch.org/whl/cu121"])
sh([sys.executable, "-m", "pip", "install", "-q", "numpy==1.26.4"])
sh([sys.executable, "-m", "pip", "install", "-q", "-e", RUNTIME_DIR])
sh([sys.executable, "-m", "pip", "install", "-q", "fastapi", "uvicorn", "soundfile",
    "ebooklib", "beautifulsoup4", "lxml", "num2words", "requests", "faster-whisper"])

epubs = glob.glob("/kaggle/input/**/*.epub", recursive=True)
assert epubs, "no .epub under /kaggle/input"
os.makedirs(OUT, exist_ok=True)
env = dict(os.environ)
env.update({"VOICES_DIR": f"{REPO_DIR}/chatterbox/voices", "HF_HOME": "/tmp/hf",
            "VIBEVOICE_DTYPE": "float16", "PYTHONPATH": RUNTIME_DIR})
srv = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8010"],
    cwd=f"{REPO_DIR}/vibevoice", env=env,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

for i in range(120):
    time.sleep(5)
    if srv.poll() is not None:
        raise SystemExit("VibeVoice server exited:\n" + open(LOG).read()[-4000:])
    try:
        h = requests.get("http://127.0.0.1:8010/health", timeout=5)
        if h.status_code == 200 and h.json().get("device") == "cuda":
            break
    except Exception:
        pass
else:
    raise SystemExit("VibeVoice server never became healthy")

# A real request is the model-load check; /health intentionally stays cheap.
r = requests.post("http://127.0.0.1:8010/v1/audio/speech",
                  json={"input": "Testing one two three.", "voice": VOICE,
                        "response_format": "wav", "seed": 12345}, timeout=1800)
r.raise_for_status()
assert r.content[:4] == b"RIFF" and len(r.content) > 8000

args = [sys.executable, f"{REPO_DIR}/scripts/convert_book.py",
        "--epub", epubs[0], "--engine-url", "http://127.0.0.1:8010/v1",
        "--voice", VOICE, "--out", OUT, "--start", str(START),
        "--chunk-chars", "1000000", "--request-timeout", "21600",
        "--job-id", f"kaggle-vibevoice-{START}-{END}",
        "--qa", "--qa-model", "base"]
if END:
    args += ["--end", str(END)]
if PROGRESS_URL:
    args += ["--progress-url", PROGRESS_URL]
sh(args)
qa = json.load(open(f"{OUT}/qa_report.json", encoding="utf-8"))
assert qa.get("chapters"), "VibeVoice render produced no usable QA report"
for path in sorted(glob.glob(f"{OUT}/*.mp3")) + sorted(glob.glob(f"{OUT}/*.json")):
    shutil.copy(path, os.path.join(WORK, os.path.basename(path)))
    print("OUTPUT", os.path.basename(path), os.path.getsize(path), flush=True)
