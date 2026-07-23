import os
import sys
import time
import urllib.request
import torch

print("=== CosyVoice 3 Audition Script ===")
t0 = time.time()

# Pre-install C build tools and Cython
print("Installing system dependencies & Cython...")
os.system("apt-get update && apt-get install -y build-essential python3-dev g++ sox libsox-dev ffmpeg")
os.system("pip install -q --upgrade pip setuptools<81 wheel Cython")
os.system("pip install -q pyworld")

# Clone repo & submodules if missing
if not os.path.exists("CosyVoice"):
    print("Cloning FunAudioLLM/CosyVoice repo recursively...")
    os.system("git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git")

sys.path.insert(0, os.path.abspath("CosyVoice"))
sys.path.insert(0, os.path.abspath("CosyVoice/third_party/Matcha-TTS"))

# Install unpinned python dependencies
dependencies = [
    "modelscope",
    "conformer",
    "diffusers",
    "gdown",
    "grpcio",
    "hydra-core",
    "HyperPyYAML",
    "inflect",
    "librosa",
    "networkx",
    "numpy",
    "omegaconf",
    "onnx",
    "onnxruntime",
    "protobuf",
    "pydantic",
    "soundfile",
    "transformers",
    "x-transformers",
    "wetext",
    "wget",
    "huggingface_hub",
    "tqdm",
    "torchaudio",
    "openai-whisper",
    "regex",
    "lightning"
]

print("Installing python runtime dependencies...")
os.system(f"pip install -q {' '.join(dependencies)}")

import torchaudio
import whisper
from modelscope import snapshot_download
from cosyvoice.cli.cosyvoice import AutoModel

print("Downloading CosyVoice 3 model weights...")
model_dir = snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512')
print(f"Model downloaded to {model_dir}")

# Fall back to CPU if P100 sm_60 CUDA error occurs
if torch.cuda.is_available():
    cap = torch.cuda.get_device_capability()
    print(f"GPU detected: {torch.cuda.get_device_name(0)} (Compute Capability {cap[0]}.{cap[1]})")
    if cap[0] < 7:
        print("Compute capability < 7.0 (P100). Falling back to CPU mode...")
        torch.cuda.is_available = lambda: False

cosyvoice = AutoModel(model_dir=model_dir)
if hasattr(cosyvoice, "model") and hasattr(cosyvoice.model, "llm"):
    print("Converting LLM weights to float32 for input tensor dtype match...")
    cosyvoice.model.llm.to(torch.float32)

print(f"Model loaded ({time.time()-t0:.0f}s), sample_rate={cosyvoice.sample_rate}")

ref_path = "/kaggle/working/uk_male_minter_ref.wav"
if not os.path.exists(ref_path):
    url = "https://github.com/davedavedavenm/epub-to-audiobook/raw/master/chatterbox/voices/uk_male_minter.wav"
    urllib.request.urlretrieve(url, ref_path)
    print(f"Downloaded reference voice: {ref_path}")

REF_TRANSCRIPT = (
    '"I know that," snapped Bertram. "Not that it would make any difference '
    'if she stayed," pursued the relentless George. "She flies higher than '
    'the paper trade, my boy." "Hang her!" said Bertram. "It would make it '
    'more interesting for me," I ventured to observe.'
)

# Official CosyVoice 3 prompt signature from example.py:
PROMPT_TEXT = f"You are a helpful assistant.<|endofprompt|>{REF_TRANSCRIPT}"

COMBINED_TEXT = (
    "The old lighthouse keeper climbed the spiral staircase for the last time. "
    "Forty-three years he had tended the flame, watching ships slide past the headland like grey ghosts in the fog. "
    "Tonight the automation engineers would take over, and the light would keep itself. "
    "He paused at the top, laid his hand against the cold glass of the lantern room, "
    "and looked out across the water where the last of the sunset was bleeding into the sea. "
    "Solar energy installations have increased by forty percent across northern Europe over the past decade. "
    "Recent studies published in the Journal of Renewable Energy indicate that advanced photovoltaic materials, "
    "combined with localized battery storage networks, can maintain grid stability even during extended periods of low sunlight. "
    "Urban planners are now integrating these systems into residential housing developments."
)

print(f"\n=== Synthesizing Single Sample ({len(COMBINED_TEXT)} chars) ===")
t1 = time.time()
audio_chunks = []

for model_output in cosyvoice.inference_zero_shot(
    COMBINED_TEXT,
    PROMPT_TEXT,
    ref_path,
    stream=False,
):
    audio_chunks.append(model_output["tts_speech"])

if audio_chunks:
    full_speech = torch.cat(audio_chunks, dim=1)
    out_file = "/kaggle/working/sample.wav"
    torchaudio.save(out_file, full_speech, cosyvoice.sample_rate)
    duration = full_speech.shape[1] / cosyvoice.sample_rate
    print(f"Saved {out_file}: duration = {duration:.2f}s ({time.time()-t1:.1f}s to generate)")

    # Run Whisper ASR Verification to empirically prove English text output
    print("\n=== Running Whisper ASR Verification ===")
    whisper_model = whisper.load_model("tiny")
    asr_res = whisper_model.transcribe(out_file)
    print("ASR Detected Language:", asr_res.get("language"))
    print("ASR Transcribed Text:", asr_res.get("text"))
else:
    print("ERROR: No audio chunks produced!")

print(f"\n=== Completed in {time.time()-t0:.0f}s ===")
