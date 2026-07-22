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

print("=== Installing CosyVoice ===")
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
    "cosyvoice", "huggingface_hub", "torchaudio"],
    check=True, capture_output=True)

subprocess.run([sys.executable, "-m", "pip", "install", "-q",
    "git+https://github.com/FunAudioLLM/CosyVoice.git"],
    capture_output=True)

subprocess.run(["apt-get", "install", "-y", "-q", "sox", "libsox-dev"],
    capture_output=True)

print("=== Downloading model ===")
from huggingface_hub import snapshot_download
model_dir = snapshot_download(
    "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
    local_dir="/kaggle/working/cosyvoice3_model",
)
print(f"Model at {model_dir} ({time.time()-t0:.0f}s)")

print("=== Loading model ===")
sys.path.append("/kaggle/working/CosyVoice/third_party/Matcha-TTS")
try:
    from cosyvoice.cli.cosyvoice import AutoModel
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
        "git+https://github.com/FunAudioLLM/CosyVoice.git"],
        check=True)
    from cosyvoice.cli.cosyvoice import AutoModel

import torchaudio, torch, urllib.request

cosyvoice = AutoModel(model_dir=model_dir)
print(f"Model loaded ({time.time()-t0:.0f}s), sample_rate={cosyvoice.sample_rate}")

ref_path = "/kaggle/working/uk_male_minter_ref.wav"
if not os.path.exists(ref_path):
    url = "https://github.com/davedavedavenm/epub-to-audiobook/raw/master/chatterbox/voices/uk_male_minter.wav"
    urllib.request.urlretrieve(url, ref_path)
    print(f"Downloaded reference voice: {ref_path}")

prompt_text = ""

for name, text in PARAGRAPHS.items():
    print(f"\n=== Generating {name} ({len(text)} chars) ===")
    t1 = time.time()
    for i, j in enumerate(cosyvoice.inference_zero_shot(
        text,
        prompt_text,
        ref_path,
        stream=False,
    )):
        out = f"/kaggle/working/{name}.wav"
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
