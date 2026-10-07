"""voice_audit.py - score rendered chunks against the reference voice (no GPU, no LLM).

Per chunk: voice similarity (speaker-embedding cosine vs the reference, Chatterbox voice encoder) and
95 % spectral roll-off (muffled / "speakerphone" takes roll off at 1.8-2.5 kHz; the Cillian reference
at ~4.7 kHz). Calibrated on the Armed Struggle Preface (2026-10-07): the chunks Dave heard as "not
Cillian" scored 0.813/0.816 (others 0.914-0.967); the ones he heard as muffled rolled off < 3.3 kHz.

Runs inside the chatterbox container on Zorin (it has torch, librosa and the encoder weights):

    docker cp chunks/ch08 chatterbox-nano:/tmp/va && docker cp scripts/voice_audit.py chatterbox-nano:/tmp/
    docker exec chatterbox-nano python /tmp/voice_audit.py /tmp/va --ref /app/voices/cillian_irish.wav
"""
import argparse
import glob
import json
import os

import numpy as np
import soundfile as sf

MIN_VOICE_SIM = 0.90          # same thresholds as the Modal worker (scripts/modal_higgs_book.py)
MIN_ROLLOFF_HZ = 1800.0     # higgs_colab_runner.MIN_ROLLOFF_HZ (Dave accepted 1.6-2.3 kHz takes)


def rolloff_hz(w, sr, frac=0.95):
    n, hop = 2048, 1024
    if len(w) < n * 2:
        return None
    frames = np.lib.stride_tricks.sliding_window_view(w, n)[::hop] * np.hanning(n)
    spec = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    energy = spec.sum(axis=1)
    p = spec[energy > np.percentile(energy, 40)].mean(axis=0)
    cum = np.cumsum(p) / max(float(p.sum()), 1e-12)
    return float(np.fft.rfftfreq(n, 1 / sr)[min(int(np.searchsorted(cum, frac)), len(cum) - 1)])


def main() -> int:
    import librosa
    from safetensors.torch import load_file
    from chatterbox.models.voice_encoder.voice_encoder import VoiceEncoder

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", help="folder of NNNN.wav chunk files")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--weights", default=None, help="ve.safetensors (default: chatterbox-nano in the HF cache)")
    ap.add_argument("--json", default=None, help="also write the per-chunk rows to this file")
    a = ap.parse_args()
    weights = a.weights or glob.glob("/data/hf/hub/models--ResembleAI--chatterbox-nano/snapshots/*/ve.safetensors")[0]
    ve = VoiceEncoder()
    ve.load_state_dict(load_file(weights))
    ve.eval()

    def load(p):
        w, sr = sf.read(p, dtype="float32")
        return (w.mean(axis=1) if w.ndim > 1 else w), sr

    def embed(w, sr):
        w16 = librosa.resample(w, orig_sr=sr, target_sr=16000)
        return None if len(w16) < 16000 * 1.6 else ve.embeds_from_wavs([w16], sample_rate=16000, as_spk=True)

    ref = embed(*load(a.ref))
    rows = []
    for f in sorted(glob.glob(os.path.join(a.folder, "*.wav"))):
        w, sr = load(f)
        e = embed(w, sr)
        sim = None if e is None else round(float(np.dot(ref, e)), 3)
        roll = rolloff_hz(w, sr) if len(w) / sr >= 3.0 else None
        flags = [n for n, bad in (("voice", sim is not None and sim < MIN_VOICE_SIM),
                                  ("muffled", roll is not None and roll < MIN_ROLLOFF_HZ)) if bad]
        rows.append({"chunk": os.path.basename(f), "dur": round(len(w) / sr, 1), "sim": sim,
                     "roll": None if roll is None else round(roll), "flags": flags})
        print(json.dumps(rows[-1]), flush=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
    sims = [r["sim"] for r in rows if r["sim"] is not None]
    print(json.dumps({"chunks": len(rows), "voice_flags": sum("voice" in r["flags"] for r in rows),
                      "muffled_flags": sum("muffled" in r["flags"] for r in rows),
                      "sim_min": min(sims, default=None), "sim_median": float(np.median(sims)) if sims else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
