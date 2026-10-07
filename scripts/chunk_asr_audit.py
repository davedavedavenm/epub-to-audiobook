"""chunk_asr_audit.py - check every rendered chunk says all of its text (no GPU, no LLM).

Transcribes each NNNN.wav with faster-whisper and aligns it against that chunk's own text
(webapp/qa_asr.py normalisation: numbers, apostrophes). Per chunk it reports
  cover  - share of source words heard
  tail   - source words missing after the last word heard (truncation: "cuts off at 199x")
  drops  - runs of >= 3 consecutive source words not heard (lost words mid-chunk)
A whole-chapter ASR ratio hides these: one truncated chunk among 27 still scores ~98 %.

Runs inside the webapp container on Zorin (faster-whisper is installed there):

    python chunk_asr_audit.py bundle.zip chunks/ ch08 [--model small] [--json out.json]
"""
import argparse
import json
import os
import sys
import zipfile

# a qa_asr.py next to this script (copied in for an audit) wins over the deployed /app copy
for _p in ("/app", "/app/webapp", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"),
           os.path.dirname(os.path.abspath(__file__))):
    if os.path.isdir(_p):
        if _p in sys.path:
            sys.path.remove(_p)
        sys.path.insert(0, _p)

TAIL_BAD = 3          # >= 3 source words missing at the end = truncated
DROP_RUN_BAD = 3      # >= 3 consecutive words missing mid-chunk


def audit_chunk(source: str, transcript: str) -> dict:
    import qa_asr
    rep = qa_asr.diff_report(source, transcript)
    n = rep["n_source"]
    s = qa_asr.normalize_words(source)
    h = qa_asr.normalize_words(transcript)
    import difflib
    blocks = [b for b in difflib.SequenceMatcher(a=s, b=h, autojunk=False).get_matching_blocks() if b.size]
    last = (blocks[-1].a + blocks[-1].size) if blocks else 0
    drops = [d for d in rep["divergences"] if d["type"] in ("drop", "sub")
             and len(d["source"]) - len(d["heard"]) >= DROP_RUN_BAD and d["at"] < last]
    tail = n - last
    return {"cover": round(rep["n_match"] / max(n, 1), 3), "tail": tail, "words": n,
            "drops": [d["context"] for d in drops][:3],
            "bad": tail >= TAIL_BAD or bool(drops)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("chunk_dir")
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--model", default="small")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    model_dir = os.environ.get("WHISPER_MODEL_DIR")
    model = WhisperModel(a.model, device="cpu", compute_type="int8", download_root=model_dir)
    out = []
    with zipfile.ZipFile(a.bundle) as z:
        for slug in a.slugs:
            chunks = json.loads(z.read(f"payloads/{slug}.json"))["chunks"]
            for i, ch in enumerate(chunks, 1):
                wav = os.path.join(a.chunk_dir, slug, f"{i:04d}.wav")
                if not os.path.exists(wav):
                    continue
                segs, _ = model.transcribe(wav, language="en", beam_size=5, condition_on_previous_text=False)
                heard = " ".join(s.text for s in segs)
                r = {"slug": slug, "i": i, **audit_chunk(ch["text"], heard)}
                if r["bad"]:
                    r["heard_end"] = heard[-80:]
                    r["text_end"] = ch["text"][-80:]
                out.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
    bad = [r for r in out if r["bad"]]
    print(json.dumps({"chunks": len(out), "bad": len(bad), "truncated": sum(r["tail"] >= TAIL_BAD for r in out),
                      "mid_drops": sum(bool(r["drops"]) for r in out)}))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
