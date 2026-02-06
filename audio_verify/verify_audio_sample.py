#!/usr/bin/env python3
"""
Sampled "audio fidelity" verification.

Goal: detect obvious dropped / added words by transcribing a small sample of MP3 outputs
and aligning that transcript against the EPUB source text.

This is intentionally approximate:
- It is not forced-alignment.
- It is not a full-book transcription (too expensive).
- It is designed to catch systematic pipeline bugs (empty chapters, truncation, dropped segments).
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
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import Levenshtein  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
import ebooklib  # type: ignore
from ebooklib import epub  # type: ignore
from faster_whisper import WhisperModel  # type: ignore


STOP = {
    "the", "and", "that", "with", "from", "this", "have", "were", "your", "their", "there",
    "they", "them", "then", "than", "what", "when", "where", "which", "will", "would", "could",
    "should", "into", "upon", "over", "under", "again", "about", "because", "after", "before",
    "been", "being", "such", "some", "most", "more", "very", "here",
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_append(path: Path | None, msg: str):
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.read_text(encoding="utf-8", errors="replace") + msg + "\n", encoding="utf-8")
    except Exception:
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            return


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


def sha256_hex_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def extract_epub_text(epub_path: Path) -> str:
    book = epub.read_epub(str(epub_path))
    parts: list[str] = []
    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        try:
            html = item.get_content()
        except Exception:
            continue
        try:
            soup = BeautifulSoup(html, "lxml")
            txt = soup.get_text(" ", strip=True)
            if txt:
                parts.append(txt)
        except Exception:
            continue
    return "\n".join(parts)


def mp3_duration_s(mp3: Path) -> float | None:
    # Use ffprobe (available via ffmpeg package).
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


def pick_sample_files(files: list[Path], max_files: int, seed: str) -> list[Path]:
    if not files:
        return []

    # Skip trivially small tracks (titles, very short stubs), but keep at least 1 if that's all we have.
    nontrivial = [f for f in files if f.stat().st_size >= 64_000]  # ~64KB
    if not nontrivial:
        nontrivial = files[:]

    # Deterministic randomness per job.
    r = random.Random(hashlib.sha1(seed.encode("utf-8")).hexdigest())

    # Candidate picks:
    picks: list[Path] = []
    # 1) First nontrivial file (often includes early structure).
    picks.append(nontrivial[0])
    # 2) Largest by size (often a long chapter).
    picks.append(max(nontrivial, key=lambda p: p.stat().st_size))

    # 3) Random picks from the rest.
    remaining = [p for p in nontrivial if p not in picks]
    r.shuffle(remaining)
    picks.extend(remaining[: max(0, max_files - len(picks))])

    # De-dupe while preserving order.
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


@dataclass
class AlignResult:
    start_idx: int
    window_words: list[str]
    trigram_overlap_book: float
    trigram_overlap_asr: float
    loose_word_overlap_book: float
    loose_word_overlap_asr: float
    seq_ratio: float | None
    lev_norm: float | None
    missing_top: list[dict]
    extra_top: list[dict]


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


def top_deltas(a: Counter, b: Counter, n: int = 20) -> list[dict]:
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


def align_asr_to_book(asr_words: list[str], book_words: list[str]) -> AlignResult | None:
    if len(asr_words) < 50 or len(book_words) < 200:
        return None

    # Build a cheap inverted index of content-ish words -> positions.
    index: dict[str, list[int]] = {}
    for i, w in enumerate(book_words):
        if len(w) < 5 or w in STOP:
            continue
        lst = index.get(w)
        if lst is None:
            index[w] = [i]
        elif len(lst) < 500:
            lst.append(i)

    # Pick anchor words that are rare in the book (more distinctive).
    anchors: list[tuple[str, int, int]] = []  # (word, asr_pos, book_freq)
    seen = set()
    for i, w in enumerate(asr_words):
        if len(w) < 5 or w in STOP or w in seen:
            continue
        seen.add(w)
        freq = len(index.get(w, []))
        if freq == 0:
            continue
        anchors.append((w, i, freq))
        if len(anchors) >= 40:
            break
    if not anchors:
        return None
    anchors.sort(key=lambda x: x[2])  # rarest first
    anchors = anchors[:15]

    # Candidate start positions derived from anchor matches.
    candidates: set[int] = set()
    for w, asr_i, _freq in anchors:
        for pos in index.get(w, []):
            start = max(0, pos - asr_i)
            candidates.add(start)
            # Also try slightly shifted starts (to tolerate ASR insertions/deletions).
            candidates.add(max(0, start - 50))
            candidates.add(max(0, start - 100))
            candidates.add(start + 50)
    cand_list = sorted(candidates)
    if len(cand_list) > 250:
        # Keep a deterministic subset.
        cand_list = cand_list[:250]

    window_len = max(400, min(12_000, len(asr_words) * 3))
    asr_tri = trigram_set(asr_words, max_grams=200_000)
    asr_c = Counter(asr_words)

    best = None
    best_score = -1.0
    for start in cand_list:
        win = book_words[start : start + window_len]
        if len(win) < 200:
            continue
        win_tri = trigram_set(win, max_grams=200_000)
        inter = len(asr_tri & win_tri)
        s_book = inter / (len(win_tri) or 1)
        s_asr = inter / (len(asr_tri) or 1)
        score = (s_book + s_asr) / 2.0
        if score > best_score:
            best_score = score
            best = (start, win, s_book, s_asr)

    if not best:
        return None

    start, win, s_book, s_asr = best
    win_c = Counter(win)
    overlap = multiset_overlap(asr_c, win_c)
    total_asr = sum(asr_c.values()) or 1
    total_win = sum(win_c.values()) or 1
    w_asr = overlap / total_asr
    w_book = overlap / total_win

    # Optional order-sensitive ratios on bounded strings.
    seq_ratio = None
    lev_norm = None
    try:
        # Compare ASR to the same-length-ish prefix of the window to keep it stable.
        pref = win[: max(200, min(len(win), len(asr_words) * 2))]
        a = " ".join(asr_words[:5000])
        b = " ".join(pref[:5000])
        if a and b:
            seq_ratio = round(Levenshtein.ratio(a, b), 6)
            # Normalize distance by length (approximate; not token-WER).
            dist = Levenshtein.distance(a, b)
            lev_norm = round(dist / max(1, len(b)), 6)
    except Exception:
        pass

    missing_top = top_deltas(Counter(win), Counter(asr_words), n=20)
    extra_top = top_deltas(Counter(asr_words), Counter(win), n=20)
    return AlignResult(
        start_idx=int(start),
        window_words=win,
        trigram_overlap_book=round(s_book, 6),
        trigram_overlap_asr=round(s_asr, 6),
        loose_word_overlap_book=round(w_book, 6),
        loose_word_overlap_asr=round(w_asr, 6),
        seq_ratio=seq_ratio,
        lev_norm=lev_norm,
        missing_top=missing_top,
        extra_top=extra_top,
    )


def transcribe(model: WhisperModel, mp3: Path, language: str | None) -> dict:
    segments, info = model.transcribe(
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
    text = " ".join(texts)
    return {
        "text": text,
        "language": getattr(info, "language", None),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--epub", required=True, help="Path to epub inside container (mounted /data/...).")
    ap.add_argument("--outdir", required=True, help="Output dir inside container (mounted /data/audiobooks/...).")
    ap.add_argument("--log", default="", help="Job log file to append to (mounted /data/logs/<id>.log).")
    ap.add_argument("--model", default=os.environ.get("AUDIO_ASR_VERIFY_MODEL", "tiny"))
    ap.add_argument("--max-files", type=int, default=int(os.environ.get("AUDIO_ASR_VERIFY_MAX_FILES", "4")))
    ap.add_argument("--min-duration-s", type=int, default=int(os.environ.get("AUDIO_ASR_VERIFY_MIN_DURATION_S", "45")))
    ap.add_argument("--language", default=os.environ.get("AUDIO_ASR_VERIFY_LANGUAGE", "en"))
    ap.add_argument("--cpu-threads", type=int, default=int(os.environ.get("AUDIO_ASR_VERIFY_CPU_THREADS", "4")))
    args = ap.parse_args()

    job_id = args.job_id
    epub_path = Path(args.epub)
    outdir = Path(args.outdir)
    log_path = Path(args.log) if args.log else None

    t0 = time.time()
    log_append(log_path, f"[{now_iso()}] Audio verify(sample) start (model={args.model}, max_files={args.max_files})")

    if not epub_path.exists():
        log_append(log_path, f"[{now_iso()}] Audio verify(sample) skipped: epub not found: {epub_path}")
        return 0
    if not outdir.exists():
        log_append(log_path, f"[{now_iso()}] Audio verify(sample) skipped: outdir not found: {outdir}")
        return 0

    mp3s = sorted(outdir.glob("*.mp3"))
    if not mp3s:
        log_append(log_path, f"[{now_iso()}] Audio verify(sample) skipped: no mp3 files in {outdir}")
        return 0

    # Filter by duration if possible.
    kept: list[Path] = []
    for p in mp3s:
        d = mp3_duration_s(p)
        if d is None or d >= float(args.min_duration_s):
            kept.append(p)
    if not kept:
        kept = mp3s

    sample = pick_sample_files(kept, max(1, int(args.max_files)), seed=job_id)
    log_append(log_path, f"[{now_iso()}] Audio verify(sample) picked {len(sample)} file(s)")

    # Extract book text once.
    book_raw = extract_epub_text(epub_path)
    book_loose_words = words_list(book_raw, max_words=250_000)
    if not book_loose_words:
        log_append(log_path, f"[{now_iso()}] Audio verify(sample) skipped: could not extract text from epub")
        return 0

    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=int(args.cpu_threads))

    per_file: list[dict] = []
    for p in sample:
        try:
            tr = transcribe(model, p, (args.language or None))
            asr_text = tr.get("text") or ""
            asr_words = words_list(asr_text, max_words=60_000)
            aligned = align_asr_to_book(asr_words, book_loose_words)
            entry = {
                "file": p.name,
                "bytes": int(p.stat().st_size),
                "duration_s": mp3_duration_s(p),
                "asr_text_sha256": sha256_hex_text(asr_text),
                "asr_word_count": int(len(asr_words)),
                "asr_language": tr.get("language"),
                "align": None,
            }
            if aligned:
                entry["align"] = {
                    "book_window_start_word_index": int(aligned.start_idx),
                    "loose_word_overlap_ratio_of_book_window": float(aligned.loose_word_overlap_book),
                    "loose_word_overlap_ratio_of_asr": float(aligned.loose_word_overlap_asr),
                    "loose_trigram_overlap_ratio_of_book_window": float(aligned.trigram_overlap_book),
                    "loose_trigram_overlap_ratio_of_asr": float(aligned.trigram_overlap_asr),
                    "sampled_seq_ratio": aligned.seq_ratio,
                    "sampled_levenshtein_norm": aligned.lev_norm,
                    "top_missing_words_in_asr": aligned.missing_top,
                    "top_extra_words_in_asr": aligned.extra_top,
                }
            per_file.append(entry)
            log_append(log_path, f"[{now_iso()}] Audio verify(sample) ok: {p.name} (asr_words={len(asr_words)})")
        except Exception as e:
            per_file.append({"file": p.name, "error": str(e)[:200]})
            log_append(log_path, f"[{now_iso()}] Audio verify(sample) failed: {p.name}: {e}")

    # Aggregate summary.
    tri_books = []
    tri_asrs = []
    word_books = []
    word_asrs = []
    seqs = []
    for e in per_file:
        a = (e.get("align") or {})
        if a:
            tri_books.append(a.get("loose_trigram_overlap_ratio_of_book_window"))
            tri_asrs.append(a.get("loose_trigram_overlap_ratio_of_asr"))
            word_books.append(a.get("loose_word_overlap_ratio_of_book_window"))
            word_asrs.append(a.get("loose_word_overlap_ratio_of_asr"))
            if a.get("sampled_seq_ratio") is not None:
                seqs.append(a.get("sampled_seq_ratio"))

    def _flt(xs):
        return [float(x) for x in xs if x is not None]

    tri_books_f = _flt(tri_books)
    tri_asrs_f = _flt(tri_asrs)
    word_books_f = _flt(word_books)
    word_asrs_f = _flt(word_asrs)
    seqs_f = _flt(seqs)

    summary = {
        "job_id": job_id,
        "created_at": now_iso(),
        "model": args.model,
        "sample_count": int(len(sample)),
        "book_word_count": int(len(book_loose_words)),
        "metrics": {
            "min_trigram_overlap_book_window": min(tri_books_f) if tri_books_f else None,
            "avg_trigram_overlap_book_window": (sum(tri_books_f) / len(tri_books_f)) if tri_books_f else None,
            "min_trigram_overlap_asr": min(tri_asrs_f) if tri_asrs_f else None,
            "avg_trigram_overlap_asr": (sum(tri_asrs_f) / len(tri_asrs_f)) if tri_asrs_f else None,
            "min_word_overlap_book_window": min(word_books_f) if word_books_f else None,
            "avg_word_overlap_book_window": (sum(word_books_f) / len(word_books_f)) if word_books_f else None,
            "min_word_overlap_asr": min(word_asrs_f) if word_asrs_f else None,
            "avg_word_overlap_asr": (sum(word_asrs_f) / len(word_asrs_f)) if word_asrs_f else None,
            "avg_sampled_seq_ratio": (sum(seqs_f) / len(seqs_f)) if seqs_f else None,
        },
        "files": per_file,
        "elapsed_s": round(time.time() - t0, 3),
    }

    vdir = outdir / "_verification"
    vdir.mkdir(parents=True, exist_ok=True)
    out_json = vdir / "audio_verify_sample.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    log_append(
        log_path,
        f"[{now_iso()}] Audio verify(sample) written: {out_json} (elapsed={summary['elapsed_s']}s)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
