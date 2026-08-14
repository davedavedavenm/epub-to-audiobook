#!/usr/bin/env python3
"""Stage the free-Kaggle VibeVoice cfg-2 app-path reproduction.

The text builder is shared with the cfg-2/cfg-3 blind test, and its hash is
pinned to that test.  This run invokes the repository's real HTTP adapter at a
pinned app commit; the existing blind-B file is the direct-upstream comparator.

Usage: python scripts/kaggle/build_vibe_app_path_kernel.py <APP_REF_40_HEX>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from build_chapter_kernel import chunk, extract_paragraphs

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch" / "vibe_app_path" / "kernel"
EXPECTED_TEXT_SHA = "405cb7ff75f75bfa21c9845f08ba16d17306d56d3af129926b2b23381933ce31"
RUNTIME_SHA = "07cb79feadd2d3fd7f47530d4c964a12857936a0"
REF_SHA = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"

KERNEL = r"""import hashlib
import json
import os
import re
import subprocess
import sys
import time

import requests
import soundfile as sf

APP_REF = __APP_REF__
TEXT = json.loads(r'''__TEXT__''')
TEXT_SHA = __TEXT_SHA__
RUNTIME_SHA = __RUNTIME_SHA__
REF_SHA = __REF_SHA__
WORK = "/kaggle/working"
APP = "/tmp/epub-to-audiobook"
RUNTIME = "/tmp/VibeVoice"
REF = APP + "/chatterbox/voices/uk_male_minter.wav"


def sh(args, **kwargs):
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, check=True, **kwargs)


assert hashlib.sha256(TEXT.encode()).hexdigest() == TEXT_SHA
WORD_COUNT = len(re.sub(r"[^a-z0-9' ]+", " ", TEXT.lower()).split())
assert WORD_COUNT == 6166
sh(["apt-get", "update", "-qq"])
sh(["apt-get", "install", "-y", "-qq", "ffmpeg", "git-lfs"])
sh(["git", "lfs", "install"])
sh(["git", "clone", "--filter=blob:none", "--no-checkout",
    "https://github.com/davedavedavenm/epub-to-audiobook.git", APP])
sh(["git", "-C", APP, "fetch", "origin", APP_REF])
sh(["git", "-C", APP, "checkout", "--detach", APP_REF])
sh(["git", "-C", APP, "lfs", "pull", "--include",
    "chatterbox/voices/uk_male_minter.wav"])
assert subprocess.check_output(["git", "-C", APP, "rev-parse", "HEAD"], text=True).strip() == APP_REF
ref = open(REF, "rb").read()
assert ref[:4] == b"RIFF" and len(ref) == 864182
assert hashlib.sha256(ref).hexdigest() == REF_SHA

sh(["git", "clone", "https://github.com/vibevoice-community/VibeVoice.git", RUNTIME])
sh(["git", "-C", RUNTIME, "checkout", "--detach", RUNTIME_SHA])
assert subprocess.check_output(["git", "-C", RUNTIME, "rev-parse", "HEAD"], text=True).strip() == RUNTIME_SHA
sh([sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
    "torch==2.3.1", "torchvision==0.18.1", "torchaudio==2.3.1",
    "--index-url", "https://download.pytorch.org/whl/cu121"])
sh([sys.executable, "-m", "pip", "install", "-q", "numpy==1.26.4"])
sh([sys.executable, "-m", "pip", "install", "-q", "-e", RUNTIME])
sh([sys.executable, "-m", "pip", "install", "-q", "fastapi", "uvicorn",
    "soundfile", "requests"])

env = dict(os.environ)
env.update({
    "USE_TF": "0", "USE_TENSORFLOW": "0", "PYTHONPATH": RUNTIME,
    "VOICES_DIR": APP + "/chatterbox/voices", "HF_HOME": "/tmp/hf",
    "VIBEVOICE_DTYPE": "float16", "VIBEVOICE_CFG_SCALE": "2.0",
    "VIBEVOICE_DDPM_STEPS": "10",
})
log = open(WORK + "/vibe_app_server.log", "w")
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1",
     "--port", "8010"], cwd=APP + "/vibevoice", env=env,
    stdout=log, stderr=subprocess.STDOUT)
for _ in range(120):
    time.sleep(5)
    if server.poll() is not None:
        log.flush()
        raise SystemExit("adapter exited:\n" + open(log.name).read()[-4000:])
    try:
        health = requests.get("http://127.0.0.1:8010/health", timeout=5)
        if health.status_code == 200 and health.json().get("device") == "cuda":
            break
    except Exception:
        pass
else:
    raise SystemExit("adapter did not become healthy")

started = time.time()
response = requests.post(
    "http://127.0.0.1:8010/v1/audio/speech",
    json={"input": TEXT, "voice": "uk_male_minter_vibevoice",
          "response_format": "wav", "seed": 12345},
    timeout=(30, 21600))
response.raise_for_status()
wav = response.content
assert wav[:4] == b"RIFF" and len(wav) > 50_000_000
wav_path = WORK + "/vibe_cfg2_app_path.wav"
mp3_path = WORK + "/vibe_cfg2_app_path.mp3"
open(wav_path, "wb").write(wav)
info = sf.info(wav_path)
duration = info.frames / info.samplerate
# The heard direct cfg-2 arm was 1372 s. This broad bound catches a truncated
# HTTP response without pretending duration or code can judge voice quality.
assert 1200 <= duration <= 1600, duration
sh(["ffmpeg", "-y", "-v", "error", "-i", wav_path,
    "-codec:a", "libmp3lame", "-b:a", "192k", mp3_path])
sh(["ffmpeg", "-v", "error", "-i", mp3_path, "-f", "null", "-"])
manifest = {
    "official_weights": "microsoft/VibeVoice-1.5B",
    "runtime": "vibevoice-community/VibeVoice", "runtime_commit": RUNTIME_SHA,
    "app_ref": APP_REF, "path": "vibevoice/server.py HTTP /v1/audio/speech",
    "cfg_scale": 2.0, "ddpm_steps": 10, "seed": 12345,
    "text_sha256": TEXT_SHA, "words": WORD_COUNT,
    "reference_sha256": REF_SHA, "audio_seconds": round(duration, 3),
    "wav_bytes": len(wav), "mp3_bytes": os.path.getsize(mp3_path),
    "mp3_sha256": hashlib.sha256(open(mp3_path, "rb").read()).hexdigest(),
    "synthesis_seconds": round(time.time() - started, 3),
}
open(WORK + "/vibe_cfg2_app_path_manifest.json", "w").write(
    json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2), flush=True)
"""


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]):
        raise SystemExit("usage: build_vibe_app_path_kernel.py <APP_REF_40_HEX>")
    text = "\n\n".join(chunk(extract_paragraphs()))
    assert len(re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()) == 6166
    assert hashlib.sha256(text.encode()).hexdigest() == EXPECTED_TEXT_SHA
    source = (KERNEL.replace("__APP_REF__", repr(sys.argv[1]))
              .replace("__TEXT__", json.dumps(text))
              .replace("__TEXT_SHA__", repr(EXPECTED_TEXT_SHA))
              .replace("__RUNTIME_SHA__", repr(RUNTIME_SHA))
              .replace("__REF_SHA__", repr(REF_SHA)))
    compile(source, "run_vibe_app_path.py", "exec")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run_vibe_app_path.py").write_text(source, encoding="utf-8", newline="\n")
    metadata = {
        "id": "davedavedavenm/vibevoice-cfg2-app-path",
        "title": "vibevoice-cfg2-app-path",
        "code_file": "run_vibe_app_path.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
    }
    (OUT / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"text: 6166 words sha256={EXPECTED_TEXT_SHA}")
    print(f"kernel: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
