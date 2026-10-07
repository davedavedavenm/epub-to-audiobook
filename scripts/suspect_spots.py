"""suspect_spots.py - list the few places in a chapter most worth a human listen (no GPU, no LLM).

The per-chunk ASR audit proves every word is present; it cannot hear a second of garble inside a
sentence whose words still come through (Dave heard two in the first Modal Preface, at 2:40 and
4:40). Whisper's per-word probability drops on exactly that kind of audio, so this ranks the
clusters of low-confidence words and prints timestamps to spot-check - a short list instead of
listening to the whole chapter. It is a pointer for ears, not a verdict: on the first Modal
Preface its 12 flags included 2 of the 4 spots Dave reported (2:46 ~ his 2:40, 10:46 ~ his 10:40)
and missed 4:40 and the 8:16 cut-off; most other flags were unusual names.

Runs in the webapp container on Zorin (faster-whisper):
    python suspect_spots.py CHAPTER.mp3 [--offset SECONDS] [--top 8] [--below 0.35]
--offset adds the chapter's start time in the m4b, so the timestamps match the player.
"""
import argparse
import os


def clusters(words, below: float, gap: float = 3.0) -> list:
    """words = [(start, end, word, prob)] -> [(start, end, min_prob, text)] of nearby low-prob words."""
    low = [w for w in words if w[3] < below]
    out, cur = [], []
    for w in low:
        if cur and w[0] - cur[-1][1] > gap:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [(c[0][0], c[-1][1], min(x[3] for x in c), " ".join(x[2].strip() for x in c)) for c in out]


def fmt(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("audio")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--below", type=float, default=0.35)
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device="cpu", compute_type="int8", download_root=os.environ.get("WHISPER_MODEL_DIR"))
    segs, _ = m.transcribe(a.audio, language="en", beam_size=5, word_timestamps=True,
                           condition_on_previous_text=False)
    words = [(w.start, w.end, w.word, w.probability) for s in segs for w in (s.words or [])]
    ranked = sorted(clusters(words, a.below), key=lambda c: (c[2], -(c[1] - c[0])))[: a.top]
    print(f"{len(words)} words; {len(ranked)} spots to check (lowest confidence first):")
    for s, e, p, text in sorted(ranked):
        print(f"  {fmt(s + a.offset)}  (p={p:.2f})  {text[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
