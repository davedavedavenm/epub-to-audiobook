"""Kaggle GPU kernel: convert EPUB chapters via the repo's CHATTERBOX engine +
the full fixed preprocessing pipeline. Runs the real chatterbox/server.py and
scripts/convert_book.py, so this is a faithful test of the shipped setup.

Chatterbox is the chosen full-book engine (Dave, 2026-07-10 — "really really
good"); on CPU it's ~days/book, so this renders it on a free T4 GPU instead.

Reusable: change START/END/VOICE below and re-push. Outputs -> /kaggle/working.
"""
import os, sys, time, glob, shutil, subprocess

# ---- knobs -----------------------------------------------------------------
REPO   = "https://github.com/davedavedavenm/epub-to-audiobook.git"
BRANCH = "master"
VOICE  = "uk_male_minter"     # "Arthur" — the approved voice
START  = 1
END    = 0                    # 0 = to end of book
# ---------------------------------------------------------------------------

WORK, REPO_DIR, OUT = "/kaggle/working", "/kaggle/working/repo", "/kaggle/working/out"


def sh(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


# 1. deps. Chatterbox pins torch==2.6.0; install its cu124 build FIRST (T4 is
#    sm_75, well-supported by cu124) so chatterbox-tts finds it satisfied and
#    doesn't re-resolve to a CPU/wrong-CUDA wheel (the class of bug that made
#    TADA silently run on CPU). setuptools<81: perth watermarker imports the
#    removed pkg_resources.
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "torch==2.6.0", "torchaudio==2.6.0",
                "--index-url", "https://download.pytorch.org/whl/cu124"], check=False)
sh([sys.executable, "-m", "pip", "install", "-q",
    "chatterbox-tts", "setuptools<81", "fastapi", "uvicorn", "soundfile",
    "num2words", "beautifulsoup4", "lxml", "requests", "faster-whisper"])

# 2. repo (server.py, convert_book.py, voice refs, fixed preprocessing)
if not os.path.isdir(REPO_DIR):
    sh(["git", "clone", "--depth", "1", "-b", BRANCH, REPO, REPO_DIR])
sh(["git", "-C", REPO_DIR, "log", "--oneline", "-1"])
os.makedirs(OUT, exist_ok=True)

# 3. locate the attached epub
epubs = glob.glob("/kaggle/input/**/*.epub", recursive=True)
assert epubs, "no .epub under /kaggle/input — attach the epub dataset"
EPUB = epubs[0]
print("epub:", EPUB, flush=True)

# 4. start the real Chatterbox server (lazy model load on first request)
env = dict(os.environ)
env["VOICES_DIR"] = f"{REPO_DIR}/chatterbox/voices"
env["HF_HOME"] = "/tmp/hf"     # keep the model cache OUT of /kaggle/working
LOG = f"{WORK}/server.log"
srv = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8004"],
    cwd=f"{REPO_DIR}/chatterbox", env=env,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

import requests
healthy = False
for i in range(60):
    time.sleep(5)
    if srv.poll() is not None:
        print("SERVER EXITED early — log tail:", flush=True)
        print(open(LOG).read()[-3000:], flush=True)
        raise SystemExit("chatterbox server died on startup")
    try:
        h = requests.get("http://127.0.0.1:8004/health", timeout=5).json()
        print(f"health[{i}]", h, flush=True)
        if h.get("status") == "ok":
            healthy = True
            print("CUDA available:", h.get("cuda_available"), flush=True)
            assert h.get("cuda_available"), "GPU NOT visible to torch — refusing CPU run"
            break
    except Exception as e:
        print(f"waiting[{i}]", str(e)[:70], flush=True)
assert healthy, "server never became healthy"

# 5. convert. --chunk-chars 600, --qa base. Full preprocessing (modern engine
#    contract). Per-chapter MP3s land in OUT as each finishes.
args = [sys.executable, f"{REPO_DIR}/scripts/convert_book.py",
        "--epub", EPUB, "--engine-url", "http://127.0.0.1:8004/v1",
        "--voice", VOICE, "--out", OUT, "--start", str(START),
        "--chunk-chars", "600", "--qa", "--qa-model", "base"]
if END and int(END) > 0:
    args += ["--end", str(END)]
t0 = time.time()
sh(args)
print(f"conversion wall time: {time.time()-t0:.0f}s", flush=True)

# 6. surface outputs
for f in sorted(glob.glob(f"{OUT}/*.mp3")) + sorted(glob.glob(f"{OUT}/*.json")):
    shutil.copy(f, os.path.join(WORK, os.path.basename(f)))
    print("OUTPUT:", os.path.basename(f), os.path.getsize(f), "bytes", flush=True)
print("ALL DONE", flush=True)
