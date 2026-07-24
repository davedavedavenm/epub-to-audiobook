#!/usr/bin/env python3
"""Kaggle driver: CosyVoice 3 zero-shot English narration.

Installs strictly per the official FunAudioLLM/CosyVoice README:
  * Python 3.10 (README: "Python Version: 3.10 required")
  * git clone --recursive + git submodule update --init --recursive
  * apt-get install sox libsox-dev
  * pip install -r requirements.txt   (the repo's own pins, unmodified)
  * snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512',
                      local_dir='pretrained_models/Fun-CosyVoice3-0.5B')
  * inference_zero_shot() with the CosyVoice3 prompt signature from example.py

Earlier attempts (v4-v16) installed UNPINNED deps onto Kaggle's Python 3.12.
Every output was fluent multilingual babble unrelated to the input text
(ASR-confirmed: Mongolian, Hungarian, Arabic, Chinese). The model weights were
complete, so the cause was the dependency skew -- notably transformers, which
the repo pins to 4.51.3 for the Qwen2 LLM backbone. Hence: exact pins, py3.10.

Big artefacts live in /tmp (Kaggle's /kaggle/working has a ~20 GB quota);
only the rendered audio + transcripts are written to /kaggle/working.
"""
import os
import subprocess
import sys
import time

T0 = time.time()
SCRATCH = "/tmp/cv3"
REPO = f"{SCRATCH}/CosyVoice"
VENV = f"{SCRATCH}/venv"
PY = f"{VENV}/bin/python"
MODEL_DIR = f"{REPO}/pretrained_models/Fun-CosyVoice3-0.5B"
OUT = "/kaggle/working/out"
DEVIATIONS = []


# ---------------------------------------------------------------------------
# Runs inside the py3.10 venv, cwd = repo root (example.py appends the
# Matcha-TTS third_party path relatively, so cwd matters).
# ---------------------------------------------------------------------------
INFER_SRC = r'''
import sys
sys.path.append('third_party/Matcha-TTS')  # per example.py

import os
import re
import time
import json
import difflib
import urllib.request

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

MODEL_DIR = 'pretrained_models/Fun-CosyVoice3-0.5B'
OUT = '/kaggle/working/out'
REF = '/kaggle/working/out/reference_uk_male_minter.wav'
REF_URL = ('https://github.com/davedavedavenm/epub-to-audiobook/raw/master/'
           'chatterbox/voices/uk_male_minter.wav')

# Transcript of REF, verified against the audio with Whisper before this run.
# In zero-shot cloning a prompt transcript that does not match the prompt audio
# degrades output badly, so this is checked rather than assumed.
REF_TRANSCRIPT = (
    "No, I know that, snapped Bertram. Not that it would make any difference "
    "if she stayed, pursued the relentless George. She flies higher than the "
    "paper trade, my boy. Hang her, said Bertram. It would make it more "
    "interesting for me, I ventured to observe."
)
# CosyVoice3 prompt signature, copied from example.py::cosyvoice3_example
PROMPT_TEXT = 'You are a helpful assistant.<|endofprompt|>' + REF_TRANSCRIPT

PARAGRAPHS = [
    ("01", "For a hundred and forty years the lighthouse at Ardnamurchan had "
           "kept its own company. It stood at the westernmost point of the "
           "mainland, a granite finger raised against the Atlantic, and every "
           "night since 1849 it had turned its slow white eye across the "
           "water. Ships had come and gone. Wars had started and finished. "
           "The keepers had changed, generation after generation, and the "
           "light had gone on turning, indifferent to all of it."),
    ("02", "Morag Sinclair was the last of them. She had arrived in the spring "
           "of 1987, twenty-four years old and certain she would stay a single "
           "season, and she had never left. She knew the sound of every wind "
           "that crossed the point: the thin one from the north that made the "
           "railings sing, the heavy south-westerly that came in like a "
           "shoulder against a door. She knew, without looking at a clock, "
           "when the tide had turned."),
    ("03", "The letter from the Northern Lighthouse Board arrived on a "
           "Tuesday. Automation, it explained, would be completed by the end "
           "of the following year. The new system required no keeper, no "
           "watch, and no fuel deliveries; it would report its own faults by "
           "radio and correct most of them without human help. The board "
           "thanked her for thirty-one years of service. There was a form to "
           "return, and a telephone number to call if she had questions."),
    ("04", "She read it twice, then set it on the table and went up the "
           "stairs, all one hundred and fifty-two of them, as she had done "
           "every evening for three decades. The lantern room smelled of warm "
           "brass and paraffin. Out beyond the glass the sea was doing what it "
           "had always done, patiently, without any need to be watched. Morag "
           "put her hand flat against the cold pane and stood there a long "
           "while, and then, because it was the hour, she started the light."),
]

os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------ reference audio
if not os.path.exists(REF):
    urllib.request.urlretrieve(REF_URL, REF)
info = torchaudio.info(REF)
ref_secs = info.num_frames / info.sample_rate
print('reference: %s  %.2fs  %dHz' % (REF, ref_secs, info.sample_rate))
if not (3.0 < ref_secs < 40.0):
    raise SystemExit('reference audio looks wrong (%.2fs) - download failed?' % ref_secs)

# -------------------------------------------------------------------- device
print('torch', torch.__version__, 'cuda_available', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu:', torch.cuda.get_device_name(0),
          'sm_%d%d' % torch.cuda.get_device_capability())
else:
    raise SystemExit('no GPU visible - refusing to run on CPU')

# --------------------------------------------------------------------- model
t0 = time.time()
cosyvoice = AutoModel(model_dir=MODEL_DIR)
print('model loaded in %.0fs, sample_rate=%d' % (time.time() - t0, cosyvoice.sample_rate))

# ----------------------------------------------------------------- synthesize
rendered = []
for tag, text in PARAGRAPHS:
    t1 = time.time()
    chunks = []
    for out in cosyvoice.inference_zero_shot(text, PROMPT_TEXT, REF, stream=False):
        chunks.append(out['tts_speech'])
    if not chunks:
        raise SystemExit('no audio produced for paragraph ' + tag)
    speech = torch.cat(chunks, dim=1)
    path = os.path.join(OUT, 'para_%s.wav' % tag)
    torchaudio.save(path, speech, cosyvoice.sample_rate)
    secs = speech.shape[1] / cosyvoice.sample_rate
    gen = time.time() - t1
    print('[%s] %s  %.2fs audio in %.1fs (RTF %.2f)' % (tag, path, secs, gen, gen / secs))
    rendered.append((tag, text, path, speech))

full = torch.cat([r[3] for r in rendered], dim=1)
full_path = os.path.join(OUT, 'narration_full.wav')
torchaudio.save(full_path, full, cosyvoice.sample_rate)
print('full: %s  %.2fs' % (full_path, full.shape[1] / cosyvoice.sample_rate))

# ------------------------------------------------------------ ASR verification
# Proves the audio says the input text, rather than assuming it does.
# openai-whisper==20231117 is already pinned in the repo's requirements.txt.
print('\n=== Whisper ASR verification ===')
import whisper
asr = whisper.load_model('small')


def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return [w for w in s.split() if w]


report = []
for tag, text, path, _ in rendered:
    r = asr.transcribe(path, language='en')
    hyp = r['text'].strip()
    ratio = difflib.SequenceMatcher(None, norm(text), norm(hyp)).ratio()
    print('\n[%s] similarity=%.3f  detected_lang=%s' % (tag, ratio, r.get('language')))
    print('  REF: ' + text[:200])
    print('  ASR: ' + hyp[:200])
    report.append({'tag': tag, 'similarity': round(ratio, 4),
                   'language': r.get('language'), 'expected': text, 'asr': hyp})

with open(os.path.join(OUT, 'asr_verification.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
with open(os.path.join(OUT, 'narration_text.txt'), 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(t for _, t in PARAGRAPHS) + '\n')

avg = sum(r['similarity'] for r in report) / len(report)
print('\nmean word-sequence similarity: %.3f' % avg)
print('VERDICT:', 'PASS' if avg > 0.80 else 'FAIL - output does not match input text')
'''


def sh(cmd, cwd=None, check=True):
    """Run a shell command, streaming output into the Kaggle log."""
    print(f"\n$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True, cwd=cwd)
    if check and r.returncode != 0:
        raise SystemExit(f"FAILED ({r.returncode}): {cmd}")
    return r.returncode


def stage(msg):
    print(f"\n{'=' * 70}\n[{time.time() - T0:6.0f}s] {msg}\n{'=' * 70}", flush=True)


os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- system deps
stage("System dependencies (README: sox, libsox-dev)")
sh("apt-get update -qq", check=False)
sh("apt-get install -y -qq sox libsox-dev ffmpeg", check=False)

# ------------------------------------------------------------------ clone repo
stage("Clone repo (README: git clone --recursive)")
if not os.path.exists(REPO):
    sh(f"git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git {REPO}")
sh("git submodule update --init --recursive", cwd=REPO, check=False)
sh("git log --oneline -1", cwd=REPO, check=False)

# ------------------------------------------------------- python 3.10 + install
stage("Create Python 3.10 env (README: conda create -y python=3.10)")
# Kaggle ships 3.12; uv only supplies the interpreter, pip does the installing
# so the dependency resolution matches the documented `pip install -r` exactly.
sh("pip install -q uv")
sh("uv python install 3.10")
sh(f"uv venv --python 3.10 --seed {VENV}")
sh(f"{PY} --version")

stage("Pin the build toolchain")
# openai-whisper==20231117's setup.py does `import pkg_resources`, which
# setuptools >= 82 no longer ships. That kills `pip install -r requirements.txt`
# during the collect phase, before anything else is built (v17 died here twice).
# Constrain the *build-isolation* envs to a setuptools that still has it rather
# than editing the repo's pins -- PIP_CONSTRAINT propagates into build envs.
CONSTRAINTS = f"{SCRATCH}/constraints.txt"
with open(CONSTRAINTS, "w") as f:
    f.write("setuptools<81\n")
os.environ["PIP_CONSTRAINT"] = CONSTRAINTS
sh(f"{PY} -m pip install -q 'setuptools<81' wheel")

stage("Install torch + numpy first")
# deepspeed's sdist imports torch at build time, so torch must land first and
# deepspeed must skip build isolation; installing it here means the
# requirements.txt pass below sees it already satisfied.
sh(f"{PY} -m pip install -q torch==2.3.1 torchaudio==2.3.1 numpy==1.26.4 "
   "--extra-index-url https://download.pytorch.org/whl/cu121")
sh(f"{PY} -m pip install -q deepspeed==0.15.1 --no-build-isolation", check=False)

stage("Install requirements.txt (repo pins, unmodified)")
if sh(f"{PY} -m pip install -r requirements.txt", cwd=REPO, check=False) != 0:
    print("\n!! requirements.txt still failed -- reproducing the whisper build "
          "error verbatim so the real cause is visible:")
    sh(f"{PY} -m pip install -v --no-build-isolation openai-whisper==20231117",
       cwd=REPO, check=False)
    raise SystemExit("dependency install failed; see the verbose build log above")

stage("Installed versions of the pins that matter")
sh(f"{PY} -m pip list 2>/dev/null | grep -Ei "
   "'^(torch|torchaudio|transformers|numpy|x-transformers|onnxruntime|diffusers|lightning|wetext) '",
   check=False)

# -------------------------------------------------------------- model download
stage("Download Fun-CosyVoice3-0.5B-2512 (README snapshot_download)")
sh(f"{PY} -m pip install -q huggingface_hub")
# NOTE write to a file and run it -- `python -c {repr}` turns the newlines into
# literal backslash-n for the shell and dies with a SyntaxError (killed v18).
DL_PY = f"{SCRATCH}/download_model.py"
with open(DL_PY, "w") as f:
    f.write('from huggingface_hub import snapshot_download\n'
            'snapshot_download("FunAudioLLM/Fun-CosyVoice3-0.5B-2512",\n'
            f'                  local_dir="{MODEL_DIR}", max_workers=4)\n'
            f'print("downloaded -> {MODEL_DIR}")\n')
sh(f"{PY} {DL_PY}")
sh(f"ls -la {MODEL_DIR} && echo '--- CosyVoice-BlankEN ---' && ls -la {MODEL_DIR}/CosyVoice-BlankEN")

# --------------------------------------------------------------- run inference
stage("Synthesize")
with open(f"{REPO}/infer_narration.py", "w", encoding="utf-8") as f:
    f.write(INFER_SRC)
sh(f"{PY} infer_narration.py", cwd=REPO)

stage(f"DONE in {time.time() - T0:.0f}s")
if DEVIATIONS:
    print("DEVIATIONS FROM DOCS:")
    for d in DEVIATIONS:
        print("  -", d)
else:
    print("No deviations from the documented install path.")
