#!/usr/bin/env python3
"""
EPUB/PDF to Audiobook Web UI
Allows users to upload EPUB/PDF files, preview voices, and convert to audiobooks.
"""

import os
import subprocess
import threading
import uuid
import shutil
import zipfile
import re
import sqlite3
import json
import signal
import shlex
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from collections import Counter
from typing import Any, Optional, Dict, List

from flask import Flask, render_template, request, jsonify, send_file, Response
import requests

# Telegram notification settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
TTS_PROXY_URL = os.environ.get('TTS_PROXY_URL', '').strip().rstrip('/')

app = Flask(__name__)

# Configuration
# NOTE: KOKORO_URL is a mutable global — gpu_manager.py switches it
# between CPU and GPU endpoints at runtime. Do NOT cache this value.
KOKORO_URL = os.environ.get('KOKORO_URL', 'http://localhost:8880/v1')
PIPER_URL = os.environ.get('PIPER_URL', 'http://piper-tts:8000/v1')
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/data/uploads'))
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', '/data/audiobooks'))
PREVIEWS_DIR = Path(os.environ.get('PREVIEWS_DIR', '/data/previews'))
DB_PATH = Path(os.environ.get('DB_PATH', '/data/jobs.db'))
TRANSCRIPTS_DIR = Path(os.environ.get('TRANSCRIPTS_DIR', '/data/transcripts'))
APP_VERSION = os.environ.get('APP_VERSION', 'dev')
APP_GIT_SHA = os.environ.get('APP_GIT_SHA', 'unknown')
APP_BUILD_TIME = os.environ.get('APP_BUILD_TIME', 'unknown')
HEALTH_KOKORO_TIMEOUT = int(os.environ.get('HEALTH_KOKORO_TIMEOUT', '8'))
HEALTH_KOKORO_RETRIES = int(os.environ.get('HEALTH_KOKORO_RETRIES', '2'))
QUEUE_RUNNER_ENABLED = os.environ.get('QUEUE_RUNNER_ENABLED', '1').lower() in ('1', 'true', 'yes')

# Lock to prevent race conditions when claiming jobs from the queue.
# Both the worker loop and API endpoints could try to start the same job simultaneously.
_job_claim_lock = threading.Lock()

# Minimum fraction of chapters required to mark a book complete (1.0 = 100%).
# No more half-finished audiobooks.
CHAPTER_COMPLETION_THRESHOLD = float(os.environ.get('CHAPTER_COMPLETION_THRESHOLD', '1.0'))
MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))

# Optional: sampled ASR verification (audio waveform -> transcript -> compare vs EPUB text).
# Off by default because it can be CPU-expensive.
AUDIO_ASR_VERIFY_ENABLED = os.environ.get('AUDIO_ASR_VERIFY_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')
AUDIO_ASR_VERIFY_IMAGE = os.environ.get('AUDIO_ASR_VERIFY_IMAGE', 'epub-to-audiobook-audio-verify:local').strip()
AUDIO_ASR_VERIFY_MAX_FILES = int(os.environ.get('AUDIO_ASR_VERIFY_MAX_FILES', '4'))
AUDIO_ASR_VERIFY_MODEL = os.environ.get('AUDIO_ASR_VERIFY_MODEL', 'tiny').strip()
AUDIO_ASR_VERIFY_TIMEOUT_S = int(os.environ.get('AUDIO_ASR_VERIFY_TIMEOUT_S', '1200'))  # 20 min default

# Host paths for Docker volume mounts (where the stack is deployed)
HOST_STACK_DIR = os.environ.get('HOST_STACK_DIR', '/home/dave/stacks/epub-to-audiobook')
STACK_PATH = os.environ.get('STACK_PATH', HOST_STACK_DIR)
HOST_UPLOAD_DIR = f"{HOST_STACK_DIR}/data/uploads"
HOST_OUTPUT_DIR = f"{HOST_STACK_DIR}/data/audiobooks"
HOST_DATA_DIR = f"{HOST_STACK_DIR}/data"

# Audiobookshelf integration - copy completed books here
AUDIOBOOKSHELF_DIR = os.environ.get('AUDIOBOOKSHELF_DIR', '')
AUDIOBOOKSHELF_HOST = os.environ.get('AUDIOBOOKSHELF_HOST', 'docker-vm')
AUDIOBOOKSHELF_USER = os.environ.get('AUDIOBOOKSHELF_USER', 'dave')
AUDIOBOOKSHELF_PORT = os.environ.get('AUDIOBOOKSHELF_PORT', '')

# OpenBooks/Library directory for browsing available EPUBs
LIBRARY_DIR = Path(os.environ.get('LIBRARY_DIR', '/data/library'))
LOG_DIR = Path(os.environ.get('LOG_DIR', '/data/logs'))

# Supported ebook formats (converted to EPUB via Calibre)
SUPPORTED_FORMATS = {'.epub', '.pdf', '.mobi', '.azw3', '.fb2', '.txt', '.html', '.htm', '.docx'}

# Default voice when none specified (George Classic - British Male)
DEFAULT_VOICE = 'bm_v0george'

# TTS speed: 1.0 = normal, <1.0 = slower with more pauses, range 0.5-1.5
# Default 1.0 (Kokoro's natural speed sounds good; adjust per-job if needed)
DEFAULT_TTS_SPEED = float(os.environ.get('DEFAULT_TTS_SPEED', '1.0'))

# Post-conversion cleanup: remove MP3 files smaller than this (catches photo captions, part dividers)
MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))

# Auto-retry configuration
MAX_RETRY_COUNT = 3
RETRY_BACKOFF_BASE = 30  # seconds (30, 60, 120 for attempts 1, 2, 3)

# Audiobookshelf API for triggering rescans after sync
ABS_API_TOKEN = os.environ.get('ABS_API_TOKEN', '')
ABS_API_URL = os.environ.get('ABS_API_URL', 'http://docker-vm:13378')

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Track running conversion processes and containers
running_processes = {}  # job_id -> subprocess.Popen
running_containers = {}  # job_id -> container_name
_recovery_in_progress = {}  # job_id -> True (prevents duplicate recovery threads)
# When routing TTS via tts-proxy, conversion containers may not emit useful progress logs.
# Track transcript progress incrementally by file offset so we can show real progress.
_proxy_progress_state: dict[str, dict[str, int]] = {}

_re_ws = re.compile(r"\s+")
_re_punct = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def normalize_strict_text(s: str) -> str:
    """Deterministic whitespace normalization (preserve case/punctuation)."""
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join([ln.rstrip() for ln in s.split("\n")])
    s = _re_ws.sub(" ", s).strip()
    return s


def normalize_loose_text(s: str) -> str:
    """Loose normalization for comparison (casefold + strip punctuation + collapse whitespace)."""
    s = (s or "").casefold()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _re_punct.sub(" ", s)
    s = _re_ws.sub(" ", s).strip()
    return s


def sha256_hex_text(s: str) -> str:
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8", errors="replace")).hexdigest()


def _read_captured_chunks(job_id: str) -> dict | None:
    p = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
    if not p.exists():
        return None
    raw_all: list[str] = []
    strict_all: list[str] = []
    loose_all: list[str] = []
    n = 0
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("text") or ""
            raw_all.append(t)
            strict_all.append(obj.get("strict") or normalize_strict_text(t))
            loose_all.append(obj.get("loose") or normalize_loose_text(t))
            n += 1
    raw_join = "\n".join(raw_all)
    strict_join = "\n".join(strict_all)
    loose_join = "\n".join(loose_all)
    return {
        "chunks": n,
        "raw_text": raw_join,
        "strict_text": strict_join,
        "loose_text": loose_join,
    }


def verify_tts_against_epub(job_id: str, epub_path: Path, output_path: Path):
    """Best-effort verification that voiced text matches extracted book text.

    This is not a formal proof. It provides:
    - hashes of captured chunk text (raw/strict/loose)
    - hashes of extracted book text (strict/loose)
    - token coverage metrics (loose)
    """
    try:
        captured = _read_captured_chunks(job_id)
        if not captured:
            append_job_log(job_id, "Verification skipped: no captured transcript chunks")
            return

        vdir = output_path / "_verification"
        vdir.mkdir(parents=True, exist_ok=True)

        # Extract text from EPUB using Calibre (already present in the stack image).
        extracted_txt = vdir / "book.txt"
        try:
            subprocess.run(
                ["ebook-convert", str(epub_path), str(extracted_txt)],
                capture_output=True,
                text=True,
                timeout=300,
                check=True,
            )
        except Exception as e:
            append_job_log(job_id, f"Verification: ebook-convert failed: {e}")
            return

        book_raw = extracted_txt.read_text(encoding="utf-8", errors="replace")
        book_strict = normalize_strict_text(book_raw)
        book_loose = normalize_loose_text(book_raw)

        tts_raw = captured["raw_text"]
        tts_strict = captured["strict_text"]
        tts_loose = captured["loose_text"]

        # Coverage + structure metrics (word-level, loose normalized).
        #
        # Important:
        # - Word overlap is order-insensitive. It catches gross omissions/additions but can miss re-ordering.
        # - Trigram overlap is weakly order-sensitive and more robust for "word-for-word-ish" checks.
        # - Sampled SequenceMatcher ratio is an order-sensitive sanity check on the start of the book.
        def words_list(s: str, max_words: int = 250_000) -> list[str]:
            ws = [w for w in (s or "").split(" ") if w]
            if len(ws) > max_words:
                ws = ws[:max_words]
            return ws

        book_words = words_list(book_loose)
        tts_words = words_list(tts_loose)
        c_book = Counter(book_words)
        c_tts = Counter(tts_words)
        total_book = sum(c_book.values()) or 1
        total_tts = sum(c_tts.values()) or 1
        overlap = sum(min(c_book[w], c_tts.get(w, 0)) for w in c_book.keys())
        book_covered = overlap / total_book
        tts_covered = overlap / total_tts

        # Weakly order-sensitive overlap via word trigrams (caps to avoid memory blow-ups).
        def trigram_set(ws: list[str], max_grams: int = 250_000) -> set[str]:
            grams: set[str] = set()
            if len(ws) < 3:
                return grams
            # Use a delimiter unlikely to appear in normalized tokens.
            delim = "\x1f"
            # Keep a deterministic prefix to make numbers stable run-to-run.
            end = min(len(ws) - 2, max_grams)
            for i in range(end):
                grams.add(delim.join((ws[i], ws[i + 1], ws[i + 2])))
            return grams

        book_tri = trigram_set(book_words)
        tts_tri = trigram_set(tts_words)
        tri_inter = len(book_tri & tts_tri)
        tri_book = len(book_tri) or 1
        tri_tts = len(tts_tri) or 1
        tri_book_covered = tri_inter / tri_book
        tri_tts_covered = tri_inter / tri_tts

        # Order-sensitive "does the beginning match" metric (sample first N words).
        # This is intentionally conservative: we're not trying to do full forced-alignment.
        import difflib
        sample_n = 5000
        book_sample = " ".join(book_words[:sample_n])
        tts_sample = " ".join(tts_words[:sample_n])
        seq_ratio = None
        if book_sample and tts_sample:
            # SequenceMatcher can be expensive; keep samples bounded.
            seq_ratio = round(difflib.SequenceMatcher(None, book_sample, tts_sample).ratio(), 6)

        # Diagnostics: top "missing" vs "extra" content words.
        stop = {
            # minimal stoplist to keep reports readable
            "the", "and", "that", "with", "from", "this", "have", "were", "your", "their", "there",
            "they", "them", "then", "than", "what", "when", "where", "which", "will", "would", "could",
            "should", "into", "upon", "over", "under", "again", "about", "because", "after", "before",
            "been", "being", "such", "some", "most", "more", "very", "here", "himself", "herself",
        }

        def top_deltas(a: Counter, b: Counter, n: int = 20) -> list[dict]:
            # a - b (positive deltas only)
            deltas = []
            for w, cnt in a.items():
                if cnt <= 0:
                    continue
                if len(w) < 5:
                    continue
                if w in stop:
                    continue
                d = cnt - b.get(w, 0)
                if d > 0:
                    deltas.append((w, int(d)))
            deltas.sort(key=lambda x: x[1], reverse=True)
            return [{"word": w, "delta": d} for (w, d) in deltas[:n]]

        missing_in_tts_top = top_deltas(c_book, c_tts, n=20)
        extra_in_tts_top = top_deltas(c_tts, c_book, n=20)

        report = {
            "job_id": job_id,
            "captured_chunks": captured["chunks"],
            "tts_raw_sha256": sha256_hex_text(tts_raw),
            "tts_strict_sha256": sha256_hex_text(tts_strict),
            "tts_loose_sha256": sha256_hex_text(tts_loose),
            "book_strict_sha256": sha256_hex_text(book_strict),
            "book_loose_sha256": sha256_hex_text(book_loose),
            "book_loose_word_count": int(len(book_words)),
            "tts_loose_word_count": int(len(tts_words)),
            "loose_word_overlap_ratio_of_book": round(book_covered, 6),
            "loose_word_overlap_ratio_of_tts": round(tts_covered, 6),
            "loose_trigram_overlap_ratio_of_book": round(tri_book_covered, 6),
            "loose_trigram_overlap_ratio_of_tts": round(tri_tts_covered, 6),
            "sampled_sequence_ratio_first_5000_words": seq_ratio,
            "top_missing_words_in_tts": missing_in_tts_top,
            "top_extra_words_in_tts": extra_in_tts_top,
            "created_at": datetime.now().isoformat(),
        }

        (vdir / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        append_job_log(
            job_id,
            f"Verification written: overlap(book)={report['loose_word_overlap_ratio_of_book']:.3f}, overlap(tts)={report['loose_word_overlap_ratio_of_tts']:.3f}",
        )
    except Exception as e:
        append_job_log(job_id, f"Verification exception: {e}")


def _run_audio_asr_verify_sample(job_id: str, epub_filename: str, output_dirname: str):
    """Run sampled ASR verification in a separate container (best-effort; does not affect job outcome)."""
    try:
        if not AUDIO_ASR_VERIFY_ENABLED:
            return
        if not HOST_STACK_DIR:
            append_job_log(job_id, "Audio verify(sample) skipped: HOST_STACK_DIR not set")
            return
        if not AUDIO_ASR_VERIFY_IMAGE:
            append_job_log(job_id, "Audio verify(sample) skipped: AUDIO_ASR_VERIFY_IMAGE not set")
            return

        epub_in_container = f"/data/uploads/{epub_filename}"
        outdir_in_container = f"/data/audiobooks/{output_dirname}"
        log_in_container = f"/data/logs/{job_id}.log"

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{HOST_STACK_DIR}/data:/data",
            # Cache ASR model downloads across runs.
            "-v", f"{HOST_STACK_DIR}/data/asr_cache:/root/.cache",
            AUDIO_ASR_VERIFY_IMAGE,
            "--job-id", job_id,
            "--epub", epub_in_container,
            "--outdir", outdir_in_container,
            "--log", log_in_container,
            "--model", AUDIO_ASR_VERIFY_MODEL,
            "--max-files", str(max(1, AUDIO_ASR_VERIFY_MAX_FILES)),
        ]
        append_job_log(job_id, f"Audio verify(sample) starting (model={AUDIO_ASR_VERIFY_MODEL}, files={AUDIO_ASR_VERIFY_MAX_FILES})")
        subprocess.run(cmd, capture_output=True, text=True, timeout=AUDIO_ASR_VERIFY_TIMEOUT_S)
        append_job_log(job_id, "Audio verify(sample) done (see _verification/audio_verify_sample.json)")
    except subprocess.TimeoutExpired:
        append_job_log(job_id, f"Audio verify(sample) timeout after {AUDIO_ASR_VERIFY_TIMEOUT_S}s")
    except Exception as e:
        append_job_log(job_id, f"Audio verify(sample) exception: {e}")

# TTS Engines configuration
TTS_ENGINES = {
    'kokoro': {
        'name': 'Kokoro',
        'description': 'High-quality neural TTS with voice mixing',
        'url_env': 'KOKORO_URL',
        'default_url': 'http://kokoro-tts:8880/v1'
    },
    'piper': {
        'name': 'Piper',
        'description': 'Fast, lightweight neural TTS',
        'url_env': 'PIPER_URL',
        'default_url': 'http://piper-tts:8000/v1'
    }
}

# Curated voice list - All English voices organized by engine
VOICES = {
    # ============ KOKORO VOICES ============
    # British Female (5 voices)
    'bf_emma': {'name': 'Emma', 'accent': 'British', 'gender': 'Female', 'engine': 'kokoro'},
    'bf_alice': {'name': 'Alice', 'accent': 'British', 'gender': 'Female', 'engine': 'kokoro'},
    'bf_lily': {'name': 'Lily', 'accent': 'British', 'gender': 'Female', 'engine': 'kokoro'},
    'bf_v0emma': {'name': 'Emma Classic', 'accent': 'British', 'gender': 'Female', 'engine': 'kokoro'},
    'bf_v0isabella': {'name': 'Isabella', 'accent': 'British', 'gender': 'Female', 'engine': 'kokoro'},
    # British Male (6 voices)
    'bm_george': {'name': 'George', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    'bm_daniel': {'name': 'Daniel', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    'bm_lewis': {'name': 'Lewis', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    'bm_fable': {'name': 'Fable', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    'bm_v0george': {'name': 'George Classic', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    'bm_v0lewis': {'name': 'Lewis Classic', 'accent': 'British', 'gender': 'Male', 'engine': 'kokoro'},
    # European English (3 voices)
    'ef_dora': {'name': 'Dora', 'accent': 'European', 'gender': 'Female', 'engine': 'kokoro'},
    'em_alex': {'name': 'Alex', 'accent': 'European', 'gender': 'Male', 'engine': 'kokoro'},
    'em_santa': {'name': 'Santa', 'accent': 'European', 'gender': 'Male', 'engine': 'kokoro'},
    # American Female (4 voices)
    'af_bella': {'name': 'Bella', 'accent': 'American', 'gender': 'Female', 'engine': 'kokoro'},
    'af_nova': {'name': 'Nova', 'accent': 'American', 'gender': 'Female', 'engine': 'kokoro'},
    'af_sky': {'name': 'Sky', 'accent': 'American', 'gender': 'Female', 'engine': 'kokoro'},
    'af_nicole': {'name': 'Nicole', 'accent': 'American', 'gender': 'Female', 'engine': 'kokoro'},
    # American Male (4 voices)
    'am_adam': {'name': 'Adam', 'accent': 'American', 'gender': 'Male', 'engine': 'kokoro'},
    'am_michael': {'name': 'Michael', 'accent': 'American', 'gender': 'Male', 'engine': 'kokoro'},
    'am_eric': {'name': 'Eric', 'accent': 'American', 'gender': 'Male', 'engine': 'kokoro'},
    'am_liam': {'name': 'Liam', 'accent': 'American', 'gender': 'Male', 'engine': 'kokoro'},

    # ============ PIPER VOICES - HIGH QUALITY ONLY ============
    'cori': {'name': 'Cori', 'accent': 'British', 'gender': 'Female', 'engine': 'piper'},
    'lessac': {'name': 'Lessac', 'accent': 'American', 'gender': 'Female', 'engine': 'piper'},
    'ljspeech': {'name': 'LJ Speech', 'accent': 'American', 'gender': 'Female', 'engine': 'piper'},
    'ryan': {'name': 'Ryan', 'accent': 'American', 'gender': 'Male', 'engine': 'piper'},
    'libritts_1': {'name': 'LibriTTS 1', 'accent': 'American', 'gender': 'Neutral', 'engine': 'piper'},
    'libritts_2': {'name': 'LibriTTS 2', 'accent': 'American', 'gender': 'Neutral', 'engine': 'piper'},
    'libritts_3': {'name': 'LibriTTS 3', 'accent': 'American', 'gender': 'Neutral', 'engine': 'piper'},

    # ============ EDGETTS VOICES (FREE, HIGH QUALITY) ============
    # British Edge Voices
    'en-GB-SoniaNeural': {'name': 'Sonia', 'accent': 'British', 'gender': 'Female', 'engine': 'edge'},
    'en-GB-RyanNeural': {'name': 'Ryan', 'accent': 'British', 'gender': 'Male', 'engine': 'edge'},
    'en-GB-LibbyNeural': {'name': 'Libby', 'accent': 'British', 'gender': 'Female', 'engine': 'edge'},
    'en-GB-MaisieNeural': {'name': 'Maisie', 'accent': 'British', 'gender': 'Female', 'engine': 'edge'},
    'en-GB-ThomasNeural': {'name': 'Thomas', 'accent': 'British', 'gender': 'Male', 'engine': 'edge'},
    
    # American Edge Voices
    'en-US-AvaNeural': {'name': 'Ava', 'accent': 'American', 'gender': 'Female', 'engine': 'edge'},
    'en-US-AndrewNeural': {'name': 'Andrew', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    'en-US-EmmaNeural': {'name': 'Emma', 'accent': 'American', 'gender': 'Female', 'engine': 'edge'},
    'en-US-BrianNeural': {'name': 'Brian', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    'en-US-AriaNeural': {'name': 'Aria', 'accent': 'American', 'gender': 'Female', 'engine': 'edge'},
    'en-US-ChristopherNeural': {'name': 'Christopher', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    'en-US-GuyNeural': {'name': 'Guy', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    'en-US-JennyNeural': {'name': 'Jenny', 'accent': 'American', 'gender': 'Female', 'engine': 'edge'},
    'en-US-MichelleNeural': {'name': 'Michelle', 'accent': 'American', 'gender': 'Female', 'engine': 'edge'},
    'en-US-RogerNeural': {'name': 'Roger', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    'en-US-SteffanNeural': {'name': 'Steffan', 'accent': 'American', 'gender': 'Male', 'engine': 'edge'},
    
    # Australian Edge Voices
    'en-AU-NatashaNeural': {'name': 'Natasha', 'accent': 'Australian', 'gender': 'Female', 'engine': 'edge'},
    'en-AU-WilliamNeural': {'name': 'William', 'accent': 'Australian', 'gender': 'Male', 'engine': 'edge'},

    # ============ AWS POLLY LONG-FORM VOICES ============
    'polly_ruth': {'name': 'Ruth', 'accent': 'American', 'gender': 'Female', 'engine': 'polly'},
    'polly_danielle': {'name': 'Danielle', 'accent': 'American', 'gender': 'Female', 'engine': 'polly'},
    'polly_gregory': {'name': 'Gregory', 'accent': 'American', 'gender': 'Male', 'engine': 'polly'},
    'polly_patrick': {'name': 'Patrick', 'accent': 'American', 'gender': 'Male', 'engine': 'polly'},
}

PREVIEW_TEXT = "The quick brown fox jumps over the lazy dog. This is a preview of how this voice sounds when reading audiobooks."


# ============ Database Functions ============

def init_db():
    """Initialize SQLite database for job persistence."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                book_name TEXT,
                voice TEXT,
                voice_name TEXT,
                voice2 TEXT,
                voice2_name TEXT,
                tts_engine TEXT DEFAULT 'kokoro',
                status TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                input_filename TEXT,
                output_dirname TEXT,
                is_pdf INTEGER,
                char_count INTEGER,
                timeout_minutes INTEGER,
                total_chapters INTEGER,
                current_chapter INTEGER,
                current_chapter_name TEXT,
                progress_percent INTEGER,
                eta_minutes INTEGER,
                file_count INTEGER,
                error TEXT,
                synced_to_abs INTEGER DEFAULT 0,
                container_name TEXT,
                start_chapter INTEGER,
                end_chapter INTEGER,
                notify_telegram INTEGER DEFAULT 0,
                queue_rank INTEGER DEFAULT 0,
                sync_target_host TEXT,
                sync_target_path TEXT,
                sync_timestamp TEXT,
                sync_file_count INTEGER,
                sync_status TEXT,
                sync_error TEXT,
                job_log_path TEXT,
                newline_mode TEXT DEFAULT 'double',
                title_mode TEXT DEFAULT 'auto',
                custom_regex TEXT
            )
        ''')

        # Add newline_mode column (migration)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN newline_mode TEXT DEFAULT 'double'")
        except sqlite3.OperationalError:
            pass

        # Add title_mode column (migration)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN title_mode TEXT DEFAULT 'auto'")
        except sqlite3.OperationalError:
            pass

        # Add custom_regex column (migration)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN custom_regex TEXT")
        except sqlite3.OperationalError:
            pass

        # Add tts_engine column if it doesn't exist (migration)
        try:
            conn.execute('ALTER TABLE jobs ADD COLUMN tts_engine TEXT DEFAULT "kokoro"')
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Add retry_count column if it doesn't exist (migration for orphan recovery)
        try:
            conn.execute('ALTER TABLE jobs ADD COLUMN retry_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Add queue_rank column if it doesn't exist (queue ordering/reordering)
        try:
            conn.execute('ALTER TABLE jobs ADD COLUMN queue_rank INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Add tts_speed column (0.5-1.5, default 0.9 for natural pacing)
        try:
            conn.execute('ALTER TABLE jobs ADD COLUMN tts_speed REAL DEFAULT 0.9')
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add sync metadata columns if they don't exist
        for col, col_type in [
            ('sync_target_host', 'TEXT'),
            ('sync_target_path', 'TEXT'),
            ('sync_timestamp', 'TEXT'),
            ('sync_file_count', 'INTEGER'),
            ('sync_status', 'TEXT'),
            ('sync_error', 'TEXT'),
            ('job_log_path', 'TEXT'),
        ]:
            try:
                conn.execute(f'ALTER TABLE jobs ADD COLUMN {col} {col_type}')
            except sqlite3.OperationalError:
                pass  # Column already exists

        # App settings table (pause state, feature flags)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Create conversion_metrics table for ETA learning
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversion_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voice TEXT NOT NULL,
                engine TEXT NOT NULL,
                file_type TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                chapter_count INTEGER NOT NULL,
                actual_duration_seconds INTEGER NOT NULL,
                chars_per_second REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Index for fast lookups on voice/engine/file_type
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_metrics_lookup
            ON conversion_metrics(voice, engine, file_type)
        ''')
        conn.commit()


@contextmanager
def get_db():
    """Get database connection with proper cleanup."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def job_to_dict(row):
    """Convert database row to dictionary."""
    if row is None:
        return None
    d = dict(row)
    # Convert integer booleans back
    d['is_pdf'] = bool(d.get('is_pdf', 0))
    d['synced_to_abs'] = bool(d.get('synced_to_abs', 0))
    # Ensure retry_count has a default value
    d['retry_count'] = d.get('retry_count', 0) or 0
    # Ensure sync status fields have defaults
    d['sync_status'] = d.get('sync_status') or ''
    d['sync_error'] = d.get('sync_error') or ''
    if not d.get('job_log_path') and d.get('id'):
        d['job_log_path'] = str(get_job_log_path(d['id']))
    return d


def get_job_log_path(job_id: str) -> Path:
    return LOG_DIR / f"{job_id}.log"


def append_job_log(job_id: str, message: str):
    """Append a timestamped line to the job log file."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().isoformat(timespec='seconds')
        path = get_job_log_path(job_id)
        with path.open('a', encoding='utf-8') as f:
            f.write(f"[{ts}] {message}\n")
    except Exception as e:
        app.logger.warning(f"Failed to write job log for {job_id}: {e}")


def tail_text_file(path: Path, max_lines: int = 200, max_bytes: int = 15000) -> str:
    """Return last N lines (bounded by bytes) from a text file."""
    if not path.exists():
        return ''
    try:
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        tail = ''.join(lines[-max_lines:])
        return tail[-max_bytes:]
    except Exception:
        return ''


def save_job(job: dict):
    """Save or update a job in the database."""
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO jobs
            (id, book_name, voice, voice_name, voice2, voice2_name, tts_engine, status, created_at, started_at,
             completed_at, input_filename, output_dirname, is_pdf, char_count,
             timeout_minutes, total_chapters, current_chapter, current_chapter_name,
             progress_percent, eta_minutes, file_count, error, synced_to_abs, container_name,
             start_chapter, end_chapter, notify_telegram, retry_count, queue_rank,
             sync_target_host, sync_target_path, sync_timestamp, sync_file_count, sync_status, sync_error, job_log_path,
             tts_speed, newline_mode, title_mode, custom_regex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job.get('id'),
            job.get('book_name'),
            job.get('voice'),
            job.get('voice_name'),
            job.get('voice2'),
            job.get('voice2_name'),
            job.get('tts_engine', 'kokoro'),
            job.get('status'),
            job.get('created_at'),
            job.get('started_at'),
            job.get('completed_at'),
            job.get('input_filename'),
            job.get('output_dirname'),
            1 if job.get('is_pdf') else 0,
            job.get('char_count'),
            job.get('timeout_minutes'),
            job.get('total_chapters'),
            job.get('current_chapter'),
            job.get('current_chapter_name'),
            job.get('progress_percent'),
            job.get('eta_minutes'),
            job.get('file_count'),
            job.get('error'),
            1 if job.get('synced_to_abs') else 0,
            job.get('container_name'),
            job.get('start_chapter'),
            job.get('end_chapter'),
            1 if job.get('notify_telegram') else 0,
            job.get('retry_count', 0),
            job.get('queue_rank', 0),
            job.get('sync_target_host'),
            job.get('sync_target_path'),
            job.get('sync_timestamp'),
            job.get('sync_file_count'),
            job.get('sync_status'),
            job.get('sync_error'),
            job.get('job_log_path'),
            job.get('tts_speed', DEFAULT_TTS_SPEED),
            job.get('newline_mode', 'double'),
            job.get('title_mode', 'auto'),
            job.get('custom_regex')
        ))
        conn.commit()


def get_job(job_id: str) -> dict:
    """Get a job from the database."""
    with get_db() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        return job_to_dict(row)


def get_all_jobs() -> list:
    """Get all jobs from the database."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT * FROM jobs
            ORDER BY
                CASE
                    WHEN status IN ('converting', 'converting PDF', 'converting to audio') THEN 0
                    WHEN status = 'queued' THEN 1
                    ELSE 2
                END,
                CASE WHEN status = 'queued' THEN COALESCE(queue_rank, 0) END ASC,
                created_at DESC
        ''').fetchall()
        return [job_to_dict(row) for row in rows]


def update_job(job_id: str, **kwargs):
    """Update specific fields of a job."""
    job = get_job(job_id)
    if job:
        job.update(kwargs)
        save_job(job)


def get_setting(key: str, default=None):
    """Fetch app setting value from database, falling back to ENV."""
    try:
        with get_db() as conn:
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
            if row:
                return row['value']
    except Exception:
        pass
    return os.environ.get(key, default)


def set_setting(key: str, value):
    """Store app setting value in database."""
    with get_db() as conn:
        conn.execute(
            'INSERT INTO app_settings (key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, str(value))
        )
        conn.commit()


def is_queue_paused() -> bool:
    """Check whether queue processing is paused."""
    return str(get_setting('queue_paused', '0')).lower() in ('1', 'true', 'yes')


def set_queue_paused(paused: bool):
    """Pause or resume queue processing."""
    set_setting('queue_paused', '1' if paused else '0')


def next_queue_rank() -> int:
    """Return next queue rank for FIFO ordering."""
    with get_db() as conn:
        row = conn.execute('SELECT COALESCE(MAX(queue_rank), 0) AS max_rank FROM jobs').fetchone()
        return int((row['max_rank'] if row else 0) or 0) + 1


# ============ ETA Learning Functions ============

def record_conversion_metrics(job):
    """Record actual conversion performance for learning.
    
    Called when a job completes successfully to store metrics that
    can be used to improve future ETA estimates.
    """
    if not job.get('started_at') or not job.get('completed_at'):
        return
    
    try:
        started = datetime.fromisoformat(job['started_at'])
        completed = datetime.fromisoformat(job['completed_at'])
        duration_seconds = (completed - started).total_seconds()
        
        if duration_seconds <= 0 or not job.get('char_count'):
            return
        
        chars_per_second = job['char_count'] / duration_seconds
        file_type = 'pdf' if job.get('is_pdf') else 'epub'
        
        with get_db() as conn:
            conn.execute('''
                INSERT INTO conversion_metrics 
                (voice, engine, file_type, char_count, chapter_count, actual_duration_seconds, chars_per_second)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (job['voice'], job.get('tts_engine', 'kokoro'), file_type, job['char_count'], 
                  job.get('total_chapters', 1) or 1, int(duration_seconds), chars_per_second))
            conn.commit()
        
        app.logger.info(f"Recorded conversion metrics: {chars_per_second:.2f} chars/sec for {job['voice']}/{file_type}")
    except Exception as e:
        app.logger.warning(f"Failed to record conversion metrics: {e}")


def estimate_eta_minutes(voice, engine, file_type, char_count):
    """Estimate conversion time using historical data.
    
    Uses a tiered fallback approach:
    1. Exact match (voice + engine + format)
    2. Engine + format only
    3. Default rate (10 chars/second = 600 chars/min)
    
    Adds 20% buffer for safety.
    """
    with get_db() as conn:
        # Try exact match (voice + engine + format)
        result = conn.execute('''
            SELECT AVG(chars_per_second) as avg_rate
            FROM conversion_metrics
            WHERE voice = ? AND engine = ? AND file_type = ?
        ''', (voice, engine, file_type)).fetchone()
        
        if result and result['avg_rate']:
            rate = result['avg_rate']
            app.logger.debug(f"ETA using exact match rate: {rate:.2f} chars/sec")
        else:
            # Try engine + format only
            result = conn.execute('''
                SELECT AVG(chars_per_second) as avg_rate
                FROM conversion_metrics
                WHERE engine = ? AND file_type = ?
            ''', (engine, file_type)).fetchone()
            
            if result and result['avg_rate']:
                rate = result['avg_rate']
                app.logger.debug(f"ETA using engine+format rate: {rate:.2f} chars/sec")
            else:
                # Default: 10 chars/second (600 chars/min)
                rate = 10.0
                app.logger.debug(f"ETA using default rate: {rate:.2f} chars/sec")
    
    # Add 20% buffer
    eta_seconds = (char_count / rate) * 1.2
    return max(1, int(eta_seconds / 60))



# ============ Orphan Job Detection & Recovery ============

def check_container_running(container_name):
    """Check if a Docker container exists and is running."""
    if not container_name:
        return False
    try:
        result = subprocess.run(
            ['docker', 'inspect', '-f', '{{.State.Running}}', container_name],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == 'true'
    except Exception:
        return False


def remove_stale_container(container_name):
    """Remove an existing container by name to avoid name conflicts."""
    if not container_name:
        return False
    try:
        result = subprocess.run(
            ['docker', 'rm', '-f', container_name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            app.logger.warning(f"Removed stale container {container_name}")
            return True
    except Exception as e:
        app.logger.warning(f"Could not remove stale container {container_name}: {e}")
    return False


def verify_book_complete(job_id: str, output_path: Path, total_chapters: int | None,
                         start_chapter: int | None = None,
                         end_chapter: int | None = None,
                         cleaned_up_count: int = 0) -> tuple[bool, str]:
    """Verify all chapters exist and have valid audio.

    Returns (is_complete, message). Used before marking any job as completed
    to ensure no half-finished audiobooks ever get synced.

    When *start_chapter* / *end_chapter* are set (chapter-range jobs), only
    the requested range is expected — not the full book.

    *cleaned_up_count* reduces the expected chapter count to account for
    intentionally removed noise/tiny files (e.g. photo captions, part dividers).
    """
    output_files = sorted(output_path.glob('*.mp3')) if output_path.exists() else []

    if not output_files:
        return False, "No output MP3 files found"

    # Determine expected chapter count (range-aware)
    if start_chapter and end_chapter:
        expected = end_chapter - start_chapter + 1
    elif total_chapters:
        expected = total_chapters
    else:
        expected = None

    # Subtract cleaned-up files from expected (they were intentionally removed)
    if expected and cleaned_up_count > 0:
        expected = max(1, expected - cleaned_up_count)

    # Check 1: Chapter count matches expected
    if expected:
        min_required = int(expected * CHAPTER_COMPLETION_THRESHOLD)
        if len(output_files) < min_required:
            return False, (
                f"Only {len(output_files)}/{expected} chapters "
                f"(need {min_required}, threshold={CHAPTER_COMPLETION_THRESHOLD:.0%})")

    # Check 2: Every MP3 has reasonable file size (not corrupt/empty)
    min_bytes = MIN_CHAPTER_SIZE_KB * 1024
    bad_files = [f.name for f in output_files if f.stat().st_size < min_bytes]
    # Allow up to 2 small files (frontmatter/TOC), but flag if many are tiny
    if len(bad_files) > 2 and expected and len(bad_files) > expected * 0.2:
        return False, (
            f"{len(bad_files)} files under {MIN_CHAPTER_SIZE_KB}KB: "
            f"{bad_files[:5]}{'...' if len(bad_files) > 5 else ''}")

    # Check 3: Total audio size sanity (should be at least 1MB for a real book)
    # For single-chapter samples, lower the threshold
    min_total_mb = 0.1 if (start_chapter and end_chapter and end_chapter - start_chapter < 3) else 1.0
    total_size_mb = sum(f.stat().st_size for f in output_files) / (1024 * 1024)
    if total_size_mb < min_total_mb:
        return False, f"Total audio only {total_size_mb:.1f}MB — likely corrupted"

    return True, (
        f"Verified: {len(output_files)} files, {total_size_mb:.0f}MB total"
        + (f" ({len(output_files)}/{expected} chapters)" if expected else ""))


def finalize_completed_job_if_outputs_exist(job_id):
    """Mark an in-flight job completed when output files prove success.

    This is mainly used after webapp restarts, where the original worker thread
    may no longer be alive to update final job status.
    """
    job = get_job(job_id)
    if not job:
        return False

    output_dirname = job.get('output_dirname')
    if not output_dirname:
        return False

    output_path = OUTPUT_DIR / output_dirname
    total_chapters = job.get('total_chapters')

    # Use verify_book_complete for consistent validation
    is_ok, msg = verify_book_complete(
        job_id, output_path, total_chapters,
        start_chapter=job.get('start_chapter'),
        end_chapter=job.get('end_chapter'))
    if not is_ok:
        app.logger.info(f"Cannot finalize {job_id}: {msg}")
        return False

    rename_output_files(output_path, job['book_name'])
    output_files = list(output_path.glob('*.mp3'))
    synced = copy_to_audiobookshelf(output_path, job['book_name'], job_id=job_id)
    update_job(
        job_id,
        status='completed',
        file_count=len(output_files),
        progress_percent=100,
        synced_to_abs=synced,
        completed_at=datetime.now().isoformat()
    )
    app.logger.info(f"Recovered completion for job {job_id} with {len(output_files)} files")

    job = get_job(job_id)
    if job:
        record_conversion_metrics(job)
        if job.get('notify_telegram'):
            send_telegram_notification(job, success=True)
    return True


def cleanup_orphan_jobs():
    """Detect and handle orphan jobs on startup.

    Finds jobs marked as 'converting' but whose containers are no longer running,
    and either finalizes them (if outputs exist) or re-queues them so they can
    resume after a webapp restart.

    Queued jobs are preserved so they can resume after restart.
    """
    with get_db() as conn:
        # Handle converting/recovering jobs with dead containers or threads
        # 'recovering' jobs are included because the recovery thread may have
        # been killed by a container restart, leaving the job stuck.
        converting_jobs = conn.execute(
            """
            SELECT id, container_name, retry_count
            FROM jobs
            WHERE status IN ('converting', 'converting PDF', 'converting to audio', 'recovering')
            """
        ).fetchall()

        orphan_count = 0
        for job in converting_jobs:
            job_id = job['id']
            container_name = job['container_name']
            retry_count = int(job['retry_count'] or 0)

            # If the container is still running, the resume logic will re-attach monitors.
            if check_container_running(container_name):
                continue

            # If conversion actually finished during downtime, output files prove success.
            try:
                if finalize_completed_job_if_outputs_exist(job_id):
                    continue
            except Exception:
                # Fall through to re-queue/fail logic.
                pass

            # If the container exists but isn't running anymore, remove it to avoid name conflicts on retry.
            remove_stale_container(container_name)

            # Check for partial output — if chapters exist, use chapter-level recovery
            # instead of re-running the entire book from scratch.
            job_data = get_job(job_id)
            output_dirname = job_data.get('output_dirname', '') if job_data else ''
            output_path = OUTPUT_DIR / output_dirname if output_dirname else None
            partial_files = list(output_path.glob('*.mp3')) if output_path and output_path.exists() else []

            job_status = job_data.get('status', '') if job_data else ''
            if partial_files and len(partial_files) >= 3:
                # Significant partial output exists — recover missing chapters only
                _recovery_in_progress[job_id] = True
                # Don't double-increment retry_count if already in 'recovering' status
                # (means a previous recovery thread was killed by restart)
                new_retry = retry_count if job_status == 'recovering' else retry_count + 1
                conn.execute('''
                    UPDATE jobs
                    SET retry_count = ?,
                        status = 'recovering'
                    WHERE id = ?
                ''', (new_retry, job_id))
                conn.commit()
                orphan_count += 1
                print(f"Orphan job {job_id} has {len(partial_files)} chapters — starting chapter recovery")
                append_job_log(job_id,
                    f"Orphan cleanup: {len(partial_files)} chapters exist; "
                    f"recovering missing chapters instead of full restart")

                # Run recovery in background
                def _orphan_recovery(jid=job_id):
                    import time as t
                    t.sleep(10)
                    try:
                        recover_partial_conversion(jid)
                    except Exception as e:
                        app.logger.error(f"Orphan recovery failed for {jid}: {e}")
                        with get_db() as c:
                            c.execute('''
                                UPDATE jobs SET status='failed', error=?, completed_at=?
                                WHERE id=?
                            ''', (f"Recovery failed: {e}", datetime.now().isoformat(), jid))
                            c.commit()
                        maybe_start_next_queued_job()
                    finally:
                        _recovery_in_progress.pop(jid, None)

                threading.Thread(target=_orphan_recovery, daemon=True).start()
                continue

            # No significant partial output — re-queue from scratch
            if retry_count < MAX_RETRY_COUNT:
                conn.execute('''
                    UPDATE jobs
                    SET status = 'queued',
                        retry_count = ?,
                        error = ?,
                        completed_at = NULL
                    WHERE id = ?
                ''', (retry_count + 1, 'Recovered after webapp restart. Re-queued to resume.', job_id))
                orphan_count += 1
                print(f"Re-queued orphan converting job {job_id} (retry {retry_count + 1}/{MAX_RETRY_COUNT})")
                append_job_log(job_id, "Orphan cleanup: container missing; re-queued for resume after restart")
            else:
                conn.execute('''
                    UPDATE jobs
                    SET status = 'failed',
                        error = ?,
                        completed_at = ?
                    WHERE id = ?
                ''', ('Container missing after restart and retry limit exceeded. Click Retry to restart.', datetime.now().isoformat(), job_id))
                orphan_count += 1
                print(f"Marked orphan converting job {job_id} as failed (retry limit exceeded)")
                append_job_log(job_id, "Orphan cleanup: container missing; marked failed (retry limit exceeded)")

        if orphan_count > 0:
            conn.commit()
            print(f"Cleaned up {orphan_count} orphan jobs")


# ============ Job Queue Management ============

MAX_CONCURRENT_JOBS = int(os.environ.get('MAX_CONCURRENT_JOBS', '1'))


def running_job_count():
    """Return the number of currently converting jobs."""
    with get_db() as conn:
        result = conn.execute('''
            SELECT COUNT(*) FROM jobs
            WHERE status IN ('converting', 'converting PDF', 'converting to audio', 'recovering')
        ''').fetchone()
        return result[0]


def queued_job_count():
    """Return the number of queued jobs waiting to start."""
    with get_db() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"
        ).fetchone()
        return result[0]


def is_job_running():
    """Check if we've reached the concurrent job limit."""
    return running_job_count() >= MAX_CONCURRENT_JOBS


def get_next_queued_job():
    """Get the oldest queued job."""
    with get_db() as conn:
        result = conn.execute('''
            SELECT * FROM jobs
            WHERE status = 'queued'
            ORDER BY COALESCE(queue_rank, 0) ASC, created_at ASC
            LIMIT 1
        ''').fetchone()
        return job_to_dict(result) if result else None


def start_next_queued_job():
    """Start the next queued job if no job is currently running.

    Uses _job_claim_lock to prevent race conditions where multiple callers
    (worker loop iterations, API endpoints) could start the same job twice.
    The job status is set to 'converting' BEFORE the thread starts, so any
    concurrent caller will see it as running and skip it.
    """
    with _job_claim_lock:
        if is_queue_paused():
            app.logger.info("Queue is paused; not starting queued jobs")
            return False
        if is_job_running():
            return False

        job = get_next_queued_job()
        if not job:
            return False

        # CRITICAL: Mark the job as 'converting' BEFORE starting the thread.
        # This prevents any other caller from seeing it as 'queued' and starting
        # a duplicate conversion.
        update_job(job['id'], status='converting', started_at=datetime.now().isoformat())
        app.logger.info(f"Claimed job {job['id']} for conversion (status → converting)")

    # Start conversion thread OUTSIDE the lock (thread will see status already set)
    thread = threading.Thread(
        target=convert_book,
        args=(job['id'], job['input_filename'], job['output_dirname'],
              job['voice'], job.get('is_pdf', False))
    )
    thread.daemon = True
    thread.start()
    app.logger.info(f"Started next queued job: {job['id']}")
    return True


def maybe_start_next_queued_job():
    if QUEUE_RUNNER_ENABLED:
        return start_next_queued_job()
    return False


# ============ Self-Healing Helpers ============

# Watchdog stall tracking: {job_id: (current_chapter, progress_percent, timestamp)}
_watchdog_last_progress = {}

STALL_TIMEOUT_MINUTES = 45   # Kill job if no progress (chapter OR chunk) for this long
ETA_KILL_MULTIPLIER = 3      # Kill job if elapsed > N × ETA


def wait_for_kokoro(timeout: int = 300, label: str = '') -> bool:
    """Wait for Kokoro TTS to become healthy, with polling.

    Returns True if Kokoro responded within timeout, False otherwise.
    """
    import time as _time
    prefix = f"[{label}] " if label else ""
    deadline = _time.time() + timeout
    attempt = 0
    while _time.time() < deadline:
        attempt += 1
        try:
            resp = requests.get(f"{KOKORO_URL}/audio/voices", timeout=8)
            if resp.status_code == 200:
                app.logger.info(f"{prefix}Kokoro healthy after {attempt * 10}s")
                return True
        except Exception:
            pass
        _time.sleep(10)
    app.logger.warning(f"{prefix}Kokoro not ready after {timeout}s")
    return False


def restart_kokoro(label: str = '') -> bool:
    """Restart Kokoro TTS container and wait for it to become healthy.

    Used proactively between books (clear memory leak) and reactively
    when Kokoro is detected as unhealthy.
    Returns True if Kokoro is healthy after restart.
    """
    prefix = f"[{label}] " if label else ""
    app.logger.info(f"{prefix}Restarting Kokoro TTS to clear memory")
    try:
        subprocess.run(['docker', 'restart', 'kokoro-tts'],
                       capture_output=True, timeout=120)
    except Exception as e:
        app.logger.error(f"{prefix}Failed to restart Kokoro: {e}")
        return False
    return wait_for_kokoro(timeout=300, label=label)


# ============ Auto-Retry Logic ============

def handle_job_failure(job_id, error_type, error_msg):
    """Handle job failure with smart recovery.

    When the container dies with partial output (some chapters already converted),
    tries chapter-level recovery instead of re-running the entire book.
    Falls back to full job retry if no partial output exists.

    Self-healing: always retries up to MAX_RETRY_COUNT regardless of error type.

    Args:
        job_id: The job ID
        error_type: Type of failure ('container_died', 'timeout', 'other')
        error_msg: Error message to store

    Returns:
        True if job was recovered/queued for retry, False if permanently failed
    """
    import time as time_module

    # Clean up watchdog stall tracking for this job
    _watchdog_last_progress.pop(job_id, None)

    job = get_job(job_id)
    if not job:
        return False

    retry_count = job.get('retry_count', 0)

    # Check for partial output — if chapters exist, try chapter-level recovery
    output_dirname = job.get('output_dirname', '')
    output_path = OUTPUT_DIR / output_dirname
    existing_files = list(output_path.glob('*.mp3')) if output_path.exists() else []

    if existing_files and error_type in ('container_died', 'timeout'):
        # Prevent duplicate recovery threads (watchdog can fire repeatedly)
        if _recovery_in_progress.get(job_id):
            app.logger.info(f"Job {job_id}: Recovery already in progress, skipping duplicate")
            return True

        app.logger.info(
            f"Job {job_id} died with {len(existing_files)} chapters done — "
            f"attempting chapter-level recovery")
        append_job_log(
            job_id,
            f"Container died with {len(existing_files)} chapters. "
            f"Starting chapter-level recovery instead of full restart.")

        _recovery_in_progress[job_id] = True

        # Use 'recovering' status so watchdog ignores this job
        with get_db() as conn:
            conn.execute('''
                UPDATE jobs
                SET retry_count = retry_count + 1,
                    status = 'recovering'
                WHERE id = ?
            ''', (job_id,))
            conn.commit()

        # Run recovery in background thread (it may take a while)
        def _do_recovery():
            time_module.sleep(30)  # Brief delay to let Kokoro settle
            try:
                recover_partial_conversion(job_id)
            except Exception as e:
                app.logger.error(f"Recovery failed for {job_id}: {e}")
                append_job_log(job_id, f"Recovery failed: {e}")
                with get_db() as conn:
                    conn.execute('''
                        UPDATE jobs
                        SET status = 'failed',
                            error = ?,
                            completed_at = ?
                        WHERE id = ?
                    ''', (f"Recovery failed: {e}", datetime.now().isoformat(), job_id))
                    conn.commit()
                maybe_start_next_queued_job()
            finally:
                _recovery_in_progress.pop(job_id, None)

        recovery_thread = threading.Thread(target=_do_recovery, daemon=True)
        recovery_thread.start()
        return True

    # No partial output — fall back to full job retry
    if retry_count < MAX_RETRY_COUNT and error_type in ('container_died', 'timeout'):
        delay = RETRY_BACKOFF_BASE * (2 ** retry_count)  # 30s, 60s, 120s
        new_rank = next_queue_rank()

        with get_db() as conn:
            conn.execute('''
                UPDATE jobs
                SET status = 'queued',
                    retry_count = retry_count + 1,
                    error = NULL,
                    started_at = NULL,
                    progress_percent = 0,
                    current_chapter = NULL,
                    current_chapter_name = NULL,
                    queue_rank = ?
                WHERE id = ?
            ''', (new_rank, job_id))
            conn.commit()

        app.logger.info(f"Auto-retrying job {job_id} (attempt {retry_count + 1}/{MAX_RETRY_COUNT}) after {delay}s delay")
        append_job_log(job_id, f"Auto-retry scheduled (attempt {retry_count + 1}/{MAX_RETRY_COUNT}) after {delay}s")

        def delayed_retry():
            time_module.sleep(delay)
            maybe_start_next_queued_job()

        retry_thread = threading.Thread(target=delayed_retry)
        retry_thread.daemon = True
        retry_thread.start()
        return True
    else:
        # Max retries exceeded or non-recoverable error
        final_error = f"Failed after {retry_count} retries: {error_msg}" if retry_count > 0 else error_msg
        with get_db() as conn:
            conn.execute('''
                UPDATE jobs
                SET status = 'failed',
                    error = ?,
                    completed_at = ?
                WHERE id = ?
            ''', (final_error, datetime.now().isoformat(), job_id))
            conn.commit()
        app.logger.error(f"Job {job_id} permanently failed: {final_error}")
        append_job_log(job_id, f"Permanently failed: {final_error}")
        return False


# ============ Watchdog Thread ============

def watchdog_loop():
    """Background thread to monitor job health.

    Runs every 60 seconds and checks for:
    1. Dead containers → recovery/retry
    2. Stalled progress (no chapter advance for STALL_TIMEOUT_MINUTES) → kill + retry
    3. Exceeded ETA_KILL_MULTIPLIER × ETA → kill + retry

    Self-healing: all detected failures feed into handle_job_failure() which
    does chapter-level recovery if partial output exists, or full retry up to
    MAX_RETRY_COUNT.
    """
    import time as time_module

    while True:
        time_module.sleep(60)  # Check every minute

        try:
            now = time_module.time()

            with get_db() as conn:
                active_jobs = conn.execute('''
                    SELECT id, container_name, started_at, eta_minutes, book_name,
                           current_chapter
                    FROM jobs
                    WHERE status IN ('converting', 'converting PDF', 'converting to audio')
                ''').fetchall()

                for job in active_jobs:
                    job_id = job['id']
                    container_name = job['container_name']
                    book_label = (job['book_name'] or '')[:30]
                    container_running = check_container_running(container_name)

                    # --- Check 1: Container dead ---
                    if not container_running:
                        if finalize_completed_job_if_outputs_exist(job_id):
                            _watchdog_last_progress.pop(job_id, None)
                            continue
                        app.logger.warning(
                            f"Watchdog: {book_label} container died, triggering recovery")
                        append_job_log(job_id, "Watchdog: container died — triggering recovery")
                        handle_job_failure(job_id, 'container_died',
                                          'Container died unexpectedly (detected by watchdog)')
                        continue

                    # --- Check 2: Progress stall (no chapter OR chunk advance) ---
                    # Track both current_chapter and progress_percent so that
                    # large chapters (e.g. 130K+ chars) making chunk progress
                    # aren't falsely killed as "stalled".
                    current_ch = job['current_chapter']
                    current_pct = job.get('progress_percent') or 0
                    prev = _watchdog_last_progress.get(job_id)

                    if prev is not None:
                        prev_ch, prev_pct, prev_time = prev
                        chapter_advanced = (current_ch is not None and current_ch != prev_ch)
                        chunk_advanced = (current_pct > prev_pct)

                        if chapter_advanced or chunk_advanced:
                            # Any progress (chapter or chunk) → reset stall timer
                            _watchdog_last_progress[job_id] = (current_ch, current_pct, now)
                        elif current_ch is not None:
                            stall_minutes = (now - prev_time) / 60
                            if stall_minutes >= STALL_TIMEOUT_MINUTES:
                                app.logger.warning(
                                    f"Watchdog: {book_label} STALLED at ch {current_ch} "
                                    f"({current_pct}%) for {stall_minutes:.0f} min — killing container")
                                append_job_log(
                                    job_id,
                                    f"Watchdog: stalled at ch {current_ch} ({current_pct}%) for "
                                    f"{stall_minutes:.0f} min — killing and retrying")
                                # Kill the stuck container
                                subprocess.run(['docker', 'stop', container_name],
                                               capture_output=True, timeout=10)
                                subprocess.run(['docker', 'rm', '-f', container_name],
                                               capture_output=True, timeout=10)
                                handle_job_failure(
                                    job_id, 'container_died',
                                    f'Stalled at chapter {current_ch} ({current_pct}%) for '
                                    f'{stall_minutes:.0f} min (watchdog kill)')
                                continue
                        # If current_ch is None, don't update — keep previous tracking
                    else:
                        # First time seeing this job — start tracking
                        if current_ch is not None:
                            _watchdog_last_progress[job_id] = (current_ch, current_pct, now)

                    # --- Check 3: Exceeded ETA_KILL_MULTIPLIER × ETA ---
                    eta_minutes = job['eta_minutes']
                    started_at = job['started_at']
                    if eta_minutes and eta_minutes > 0 and started_at:
                        elapsed = (datetime.now() - datetime.fromisoformat(
                            job['started_at'])).total_seconds() / 60
                        if elapsed > (eta_minutes * ETA_KILL_MULTIPLIER):
                            app.logger.warning(
                                f"Watchdog: {book_label} running {elapsed:.0f}min, "
                                f"exceeds {ETA_KILL_MULTIPLIER}x ETA ({eta_minutes}min) "
                                f"— killing container")
                            append_job_log(
                                job_id,
                                f"Watchdog: exceeded {ETA_KILL_MULTIPLIER}x ETA "
                                f"({elapsed:.0f}m vs {eta_minutes}m) — killing and retrying")
                            subprocess.run(['docker', 'stop', container_name],
                                           capture_output=True, timeout=10)
                            subprocess.run(['docker', 'rm', '-f', container_name],
                                           capture_output=True, timeout=10)
                            handle_job_failure(
                                job_id, 'timeout',
                                f'Exceeded {ETA_KILL_MULTIPLIER}x ETA '
                                f'({elapsed:.0f}min vs {eta_minutes}min ETA)')
                            continue
                        elif elapsed > (eta_minutes * 2):
                            app.logger.info(
                                f"Watchdog: {book_label} running {elapsed:.0f}min "
                                f"(2x ETA warning, will kill at {ETA_KILL_MULTIPLIER}x)")

            # Clean up stale tracking for jobs no longer active
            active_ids = {j['id'] for j in active_jobs} if active_jobs else set()
            stale_keys = [k for k in _watchdog_last_progress if k not in active_ids]
            for k in stale_keys:
                _watchdog_last_progress.pop(k, None)

        except Exception as e:
            app.logger.error(f"Watchdog error: {e}")


def start_watchdog():
    """Start the watchdog background thread."""
    watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    watchdog_thread.start()


def resume_inflight_jobs():
    """Reattach monitors to running conversion containers after restart."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, container_name
            FROM jobs
            WHERE status IN ('converting', 'converting PDF', 'converting to audio')
        ''').fetchall()

    resumed = 0
    for row in rows:
        job_id = row['id']
        container_name = row['container_name']
        if check_container_running(container_name):
            running_containers[job_id] = container_name
            monitor_thread = threading.Thread(target=monitor_conversion, args=(job_id, container_name), daemon=True)
            monitor_thread.start()
            resumed += 1
            app.logger.info(f"Resumed monitoring for job {job_id} ({container_name})")

    if resumed:
        app.logger.info(f"Recovered {resumed} in-flight conversion(s) after restart")


# ============ Utility Functions ============

def convert_to_epub(input_path: Path) -> Path:
    """Convert any supported ebook format to EPUB using Calibre's ebook-convert.

    Args:
        input_path: Path to the input ebook file

    Returns:
        Path to the EPUB file (same as input if already EPUB, otherwise converted)

    Raises:
        RuntimeError: If conversion fails
    """
    if input_path.suffix.lower() == '.epub':
        return input_path

    output_path = input_path.with_suffix('.epub')

    # Skip if already converted
    if output_path.exists():
        return output_path

    app.logger.info(f"Converting {input_path.name} to EPUB...")

    try:
        result = subprocess.run(
            ['ebook-convert', str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large files
        )

        if result.returncode != 0:
            raise RuntimeError(f"ebook-convert failed: {result.stderr[:500]}")

        app.logger.info(f"Converted to {output_path.name}")
        return output_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("Conversion timed out after 10 minutes")
    except FileNotFoundError:
        raise RuntimeError("Calibre ebook-convert not installed")


def estimate_epub_size(epub_path: Path) -> int:
    """Extract approximate character count from EPUB for timeout estimation."""
    try:
        total_chars = 0
        with zipfile.ZipFile(epub_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith(('.html', '.xhtml', '.htm')):
                    content = zf.read(name).decode('utf-8', errors='ignore')
                    text = re.sub(r'<[^>]+>', ' ', content)
                    total_chars += len(text)
        return total_chars
    except Exception as e:
        app.logger.warning(f"Could not estimate EPUB size: {e}")
        return 100000


def calculate_timeout(char_count: int) -> int:
    """Calculate timeout in seconds based on character count."""
    base_timeout = 1800  # 30 minutes minimum
    per_char_timeout = 0.06  # 60 seconds per 1000 chars
    calculated = base_timeout + int(char_count * per_char_timeout)
    return min(calculated, 86400)  # Cap at 24 hours


def get_voice_preview(voice_id: str) -> Path:
    """Generate or retrieve cached voice preview."""
    preview_path = PREVIEWS_DIR / f"{voice_id}.mp3"

    if preview_path.exists():
        return preview_path

    # Determine TTS engine from voice definition
    voice_info = VOICES.get(voice_id, {})
    engine = voice_info.get('engine', 'kokoro')

    try:
        if engine == 'piper':
            # Use Piper TTS
            response = requests.post(
                f"{PIPER_URL}/audio/speech",
                json={
                    "model": "tts-1",
                    "input": PREVIEW_TEXT,
                    "voice": voice_id
                },
                timeout=60
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)
        elif engine == 'polly':
            # Use AWS Polly via tts-proxy
            # Map internal network alias if available, otherwise assume localhost for dev
            proxy_base = os.environ.get('TTS_PROXY_URL', 'http://tts-proxy:8882')
            response = requests.post(
                f"{proxy_base}/j/preview/v1/audio/speech",
                json={
                    "model": "polly",
                    "input": PREVIEW_TEXT,
                    "voice": voice_id
                },
                timeout=60
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)
        elif engine == 'edge':
            # Use EdgeTTS via Docker
            # Map PREVIEWS_DIR to /output in the container
            cmd = [
                'docker', 'run', '--rm',
                '-v', f"{HOST_DATA_DIR}/previews:/output",
                'ghcr.io/p0n1/epub_to_audiobook:latest',
                '--voice_name', voice_id,
                '--tts', 'edge',
                '--preview', # This will output preview to console, but we want a file
                '--text', PREVIEW_TEXT,
                '--output_folder', '/output',
            ]
            # Wait, the p0n1 tool might not have a simple "generate preview file" command for Edge
            # Actually, we can use edge-tts directly if the container has it
            cmd = [
                'docker', 'run', '--rm',
                '-v', f"{HOST_DATA_DIR}/previews:/output",
                '--entrypoint', 'edge-tts',
                'ghcr.io/p0n1/epub_to_audiobook:latest',
                '--voice', voice_id,
                '--text', PREVIEW_TEXT,
                '--write-media', f"/output/{voice_id}.mp3"
            ]
            app.logger.info(f"Generating EdgeTTS preview: {' '.join(cmd)}")
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        else:
            # Use Kokoro TTS
            response = requests.post(
                f"{KOKORO_URL}/audio/speech",
                json={
                    "model": "kokoro",
                    "input": PREVIEW_TEXT,
                    "voice": voice_id,
                    "response_format": "mp3"
                },
                timeout=60
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)

        return preview_path
    except Exception as e:
        app.logger.error(f"Failed to generate preview for {voice_id}: {e}")
        return None


def rename_output_files(output_dir: Path, book_name: str) -> int:
    """Rename output MP3 files to human-readable format.

    Converts files like '001_chapter_name.mp3' to '01 - Chapter Name.mp3'
    Returns the number of files renamed.
    """
    renamed = 0
    mp3_files = sorted(output_dir.glob('*.mp3'))

    for mp3_file in mp3_files:
        original_name = mp3_file.stem

        # Parse the filename - typically format: 001_chapter_name or similar
        # Try to extract chapter number and name
        match = re.match(r'^(\d+)[_\-\s]*(.*)$', original_name)

        if match:
            chapter_num = int(match.group(1))
            chapter_name = match.group(2)

            # Clean up chapter name
            # Replace underscores with spaces
            chapter_name = chapter_name.replace('_', ' ')
            # Title case each word
            chapter_name = ' '.join(word.capitalize() for word in chapter_name.split())
            # Remove multiple spaces
            chapter_name = re.sub(r'\s+', ' ', chapter_name).strip()

            # If no chapter name, use generic
            if not chapter_name:
                chapter_name = f"Chapter {chapter_num}"

            # Create new filename: "01 - Chapter Name.mp3"
            new_name = f"{chapter_num:02d} - {chapter_name}.mp3"
            new_path = output_dir / new_name

            # Only rename if different and doesn't already exist
            if new_path != mp3_file and not new_path.exists():
                try:
                    mp3_file.rename(new_path)
                    renamed += 1
                    app.logger.debug(f"Renamed: {mp3_file.name} -> {new_name}")
                except Exception as e:
                    app.logger.warning(f"Failed to rename {mp3_file.name}: {e}")

    if renamed:
        app.logger.info(f"Renamed {renamed} files in {output_dir}")

    return renamed


MAX_CHAPTER_RETRIES = int(os.environ.get('MAX_CHAPTER_RETRIES', '3'))
"""Max times to retry a single chapter that failed TTS conversion (connection errors etc.)."""


def get_expected_chapter_count(output: str) -> int | None:
    """Parse 'Chapters count: N' from converter stdout/stderr."""
    m = re.search(r'Chapters count:\s*(\d+)', output)
    return int(m.group(1)) if m else None


def find_missing_chapters(output_dir: Path, total_chapters: int,
                          start_chapter: int | None = None,
                          end_chapter: int | None = None) -> list[int]:
    """Return 1-based chapter numbers that have no matching output file.

    The converter names files like ``0001_Title.mp3``, ``0002_Title.mp3``, etc.
    A chapter is 'missing' if no file with that prefix exists.

    When *start_chapter* / *end_chapter* are given (chapter-range jobs like
    quality samples), only chapters in that range are expected.
    """
    existing = set()
    for f in output_dir.glob('*.mp3'):
        m = re.match(r'^(\d{4})_', f.name)
        if m:
            existing.add(int(m.group(1)))

    first = start_chapter or 1
    last = end_chapter or total_chapters
    return [ch for ch in range(first, last + 1) if ch not in existing]


def retry_missing_chapters(
    job_id: str,
    missing: list[int],
    cmd_template: list[str],
    host_output_dir: str,
    output_path: Path,
    timeout_seconds: int,
) -> list[int]:
    """Re-run the converter for each missing chapter individually.

    Uses ``--chapter_start N --chapter_end N`` to convert one chapter at a time.
    Returns the list of chapters that still failed after all retries.
    """
    still_missing = []
    for ch in missing:
        success = False
        for attempt in range(1, MAX_CHAPTER_RETRIES + 1):
            retry_container = f"audiobook-{job_id}-retry-ch{ch}"
            # Build retry command — same as original but targeting a single chapter
            retry_cmd = [c for c in cmd_template]  # shallow copy
            # Replace container name
            name_idx = retry_cmd.index('--name') + 1
            retry_cmd[name_idx] = retry_container
            # Add/replace chapter range
            retry_cmd = [c for c in retry_cmd
                         if c not in ('--chapter_start', '--chapter_end')]
            # Also remove the values after those flags if present
            clean = []
            skip_next = False
            for c in retry_cmd:
                if skip_next:
                    skip_next = False
                    continue
                if c in ('--chapter_start', '--chapter_end'):
                    skip_next = True
                    continue
                clean.append(c)
            clean.extend(['--chapter_start', str(ch), '--chapter_end', str(ch)])

            app.logger.info(f"Retry chapter {ch} attempt {attempt}/{MAX_CHAPTER_RETRIES}")
            append_job_log(job_id, f"Retrying chapter {ch} (attempt {attempt}/{MAX_CHAPTER_RETRIES})")

            subprocess.run(['docker', 'rm', '-f', retry_container], capture_output=True)

            try:
                proc = subprocess.Popen(clean, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                subprocess.run(['docker', 'stop', retry_container], capture_output=True)
                app.logger.warning(f"Retry chapter {ch} attempt {attempt} timed out")
                continue
            finally:
                subprocess.run(['docker', 'rm', '-f', retry_container], capture_output=True)

            # Check if the chapter file now exists
            ch_files = list(output_path.glob(f'{ch:04d}_*.mp3'))
            if ch_files and all(f.stat().st_size > 1024 for f in ch_files):
                app.logger.info(f"Chapter {ch} recovered on attempt {attempt}")
                append_job_log(job_id, f"Chapter {ch} recovered on attempt {attempt}")
                success = True
                break
            else:
                app.logger.warning(f"Chapter {ch} still missing after attempt {attempt}")
                # Small delay before next attempt to let Kokoro recover
                import time
                time.sleep(10)

        if not success:
            still_missing.append(ch)
            append_job_log(job_id, f"Chapter {ch} FAILED after {MAX_CHAPTER_RETRIES} retries")

    return still_missing


def build_retry_cmd_from_job(job: dict) -> list[str]:
    """Reconstruct the docker run command from job metadata.

    Used by the watchdog recovery path when the original cmd variable
    is no longer available (container died, process lost).
    """
    job_id = job['id']
    input_filename = job['input_filename']
    output_dirname = job['output_dirname']
    voice = job['voice']
    tts_engine = job.get('tts_engine', 'kokoro')
    tts_speed = float(job.get('tts_speed') or DEFAULT_TTS_SPEED)

    host_input_path = f"{HOST_UPLOAD_DIR}/{input_filename}"
    host_output_dir = f"{HOST_OUTPUT_DIR}/{output_dirname}"

    # Handle EPUB from PDF conversion
    if job.get('is_pdf'):
        epub_filename = input_filename.rsplit('.', 1)[0] + '.epub'
        host_input_path = f"{HOST_UPLOAD_DIR}/{epub_filename}"

    # Effective voice (combine if voice2 specified for Kokoro)
    effective_voice = voice
    if tts_engine == 'kokoro' and job.get('voice2'):
        effective_voice = f"{voice}+{job['voice2']}"

    # TTS configuration
    if tts_engine == 'piper':
        tts_base_url = 'http://piper-tts:8000/v1'
        tts_model = 'tts-1'
    else:
        tts_base_url = KOKORO_URL
        tts_model = 'kokoro'

    # Optional TTS proxy
    if tts_engine == 'kokoro' and TTS_PROXY_URL:
        tts_base_url = f"{TTS_PROXY_URL}/j/{job_id}/v1"

    container_name = f"audiobook-{job_id}"

    cmd = [
        'docker', 'run', '--rm',
        '--name', container_name,
        '--network', 'epub-to-audiobook_default',
        '-e', 'OPENAI_API_KEY=not-needed',
        '-e', f'OPENAI_BASE_URL={tts_base_url}',
        '-v', f'{host_input_path}:/input/book.epub:ro',
        '-v', f'{host_output_dir}:/output',
        'ghcr.io/p0n1/epub_to_audiobook:latest',
        '/input/book.epub', '/output',
        '--tts', 'openai',
        '--voice_name', effective_voice,
        '--model_name', tts_model,
        '--no_prompt',
        '--remove_endnotes',
        '--speed', str(tts_speed),
    ]

    return cmd


def recover_partial_conversion(job_id: str):
    """Recover a job that died mid-conversion by retrying only missing chapters.

    Called by handle_job_failure when the container died but partial output
    (some MP3 files) already exists. Instead of re-running the entire book,
    this detects which chapters are missing and retries each individually.

    After retries, finalizes the job (rename, sync to ABS, notify).
    """
    # Guard against duplicate recovery threads (e.g. orphan cleanup + watchdog racing)
    # Use a separate lock-like dict to track which thread "owns" recovery.
    # _recovery_in_progress is set by callers (orphan cleanup, handle_job_failure)
    # before spawning threads, so we use a thread-local marker instead.
    _recovery_thread_key = f"_thread_{job_id}"
    if _recovery_in_progress.get(_recovery_thread_key):
        app.logger.info(f"Recovery {job_id}: Another recovery thread is already running, skipping")
        return
    _recovery_in_progress[_recovery_thread_key] = True

    try:
        _recover_partial_inner(job_id, _recovery_thread_key)
    finally:
        _recovery_in_progress.pop(_recovery_thread_key, None)
        _recovery_in_progress.pop(job_id, None)


def _recover_partial_inner(job_id: str, _recovery_thread_key: str):
    """Inner implementation of recover_partial_conversion (wrapped in try/finally)."""
    job = get_job(job_id)
    if not job:
        return

    output_dirname = job.get('output_dirname', '')
    output_path = OUTPUT_DIR / output_dirname
    host_output_dir = f"{HOST_OUTPUT_DIR}/{output_dirname}"

    # Chapter range (quality-sample jobs only convert a subset)
    start_chapter = job.get('start_chapter')
    end_chapter = job.get('end_chapter')

    # Count existing chapters
    existing_files = list(output_path.glob('*.mp3')) if output_path.exists() else []
    if not existing_files:
        app.logger.info(f"Recovery {job_id}: No output files, skipping chapter recovery")
        return

    # We need total_chapters from the DB or from counting EPUB chapters
    total_chapters = job.get('total_chapters')
    if not total_chapters:
        # Try counting chapters from the EPUB directly
        input_filename = job.get('input_filename', '')
        epub_path = UPLOAD_DIR / input_filename
        if job.get('is_pdf'):
            epub_filename = input_filename.rsplit('.', 1)[0] + '.epub'
            epub_path = UPLOAD_DIR / epub_filename
        if epub_path.exists():
            try:
                import zipfile
                with zipfile.ZipFile(epub_path) as zf:
                    # Count XHTML/HTML files in the EPUB (each is typically a chapter)
                    xhtml_files = [n for n in zf.namelist()
                                   if n.endswith(('.xhtml', '.html', '.htm'))
                                   and 'toc' not in n.lower()
                                   and 'nav' not in n.lower()]
                    if xhtml_files:
                        total_chapters = len(xhtml_files)
                        app.logger.info(
                            f"Recovery {job_id}: Counted {total_chapters} chapters from EPUB")
            except Exception as e:
                app.logger.warning(f"Recovery {job_id}: EPUB chapter count failed: {e}")

    if not total_chapters:
        # Fallback: use the highest chapter number found in output
        max_ch = 0
        for f in output_path.glob('*.mp3'):
            m = re.match(r'^(\d{4})_', f.name)
            if m:
                max_ch = max(max_ch, int(m.group(1)))
        if max_ch == 0:
            app.logger.warning(f"Recovery {job_id}: Can't determine chapter count")
            return
        total_chapters = max_ch
        app.logger.info(f"Recovery {job_id}: Using max chapter number {max_ch} as total")

    missing = find_missing_chapters(output_path, total_chapters,
                                    start_chapter=start_chapter,
                                    end_chapter=end_chapter)
    expected_desc = (f"ch {start_chapter}-{end_chapter}" if start_chapter and end_chapter
                     else f"{total_chapters} chapters")
    if not missing:
        app.logger.info(f"Recovery {job_id}: All {expected_desc} present, finalizing")
    else:
        app.logger.info(
            f"Recovery {job_id}: {len(existing_files)} files exist, "
            f"{len(missing)} chapters missing: {missing}")
        append_job_log(
            job_id,
            f"Container died with {len(existing_files)} chapters done. "
            f"Retrying {len(missing)} missing: {missing}")

        # Restart Kokoro before retries to clear memory leak
        append_job_log(job_id, "Restarting Kokoro TTS to clear memory before chapter retries")
        restart_kokoro(label=f"Recovery {job_id}")

        # Build cmd and retry missing chapters
        cmd = build_retry_cmd_from_job(job)
        char_count = job.get('char_count') or 500000
        timeout_seconds = calculate_timeout(char_count)

        still_missing = retry_missing_chapters(
            job_id, missing, cmd, host_output_dir, output_path, timeout_seconds)

        if still_missing:
            # ANY missing chapters → fail. No more half-finished audiobooks.
            error_msg = (f"Recovery failed: {len(still_missing)}/{total_chapters} chapters "
                         f"still missing after retries: {still_missing}")
            app.logger.error(f"Recovery {job_id}: {error_msg}")
            append_job_log(job_id, error_msg)
            update_job(
                job_id,
                status='failed',
                error=error_msg,
                completed_at=datetime.now().isoformat(),
            )
            maybe_start_next_queued_job()
            return
        else:
            app.logger.info(f"Recovery {job_id}: All {total_chapters} chapters recovered")
            append_job_log(job_id, f"All {total_chapters} chapters recovered after retries")

    # Finalize: rename, cleanup, sync, complete
    book_name = job['book_name']
    rename_output_files(output_path, book_name)
    removed = cleanup_small_files(output_path, MIN_CHAPTER_SIZE_KB)
    if removed:
        append_job_log(job_id, f"Removed {removed} small noise files (<{MIN_CHAPTER_SIZE_KB}KB)")

    output_files = list(output_path.glob('*.mp3'))

    # Final verification: NO incomplete audiobooks ever get marked complete
    is_ok, verify_msg = verify_book_complete(
        job_id, output_path, total_chapters,
        start_chapter=start_chapter, end_chapter=end_chapter,
        cleaned_up_count=removed)
    if not is_ok:
        error_msg = f"Verification failed after recovery: {verify_msg}"
        app.logger.error(f"Recovery {job_id}: {error_msg}")
        append_job_log(job_id, error_msg)
        update_job(
            job_id,
            status='failed',
            error=error_msg,
            completed_at=datetime.now().isoformat(),
        )
        maybe_start_next_queued_job()
        return
    append_job_log(job_id, f"Verification passed: {verify_msg}")

    synced = copy_to_audiobookshelf(output_path, book_name, job_id=job_id)

    update_job(
        job_id,
        status='completed',
        file_count=len(output_files),
        progress_percent=100,
        synced_to_abs=synced,
        completed_at=datetime.now().isoformat(),
        total_chapters=total_chapters,
    )
    app.logger.info(
        f"Recovery {job_id}: Completed with {len(output_files)} files, synced={synced}")
    append_job_log(job_id, f"Completed with {len(output_files)} chapters (recovery path)")

    job = get_job(job_id)
    if job:
        record_conversion_metrics(job)
        if job.get('notify_telegram'):
            send_telegram_notification(job, success=True)

    # Start next queued job
    maybe_start_next_queued_job()


def cleanup_small_files(output_dir: Path, min_size_kb: int = 500) -> int:
    """Remove MP3 files smaller than min_size_kb.

    These are typically photo captions, part dividers, or other noise
    that the EPUB converter produced from non-textual content.
    Returns the count of files removed.
    """
    removed = 0
    min_bytes = min_size_kb * 1024
    for mp3_file in sorted(output_dir.glob('*.mp3')):
        if mp3_file.stat().st_size < min_bytes:
            app.logger.info(f"Removing small file ({mp3_file.stat().st_size} bytes): {mp3_file.name}")
            mp3_file.unlink()
            removed += 1
    if removed:
        # Renumber remaining files sequentially
        remaining = sorted(output_dir.glob('*.mp3'))
        for idx, mp3_file in enumerate(remaining, 1):
            # Extract name after the track number prefix
            match = re.match(r'^\d+\s*-\s*(.*)$', mp3_file.stem)
            chapter_name = match.group(1) if match else mp3_file.stem
            new_name = f"{idx:02d} - {chapter_name}.mp3"
            new_path = output_dir / new_name
            if new_path != mp3_file:
                mp3_file.rename(new_path)
        app.logger.info(f"Cleaned up {removed} small files, renumbered {len(remaining)} remaining")
    return removed


def _trigger_abs_rescan(job_id: str | None = None):
    """Trigger an Audiobookshelf library rescan via the ABS API.

    This ensures chapter metadata is regenerated after files are synced.
    Failures are logged but do not affect job status.
    """
    if not ABS_API_TOKEN:
        return
    try:
        # First get library ID
        resp = requests.get(
            f"{ABS_API_URL}/api/libraries",
            headers={"Authorization": f"Bearer {ABS_API_TOKEN}"},
            timeout=10,
        )
        if resp.status_code != 200:
            app.logger.warning(f"ABS: Could not list libraries: {resp.status_code}")
            return
        libraries = resp.json().get('libraries', [])
        for lib in libraries:
            scan_resp = requests.post(
                f"{ABS_API_URL}/api/libraries/{lib['id']}/scan",
                headers={"Authorization": f"Bearer {ABS_API_TOKEN}"},
                timeout=10,
            )
            app.logger.info(f"ABS: Triggered rescan for library '{lib['name']}': {scan_resp.status_code}")
            if job_id:
                append_job_log(job_id, f"ABS rescan triggered for library '{lib['name']}'")
    except Exception as e:
        app.logger.warning(f"ABS rescan failed (non-fatal): {e}")


def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    """Copy completed audiobook to Audiobookshelf library via SSH."""
    if not AUDIOBOOKSHELF_DIR or not AUDIOBOOKSHELF_HOST:
        return False

    target = f"{AUDIOBOOKSHELF_USER}@{AUDIOBOOKSHELF_HOST}"
    # Use the output dir name for destination to avoid shell quoting issues (apostrophes, spaces, etc).
    # output_dirname already includes job_id for uniqueness.
    dest_folder = output_dir.name
    dest_path = f"{AUDIOBOOKSHELF_DIR}/{dest_folder}"

    ssh_args = [
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-F', '/dev/null',
        '-i', '/root/.ssh/id_ed25519',
    ]
    if AUDIOBOOKSHELF_PORT:
        ssh_args += ['-p', str(AUDIOBOOKSHELF_PORT)]
    rsync_ssh = 'ssh ' + ' '.join(shlex.quote(a) for a in ssh_args)

    if job_id:
        update_job(job_id,
            sync_target_host=AUDIOBOOKSHELF_HOST,
            sync_target_path=dest_path,
            sync_status='started',
            sync_error='',
            sync_timestamp=datetime.now().isoformat()
        )
        append_job_log(job_id, f"Sync start -> {target}:{dest_path}")

    try:
        # Ensure destination exists
        remote_mkdir = ' '.join(shlex.quote(x) for x in ['mkdir', '-p', '--', dest_path])
        mkdir_cmd = ['ssh', *ssh_args, target, remote_mkdir]
        mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)
        if mkdir_result.returncode != 0:
            err = (mkdir_result.stderr or mkdir_result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync mkdir failed: {err}")
            app.logger.error(f"Audiobookshelf mkdir failed: {err}")
            return False

        # Rsync to target
        cmd = ['rsync', '-av', '-e', rsync_ssh, f'{output_dir}/', f"{target}:{dest_path}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync failed: {err}")
            app.logger.error(f"Failed to copy to Audiobookshelf: {err}")
            return False

        # Count files at destination
        remote_count = f"find -- {shlex.quote(dest_path)} -type f | wc -l"
        count_cmd = ['ssh', *ssh_args, target, remote_count]
        count_result = subprocess.run(count_cmd, capture_output=True, text=True, timeout=30)
        file_count = 0
        if count_result.returncode == 0:
            try:
                file_count = int(count_result.stdout.strip())
            except Exception:
                file_count = 0

        if job_id:
            update_job(job_id,
                sync_status='ok',
                sync_file_count=file_count,
                sync_error='',
                sync_timestamp=datetime.now().isoformat()
            )
            append_job_log(job_id, f"Sync ok: {file_count} files")

        app.logger.info(f"Copied {book_name} to Audiobookshelf")

        # Trigger ABS library rescan so chapters are detected immediately
        _trigger_abs_rescan(job_id)

        return True
    except Exception as e:
        if job_id:
            update_job(job_id, sync_status='failed', sync_error=str(e))
            append_job_log(job_id, f"Sync exception: {e}")
        app.logger.error(f"Audiobookshelf copy failed: {e}")
        return False


def send_telegram_notification(job: dict, success: bool):
    """Send Telegram notification when job completes."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        if success:
            message = f"✅ Audiobook completed!\n\n📖 {job['book_name']}\n🎙️ Voice: {job['voice_name']}\n📁 {job.get('file_count', '?')} MP3 files"
            if job.get('synced_to_abs'):
                message += "\n☁️ Synced to Audiobookshelf"
        else:
            message = f"❌ Audiobook conversion failed\n\n📖 {job['book_name']}\n⚠️ {job.get('error', 'Unknown error')[:200]}"

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        app.logger.info(f"Sent Telegram notification for job {job['id']}")
    except Exception as e:
        app.logger.warning(f"Failed to send Telegram notification: {e}")


def parse_conversion_progress(container_name: str, job_id: str):
    """Parse conversion container logs to update progress."""
    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', '500', container_name],
            capture_output=True, text=True, timeout=5
        )
        logs = result.stderr + result.stdout

        job = get_job(job_id)

        # If conversion runs through tts-proxy, we can estimate progress from captured transcript chunks.
        # This handles cases where the conversion container is quiet (no usable stdout/stderr).
        def proxy_processed_chars() -> int | None:
            if not TTS_PROXY_URL:
                return None
            try:
                chunks_path = TRANSCRIPTS_DIR / job_id / "chunks.jsonl"
                if not chunks_path.exists():
                    _proxy_progress_state.pop(job_id, None)
                    return None

                st = _proxy_progress_state.get(job_id) or {"pos": 0, "chars": 0}
                pos = int(st.get("pos") or 0)
                chars = int(st.get("chars") or 0)

                size = chunks_path.stat().st_size
                if size < pos:
                    pos = 0
                    chars = 0

                with chunks_path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        s = obj.get("strict") or obj.get("text") or ""
                        chars += len(s)
                    pos = f.tell()

                _proxy_progress_state[job_id] = {"pos": pos, "chars": chars}
                return chars
            except Exception:
                return None

        # Parse total chapters — first try the tail-500 logs we already have
        chapters_match = re.search(r'Chapters count: (\d+)', logs)
        total_chapters = int(chapters_match.group(1)) if chapters_match else None

        # If not in tail, check the DB (already stored from a previous poll)
        if total_chapters is None and job:
            total_chapters = job.get('total_chapters')

        # Last resort: grep the FULL container log for the chapters count line.
        # This handles long conversions where --tail 500 has scrolled past it.
        if total_chapters is None:
            try:
                tc_result = subprocess.run(
                    ['docker', 'logs', container_name],
                    capture_output=True, text=True, timeout=10
                )
                tc_match = re.search(r'Chapters count: (\d+)', tc_result.stderr + tc_result.stdout)
                if tc_match:
                    total_chapters = int(tc_match.group(1))
            except Exception:
                pass

        # Parse current chapter being processed
        chapter_matches = re.findall(r'Processing chapter (\d+): (\w+)', logs)
        current_chapter = None
        current_chapter_name = None
        if chapter_matches:
            current_chapter = int(chapter_matches[-1][0])
            current_chapter_name = chapter_matches[-1][1].replace('_', ' ')

        # Count completed chapters from logs (tail-500 may undercount)
        completed = len(re.findall(r'Converted chapter \d+', logs))
        # If current_chapter is known and higher, use it as a better estimate
        # (current_chapter - 1 = chapters already done)
        if current_chapter and current_chapter - 1 > completed:
            completed = current_chapter - 1

        # Parse fine-grained progress (chunk X of Y)
        chunk_matches = re.findall(r'Processing chapter-(\d+)_.*?_chunk_(\d+)_of_(\d+)', logs)
        chunk_chapter = None
        chunk_idx = None
        chunk_total = None
        if chunk_matches:
            try:
                chunk_chapter = int(chunk_matches[-1][0])
                chunk_idx = int(chunk_matches[-1][1])
                chunk_total = int(chunk_matches[-1][2])
            except Exception:
                chunk_chapter = chunk_idx = chunk_total = None

        # Calculate progress and ETA
        progress_percent = None
        eta_minutes = None
        if total_chapters and current_chapter:
            frac = completed / total_chapters
            if chunk_chapter and chunk_idx and chunk_total and chunk_total > 0:
                # Only count chunk progress for the currently converting chapter.
                if (chunk_chapter == current_chapter) and (chunk_chapter == completed + 1):
                    frac += max(0.0, (chunk_idx - 1) / chunk_total) / total_chapters
            progress_percent = int(frac * 100)
            if progress_percent == 0 and frac > 0:
                progress_percent = 1

            # Get elapsed time and calculate ETA based on actual progress
            if job and job.get('started_at') and frac > 0.001:
                started = datetime.fromisoformat(job['started_at'])
                elapsed = (datetime.now() - started).total_seconds()
                remaining = elapsed * (1.0 / frac - 1.0)
                eta_minutes = int(remaining / 60)

        # Fallback: estimate progress from transcript capture (tts-proxy).
        # We prefer the max of (log-based progress, proxy-based progress).
        if job and job.get("char_count"):
            pchars = proxy_processed_chars()
            if pchars is not None and int(job["char_count"]) > 0:
                pfrac = max(0.0, min(1.0, pchars / float(job["char_count"])))
                pprog = int(pfrac * 100)
                if 0 < pprog < 100:
                    pprog = min(99, pprog)
                if progress_percent is None or (pprog is not None and pprog > (progress_percent or 0)):
                    progress_percent = pprog
                    if job.get("started_at") and pfrac > 0.001:
                        started = datetime.fromisoformat(job["started_at"])
                        elapsed = (datetime.now() - started).total_seconds()
                        remaining = elapsed * (1.0 / pfrac - 1.0)
                        eta_minutes = int(remaining / 60)

        # Update job — never overwrite stored values with None (tail-500 can
        # lose context, causing transient None values that shouldn't clobber DB).
        update_kwargs = {}
        for key, val in [
            ('total_chapters', total_chapters),
            ('current_chapter', current_chapter),
            ('current_chapter_name', current_chapter_name),
            ('progress_percent', progress_percent),
            ('eta_minutes', eta_minutes),
        ]:
            if val is not None:
                update_kwargs[key] = val
        if update_kwargs:
            update_job(job_id, **update_kwargs)

    except Exception as e:
        app.logger.debug(f"Could not parse progress: {e}")


def monitor_conversion(job_id: str, container_name: str):
    """Background thread to monitor conversion progress."""
    while True:
        job = get_job(job_id)
        if not job or job.get('status') not in ('converting', 'converting to audio'):
            break

        parse_conversion_progress(container_name, job_id)

        import time
        time.sleep(5)


# ============ Conversion Function ============

def convert_book(job_id: str, input_filename: str, output_dirname: str, voice: str, is_pdf: bool = False):
    """Run book conversion via Docker in background."""
    # Guard: if this job is already being converted (e.g. another process claimed it),
    # bail out immediately to prevent duplicate Docker containers.
    with _job_claim_lock:
        current = get_job(job_id)
        if current and current.get('status') == 'converting' and current.get('container_name'):
            app.logger.warning(
                f"Job {job_id} already has container {current['container_name']} — aborting duplicate start")
            return
        update_job(job_id, status='converting', started_at=datetime.now().isoformat())
    append_job_log(job_id, f"Conversion start (input={input_filename}, output={output_dirname})")

    host_input_path = f"{HOST_UPLOAD_DIR}/{input_filename}"
    host_output_dir = f"{HOST_OUTPUT_DIR}/{output_dirname}"
    local_input_path = UPLOAD_DIR / input_filename
    epub_path = local_input_path

    try:
        # PDF conversion
        if is_pdf:
            update_job(job_id, status='converting PDF')
            append_job_log(job_id, "PDF detected; converting to EPUB")
            epub_filename = input_filename.rsplit('.', 1)[0] + '.epub'
            host_epub_path = f"{HOST_UPLOAD_DIR}/{epub_filename}"

            pdf_cmd = [
                'docker', 'run', '--rm',
                '-v', f'{HOST_UPLOAD_DIR}:/data',
                'linuxserver/calibre:latest',
                'ebook-convert',
                f'/data/{input_filename}',
                f'/data/{epub_filename}'
            ]
            app.logger.info(f"Converting PDF: {' '.join(pdf_cmd)}")
            pdf_result = subprocess.run(pdf_cmd, capture_output=True, text=True, timeout=600)

            if pdf_result.returncode != 0:
                update_job(job_id,
                    status='failed',
                    error=f"PDF conversion failed: {pdf_result.stderr[:500]}",
                    completed_at=datetime.now().isoformat()
                )
                append_job_log(job_id, f"PDF conversion failed: {pdf_result.stderr[:200]}")
                return

            host_input_path = host_epub_path
            epub_path = UPLOAD_DIR / epub_filename
            update_job(job_id, status='converting to audio')

        # Preprocess EPUB for better TTS pronunciation (numbers, abbreviations, etc.)
        try:
            from tts_preprocess import preprocess_epub
            preprocessed_path = epub_path.parent / f"{epub_path.stem}_tts{epub_path.suffix}"
            preprocess_epub(epub_path, preprocessed_path)
            # Use preprocessed version for conversion, keep original for reference
            host_input_path = f"{HOST_UPLOAD_DIR}/{preprocessed_path.name}"
            epub_path = preprocessed_path
            append_job_log(job_id, "Text preprocessed (numbers, abbreviations normalized for TTS)")
        except Exception as e:
            app.logger.warning(f"TTS preprocessing failed, using original: {e}")
            append_job_log(job_id, f"TTS preprocessing skipped: {e}")

        # Calculate timeout and initial ETA using learning algorithm
        char_count = estimate_epub_size(epub_path)
        timeout_seconds = calculate_timeout(char_count)
        job = get_job(job_id)
        tts_engine = job.get('tts_engine', 'kokoro') if job else 'kokoro'
        start_chapter = job.get('start_chapter') if job else None
        end_chapter = job.get('end_chapter') if job else None
        file_type = 'pdf' if is_pdf else 'epub'
        initial_eta = estimate_eta_minutes(voice, tts_engine, file_type, char_count)
        update_job(job_id, char_count=char_count, timeout_minutes=timeout_seconds // 60, eta_minutes=initial_eta)
        app.logger.info(f"Book has ~{char_count:,} chars, ETA {initial_eta} min, timeout {timeout_seconds // 60} min")
        append_job_log(job_id, f"Estimated chars={char_count}, ETA={initial_eta}m, timeout={timeout_seconds // 60}m")

        # Verify Kokoro is healthy before starting conversion
        if tts_engine in ('kokoro', None):
            append_job_log(job_id, "Checking Kokoro TTS health...")
            if not wait_for_kokoro(timeout=30, label=f"Job {job_id}"):
                append_job_log(job_id, "Kokoro unhealthy — restarting before conversion")
                if not restart_kokoro(label=f"Job {job_id}"):
                    raise RuntimeError("Kokoro TTS not available after restart")
                append_job_log(job_id, "Kokoro restarted and healthy")

        # Generate unique container name
        container_name = f"audiobook-{job_id}"
        update_job(job_id, container_name=container_name)
        remove_stale_container(container_name)
        append_job_log(job_id, f"Using container {container_name}")

        # Determine effective voice (combine if voice2 specified - Kokoro only)
        effective_voice = voice
        if tts_engine == 'kokoro' and job and job.get('voice2'):
            effective_voice = f"{voice}+{job['voice2']}"

        # Configure TTS settings based on engine
        if tts_engine == 'piper':
            # Piper via openedai-speech
            tts_base_url = 'http://piper-tts:8000/v1'
            tts_model = 'tts-1'  # openedai-speech model name
            # For Piper, voice names are like 'en_GB-alan-medium'
            # openedai-speech expects just the voice name
        elif tts_engine == 'edge':
            # EdgeTTS (direct)
            tts_base_url = 'not-needed'
            tts_model = 'not-needed'
        elif tts_engine == 'polly':
            # AWS Polly via tts-proxy
            # We force it through proxy because the upstream tool doesn't support Polly natively
            tts_base_url = f"{TTS_PROXY_URL}/j/{job_id}/v1" if TTS_PROXY_URL else f"http://tts-proxy:8882/j/{job_id}/v1"
            tts_model = 'polly'
        else:
            # Kokoro (default)
            tts_base_url = KOKORO_URL
            tts_model = 'kokoro'

        # Optional: route TTS via proxy so we can capture exact text chunks for verification.
        if tts_engine == 'kokoro' and TTS_PROXY_URL:
            tts_base_url = f"{TTS_PROXY_URL}/j/{job_id}/v1"

        # Determine TTS speed for this job
        tts_speed = DEFAULT_TTS_SPEED
        if job and job.get('tts_speed'):
            tts_speed = float(job['tts_speed'])

                # Handle custom regex and global pronunciations
        search_conf_path = None
        host_search_conf_path = None
        
        global_conf = UPLOAD_DIR / 'global_pronunciations.conf'
        global_regex = ''
        if global_conf.exists():
            try:
                with open(global_conf, 'r', encoding='utf-8') as gf:
                    global_regex = gf.read() + '\n'
            except Exception as e:
                app.logger.warning(f"Could not read global_pronunciations.conf: {e}")
                
        custom_regex = job.get('custom_regex') or ''
        combined_regex = (global_regex + custom_regex).strip()
        
        if combined_regex:
            try:
                # Create temporary search.conf for this job
                conf_filename = f"search_{job_id}.conf"
                search_conf_path = UPLOAD_DIR / conf_filename
                with open(search_conf_path, 'w', encoding='utf-8') as f:
                    f.write(combined_regex)
                host_search_conf_path = f"{HOST_UPLOAD_DIR}/{conf_filename}"
                append_job_log(job_id, "Pronunciation regex rules (global + custom) applied")
            except Exception as e:
                app.logger.error(f"Failed to create search.conf: {e}")
                append_job_log(job_id, f"Warning: Failed to apply regex rules: {e}")

        # Run conversion
        cmd = [
            'docker', 'run', '--rm',
            '--name', container_name,
            '--network', 'epub-to-audiobook_default',
            '-e', 'OPENAI_API_KEY=not-needed',
            '-e', f'OPENAI_BASE_URL={tts_base_url}',
            '-v', f'{host_input_path}:/input/book.epub:ro',
            '-v', f'{host_output_dir}:/output',
        ]

        # Mount search.conf if exists
        if host_search_conf_path:
            cmd.extend(['-v', f'{host_search_conf_path}:/input/search.conf:ro'])

        cmd.extend([
            'ghcr.io/p0n1/epub_to_audiobook:latest',
            '/input/book.epub', '/output',
            '--tts', 'edge' if tts_engine == 'edge' else 'openai',
            '--voice_name', voice if tts_engine == 'edge' else effective_voice,
            '--model_name', tts_model,
            '--no_prompt',
            '--remove_endnotes',
            '--speed', str(tts_speed),
        ])

        # Pass parsing flags
        if job.get('newline_mode'):
            cmd.extend(['--newline_mode', job['newline_mode']])
        if job.get('title_mode'):
            cmd.extend(['--title_mode', job['title_mode']])
        if host_search_conf_path:
            cmd.extend(['--search_and_replace_file', '/input/search.conf'])

        # Add chapter selection if specified
        if job and job.get('start_chapter'):
            cmd.extend(['--chapter_start', str(job['start_chapter'])])
        if job and job.get('end_chapter'):
            cmd.extend(['--chapter_end', str(job['end_chapter'])])

        app.logger.info(f"Running conversion: {' '.join(cmd)}")
        append_job_log(job_id, f"Running conversion (engine={tts_engine}, voice={effective_voice})")

        # Start process
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        running_processes[job_id] = process
        running_containers[job_id] = container_name

        # Start progress monitor
        monitor_thread = threading.Thread(target=monitor_conversion, args=(job_id, container_name))
        monitor_thread.daemon = True
        monitor_thread.start()

        # Wait for completion
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            subprocess.run(['docker', 'stop', container_name], capture_output=True)
            raise
        finally:
            running_processes.pop(job_id, None)
            running_containers.pop(job_id, None)
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)

        # Check results
        output_path = Path(f"/data/audiobooks/{output_dirname}")
        output_files = list(output_path.glob('*.mp3')) if output_path.exists() else []

        # Finalize transcript capture (best effort; does not affect job outcome)
        if TTS_PROXY_URL:
            try:
                requests.post(f"{TTS_PROXY_URL}/j/{job_id}/finalize", timeout=10)
            except Exception:
                pass

        if process.returncode == 0 and output_files:
            # --- Chapter completeness check with retry ---
            combined_output = (stdout.decode(errors='replace') + '\n' +
                               stderr.decode(errors='replace'))
            total_chapters = get_expected_chapter_count(combined_output)
            if total_chapters:
                missing = find_missing_chapters(
                    output_path, total_chapters,
                    start_chapter=start_chapter, end_chapter=end_chapter)
                if missing:
                    app.logger.warning(
                        f"Job {job_id}: {len(missing)} chapters missing after initial run: {missing}")
                    append_job_log(
                        job_id, f"{len(missing)} chapters missing: {missing}. Handing off to recovery...")

                    # Hand off to recover_partial_conversion (same path the watchdog uses).
                    # This avoids a race between inline retry and watchdog recovery.
                    _recovery_in_progress[job_id] = True
                    with get_db() as conn:
                        conn.execute('''
                            UPDATE jobs SET status = 'recovering',
                                           retry_count = COALESCE(retry_count, 0) + 1
                            WHERE id = ?
                        ''', (job_id,))
                        conn.commit()

                    def _inline_recovery():
                        try:
                            recover_partial_conversion(job_id)
                        finally:
                            _recovery_in_progress.pop(job_id, None)

                    threading.Thread(target=_inline_recovery, daemon=True).start()
                    app.logger.info(f"Job {job_id}: Recovery thread started for {len(missing)} missing chapters")
                    return  # Exit convert_book — recovery thread handles everything from here
                else:
                    app.logger.info(f"Job {job_id}: All {total_chapters} chapters present")
                    append_job_log(job_id, f"All {total_chapters} chapters present (no retries needed)")

            # Rename files to human-readable format
            job = get_job(job_id)
            rename_output_files(output_path, job['book_name'])

            # Remove small noise files (photo captions, part dividers, etc.)
            removed = cleanup_small_files(output_path, MIN_CHAPTER_SIZE_KB)
            if removed:
                append_job_log(job_id, f"Removed {removed} small noise files (<{MIN_CHAPTER_SIZE_KB}KB)")

            # Re-count files after renaming and cleanup
            output_files = list(output_path.glob('*.mp3'))

            # Final verification: NO incomplete audiobooks ever get marked complete
            total_ch = job.get('total_chapters')
            is_ok, verify_msg = verify_book_complete(
                job_id, output_path, total_ch,
                start_chapter=job.get('start_chapter'),
                end_chapter=job.get('end_chapter'),
                cleaned_up_count=removed)
            if not is_ok:
                error_msg = f"Verification failed: {verify_msg}"
                app.logger.error(f"Job {job_id}: {error_msg}")
                append_job_log(job_id, error_msg)
                update_job(job_id, status='failed', error=error_msg,
                           completed_at=datetime.now().isoformat())
                maybe_start_next_queued_job()
                return
            append_job_log(job_id, f"Verification passed: {verify_msg}")

            # Sync to Audiobookshelf
            synced = copy_to_audiobookshelf(output_path, job['book_name'], job_id=job_id)

            # Best-effort transcript verification (only meaningful if TTS_PROXY_URL is enabled).
            try:
                verify_tts_against_epub(job_id, epub_path, output_path)
            except Exception:
                pass

            # Best-effort sampled ASR verification (audio -> transcript -> align vs EPUB).
            # Runs in a separate container to avoid pulling heavy dependencies into the webapp image.
            try:
                threading.Thread(
                    target=_run_audio_asr_verify_sample,
                    args=(job_id, epub_path.name, output_dirname),
                    daemon=True,
                ).start()
            except Exception:
                pass

            update_job(job_id,
                status='completed',
                file_count=len(output_files),
                progress_percent=100,
                synced_to_abs=synced,
                completed_at=datetime.now().isoformat()
            )
            app.logger.info(f"Job {job_id} completed with {len(output_files)} files")
            append_job_log(job_id, f"Completed with {len(output_files)} files")

            # Record conversion metrics for ETA learning
            job = get_job(job_id)
            if job:
                record_conversion_metrics(job)

            # Send Telegram notification if requested
            if job and job.get('notify_telegram'):
                send_telegram_notification(job, success=True)
        else:
            error_msg = stderr.decode()[:1000] if stderr else 'No output files created'
            app.logger.error(f"Job {job_id} failed: {error_msg}")
            append_job_log(job_id, f"Failed: {error_msg[:200]}")

            # Always attempt recovery/retry for conversion failures.
            # handle_job_failure respects MAX_RETRY_COUNT and will
            # permanently fail the job after exhausting retries.
            retried = handle_job_failure(job_id, 'container_died', error_msg)

            # Send Telegram notification if NOT being retried
            if not retried:
                job = get_job(job_id)
                if job and job.get('notify_telegram'):
                    send_telegram_notification(job, success=False)

    except subprocess.TimeoutExpired:
        job = get_job(job_id)
        timeout_mins = job.get('timeout_minutes', 'unknown') if job else 'unknown'
        error_msg = f'Conversion timed out after {timeout_mins} minutes'
        app.logger.error(f"Job {job_id} timed out")
        append_job_log(job_id, error_msg)
        retried = handle_job_failure(job_id, 'timeout', error_msg)

        # Send Telegram notification if NOT being retried
        if not retried:
            job = get_job(job_id)
            if job and job.get('notify_telegram'):
                send_telegram_notification(job, success=False)

    except Exception as e:
        update_job(job_id, status='failed', error=str(e), completed_at=datetime.now().isoformat())
        app.logger.error(f"Job {job_id} exception: {e}")
        append_job_log(job_id, f"Exception: {e}")
    finally:
        # Clean up watchdog stall tracking
        _watchdog_last_progress.pop(job_id, None)

        # Proactively restart Kokoro between books to clear memory leak.
        # CPU Kokoro leaks ~1GB per chapter; restarting between books prevents
        # mid-chapter crashes that kill active conversions.
        # Skip in GPU mode — GPU Kokoro is on Vast.ai, local restart is pointless
        # and would interfere with other parallel GPU jobs.
        job_final = get_job(job_id)
        tts_final = job_final.get('tts_engine', 'kokoro') if job_final else 'kokoro'
        if tts_final in ('kokoro', None) and not _is_gpu_mode():
            app.logger.info("Proactively restarting Kokoro between books (memory leak prevention)")
            restart_kokoro(label="between-books")

        # Start next queued job (one at a time queue system)
        maybe_start_next_queued_job()


# ============ Routes ============

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html', voices=VOICES, engines=TTS_ENGINES)


@app.route('/api/voices')
def list_voices():
    """Return available voices grouped by engine."""
    return jsonify({
        'voices': VOICES,
        'engines': TTS_ENGINES
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update system settings/API keys."""
    # List of keys that should be masked in the UI
    secret_keys = [
        'AWS_SECRET_ACCESS_KEY', 'AWS_ACCESS_KEY_ID',
        'OPENAI_API_KEY', 'TELEGRAM_BOT_TOKEN',
        'EVOLUTION_API_KEY', 'ABS_API_TOKEN'
    ]

    if request.method == 'POST':
        try:
            data = request.json
            for key, value in data.items():
                if value and value.strip():
                    set_setting(key, value.strip())
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # GET: return current settings (masked)
    settings = {}
    for key in secret_keys:
        val = get_setting(key)
        if val:
            # Mask key: show first 4 and last 4 chars
            if len(val) > 10:
                settings[key] = f"{val[:4]}...{val[-4:]}"
            else:
                settings[key] = "********"
        else:
            settings[key] = ""
    
    return jsonify(settings)


# ============ GPU Auto-Scaling API ============

# GPU manager singleton — set by the worker process at startup.
# The webapp process can read status but scaling actions happen in the worker.
_gpu_manager = None


def set_gpu_manager(mgr):
    """Called by worker.py to register the GPU manager instance."""
    global _gpu_manager
    _gpu_manager = mgr


def _is_gpu_mode() -> bool:
    """Check if TTS is currently routed to a GPU instance."""
    return _gpu_manager is not None and _gpu_manager.state == 'active'


@app.route('/api/gpu/status')
def gpu_status():
    """Get current GPU state."""
    if _gpu_manager:
        return jsonify(_gpu_manager.get_status())
    # Webapp process: read status from shared file written by worker
    try:
        from gpu_manager import GPUManager
        status = GPUManager.load_status_from_file()
        if status:
            return jsonify(status)
    except ImportError:
        pass
    return jsonify({
        'state': 'idle',
        'autoscale_enabled': os.environ.get('AUTOSCALE_ENABLED', 'false').lower() in ('1', 'true', 'yes'),
        'autoscale_threshold': int(os.environ.get('AUTOSCALE_THRESHOLD', '3')),
        'cost_cap': float(os.environ.get('AUTOSCALE_COST_CAP', '1.00')),
    })


@app.route('/api/gpu/scale-up', methods=['POST'])
def gpu_scale_up():
    """Manually trigger GPU scale-up."""
    if not _gpu_manager:
        return jsonify({'error': 'GPU manager not available'}), 503
    if _gpu_manager.state == 'active':
        return jsonify({'status': 'already_active', **_gpu_manager.get_status()})
    if _gpu_manager.state == 'provisioning':
        return jsonify({'status': 'provisioning', **_gpu_manager.get_status()})

    # Run scale-up in background thread to avoid blocking the request
    import threading
    def _do_scale_up():
        _gpu_manager.scale_up()
    threading.Thread(target=_do_scale_up, daemon=True).start()
    return jsonify({'status': 'provisioning'})


@app.route('/api/gpu/scale-down', methods=['POST'])
def gpu_scale_down():
    """Manually trigger GPU scale-down."""
    if not _gpu_manager:
        return jsonify({'error': 'GPU manager not available'}), 503
    if _gpu_manager.state == 'idle':
        return jsonify({'status': 'already_idle'})

    _gpu_manager.scale_down()
    return jsonify({'status': 'idle', **_gpu_manager.get_status()})


@app.route('/api/health')
def health_check():
    """System health check endpoint.

    Checks:
    - webapp: Always ok if this endpoint responds
    - database: SQLite connection test
    - kokoro: Kokoro TTS service availability

    Returns:
    - 200 when core services are healthy (or degraded due to optional dependency latency)
    - 503 when core services fail
    """
    checks = {
        'webapp': 'ok',
        'version': APP_VERSION,
        'git_sha': APP_GIT_SHA,
        'stack_path': STACK_PATH
    }

    # Check database
    try:
        with get_db() as conn:
            conn.execute('SELECT 1').fetchone()
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = str(e)

    # Check Kokoro TTS with retries (can be slow under load)
    kokoro_error = None
    checks['kokoro'] = 'degraded'
    for _ in range(max(1, HEALTH_KOKORO_RETRIES)):
        try:
            resp = requests.get(f"{KOKORO_URL}/audio/voices", timeout=HEALTH_KOKORO_TIMEOUT)
            if resp.status_code == 200:
                checks['kokoro'] = 'ok'
                kokoro_error = None
                break
            kokoro_error = f'HTTP {resp.status_code}'
        except Exception as e:
            kokoro_error = str(e)
    if kokoro_error and checks['kokoro'] != 'ok':
        checks['kokoro_detail'] = kokoro_error

    core_ok = checks.get('webapp') == 'ok' and checks.get('database') == 'ok'
    if core_ok and checks.get('kokoro') == 'ok':
        checks['overall'] = 'ok'
    elif core_ok:
        checks['overall'] = 'degraded'
    else:
        checks['overall'] = 'failed'

    return jsonify(checks), 200 if core_ok else 503


@app.route('/api/version')
def version_info():
    """Deployment fingerprint for release/debug parity checks."""
    return jsonify({
        'version': APP_VERSION,
        'git_sha': APP_GIT_SHA,
        'build_time': APP_BUILD_TIME,
        'stack_path': STACK_PATH,
        'host_stack_dir': HOST_STACK_DIR,
        'kokoro_url': KOKORO_URL,
        'piper_url': PIPER_URL
    })


@app.route('/api/history')
def get_history():
    """Get conversion history (completed books)."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT * FROM jobs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 100
        ''').fetchall()
        return jsonify([job_to_dict(row) for row in rows])


@app.route('/api/preview/<voice_id>')
def voice_preview(voice_id: str):
    """Stream voice preview audio."""
    if voice_id not in VOICES:
        return jsonify({'error': 'Voice not found'}), 404

    preview_path = get_voice_preview(voice_id)
    if preview_path and preview_path.exists():
        return send_file(preview_path, mimetype='audio/mpeg')

    return jsonify({'error': 'Preview not available'}), 500


@app.route('/api/convert', methods=['POST'])
def start_conversion():
    """Start ebook to audiobook conversion.

    Supports: EPUB, PDF, MOBI, AZW3, FB2, TXT, HTML, DOCX
    Non-EPUB formats are converted via Calibre's ebook-convert.
    """
    if 'file' not in request.files and 'epub' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    uploaded_file = request.files.get('file') or request.files.get('epub')
    voice = request.form.get('voice', DEFAULT_VOICE)
    voice2 = request.form.get('voice2', '').strip() or None
    start_chapter = request.form.get('start_chapter', '').strip()
    end_chapter = request.form.get('end_chapter', '').strip()
    notify_telegram = request.form.get('notify_telegram') == '1'
    notify_whatsapp = request.form.get('notify_whatsapp') == '1'
    whatsapp_number = request.form.get('whatsapp_number', '').strip()
    tts_speed_raw = request.form.get('tts_speed', '').strip()
    tts_speed = float(tts_speed_raw) if tts_speed_raw else DEFAULT_TTS_SPEED

    # New parsing and pronunciation options
    newline_mode = request.form.get('newline_mode', 'double')
    title_mode = request.form.get('title_mode', 'auto')
    custom_regex = request.form.get('custom_regex', '').strip() or None

    # Parse chapter numbers
    start_chapter = int(start_chapter) if start_chapter else None
    end_chapter = int(end_chapter) if end_chapter else None

    filename_lower = uploaded_file.filename.lower()
    file_ext = Path(filename_lower).suffix

    # Check if format is supported
    if file_ext not in SUPPORTED_FORMATS:
        return jsonify({'error': f'Unsupported format. Supported: {", ".join(sorted(SUPPORTED_FORMATS))}'}), 400

    is_pdf = file_ext == '.pdf'
    needs_conversion = file_ext not in {'.epub', '.pdf'}  # PDF handled separately by Docker

    if voice not in VOICES:
        return jsonify({'error': 'Invalid voice selected'}), 400

    if voice2 and voice2 not in VOICES:
        return jsonify({'error': 'Invalid secondary voice selected'}), 400

    # Create job
    job_id = str(uuid.uuid4())[:8]
    book_name = Path(uploaded_file.filename).stem
    safe_name = "".join(c for c in book_name if c.isalnum() or c in ' -_').strip()

    # Save file with original extension
    input_filename = f"{job_id}_{safe_name}{file_ext}"
    input_path = UPLOAD_DIR / input_filename
    uploaded_file.save(input_path)

    # Convert non-standard formats to EPUB using Calibre
    if needs_conversion:
        try:
            epub_path = convert_to_epub(input_path)
            input_filename = epub_path.name
            input_path = epub_path
        except RuntimeError as e:
            return jsonify({'error': f'Format conversion failed: {str(e)}'}), 500

    # Create output directory
    output_dirname = f"{safe_name}_{job_id}"
    output_dir = OUTPUT_DIR / output_dirname
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine TTS engine from voice
    tts_engine = VOICES[voice].get('engine', 'kokoro')

    # Save job to database
    job = {
        'id': job_id,
        'book_name': book_name,
        'voice': voice,
        'voice_name': VOICES[voice]['name'],
        'voice2': voice2,
        'voice2_name': VOICES.get(voice2, {}).get('name') if voice2 else None,
        'tts_engine': tts_engine,
        'status': 'queued',
        'created_at': datetime.now().isoformat(),
        'input_filename': input_filename,
        'output_dirname': output_dirname,
        'is_pdf': is_pdf,
        'start_chapter': start_chapter,
        'end_chapter': end_chapter,
        'notify_telegram': notify_telegram,
        'tts_speed': tts_speed,
        'queue_rank': next_queue_rank(),
        'sync_status': 'pending',
        'job_log_path': str(get_job_log_path(job_id)),
        'newline_mode': newline_mode,
        'title_mode': title_mode,
        'custom_regex': custom_regex
    }
    save_job(job)
    append_job_log(job_id, f"Job created: {book_name} (voice={voice}, engine={tts_engine}, speed={tts_speed})")

    # Do NOT start convert_book() here — let the worker pick it up from the queue.
    # The webapp should NEVER run conversions directly to prevent dual-execution bugs
    # where both webapp and worker start the same job simultaneously.
    app.logger.info(f"Job {job_id} queued — worker will pick it up")

    return jsonify({'job_id': job_id, 'status': 'queued'})


@app.route('/api/jobs')
def list_jobs():
    """List all conversion jobs."""
    # Refresh progress for active jobs so the UI doesn't show 0% for long-running chapters.
    jobs = get_all_jobs()
    now = datetime.now().timestamp()
    if not hasattr(list_jobs, '_last_parse'):
        list_jobs._last_parse = {}
    last_parse = list_jobs._last_parse

    for j in jobs:
        if j.get('status') in ('converting', 'converting PDF', 'converting to audio'):
            cname = j.get('container_name') or ''
            if not cname:
                continue
            prev = float(last_parse.get(j['id'], 0))
            if now - prev >= 5:
                parse_conversion_progress(cname, j['id'])
                last_parse[j['id']] = now

    return jsonify(get_all_jobs())


@app.route('/api/queue/status')
def queue_status():
    """Get queue control status."""
    with get_db() as conn:
        queued_count = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE status='queued'").fetchone()['n']
    return jsonify({
        'paused': is_queue_paused(),
        'queued_count': queued_count
    })


@app.route('/api/queue/pause', methods=['POST'])
def queue_pause():
    """Pause or resume queue processing."""
    data = request.get_json(silent=True) or {}
    paused = data.get('paused')
    if paused is None:
        paused = not is_queue_paused()
    paused = bool(paused)
    set_queue_paused(paused)
    if not paused:
        maybe_start_next_queued_job()
    return jsonify({'paused': paused})


@app.route('/api/queue/reorder', methods=['POST'])
def queue_reorder():
    """Reorder queued jobs by explicit ID order."""
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get('ordered_ids') or []
    if not isinstance(ordered_ids, list):
        return jsonify({'error': 'ordered_ids must be a list'}), 400

    with get_db() as conn:
        queued_rows = conn.execute(
            "SELECT id FROM jobs WHERE status='queued' ORDER BY COALESCE(queue_rank, 0), created_at"
        ).fetchall()
        queued_ids = [r['id'] for r in queued_rows]
        known = set(queued_ids)

        normalized = []
        for jid in ordered_ids:
            if jid in known and jid not in normalized:
                normalized.append(jid)
        for jid in queued_ids:
            if jid not in normalized:
                normalized.append(jid)

        for rank, jid in enumerate(normalized, start=1):
            conn.execute("UPDATE jobs SET queue_rank = ? WHERE id = ?", (rank, jid))
        conn.commit()

    return jsonify({'status': 'ok', 'ordered_ids': normalized})


@app.route('/api/queue/retry-failed', methods=['POST'])
def queue_retry_failed():
    """Bulk queue failed/cancelled jobs that still have retry budget."""
    data = request.get_json(silent=True) or {}
    limit = int(data.get('limit', 20))
    if limit < 1:
        return jsonify({'error': 'limit must be >= 1'}), 400

    queued = []
    with get_db() as conn:
        max_rank_row = conn.execute('SELECT COALESCE(MAX(queue_rank), 0) AS max_rank FROM jobs').fetchone()
        rank_cursor = int((max_rank_row['max_rank'] if max_rank_row else 0) or 0)
        rows = conn.execute('''
            SELECT * FROM jobs
            WHERE status IN ('failed', 'cancelled')
            ORDER BY completed_at DESC
            LIMIT ?
        ''', (limit,)).fetchall()

        for row in rows:
            job = job_to_dict(row)
            retry_count = job.get('retry_count', 0) or 0
            if retry_count >= 3:
                continue
            input_path = UPLOAD_DIR / job['input_filename']
            if not input_path.exists():
                continue
            new_retry = retry_count + 1
            rank_cursor += 1
            conn.execute('''
                UPDATE jobs
                SET status='queued',
                    started_at=NULL,
                    completed_at=NULL,
                    error=NULL,
                    current_chapter=NULL,
                    current_chapter_name=NULL,
                    progress_percent=NULL,
                    eta_minutes=NULL,
                    file_count=NULL,
                    retry_count=?,
                    queue_rank=?
                WHERE id=?
            ''', (new_retry, rank_cursor, job['id']))
            queued.append(job['id'])
        conn.commit()

    maybe_start_next_queued_job()
    return jsonify({'status': 'ok', 'queued_ids': queued})


@app.route('/api/jobs/<job_id>')
def get_job_status(job_id: str):
    """Get job status."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)


@app.route('/api/jobs/<job_id>/timeline')
def get_job_timeline(job_id: str):
    """Return derived timeline stages for a job."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    status = job.get('status') or ''
    current_chapter = job.get('current_chapter')
    total_chapters = job.get('total_chapters')

    stages = [
        {'id': 'queued', 'label': 'Queued', 'state': 'done' if status != 'queued' else 'active'},
        {'id': 'extract', 'label': 'Extract/Prepare', 'state': 'done' if status not in ('queued', 'converting PDF') else ('active' if status == 'converting PDF' else 'pending')},
        {'id': 'tts', 'label': 'TTS Conversion', 'state': 'active' if 'converting' in status else ('done' if status == 'completed' else 'pending')},
        {'id': 'sync', 'label': 'Sync/Finalize', 'state': 'done' if status == 'completed' else 'pending'}
    ]

    return jsonify({
        'job_id': job_id,
        'status': status,
        'current_chapter': current_chapter,
        'total_chapters': total_chapters,
        'progress_percent': job.get('progress_percent'),
        'retry_count': job.get('retry_count', 0),
        'stages': stages
    })


@app.route('/api/jobs/<job_id>/logs')
def get_job_logs(job_id: str):
    """Return tail logs for the job (file + container)."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    tail = request.args.get('tail', '200')
    try:
        tail = max(10, min(500, int(tail)))
    except Exception:
        tail = 200

    log_path = Path(job.get('job_log_path') or get_job_log_path(job_id))
    file_logs = tail_text_file(log_path, max_lines=tail)

    container_name = (job.get('container_name') or '').strip()
    if not container_name:
        return jsonify({'logs': file_logs, 'container': None, 'container_logs': ''})
    if not re.match(r'^[a-zA-Z0-9_.-]+$', container_name):
        return jsonify({'error': 'Invalid container name'}), 400
    include_container = request.args.get('include_container', '1') not in ('0', 'false', 'no')
    container_logs = ''
    if include_container:
        try:
            result = subprocess.run(
                ['docker', 'logs', '--tail', str(tail), container_name],
                capture_output=True, text=True, timeout=8
            )
            container_logs = ((result.stdout or '') + (result.stderr or ''))[-15000:]
        except Exception as e:
            return jsonify({'container': container_name, 'logs': file_logs, 'container_logs': '', 'error': str(e)}), 500

    combined_logs = file_logs
    if container_logs:
        combined_logs = (file_logs + "\n--- container ---\n" + container_logs).strip()

    return jsonify({'container': container_name, 'logs': combined_logs, 'container_logs': container_logs})


@app.route('/api/diagnostics')
def diagnostics():
    """Return queue/runtime diagnostics for UI drawer."""
    with get_db() as conn:
        counts = conn.execute('''
            SELECT status, COUNT(*) AS n
            FROM jobs
            GROUP BY status
        ''').fetchall()
    by_status = {row['status']: row['n'] for row in counts}

    docker_summary = ''
    try:
        result = subprocess.run(
            ['docker', 'stats', '--no-stream', '--format', '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}'],
            capture_output=True, text=True, timeout=6
        )
        lines = [ln for ln in (result.stdout or '').splitlines() if 'epub' in ln or 'kokoro' in ln or 'piper' in ln or 'audiobook-' in ln]
        docker_summary = '\n'.join(lines[:20])
    except Exception as e:
        docker_summary = f'Unavailable: {e}'

    return jsonify({
        'queue_paused': is_queue_paused(),
        'queue_runner_enabled': QUEUE_RUNNER_ENABLED,
        'jobs': by_status,
        'docker': docker_summary,
        'audiobookshelf_target': f"{AUDIOBOOKSHELF_USER}@{AUDIOBOOKSHELF_HOST}:{AUDIOBOOKSHELF_DIR}" if AUDIOBOOKSHELF_DIR else ''
    })


@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id: str):
    """Cancel a running job."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] not in ('queued', 'converting', 'converting PDF', 'converting to audio'):
        return jsonify({'error': 'Job is not running'}), 400

    # Stop the container if running
    container_name = job.get('container_name')
    if container_name:
        try:
            subprocess.run(['docker', 'stop', container_name], capture_output=True, timeout=10)
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True, timeout=10)
        except Exception as e:
            app.logger.warning(f"Could not stop container: {e}")

    # Kill the process if tracked
    if job_id in running_processes:
        try:
            running_processes[job_id].kill()
        except Exception:
            pass
        running_processes.pop(job_id, None)

    running_containers.pop(job_id, None)

    update_job(job_id,
        status='cancelled',
        error='Cancelled by user',
        completed_at=datetime.now().isoformat()
    )

    return jsonify({'status': 'cancelled'})


@app.route('/api/jobs/<job_id>/retry', methods=['POST'])
def retry_job(job_id: str):
    """Retry a failed or cancelled job.

    Limits retries to 3 attempts to prevent infinite retry loops.
    """
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] not in ('failed', 'cancelled'):
        return jsonify({'error': 'Can only retry failed or cancelled jobs'}), 400

    # Check retry limit (max 3 retries)
    retry_count = job.get('retry_count', 0) or 0
    if retry_count >= 3:
        return jsonify({
            'error': f'Maximum retry limit (3) exceeded. Job has been retried {retry_count} times.'
        }), 400

    # Check if input file still exists
    input_path = UPLOAD_DIR / job['input_filename']
    if not input_path.exists():
        return jsonify({'error': 'Input file no longer exists'}), 400

    # Clear output directory
    output_dir = OUTPUT_DIR / job['output_dirname']
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Increment retry count and reset job
    new_retry_count = retry_count + 1
    update_job(job_id,
        status='queued',
        started_at=None,
        completed_at=None,
        error=None,
        current_chapter=None,
        current_chapter_name=None,
        progress_percent=None,
        eta_minutes=None,
        file_count=None,
        synced_to_abs=False,
        retry_count=new_retry_count,
        queue_rank=next_queue_rank()
    )

    app.logger.info(f"Retrying job {job_id} (attempt {new_retry_count}/3)")

    # Do NOT start convert_book() here — let the worker pick it up from the queue.
    # Starting it directly caused dual-execution bugs where both webapp and worker
    # would run convert_book() for the same job simultaneously.
    app.logger.info(f"Retry job {job_id} queued — worker will pick it up")

    return jsonify({'status': 'queued', 'retry_count': new_retry_count})


@app.route('/api/jobs/<job_id>/download')
def download_job(job_id: str):
    """Download completed audiobook as ZIP."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400

    output_dir = OUTPUT_DIR / job['output_dirname']
    if not output_dir.exists():
        return jsonify({'error': 'Output files not found'}), 404

    # Create ZIP file
    zip_path = UPLOAD_DIR / f"{job['output_dirname']}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for mp3_file in sorted(output_dir.glob('*.mp3')):
            zf.write(mp3_file, mp3_file.name)

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{job['book_name']}.zip"
    )


@app.route('/api/jobs/<job_id>/sync', methods=['POST'])
def sync_job(job_id: str):
    """Manually sync a completed job to Audiobookshelf."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400

    output_dir = OUTPUT_DIR / job['output_dirname']
    if not output_dir.exists():
        return jsonify({'error': 'Output files not found'}), 404

    synced = copy_to_audiobookshelf(output_dir, job['book_name'], job_id=job_id)
    update_job(job_id, synced_to_abs=synced)

    if synced:
        return jsonify({'status': 'synced'})
    else:
        return jsonify({'error': 'Sync failed'}), 500


@app.route('/api/jobs/<job_id>/delete', methods=['DELETE'])
def delete_job(job_id: str):
    """Delete a job and its files."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] in ('converting', 'converting PDF', 'converting to audio'):
        return jsonify({'error': 'Cannot delete running job'}), 400

    # Delete files
    input_path = UPLOAD_DIR / job['input_filename']
    if input_path.exists():
        input_path.unlink()

    output_dir = OUTPUT_DIR / job['output_dirname']
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Delete from database
    with get_db() as conn:
        conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        conn.commit()

    return jsonify({'status': 'deleted'})


# ============ Library Routes ============

@app.route('/api/library')
def list_library():
    """List available ebooks in the library directory.

    Returns list of books with:
    - title: Book name (filename without extension)
    - path: Full path for conversion
    - format: File format (epub, pdf, mobi, etc.)
    - size: File size in bytes
    - status: 'available', 'converting', or 'completed'
    - progress: Conversion progress if converting
    """
    if not LIBRARY_DIR.exists():
        return jsonify([])

    books = []
    all_jobs = get_all_jobs()

    # Build a map of book names to their job status
    job_status_map = {}
    for job in all_jobs:
        book_name = job.get('book_name', '').lower()
        status = job.get('status', '')
        progress = job.get('progress_percent', 0)

        if status == 'completed':
            job_status_map[book_name] = {'status': 'completed', 'progress': 100}
        elif status in ('queued', 'converting', 'converting PDF', 'converting to audio'):
            job_status_map[book_name] = {'status': 'converting', 'progress': progress or 0}

    # Scan library directory for ebooks
    for ext in SUPPORTED_FORMATS:
        for file_path in LIBRARY_DIR.glob(f'**/*{ext}'):
            if file_path.is_file():
                st = file_path.stat()
                title = file_path.stem
                title_lower = title.lower()

                # Check job status
                job_info = job_status_map.get(title_lower, {'status': 'available', 'progress': 0})

                books.append({
                    'title': title,
                    'path': str(file_path),
                    'format': ext.lstrip('.'),
                    'size': st.st_size,
                    # Used for client-side sorting/filtering; epoch seconds.
                    'modified_ts': int(st.st_mtime),
                    'status': job_info['status'],
                    'progress': job_info['progress']
                })

    # Sort by title
    books.sort(key=lambda x: x['title'].lower())
    return jsonify(books)


@app.route('/api/library/convert', methods=['POST'])
def convert_from_library():
    """Start conversion of a book from the library.

    Request JSON:
    - path: Path to the ebook file
    - voice: Voice ID to use
    - notify_whatsapp: Whether to send WhatsApp notification
    - notify_telegram: Whether to send Telegram notification
    """
    data = request.get_json() or {}
    file_path = Path(data.get('path', ''))
    voice = data.get('voice', DEFAULT_VOICE)
    notify_telegram = data.get('notify_telegram', False)
    notify_whatsapp = data.get('notify_whatsapp', False)
    tts_speed = float(data.get('tts_speed', DEFAULT_TTS_SPEED))
    start_chapter = data.get('start_chapter')
    end_chapter = data.get('end_chapter')

    # Validate file exists
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    # Validate file is in library directory (security check)
    try:
        file_path.resolve().relative_to(LIBRARY_DIR.resolve())
    except ValueError:
        return jsonify({'error': 'File not in library directory'}), 403

    # Validate voice
    if voice not in VOICES:
        return jsonify({'error': 'Invalid voice selected'}), 400

    # Create job
    job_id = str(uuid.uuid4())[:8]
    book_name = file_path.stem
    safe_name = "".join(c for c in book_name if c.isalnum() or c in ' -_').strip()
    file_ext = file_path.suffix.lower()

    # New parsing and pronunciation options (defaults for library conversion)
    newline_mode = data.get('newline_mode', 'double')
    title_mode = data.get('title_mode', 'auto')
    custom_regex = data.get('custom_regex', '').strip() or None

    is_pdf = file_ext == '.pdf'
    needs_conversion = file_ext not in {'.epub', '.pdf'}

    # Copy file to upload directory
    input_filename = f"{job_id}_{safe_name}{file_ext}"
    input_path = UPLOAD_DIR / input_filename
    shutil.copy2(file_path, input_path)

    # Convert non-standard formats to EPUB
    if needs_conversion:
        try:
            epub_path = convert_to_epub(input_path)
            input_filename = epub_path.name
            input_path = epub_path
        except RuntimeError as e:
            return jsonify({'error': f'Format conversion failed: {str(e)}'}), 500

    # Create output directory
    output_dirname = f"{safe_name}_{job_id}"
    output_dir = OUTPUT_DIR / output_dirname
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine TTS engine
    tts_engine = VOICES[voice].get('engine', 'kokoro')

    # Save job to database
    job = {
        'id': job_id,
        'book_name': book_name,
        'voice': voice,
        'voice_name': VOICES[voice]['name'],
        'voice2': None,
        'voice2_name': None,
        'tts_engine': VOICES[voice].get('engine', 'kokoro'),
        'status': 'queued',
        'created_at': datetime.now().isoformat(),
        'input_filename': input_filename,
        'output_dirname': book_name,
        'is_pdf': is_pdf,
        'start_chapter': start_chapter,
        'end_chapter': end_chapter,
        'notify_telegram': notify_telegram,
        'tts_speed': tts_speed,
        'queue_rank': next_queue_rank(),
        'sync_status': 'pending',
        'job_log_path': str(get_job_log_path(job_id)),
        'newline_mode': newline_mode,
        'title_mode': title_mode,
        'custom_regex': custom_regex
    }
    save_job(job)
    ch_range = f", chapters {start_chapter}-{end_chapter}" if start_chapter or end_chapter else ""
    append_job_log(job_id, f"Library job created: {book_name} (voice={voice}, engine={tts_engine}, speed={tts_speed}{ch_range})")

    # Do NOT start convert_book() here — let the worker pick it up from the queue.
    # The webapp should NEVER run conversions directly to prevent dual-execution bugs.
    app.logger.info(f"Library job {job_id} queued — worker will pick it up")

    return jsonify({'job_id': job_id, 'status': 'queued'})


# Initialize database on startup
init_db()

# Clean up any orphan jobs from previous runs
cleanup_orphan_jobs()

# Reattach monitors for jobs already running in Docker
if QUEUE_RUNNER_ENABLED:
    resume_inflight_jobs()
    # Start watchdog thread to monitor job health
    start_watchdog()
    # Continue queued work after restart (if nothing is currently running)
    start_next_queued_job()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8881, debug=True)
