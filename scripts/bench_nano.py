"""Benchmark Chatterbox Nano vs Turbo RTF on local CPU.

Run on zorin:
    pip install git+https://github.com/resemble-ai/chatterbox.git
    python scripts/bench_nano.py

Renders 3 paragraphs with the UK Minter voice, measures wall-clock,
computes RTF (realtime factor). Compare against Turbo's measured
1.24 s/word (STATUS.md, 2026-07-20).
"""
import os
import sys
import time
import wave

VOICE_REF = os.path.join(os.path.dirname(__file__),
                         "..", "chatterbox", "voices", "uk_male_minter.wav")
OUT_DIR = os.path.join(os.path.dirname(__file__),
                       "..", "data", "audiobooks", "_samples", "nano_bench")
os.makedirs(OUT_DIR, exist_ok=True)

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


def wav_duration(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def count_words(text):
    return len(text.split())


def bench(engine_name, model):
    print(f"\n{'='*60}")
    print(f"  {engine_name}")
    print(f"{'='*60}")
    total_audio = 0.0
    total_wall = 0.0
    total_words = 0

    for name, text in PARAGRAPHS.items():
        words = count_words(text)
        out = os.path.join(OUT_DIR, f"{engine_name}_{name}.wav")

        t0 = time.time()
        wav = model.generate(text, audio_prompt_path=VOICE_REF)
        wall = time.time() - t0

        import torchaudio
        torchaudio.save(out, wav.unsqueeze(0) if wav.dim() == 1 else wav,
                        model.sr if hasattr(model, 'sr') else 24000)
        dur = wav_duration(out)

        rtf = wall / dur if dur > 0 else float('inf')
        spw = wall / words if words > 0 else 0

        print(f"  {name}: {words} words, {dur:.1f}s audio, "
              f"{wall:.1f}s wall, RTF={rtf:.2f}, {spw:.2f} s/word")

        total_audio += dur
        total_wall += wall
        total_words += words

    avg_rtf = total_wall / total_audio if total_audio > 0 else 0
    avg_spw = total_wall / total_words if total_words > 0 else 0
    print(f"\n  TOTAL: {total_words} words, {total_audio:.1f}s audio, "
          f"{total_wall:.1f}s wall")
    print(f"  AVG RTF={avg_rtf:.2f}, {avg_spw:.2f} s/word")

    book_words = 130000
    est_hours = (book_words * avg_spw) / 3600
    print(f"  130k-word book estimate: {est_hours:.1f}h")
    return avg_rtf, avg_spw


def main():
    ref = os.path.abspath(VOICE_REF)
    if not os.path.exists(ref):
        print(f"Voice ref not found: {ref}")
        sys.exit(1)

    results = {}

    try:
        from chatterbox.tts import ChatterboxTTS
        print("Loading Chatterbox Turbo (350M)...")
        t0 = time.time()
        turbo = ChatterboxTTS.from_pretrained(device="cpu")
        print(f"  Loaded in {time.time()-t0:.0f}s")
        results["Turbo"] = bench("turbo", turbo)
        del turbo
    except Exception as e:
        print(f"Turbo unavailable: {e}")

    try:
        from chatterbox.tts import ChatterboxTTS
        print("\nLoading Chatterbox Nano (110M)...")
        t0 = time.time()
        nano = ChatterboxTTS.from_pretrained(device="cpu", nano=True)
        print(f"  Loaded in {time.time()-t0:.0f}s")
        results["Nano"] = bench("nano", nano)
        del nano
    except TypeError:
        try:
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            print("\nLoading Chatterbox Nano via TurboTTS(nano=True)...")
            t0 = time.time()
            nano = ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)
            print(f"  Loaded in {time.time()-t0:.0f}s")
            results["Nano"] = bench("nano", nano)
            del nano
        except Exception as e:
            print(f"Nano unavailable: {e}")
    except Exception as e:
        print(f"Nano unavailable: {e}")

    if len(results) == 2:
        print(f"\n{'='*60}")
        print("  COMPARISON")
        print(f"{'='*60}")
        t_rtf, t_spw = results["Turbo"]
        n_rtf, n_spw = results["Nano"]
        print(f"  Turbo: RTF={t_rtf:.2f}, {t_spw:.2f} s/word")
        print(f"  Nano:  RTF={n_rtf:.2f}, {n_spw:.2f} s/word")
        print(f"  Speedup: {t_spw/n_spw:.1f}x" if n_spw > 0 else "")

    print(f"\nSamples in: {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
