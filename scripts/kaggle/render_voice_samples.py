"""Kaggle GPU kernel: render the voice-audition sample for EVERY chatterbox voice.

Chatterbox on CPU takes ~3.5 min per sample — 23 voices is over an hour and it
saturates the homelab box. On a free T4 it's seconds per voice. The samples are a
fixed, one-off set (same text, same voices), so render them once on the GPU and
pull the MP3s down; they're then cached permanently and every click is instant.

Also renders a 1997 A/B pair (raw "1997" vs spelled "nineteen ninety-seven") so
the year-pronunciation question can be settled by ear rather than by argument —
the repo records that year-spelling HURT modern engines, but that finding is
being challenged.

Outputs -> /kaggle/working/samples/<voice_id>.mp3  (+ ab_1997_raw/spelled.mp3)
"""
import os, sys, time, glob, shutil, subprocess

REPO   = "https://github.com/davedavedavenm/epub-to-audiobook.git"
BRANCH = "master"

WORK, REPO_DIR, OUT = "/kaggle/working", "/kaggle/working/repo", "/kaggle/working/samples"

os.environ["USE_TF"] = "0"
os.environ["USE_TENSORFLOW"] = "0"


def sh(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, check=True, **kw)


# 1. deps — same pinned cu124 stack the book renderer uses (torchvision must match
#    torch or transformers dies on "torchvision::nms does not exist").
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y",
                "tensorflow", "tensorflow-cpu", "keras"], check=False)
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "torch==2.6.0", "torchvision==0.21.0", "torchaudio==2.6.0",
                "--index-url", "https://download.pytorch.org/whl/cu124"], check=False)
sh([sys.executable, "-m", "pip", "install", "-q",
    "chatterbox-tts", "setuptools<81", "fastapi", "uvicorn", "soundfile",
    "num2words", "beautifulsoup4", "lxml", "requests"])

# 2. repo (voice refs + the SHARED sample text + the real preprocessing)
if not os.path.isdir(REPO_DIR):
    sh(["git", "clone", "--depth", "1", "-b", BRANCH, REPO, REPO_DIR])
sh(["git", "-C", REPO_DIR, "log", "--oneline", "-1"])
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f"{REPO_DIR}/webapp")

from voice_sample import sample_text_for, SAMPLE_TEXT, SAMPLE_LEXICON   # noqa: E402
from tts_preprocess import normalize_text_for_tts                        # noqa: E402

TEXT = sample_text_for("chatterbox")     # identical to what the web app sends
print("sample words:", len(TEXT.split()), flush=True)

# 3. start the real chatterbox server on the GPU
env = dict(os.environ)
env["VOICES_DIR"] = f"{REPO_DIR}/chatterbox/voices"
env["HF_HOME"] = "/tmp/hf"
LOG = f"{WORK}/server.log"
srv = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8004"],
    cwd=f"{REPO_DIR}/chatterbox", env=env,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT)

import requests  # noqa: E402
healthy = False
for i in range(60):
    time.sleep(5)
    if srv.poll() is not None:
        print(open(LOG).read()[-3000:], flush=True)
        raise SystemExit("chatterbox server died on startup")
    try:
        h = requests.get("http://127.0.0.1:8004/health", timeout=5).json()
        if h.get("status") == "ok":
            assert h.get("cuda_available"), "GPU NOT visible — refusing a CPU run"
            healthy = True
            print("server ready, CUDA:", h.get("cuda_available"), flush=True)
            break
    except Exception as e:
        print(f"waiting[{i}] {str(e)[:60]}", flush=True)
assert healthy, "server never became healthy"


def synth(voice_id, text, dest):
    r = requests.post("http://127.0.0.1:8004/v1/audio/speech",
                      json={"model": "tts-1", "input": text, "voice": voice_id,
                            "response_format": "mp3"}, timeout=900)
    r.raise_for_status()
    open(dest, "wb").write(r.content)
    return len(r.content)


# 4. every chatterbox voice = every reference wav in the repo
voices = sorted(os.path.splitext(os.path.basename(p))[0]
                for p in glob.glob(f"{REPO_DIR}/chatterbox/voices/*.wav"))
print(f"rendering {len(voices)} voice samples on GPU", flush=True)
t0 = time.time()
for i, vid in enumerate(voices, 1):
    try:
        n = synth(vid, TEXT, f"{OUT}/{vid}.mp3")
        print(f"[{i}/{len(voices)}] {vid}  {n} bytes  ({time.time()-t0:.0f}s elapsed)", flush=True)
    except Exception as e:
        print(f"[{i}/{len(voices)}] {vid} FAILED: {str(e)[:120]}", flush=True)

# 5. the 1997 A/B — same voice, same sentence, only the year treatment differs
AB = ("In the spring of 1997, Apple was nine weeks from bankruptcy, and few "
      "analysts believed it would survive to see the year 2000.")
ab_voice = "uk_male_minter" if "uk_male_minter" in voices else (voices[0] if voices else None)
if ab_voice:
    raw = normalize_text_for_tts(AB, lexicon=SAMPLE_LEXICON, modern=True)      # 1997 left alone
    spelled = normalize_text_for_tts(AB, lexicon=SAMPLE_LEXICON, modern=False) # year spelled out
    print("A/B raw    :", raw, flush=True)
    print("A/B spelled:", spelled, flush=True)
    for tag, txt in (("raw", raw), ("spelled", spelled)):
        try:
            synth(ab_voice, txt, f"{OUT}/ab_1997_{tag}.mp3")
            print("A/B rendered:", tag, flush=True)
        except Exception as e:
            print("A/B failed", tag, str(e)[:100], flush=True)

# 6. surface outputs
for f in sorted(glob.glob(f"{OUT}/*.mp3")):
    shutil.copy(f, os.path.join(WORK, os.path.basename(f)))
print(f"DONE: {len(glob.glob(f'{OUT}/*.mp3'))} mp3s in {time.time()-t0:.0f}s", flush=True)
