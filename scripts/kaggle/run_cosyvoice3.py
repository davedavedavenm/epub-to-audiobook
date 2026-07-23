"""
CosyVoice 3 audition kernel — renders 3 paragraphs (narrative, non-fiction,
dialogue) with a UK English reference voice on a free Kaggle T4.

Push with:
    cd scripts/kaggle
    kaggle kernels push -p .   (after editing kernel-metadata.json)

Or run interactively on Kaggle. Output WAVs land in /kaggle/working/.
"""
VOICE  = "uk_male_minter"
SEED   = 42

PARAGRAPHS = {
    "01_narrative": (
        "The old lighthouse keeper climbed the spiral staircase for the last time. "
        "Forty-three years he had tended the flame, watching ships slide past the headland "
        "like grey ghosts in the fog. Tonight the automation engineers would take over, "
        "and the light would keep itself. He paused at the top, laid his hand against the "
        "cold glass of the lantern room, and looked out across the water where the last "
        "of the sunset was bleeding into the sea."
    ),
    "02_nonfiction": (
        "In 2024, the global solar industry installed 420 gigawatts of new capacity, "
        "bringing the total to approximately 1.6 terawatts worldwide. BloombergNEF "
        "estimated that the levelised cost of electricity from utility-scale solar had "
        "fallen by 89 percent since 2010, making it the cheapest source of new electricity "
        "generation in countries representing two-thirds of the world's population. "
        "Jenny Chase, the lead analyst, noted that the decline showed no sign of slowing."
    ),
    "03_dialogue": (
        '"You can\'t be serious," said Margaret, setting down her teacup with a deliberate '
        'click. "After everything that happened in Shanghai, you want to go back?" '
        '"I don\'t want to go back," replied Thomas, turning the newspaper over in his hands. '
        '"I have to. The contract is quite specific — 30 days\' notice, or we forfeit the '
        'entire deposit." Margaret sighed. "And how much is the deposit?" '
        '"1.2 million pounds," Thomas said quietly. "Give or take."'
    ),
}

import subprocess, sys, os, time

t0 = time.time()

def sh(cmd, check=True):
    print(f"+ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, shell=isinstance(cmd, str), check=check)

print("=== System dependencies ===")
sh("apt-get update && apt-get install -y -q build-essential python3-dev g++ sox libsox-dev ffmpeg", check=False)

print("=== Python build tools & Cython ===")
sh([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools<81", "wheel", "Cython"])

print("=== Installing PyWorld ===")
sh([sys.executable, "-m", "pip", "install", "-q", "pyworld"], check=False)

print("=== Cloning CosyVoice repository ===")
cosy_dir = "/kaggle/working/CosyVoice"
if not os.path.exists(cosy_dir):
    sh(f"git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git {cosy_dir}")

sys.path.insert(0, cosy_dir)
sys.path.insert(0, os.path.join(cosy_dir, "third_party/Matcha-TTS"))

print("=== Installing CosyVoice dependencies ===")
pkgs = [
    "modelscope", "conformer", "diffusers", "gdown", "grpcio",
    "hydra-core", "HyperPyYAML", "inflect", "librosa", "networkx",
    "numpy", "omegaconf", "onnx", "onnxruntime", "protobuf",
    "pydantic", "soundfile", "transformers", "x-transformers",
    "wetext", "wget", "huggingface_hub", "tqdm", "torchaudio",
    "openai-whisper", "regex", "lightning"
]
sh([sys.executable, "-m", "pip", "install", "-q"] + pkgs, check=True)

print("=== Downloading model ===")
from huggingface_hub import snapshot_download
model_dir = snapshot_download(
    "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    local_dir="/kaggle/working/cosyvoice3_model",
)
print(f"Model at {model_dir} ({time.time()-t0:.0f}s)")

print("=== Loading model ===")
try:
    from cosyvoice.cli.cosyvoice import AutoModel
except ImportError:
    # Try importing directly from CosyVoice repo path
    from cosyvoice.cli.cosyvoice import AutoModel

import torchaudio, torch, urllib.request

if torch.cuda.is_available():
    device_name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"GPU detected: {device_name} (sm_{cap[0]}{cap[1]})")
    if cap[0] < 7:
        print(f"WARNING: {device_name} (sm_{cap[0]}{cap[1]}) is incompatible with Kaggle PyTorch CUDA build. Forcing CPU mode.")
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

print("\n=== Pass 1: Cross-lingual synthesis (audio-only prompt) ===")
for name, text in PARAGRAPHS.items():
    print(f"\n=== Generating {name}_cross_lingual ({len(text)} chars) ===")
    t1 = time.time()
    for i, j in enumerate(cosyvoice.inference_cross_lingual(
        text,
        ref_path,
        stream=False,
    )):
        out = f"/kaggle/working/{name}_cross_lingual.wav"
        torchaudio.save(out, j["tts_speech"], cosyvoice.sample_rate)
        dur = j["tts_speech"].shape[1] / cosyvoice.sample_rate
        print(f"  {out}: {dur:.1f}s ({time.time()-t1:.1f}s to generate)")
        break

PROMPT_TEXT = (
    '"I know that," snapped Bertram. "Not that it would make any difference '
    'if she stayed," pursued the relentless George. "She flies higher than '
    'the paper trade, my boy." "Hang her!" said Bertram. "It would make it '
    'more interesting for me," I ventured to observe.<|endofprompt|>'
)

print("\n=== Pass 2: Zero-shot synthesis with exact reference transcript + <|endofprompt|> ===")
for name, text in PARAGRAPHS.items():
    print(f"\n=== Generating {name}_zero_shot ({len(text)} chars) ===")
    t1 = time.time()
    for i, j in enumerate(cosyvoice.inference_zero_shot(
        text,
        PROMPT_TEXT,
        ref_path,
        stream=False,
    )):
        out = f"/kaggle/working/{name}_zero_shot.wav"
        torchaudio.save(out, j["tts_speech"], cosyvoice.sample_rate)
        dur = j["tts_speech"].shape[1] / cosyvoice.sample_rate
        print(f"  {out}: {dur:.1f}s ({time.time()-t1:.1f}s to generate)")
        break

print(f"\n=== Done in {time.time()-t0:.0f}s ===")
print("Output files:")
for f in sorted(os.listdir("/kaggle/working")):
    if f.endswith(".wav"):
        sz = os.path.getsize(f"/kaggle/working/{f}")
        print(f"  {f} ({sz:,} bytes)")
