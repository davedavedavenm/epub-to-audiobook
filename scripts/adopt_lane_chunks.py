"""adopt_lane_chunks.py - let chunks rendered elsewhere (Colab lane) join a Modal book render.

The Colab runner has the health/duration/muffled gates but not the Modal worker's per-take word
check or voice match. Its chunks are therefore audited independently first:
    chunk_asr_audit.py ... --json asr.json      (webapp container)
    voice_audit.py ...     --json voice.json    (chatterbox-nano container)
then this script keeps only the chunks that meet the SAME bars as the Modal worker and writes the
Modal resume sidecar (text + sampling key) next to them. Failing wavs are deleted, so the next
`modal_higgs_book.py` run re-renders exactly those and assembles the chapter with the V3 join.

    python scripts/adopt_lane_chunks.py BUNDLE.zip CHUNK_DIR SLUG --asr asr.json --voice voice.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_VOICE_SIM = 0.90      # same bars as scripts/modal_higgs_book.py / higgs_colab_runner.take_penalty
MIN_ROLLOFF_HZ = 1800.0
# Voice similarity is only judged on clips >= 3 s (as roll-off is): on 2-3 s sentence clips the speaker
# embedding scored 0.84-0.89 for takes with every word present, while the whole chunks Dave heard as
# "not Cillian" scored 0.81 against 0.91-0.97 (2026-10-08, Armed Struggle fill rounds 2-4).
MIN_VOICE_DUR_S = 3.0


def verdict(asr: dict | None, voice: dict | None, lenient: bool = False, accept_words: bool = False) -> tuple[bool, str]:
    """(keep?, reason). A chunk without an ASR row is never adopted (completeness unproven)."""
    if asr is None:
        return False, "no ASR audit"
    if asr.get("bad") and not accept_words:
        return False, "words"
    if voice and not lenient:
        if voice.get("sim") is not None and voice["sim"] < MIN_VOICE_SIM                 and (voice.get("dur") or MIN_VOICE_DUR_S) >= MIN_VOICE_DUR_S:
            return False, "voice"
        if voice.get("roll") is not None and voice["roll"] < MIN_ROLLOFF_HZ:
            return False, "muffled"
    return True, ""


def main() -> int:
    import os
    import tempfile
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())   # the runner module wants a work dir at import
    import higgs_colab_runner as hr
    from higgs_book_plan import chunk_key, load_bundle
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("chunk_dir")
    ap.add_argument("slug")
    ap.add_argument("--asr", required=True)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--model", default="bosonai/higgs-audio-v3-tts-4b")
    ap.add_argument("--lenient", action="store_true",
                    help="keep a take whose words are all present even if muffled / voice-low (recorded)")
    ap.add_argument("--accept-words", default="",
                    help="comma list of fill indices whose words flag is a known ASR mismatch (recorded)")
    a = ap.parse_args()
    accept = {int(x) for x in a.accept_words.split(",") if x.strip()}
    _, pay = load_bundle(Path(a.bundle))
    recipe = f"{a.model} {json.dumps(hr.SAMPLING, sort_keys=True)}"   # what the lane runner sent
    asr = {r["i"]: r for r in json.loads(Path(a.asr).read_text(encoding="utf-8")) if r.get("slug") == a.slug}
    voice = {int(r["chunk"][:4]): r for r in json.loads(Path(a.voice).read_text(encoding="utf-8"))}
    d = Path(a.chunk_dir) / a.slug
    kept = dropped = 0
    accepted: dict = {}
    reasons: dict = {}
    for i, ch in enumerate(pay[a.slug]["chunks"], 1):
        wav = d / f"{i:04d}.wav"
        if not wav.exists():
            continue
        keep, why = verdict(asr.get(i), voice.get(i), a.lenient, i in accept)
        strict_keep, strict_why = verdict(asr.get(i), voice.get(i))
        if keep:
            text = ch.get("tagged") or ch["text"]
            (d / f"{i:04d}.json").write_text(json.dumps({
                "key": chunk_key(text, recipe), "ok": True,
                "metrics": {"source": "colab-lane", "asr_cover": asr[i]["cover"],
                            "sim": (voice.get(i) or {}).get("sim"), "roll": (voice.get(i) or {}).get("roll"),
                            **({"accepted_despite": strict_why} if not strict_keep else {})}}),
                encoding="utf-8")
            kept += 1
            if not strict_keep:
                accepted[i] = strict_why
        else:
            wav.unlink()
            (d / f"{i:04d}.json").unlink(missing_ok=True)
            dropped += 1
            reasons[why] = reasons.get(why, 0) + 1
    print(json.dumps({"slug": a.slug, "adopted": kept, "dropped_for_rerender": dropped, "why": reasons,
                      "accepted_despite": accepted}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
