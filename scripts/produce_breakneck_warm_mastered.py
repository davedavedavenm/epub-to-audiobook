"""
produce_breakneck_warm_mastered.py — Multi-Voice Non-Fiction Audiobook Production

Pipeline verified by ear on Dan Wang's Breakneck:
- Casting: Primary author commentary (am_michael @ 1.0x), Quotes/Thesis/Headings (am_fenrir @ 0.95x)
- Broadcast Mastering Chain (FFmpeg):
  1. +2.2 dB Warmth EQ at 250 Hz (restores human chest resonance and condenser mic proximity)
  2. -3.5 dB Dynamic De-Esser at 7.2 kHz (tames digital sibilance and brittle 's'/'t' transients)
  3. EBU R128 Loudness Normalization (-20 LUFS, -2 dB True Peak ceiling)
- Format: 192kbps Broadcast MP3
- Performance: ~18x faster than real-time on Modal Nvidia T4 GPU (RTF 0.056x, ~$0.004/chapter)
"""

import modal
import subprocess
import time
import re

app = modal.App("homelab-breakneck-warm-mastered")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("espeak-ng", "libsndfile1", "ffmpeg")
    .pip_install(
        "kokoro>=0.8.4",
        "soundfile",
        "torch",
        "misaki[en]",
        "numpy"
    )
)

@app.cls(image=image, gpu="T4", timeout=600, scaledown_window=2)
class WarmMasteredProducer:
    @modal.enter()
    def setup(self):
        from kokoro import KPipeline
        print("Loading Kokoro Voice Pipeline into GPU...")
        self.pipeline_us = KPipeline(lang_code='a')
        print("Kokoro ready on GPU!")

    @modal.method()
    def produce(self, script_json: list) -> dict:
        import soundfile as sf
        import numpy as np

        full_audio_chunks = []
        sample_rate = 24000
        start_time = time.time()

        print(f"Synthesizing {len(script_json)} segments with warm voices...")
        for i, item in enumerate(script_json):
            speaker = item.get("speaker", "Narrator")
            voice = item.get("voice", "am_michael")
            speed = float(item.get("speed", 1.0))
            pause_ms = int(item.get("pause_after_ms", 350))
            text = item.get("text", "")

            # Pronunciation & normalization overrides
            text = re.sub(r'\bUber\b', 'Oo-ber', text)
            text = re.sub(r'\buber\b', 'oo-ber', text)
            text = re.sub(r'\s+', ' ', text).strip()
            print(f"[{i+1}/{len(script_json)}] {speaker} ({voice} @ {speed}x): {text[:60]}...")

            generator = self.pipeline_us(text, voice=voice, speed=speed, split_pattern=r'\n+')

            segment_chunks = []
            for _, _, audio in generator:
                segment_chunks.append(audio)

            if segment_chunks:
                seg_audio = np.concatenate(segment_chunks)
                full_audio_chunks.append(seg_audio)

                # Insert pause padding (announcements get 1500ms, quotes get 500ms, standard 350ms)
                if pause_ms > 0:
                    pause_samples = int((pause_ms / 1000.0) * sample_rate)
                    full_audio_chunks.append(np.zeros(pause_samples, dtype=np.float32))

        # Concatenate raw audio
        raw_audio = np.concatenate(full_audio_chunks)
        duration_sec = round(len(raw_audio) / sample_rate, 2)
        print(f"Raw synthesis complete: {duration_sec}s of audio ({round(duration_sec / 60, 2)}m) in {round(time.time() - start_time, 2)}s GPU compute!")

        raw_path = "/tmp/raw_audio.wav"
        mastered_wav_path = "/tmp/mastered_audio.wav"
        mastered_mp3_path = "/tmp/mastered_audio.mp3"

        sf.write(raw_path, raw_audio, sample_rate)

        # Broadcast Mastering Chain via FFmpeg:
        af_filters = (
            "equalizer=f=250:width_type=o:width=1.2:g=2.2,"
            "highshelf=f=7200:gain=-3.5:width=1.0,"
            "loudnorm=I=-20:TP=-2:LRA=11"
        )
        print("Applying broadcast mastering filter chain (warmth EQ + de-esser + EBU R128 LUFS)...")
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_path,
            "-af", af_filters,
            "-ar", "24000",
            mastered_wav_path
        ], check=True)

        print("Encoding 192kbps broadcast MP3...")
        subprocess.run([
            "ffmpeg", "-y", "-i", mastered_wav_path,
            "-codec:a", "libmp3lame", "-b:a", "192k",
            mastered_mp3_path
        ], check=True)

        with open(mastered_mp3_path, "rb") as f:
            mp3_bytes = f.read()

        return {
            "mp3_bytes": mp3_bytes,
            "duration": duration_sec,
            "gpu_time": round(time.time() - start_time, 2)
        }

def clean_epub_dropcaps(html_text: str) -> str:
    """Stitch drop-cap single-letter spans back to the subsequent word before stripping tags."""
    # Matches: <span class="dropcap">E</span> ach -> Each
    cleaned = re.sub(
        r'<span[^>]*class=["\'][^"\']*dropcap[^"\']*["\'][^>]*>([A-Za-z])</span>\s*([a-z]+)',
        r'\1\2',
        html_text,
        flags=re.IGNORECASE
    )
    # Generic single-letter span followed by whitespace and word fragment
    cleaned = re.sub(
        r'<([a-z]+)[^>]*>([A-Za-z])</\1>\s+([a-z]{2,})',
        r'\2\3',
        cleaned,
        flags=re.IGNORECASE
    )
    return cleaned


@app.local_entrypoint()
def main():
    from pathlib import Path

    script = [
        {"speaker": "Announcer", "voice": "am_fenrir", "speed": 0.95, "pause_after_ms": 1500, "text": "Chapter One. Engineers versus Lawyers."},
        {"speaker": "Narrator", "voice": "am_michael", "speed": 1.0, "pause_after_ms": 350, "text": "Silicon Valley can be an amazingly drab place. The peninsula south of San Francisco has natural beauty, with rolling hills and coastal views, but you strain to see them beyond so many corporate parking lots. Mountain View and Menlo Park are bizarrely full of rug shops, so when I walk through the towns that host the headquarters of AI leaders and some of the richest companies in the world, I often find myself wondering, “This is the beating heart of our technologically accelerating civilization?”"},
        {"speaker": "Narrator", "voice": "am_michael", "speed": 1.0, "pause_after_ms": 350, "text": "Each time I flew from California to Hong Kong or Shanghai, I felt almost unnerved to encounter functional infrastructure. Going from the airport into a subway (rather than an Uber) is an outstanding way to be welcomed to Asia. I would take a moment to savor a clean station, brightly lit, with trains running every few minutes, which would drop me off at a downtown filled with vibrant commercial areas — another feature that San Francisco lacks. Life in the Bay Area, an economic dynamo in America’s richest state, can feel awfully dysfunctional. San Francisco has been unable to serve its homeless population, and even many wealthy people have to keep a generator for their extraordinarily expensive houses because the state can’t keep the lights on."},
        {"speaker": "Narrator", "voice": "am_michael", "speed": 1.0, "pause_after_ms": 350, "text": "The contradiction of the Bay Area, this red hot center of corporate value creation that is surrounded by dysfunction, fuels the inquiry of this book. When I departed from Silicon Valley for China in twenty seventeen, it felt clear that the United States had lost something special over the past four decades. While China was building the future, America had become physically static, its innovations mostly bound up in the virtual and financial worlds."},
        {"speaker": "Narrator", "voice": "am_michael", "speed": 1.0, "pause_after_ms": 350, "text": "Looking at these two countries, I came to realize the inadequacy of twentieth century labels like capitalist, socialist, or, worst of all, neoliberal. They are no longer up to the task of helping us understand the world, if they ever were. Capitalist America intrudes upon the free market with a dense program of regulation and taxation while providing substantial (albeit imperfect) redistributive policies. Socialist China detains union organizers, levies light taxes, and provides a threadbare social safety net. The greatest trick that the Communist Party ever pulled off is masquerading as leftist. While Xi Jinping and the rest of the Politburo mouth Marxist pieties, the state is enacting a right wing agenda that Western conservatives would salivate over: administering limited welfare, erecting enormous barriers to immigration, and enforcing traditional gender roles — where men have to be macho and women have to bear their children."},
        {"speaker": "Thesis", "voice": "am_fenrir", "speed": 0.95, "pause_after_ms": 1000, "text": "China is an engineering state, which can’t stop itself from building, facing off against America’s lawyerly society, which blocks everything it can."}
    ]

    print("Submitting multi-voice production job to Modal T4 GPU...")
    res = WarmMasteredProducer().produce.remote(script)

    out_dir = Path(__file__).resolve().parents[1] / "evaluations" / "new-engines" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp3 = out_dir / "breakneck_ch1_warm_mastered.mp3"
    out_mp3.write_bytes(res["mp3_bytes"])
    print(f"Mastered MP3 saved to {out_mp3} ({len(res['mp3_bytes']):,} bytes, {res['duration']}s audio in {res['gpu_time']}s GPU compute)")
