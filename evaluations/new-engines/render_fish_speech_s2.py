"""
render_fish_speech_s2.py — Fish Speech 2.0 (S2 Pro) Flagship Modal Evaluation

Model Architecture:
- 4.4B Parameter Dual-Autoregressive Transformer (4B Slow AR + 400M Fast AR)
- 44.1kHz Descript Audio Codec (codec.pth)
- Repository: fishaudio/s2-pro on Hugging Face
- Hardware: Nvidia A10G (24GB VRAM) on Modal Cloud GPU

Findings on Breakneck (2026-09-17/18 Gate):
- Theatrical dialogue reference audio (Arthur uk_male_minter.wav) transfers erratic pitch jumps,
  clipped stops, and shouting into serious non-fiction narrative prose.
- Open-weights model has NO native hardcoded voices (pure zero-shot prompt-conditioned cloner).
- Requires flat, clean studio non-fiction reference prompts to avoid prosodic instability.
"""

import modal
import os
import subprocess
import glob

app = modal.App("homelab-fish-speech-s2-eval")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsox-dev", "portaudio19-dev", "libsndfile1")
    .pip_install("uv", "huggingface_hub")
    .run_commands(
        "git clone https://github.com/fishaudio/fish-speech.git /root/fish-speech",
        "cd /root/fish-speech && uv pip install -e . --system",
        "huggingface-cli download fishaudio/s2-pro --local-dir /root/checkpoints/s2-pro"
    )
)

@app.cls(image=image, gpu="A10G", timeout=900, scaledown_window=2)
class FishSpeechS2Engine:
    @modal.enter()
    def setup(self):
        import os
        import glob
        import sys
        import subprocess

        # Patch audiotools to prevent importing tensorboard (bypassing protobuf gencode mismatch)
        for path in glob.glob("/usr/local/lib/python3.*/site-packages/audiotools/ml/decorators.py"):
            try:
                with open(path, "r") as f:
                    content = f.read()
                if "from torch.utils.tensorboard import SummaryWriter" in content:
                    content = content.replace("from torch.utils.tensorboard import SummaryWriter", "SummaryWriter = None")
                    with open(path, "w") as f:
                        f.write(content)
            except Exception:
                pass

        subprocess.run(["uv", "pip", "install", "protobuf>=6.31.1", "--system"], check=False)

        if "/root/fish-speech" not in sys.path:
            sys.path.insert(0, "/root/fish-speech")
        os.environ["PYTHONPATH"] = "/root/fish-speech:" + os.environ.get("PYTHONPATH", "")

        print("Fish Speech 2.0 (S2 Pro) ready on Nvidia A10G!")

    @modal.method()
    def synthesize(self, text: str, ref_wav_bytes: bytes, prompt_text: str) -> dict:
        import time
        import os
        import subprocess
        import shutil

        work_dir = "/tmp/fish_s2_run"
        os.makedirs(work_dir, exist_ok=True)

        start_time = time.time()
        ref_path = os.path.join(work_dir, "ref_audio.wav")
        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        out_wav = os.path.join(work_dir, "output.wav")

        cmd = [
            "python", "fish_speech/models/text2semantic/inference.py",
            "--text", text,
            "--prompt-text", prompt_text,
            "--prompt-audio", ref_path,
            "--checkpoint-path", "/root/checkpoints/s2-pro",
            "--output", out_wav,
            "--output-dir", work_dir,
            "--num-samples", "1"
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = f"/root/fish-speech:{env.get('PYTHONPATH', '')}"

        res = subprocess.run(cmd, cwd="/root/fish-speech", env=env, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Inference failed:\n{res.stderr}")

        with open(out_wav, "rb") as f:
            audio_bytes = f.read()

        elapsed = round(time.time() - start_time, 2)
        shutil.rmtree(work_dir, ignore_errors=True)

        return {
            "audio_bytes": audio_bytes,
            "compute_time": elapsed
        }
