"""
modal_cosyvoice.py — Production-ready CosyVoice 3 (0.5B) voice cloning on Modal GPU.

Architecture:
- Model: FunAudioLLM/Fun-CosyVoice3-0.5B-2512 (Flow-matching diffusion with LLM conditioning, ~0.5B parameters)
- Hardware: Modal GPU (Tesla T4 or L4)
- RTF: ~0.15 (6-8x faster than realtime)
- Scaledown window: 2s (zero idle waste)
"""

import modal
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-cosyvoice3")

cosy_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1", "sox", "libsox-dev")
    .pip_install(
        "modelscope",
        "torch",
        "torchaudio",
        "soundfile>=0.13",
        "hyperpyyaml",
        "transformers==4.51.3",
        "numpy",
        "fastapi",
        "pydantic"
    )
    .run_commands(
        "git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /root/CosyVoice",
        "python3 -c \"from modelscope import snapshot_download; snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir='/root/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B')\""
    )
)


@app.cls(image=cosy_image, gpu="T4", timeout=600, scaledown_window=2)
class CosyVoiceProducer:
    @modal.enter()
    def setup(self):
        import sys
        if "/root/CosyVoice" not in sys.path:
            sys.path.insert(0, "/root/CosyVoice")
        if "/root/CosyVoice/third_party/Matcha-TTS" not in sys.path:
            sys.path.insert(0, "/root/CosyVoice/third_party/Matcha-TTS")
        import torch
        from cosyvoice.cli.cosyvoice import AutoModel

        print(f"Loading CosyVoice 3 (0.5B) on {torch.cuda.get_device_name(0)}...")
        self.model = AutoModel(model_dir="/root/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B")
        self.sample_rate = self.model.sample_rate
        print(f"CosyVoice 3 runtime ready (Sample Rate: {self.sample_rate}Hz)!")

    @modal.method()
    def synthesize(
        self,
        text: str,
        ref_wav_bytes: bytes,
        ref_text: str,
        speed: float = 1.0,
        apply_mastering: bool = True
    ) -> dict:
        import torch
        import torchaudio
        import soundfile as sf

        t0 = time.time()
        ref_path = "/tmp/cosy_ref.wav"
        out_raw_wav = "/tmp/cosy_out_raw.wav"
        out_mastered_wav = "/tmp/cosy_out_mastered.wav"
        out_mp3 = "/tmp/cosy_out.mp3"

        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        prompt_text = "You are a helpful assistant.<|endofprompt|>" + ref_text

        chunks = []
        for out in self.model.inference_zero_shot(text, prompt_text, ref_path, stream=False, speed=speed):
            chunks.append(out["tts_speech"])

        if not chunks:
            raise RuntimeError("CosyVoice 3 produced no audio chunks.")

        speech = torch.cat(chunks, dim=1)
        torchaudio.save(out_raw_wav, speech, self.sample_rate)

        audio_data, sr = sf.read(out_raw_wav)
        duration_sec = round(len(audio_data) / sr, 2)
        gpu_time = round(time.time() - t0, 2)
        rtf = round(gpu_time / max(duration_sec, 0.01), 3)

        if apply_mastering:
            af_filters = (
                "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
                "highshelf=f=7500:gain=-2.0:width=1.0,"
                "loudnorm=I=-20:TP=-2:LRA=11"
            )
            subprocess.run([
                "ffmpeg", "-y", "-i", out_raw_wav,
                "-af", af_filters,
                "-ar", str(sr),
                out_mastered_wav
            ], check=True, capture_output=True)
            target_wav = out_mastered_wav
        else:
            target_wav = out_raw_wav

        subprocess.run([
            "ffmpeg", "-y", "-i", target_wav,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            out_mp3
        ], check=True, capture_output=True)

        with open(out_mp3, "rb") as f:
            mp3_bytes = f.read()

        return {
            "duration": duration_sec,
            "gpu_time": gpu_time,
            "rtf": rtf,
            "mp3_bytes": mp3_bytes,
        }


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[1]
    cillian_wav = root / "chatterbox" / "voices" / "cillian_irish_dry.wav"
    if not cillian_wav.exists():
        print(f"Reference wav not found: {cillian_wav}")
        return

    ref_wav_bytes = cillian_wav.read_bytes()
    ref_text = (
        "You find so much empathy in novels, because there you are putting yourself into "
        "somebody else's point of view, and I've always been a big reader."
    )
    test_text = (
        "The story of the Irish Republican Army is one of conviction, conflict, and deep political conviction. "
        "From the Easter Rising of 1916 through the modern era, the movement shaped Ireland's destiny."
    )

    print("Submitting test synthesis to Modal CosyVoice 3...")
    producer = CosyVoiceProducer()
    res = producer.synthesize.remote(
        text=test_text,
        ref_wav_bytes=ref_wav_bytes,
        ref_text=ref_text
    )

    out_file = root / "output" / "cosyvoice3_cillian_test.mp3"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(res["mp3_bytes"])
    print(f"✓ Completed: {out_file} ({len(res['mp3_bytes']):,} bytes)")
    print(f"Duration: {res['duration']}s audio | GPU time: {res['gpu_time']}s | RTF: {res['rtf']}")
