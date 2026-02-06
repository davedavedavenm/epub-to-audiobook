#!/usr/bin/env python3
"""
Sampled verification: audio(STT) vs *captured TTS input*.

We can capture exact text sent to Kokoro via tts-proxy (`chunks.jsonl`), but it has no chapter IDs.
This script infers chapter boundaries by pairing:
- conversion container logs: "Processing chapter-<n>_<name>_chunk_<i>_of_<N>"
- chunk capture order in chunks.jsonl (append order matches request order)

Then, for a sample of chapter MP3s, it transcribes the audio and compares the transcript to the
captured text for that chapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import Levenshtein  # type: ignore
from faster_whisper import WhisperModel  # type: ignore


STOP = {
    "the", "and", "that", "with", "from", "this", "have", "were", "your", "their", "there",
    "they", "them", "then", "than", "what", "when", "where", "which", "will", "would", "could",
    "should", "into", "upon", "over", "under", "again", "about", "because", "after", "before",
    "been", "being", "such", "some", "most", "more", "very", "here",
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha1_hex(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()


def normalize_loose(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\\s']", " ", s)
    s = re.sub(r"\\s+", " ", s).strip()
    return s


def words_list(s: str, max_words: int = 250_000) -> list[str]:
    ws = [w for w in normalize_loose(s).split(" ") if w]
    if len(ws) > max_words:
        ws = ws[:max_words]
    return ws


def trigram_set(ws: list[str], max_grams: int = 250_000) -> set[str]:
    grams: set[str] = set()
    if len(ws) < 3:
        return grams
    delim = "\x1f"
    end = min(len(ws) - 2, max_grams)
    for i in range(end):
        grams.add(delim.join((ws[i], ws[i + 1], ws[i + 2])))
    return grams


def multiset_overlap(a: Counter, b: Counter) -> int:
    return sum(min(a[w], b.get(w, 0)) for w in a.keys())


def top_deltas(a: Counter, b: Counter, n: int = 15) -> list[dict]:
    deltas = []
    for w, cnt in a.items():
        if cnt <= 0:
            continue
        if len(w) < 5:
            continue
        if w in STOP:
            continue
        d = int(cnt) - int(b.get(w, 0))
        if d > 0:
            deltas.append((w, d))
    deltas.sort(key=lambda x: x[1], reverse=True)
    return [{"word": w, "delta": d} for (w, d) in deltas[:n]]


def mp3_duration_s(mp3: Path) -> float | None:
    try:
        cp = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(mp3)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        v = (cp.stdout or "").strip()
        if not v:
            return None
        return float(v)
    except Exception:
        return None


def read_captured_chunks(chunks_jsonl: Path) -> list[dict]:
    out: list[dict] = []
    if not chunks_jsonl.exists():
        return out
    with chunks_jsonl.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            out.append(obj)
    return out


_re_chunk = re.compile(r"Processing (chapter-(\\d+)_.*?_chunk_(\\d+)_of_(\\d+))")


@dataclass(frozen=True)
class ChunkEvent:
    chapter_num: int
    chunk_idx: int
    chunk_total: int


def parse_chunk_events(converter_log: str) -> list[ChunkEvent]:
    events: list[ChunkEvent] = []
    for m in _re_chunk.finditer(converter_log or ""):
        try:
            chap = int(m.group(2))
            idx = int(m.group(3))
            tot = int(m.group(4))
        except Exception:
            continue
        events.append(ChunkEvent(chapter_num=chap, chunk_idx=idx, chunk_total=tot))
    return events


def infer_chapter_texts(captured: list[dict], events: list[ChunkEvent]) -> dict[int, list[str]]:
    """Map chapter_num -> list of captured loose texts by pairing in order."""
    loose_stream = [str(o.get("loose") or o.get("text") or "") for o in captured]

    # Pair in sequence. If there are more captures than chunk events, we drop the prefix before first chunk event
    # by aligning from the end: assume conversion TTS requests dominate during active conversion.
    if not events or not loose_stream:
        return {}

    # Heuristic: the conversion chunk events count should be close to the number of TTS calls for chapters.
    # If the loose stream is longer, align the tail.
    start = max(0, len(loose_stream) - len(events))
    stream = loose_stream[start:]

    chapter_to_texts: dict[int, list[str]] = defaultdict(list)
    n = min(len(stream), len(events))
    for i in range(n):
        chap = events[i].chapter_num
        txt = stream[i]
        if txt:
            chapter_to_texts[chap].append(txt)
    return dict(chapter_to_texts)


def pick_chapter_mp3s(outdir: Path, max_files: int, seed: str) -> list[Path]:
    mp3s = sorted(outdir.glob("*.mp3"))
    # Only chapter-like names: 4-digit prefix underscore
    mp3s = [p for p in mp3s if re.match(r"^\\d{4}_", p.name)]
    if not mp3s:
        return []

    # Filter out obvious front matter by filename token.
    bad = re.compile(r"(contents|copyright|dedication|also_by|isbn|library_of_congress)", re.IGNORECASE)
    cand = [p for p in mp3s if not bad.search(p.name)]
    if not cand:
        cand = mp3s

    # Prefer non-trivial durations (narrative).
    nontrivial: list[Path] = []
    for p in cand:
        d = mp3_duration_s(p)
        if d is None or d >= 60.0:
            nontrivial.append(p)
    if nontrivial:
        cand = nontrivial

    r = random.Random(sha1_hex(seed))
    # Choose largest (likely narrative) and a few randoms.
    picks = [max(cand, key=lambda p: p.stat().st_size)]
    rest = [p for p in cand if p not in picks]
    r.shuffle(rest)
    picks.extend(rest[: max(0, max_files - len(picks))])

    out: list[Path] = []
    seen = set()
    for p in picks:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= max_files:
            break
    return out


def transcribe(model: WhisperModel, mp3: Path, language: str | None) -> str:
    segments, _info = model.transcribe(
        str(mp3),
        language=language,
        beam_size=1,
        vad_filter=True,
    )
    texts: list[str] = []
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            texts.append(t)
    return " ".join(texts)


def chapter_num_from_filename(p: Path) -> int | None:
    m = re.match(r"^(\\d{4})_", p.name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--chunks-jsonl", required=True)
    ap.add_argument("--converter-log", required=True)
    ap.add_argument("--model", default=os.environ.get("AUDIO_ASR_VERIFY_MODEL", "base"))
    ap.add_argument("--max-files", type=int, default=4)
    ap.add_argument("--language", default=os.environ.get("AUDIO_ASR_VERIFY_LANGUAGE", "en"))
    ap.add_argument("--cpu-threads", type=int, default=int(os.environ.get("AUDIO_ASR_VERIFY_CPU_THREADS", "4")))
    args = ap.parse_args()

    job_id = args.job_id
    outdir = Path(args.outdir)
    chunks_jsonl = Path(args.chunks_jsonl)
    converter_log = Path(args.converter_log)

    if not outdir.exists():
        print(json.dumps({"ok": False, "error": "outdir missing", "outdir": str(outdir)}))
        return 2
    if not chunks_jsonl.exists():
        print(json.dumps({"ok": False, "error": "chunks.jsonl missing", "chunks": str(chunks_jsonl)}))
        return 2
    if not converter_log.exists():
        print(json.dumps({"ok": False, "error": "converter log missing", "log": str(converter_log)}))
        return 2

    captured = read_captured_chunks(chunks_jsonl)
    events = parse_chunk_events(converter_log.read_text(encoding="utf-8", errors="replace"))
    chapter_to_texts = infer_chapter_texts(captured, events)

    sample = pick_chapter_mp3s(outdir, max(1, int(args.max_files)), seed=job_id)
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=int(args.cpu_threads))

    per_file: list[dict] = []
    for mp3 in sample:
        chap = chapter_num_from_filename(mp3)
        expected = " ".join(chapter_to_texts.get(chap or -1, []))
        exp_words = words_list(expected, max_words=60_000)

        asr_text = transcribe(model, mp3, args.language or None)
        asr_words = words_list(asr_text, max_words=60_000)

        entry = {
            "file": mp3.name,
            "chapter_num": chap,
            "duration_s": mp3_duration_s(mp3),
            "expected_words": len(exp_words),
            "asr_words": len(asr_words),
            "metrics": None,
        }

        if chap is None or not exp_words or not asr_words:
            entry["metrics"] = {"ok": False, "reason": "missing expected text (no mapping yet) or ASR empty"}
            per_file.append(entry)
            continue

        exp_c = Counter(exp_words)
        asr_c = Counter(asr_words)
        overlap = multiset_overlap(asr_c, exp_c)
        w_asr = overlap / (sum(asr_c.values()) or 1)
        w_exp = overlap / (sum(exp_c.values()) or 1)

        exp_tri = trigram_set(exp_words, max_grams=200_000)
        asr_tri = trigram_set(asr_words, max_grams=200_000)
        tri_inter = len(exp_tri & asr_tri)
        tri_asr = tri_inter / (len(asr_tri) or 1)
        tri_exp = tri_inter / (len(exp_tri) or 1)

        # Order-sensitive ratio on bounded samples.
        a = " ".join(asr_words[:5000])
        b = " ".join(exp_words[:5000])
        seq_ratio = round(Levenshtein.ratio(a, b), 6) if a and b else None

        entry["metrics"] = {
            "ok": True,
            "word_overlap_ratio_of_asr": round(w_asr, 6),
            "word_overlap_ratio_of_expected": round(w_exp, 6),
            "trigram_overlap_ratio_of_asr": round(tri_asr, 6),
            "trigram_overlap_ratio_of_expected": round(tri_exp, 6),
            "sampled_seq_ratio_first_5000_words": seq_ratio,
            "top_missing_words_in_asr": top_deltas(exp_c, asr_c, n=12),
            "top_extra_words_in_asr": top_deltas(asr_c, exp_c, n=12),
        }
        per_file.append(entry)

    out = {
        "ok": True,
        "job_id": job_id,
        "created_at": now_iso(),
        "model": args.model,
        "sample_count": len(per_file),
        "chunks_total": len(captured),
        "chunk_events_total": len(events),
        "chapters_mapped": len(chapter_to_texts),
        "files": per_file,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

