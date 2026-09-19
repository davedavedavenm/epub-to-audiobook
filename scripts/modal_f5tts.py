"""
modal_f5tts.py — Production-ready F5-TTS (300M) voice cloning on Modal GPU.

Architecture:
- Model: SWivid/F5-TTS (Flow-matching non-autoregressive diffusion, ~330M parameters)
- Hardware: Modal GPU (Tesla T4 or L4)
- RTF: ~0.10 (10x faster than realtime)
- Scaledown window: 2s (zero idle waste)
"""

import modal
import time
import subprocess
from pathlib import Path

app = modal.App("homelab-f5tts")

f5_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .pip_install(
        "f5-tts>=0.1.0",
        "torch",
        "torchaudio",
        "soundfile>=0.13",
        "numpy"
    )
)


@app.cls(image=f5_image, gpu="T4", timeout=600, scaledown_window=2)
class F5TTSProducer:
    @modal.enter()
    def setup(self):
        import torch
        from f5_tts.api import F5TTS

        print(f"Loading F5-TTS on {torch.cuda.get_device_name(0)}...")
        self.f5 = F5TTS(device="cuda")
        self.sample_rate = 24000
        print("F5-TTS model loaded and ready.")

    @modal.method()
    def synthesize(
        self,
        text: str,
        ref_wav_bytes: bytes,
        ref_text: str,
        seed: int = 42,
        apply_mastering: bool = True
    ) -> dict:
        import soundfile as sf

        t0 = time.time()
        ref_path = "/tmp/f5_ref.wav"
        out_raw_wav = "/tmp/f5_out_raw.wav"
        out_mastered_wav = "/tmp/f5_out_mastered.wav"
        out_mp3 = "/tmp/f5_out.mp3"

        with open(ref_path, "wb") as f:
            f.write(ref_wav_bytes)

        wav, sr, _ = self.f5.infer(
            ref_file=ref_path,
            ref_text=ref_text,
            gen_text=text,
            file_wave=out_raw_wav,
            seed=seed
        )

        audio_data, sr = sf.read(out_raw_wav)
        duration_sec = round(len(audio_data) / sr, 2)
        gpu_time = round(time.time() - t0, 2)
        rtf = round(gpu_time / max(duration_sec, 0.01), 3)

        if apply_mastering:
            # Broadcast mastering chain: warmth EQ, de-esser, EBU R128 (-20 LUFS)
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

    print("Submitting test synthesis to Modal F5-TTS...")
    producer = F5TTSProducer()
    res = producer.synthesize.remote(
        text=test_text,
        ref_wav_bytes=ref_wav_bytes,
        ref_text=ref_text
    )

    out_file = root / "output" / "f5tts_cillian_test.mp3"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(res["mp3_bytes"])
    print(f"✓ Completed: {out_file} ({len(res['mp3_bytes']):,} bytes)")
    print(f"Duration: {res['duration']}s audio | GPU time: {res['gpu_time']}s | RTF: {res['rtf']}")
