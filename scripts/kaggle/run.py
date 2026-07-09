"""Kaggle GPU kernel: convert EPUB chapters to audiobook via the repo's TADA
engine + the FULL fixed preprocessing pipeline. Runs the real tada/server.py
and scripts/convert_book.py so this is a faithful test of the shipped fixes,
not a bespoke path.

Reusable: change START/END/VOICE/REPO_BRANCH below (or the attached epub
dataset) and re-push. Outputs land in /kaggle/working as NNN.mp3.
"""
import os, sys, time, json, glob, shutil, subprocess

# ---- knobs -----------------------------------------------------------------
REPO   = "https://github.com/davedavedavenm/epub-to-audiobook.git"
BRANCH = "master"
VOICE  = "uk_male_minter_tada"     # "Arthur" — same voice the user is evaluating
START  = 1
END    = 2
# ---------------------------------------------------------------------------

WORK, REPO_DIR, OUT = "/kaggle/working", "/kaggle/working/repo", "/kaggle/working/out"

# Kaggle images ship TensorFlow; transformers (pulled by hume-tada) eagerly
# imports it, and Kaggle's TF/protobuf are mismatched → "cannot import name
# 'runtime_version' from google.protobuf" kills the server (run failed
# 2026-07-08). Tell transformers this is a torch-only environment so it never
# touches TF. USE_TF=0 propagates to the server subprocess via os.environ.
os.environ["USE_TF"] = "0"
os.environ["USE_TENSORFLOW"] = "0"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"


def sh(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


# 1. deps — Kaggle's torch is already CUDA-enabled; do NOT reinstall it.
#    Also remove the preinstalled TensorFlow so transformers can't import it
#    even if USE_TF is ignored (belt-and-suspenders; non-fatal if absent).
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y",
                "tensorflow", "tensorflow-cpu", "keras"], check=False)
sh([sys.executable, "-m", "pip", "install", "-q",
    "hume-tada", "fastapi", "uvicorn", "soundfile", "num2words",
    "beautifulsoup4", "lxml", "requests", "faster-whisper"])

# 2. repo (server.py, convert_book.py, voice refs, fixed preprocessing)
if not os.path.isdir(REPO_DIR):
    sh(["git", "clone", "--depth", "1", "-b", BRANCH, REPO, REPO_DIR])
print("repo HEAD:", flush=True)
sh(["git", "-C", REPO_DIR, "log", "--oneline", "-1"])

os.makedirs(OUT, exist_ok=True)

# 3. locate the attached epub
epubs = glob.glob("/kaggle/input/**/*.epub", recursive=True)
assert epubs, "no .epub found under /kaggle/input — attach the epub dataset"
EPUB = epubs[0]
print("epub:", EPUB, flush=True)

# 4. start the real TADA server (lazy model load on first request)
env = dict(os.environ)
env["VOICES_DIR"] = f"{REPO_DIR}/tada/voices"
# HF cache OUTSIDE /kaggle/working — the ~5GB model must NOT land in the kernel
# output (it bloats + truncates the real outputs and hides server.log; that's
# why v2/v3 output was just the hf cache with no mp3s/log).
env["HF_HOME"] = "/tmp/hf"
env["TADA_TRIM_LEADIN"] = "1"      # first-word cold-start fix on
LOG = f"{WORK}/server.log"
srv = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8005"],
    cwd=f"{REPO_DIR}/tada", env=env,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

import requests
healthy = False
for i in range(60):
    time.sleep(5)
    if srv.poll() is not None:
        print("SERVER EXITED early — log tail:", flush=True)
        print(open(f"{WORK}/server.log").read()[-3000:], flush=True)
        raise SystemExit("tada server died on startup")
    try:
        h = requests.get("http://127.0.0.1:8005/health", timeout=5).json()
        print(f"health[{i}]", h, flush=True)
        if h.get("status") == "ok":
            healthy = True
            print("CUDA available:", h.get("cuda_available"), flush=True)
            assert h.get("cuda_available"), "GPU NOT visible to torch — refusing CPU run"
            break
    except Exception as e:
        print(f"waiting[{i}]", str(e)[:70], flush=True)
assert healthy, "server never became healthy"

# 5. convert with the FULL post-fix pipeline: clean WAV concat, --denoise
#    (afftdn, knocks down TADA hiss), and --qa (local Whisper ASR verification
#    → qa_report.json). No LLM key here, so pronunciation uses the seed dict
#    (Cupertino/Beijing/McDonald's/etc) — enough to validate the reported names.
t0 = time.time()
sh([sys.executable, f"{REPO_DIR}/scripts/convert_book.py",
    "--epub", EPUB, "--engine-url", "http://127.0.0.1:8005/v1",
    "--voice", VOICE, "--out", OUT, "--start", str(START), "--end", str(END),
    "--denoise", "--qa", "--qa-model", "base"])
print(f"conversion wall time: {time.time()-t0:.0f}s", flush=True)

# 6. surface outputs + QA report in /kaggle/working (kernel output root)
for f in sorted(glob.glob(f"{OUT}/*.mp3")) + sorted(glob.glob(f"{OUT}/*.json")):
    dst = os.path.join(WORK, os.path.basename(f))
    shutil.copy(f, dst)
    print("OUTPUT:", os.path.basename(f), os.path.getsize(f), "bytes", flush=True)
print("ALL DONE", flush=True)
