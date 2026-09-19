"""
render_firered_modal.py — FireRedTTS3 Base Modal Cloud GPU Evaluation

Model Architecture:
- Unified speech generation with frozen audio encoder semantic regularization
- Supports zero-shot multilingual/multi-dialect cloning and text normalization
- Repository: FireRedTeam/FireRedTTS3 on GitHub / Hugging Face
- Hardware: Nvidia L4 / A10G on Modal Cloud GPU
"""

import modal

app = modal.App("homelab-fireredtts3-eval")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install("uv", "huggingface_hub", "soundfile", "torchaudio", "torch")
    .run_commands(
        "git clone https://github.com/FireRedTeam/FireRedTTS3.git /root/FireRedTTS3",
        "cd /root/FireRedTTS3 && uv pip install -r requirements.txt --system",
        "hf download FireRedTeam/FireRedTTS3 --local-dir /root/pretrained_models"
    )
)

@app.cls(image=image, gpu="L4", timeout=900, scaledown_window=2)
class FireRedEngine:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/FireRedTTS3" not in sys.path:
            sys.path.insert(0, "/root/FireRedTTS3")
        
        from fireredtts3.core import FireRedTTS3
        print("Loading FireRedTTS3 into GPU memory...")
        self.tts = FireRedTTS3("/root/pretrained_models", use_wetext=True, use_llm_tn=False)
        print("FireRedTTS3 ready on GPU!")

    @modal.method()
    def synthesize(self, text: str, ref_wav_bytes: bytes, prompt_text: str) -> dict:
        import time
        import io
        import soundfile as sf
        import torchaudio
        import torch

        start_time = time.time()
        prompt_audio, prompt_sr = torchaudio.load(io.BytesIO(ref_wav_bytes))

        gen_audio, gen_sr = self.tts.generate(
            text=text,
            language="English",
            prompt_text=prompt_text,
            prompt_audio=prompt_audio
        )

        if isinstance(gen_audio, torch.Tensor):
            gen_audio = gen_audio.squeeze().cpu().numpy()

        out_io = io.BytesIO()
        sf.write(out_io, gen_audio, gen_sr, format="WAV")
        wav_bytes = out_io.getvalue()

        duration = len(gen_audio) / gen_sr
        elapsed = round(time.time() - start_time, 2)

        return {
            "wav_bytes": wav_bytes,
            "duration": round(duration, 2),
            "compute_time": elapsed,
            "sample_rate": gen_sr
        }
