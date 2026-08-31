#!/usr/bin/env python3
"""
EPUB/PDF to Audiobook Web UI
Allows users to upload EPUB/PDF files, preview voices, and convert to audiobooks.
"""

import os
import hmac
import sys
import subprocess
import threading
import uuid
import shutil
import zipfile
import re
import sqlite3
import json
import shlex
import time
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from collections import Counter
from typing import Any, Optional, Dict, List
from gpu_manager import GPUManager
from epub_generator import package_epub3_with_audio
from qa_report import merge_qa_reports, read_qa_report, write_qa_report_atomic
from chapters import list_renderable_chapters, body_end_index
import guard

from flask import Flask, render_template, request, jsonify, send_file, Response, url_for, make_response
import requests

# Telegram notification settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
TELEGRAM_WEBHOOK_SECRET = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
TTS_PROXY_URL = os.environ.get('TTS_PROXY_URL', '').strip().rstrip('/')

app = Flask(__name__)
_trusted_hosts = [host.strip() for host in
                  os.environ.get('APP_TRUSTED_HOSTS', '').split(',') if host.strip()]
if _trusted_hosts:
    app.config['TRUSTED_HOSTS'] = _trusted_hosts


@app.before_request
def enforce_same_origin_writes():
    """Reject browser writes from another origin.

    The application is intentionally passwordless on the trusted LAN. External
    identity belongs to the Pangolin resource in front of the public hostname;
    stacking HTTP Basic here breaks that SSO flow. Scripts without an Origin
    header remain usable for local operations.
    """
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('Origin')
        if origin:
            from urllib.parse import urlsplit
            if not hmac.compare_digest(urlsplit(origin).netloc, request.host):
                return jsonify({'error': 'Cross-origin write refused'}), 403
    return None



# Configuration
# NOTE: KOKORO_URL is a mutable global — gpu_manager.py switches it
# between CPU and GPU endpoints at runtime. Do NOT cache this value.
KOKORO_URL = os.environ.get('KOKORO_URL', 'http://localhost:8880/v1')
CHATTERBOX_URL = os.environ.get('CHATTERBOX_URL', 'http://chatterbox-tts:8004/v1')
# Nano is a SEPARATE container (chatterbox-nano, CHATTERBOX_NANO=1). One
# chatterbox container loads Turbo XOR Nano at startup, so the two models
# cannot share a process — hence a second service and a second URL.
CHATTERBOX_NANO_URL = os.environ.get('CHATTERBOX_NANO_URL', 'http://chatterbox-nano:8004/v1')
TADA_URL = os.environ.get('TADA_URL', 'http://tada-tts:8005/v1')
VIBEVOICE_URL = os.environ.get('VIBEVOICE_URL', 'http://vibevoice-tts:8010/v1')
QWEN3_URL = os.environ.get('QWEN3_URL', 'http://qwen3-tts:8011/v1')
POCKET_URL = os.environ.get('POCKET_URL', 'http://pocket-tts:8012/v1')
KITTEN_URL = os.environ.get('KITTEN_URL', 'http://kitten-tts:8013/v1')
GEMINI_TTS_URL = os.environ.get('GEMINI_TTS_URL', 'http://gemini-tts:8014/v1')
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/data/uploads'))
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', '/data/audiobooks'))
PREVIEWS_DIR = Path(os.environ.get('PREVIEWS_DIR', '/data/previews'))
DB_PATH = Path(os.environ.get('DB_PATH', '/data/jobs.db'))
TRANSCRIPTS_DIR = Path(os.environ.get('TRANSCRIPTS_DIR', '/data/transcripts'))

TOC_CACHE_DIR = Path(os.environ.get('TOC_CACHE_DIR', '/data/toc_cache'))
TOC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
APP_VERSION = os.environ.get('APP_VERSION', 'dev')
APP_GIT_SHA = os.environ.get('APP_GIT_SHA', 'unknown')
APP_BUILD_TIME = os.environ.get('APP_BUILD_TIME', 'unknown')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
HEALTH_KOKORO_TIMEOUT = int(os.environ.get('HEALTH_KOKORO_TIMEOUT', '8'))
HEALTH_KOKORO_RETRIES = int(os.environ.get('HEALTH_KOKORO_RETRIES', '2'))
QUEUE_RUNNER_ENABLED = os.environ.get('QUEUE_RUNNER_ENABLED', '1').lower() in ('1', 'true', 'yes')

# Lock to prevent race conditions when claiming jobs from the queue.
# Both the worker loop and API endpoints could try to start the same job simultaneously.
_job_claim_lock = threading.Lock()

# Minimum fraction of chapters required to mark a book complete (1.0 = 100%).
# No more half-finished audiobooks.
CHAPTER_COMPLETION_THRESHOLD = float(os.environ.get('CHAPTER_COMPLETION_THRESHOLD', '1.0'))
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

# ...and completed ARTICLES here instead. Audiobookshelf serves a podcast
# library from its own folder, and the two must not be mixed: the book scanner
# reads a folder as one audiobook, so a shelf of ten-minute articles is ten
# spurious "books" with broken progress tracking and a cluttered Continue
# Listening row. Defaults to the sibling `podcasts` folder, which the ABS
# container already mounts (verified live 2026-07-27) — so this needs no
# container restart on the ABS host.
AUDIOBOOKSHELF_PODCAST_DIR = os.environ.get(
    'AUDIOBOOKSHELF_PODCAST_DIR',
    (AUDIOBOOKSHELF_DIR.rsplit('/', 1)[0] + '/podcasts') if AUDIOBOOKSHELF_DIR else '')
AUDIOBOOKSHELF_HOST = os.environ.get('AUDIOBOOKSHELF_HOST', 'audiobookshelf-host')
AUDIOBOOKSHELF_USER = os.environ.get('AUDIOBOOKSHELF_USER', 'dave')
AUDIOBOOKSHELF_PORT = os.environ.get('AUDIOBOOKSHELF_PORT', '')

# OpenBooks/Library directory for browsing available EPUBs
LIBRARY_DIR = Path(os.environ.get('LIBRARY_DIR', '/data/library'))
LOG_DIR = Path(os.environ.get('LOG_DIR', '/data/logs'))

# Supported ebook formats (converted to EPUB via Calibre)
SUPPORTED_FORMATS = {'.epub', '.pdf', '.mobi', '.azw3', '.fb2', '.txt', '.html', '.htm', '.docx'}

# Default voice when none specified (George Classic - British Male)
# Chatterbox NANO, cloned from the approved UK reference (Arthur / uk_male_minter).
# A/B'd against Turbo on an identical passage 2026-07-25: indistinguishable in
# quality ("as good as turbo, not worse anyway") at RTF 0.87 vs 3.33 — i.e.
# faster than realtime on CPU, no GPU, no quota. Turbo remains fully available
# as `uk_male_minter` and friends; this only changes what you get by default.
DEFAULT_VOICE = 'uk_female_samuel_nano'

# TTS speed: 1.0 = normal, <1.0 = slower with more pauses, range 0.5-1.5
# Default 1.0 (Kokoro's natural speed sounds good; adjust per-job if needed)
DEFAULT_TTS_SPEED = float(os.environ.get('DEFAULT_TTS_SPEED', '0.9'))

# Post-conversion cleanup: remove MP3 files smaller than this (catches photo captions, part dividers)
MIN_CHAPTER_SIZE_KB = 0

# How long a job may sit in preparation (lexicon/profile/PDF convert) before a
# container exists. Generous: preprocessing legitimately takes minutes on a big
# book. The watchdog must not mistake "no container yet" for "container died".
PREPARE_GRACE_MINUTES = float(os.environ.get('PREPARE_GRACE_MINUTES', '15'))

# Auto-retry configuration
MAX_RETRY_COUNT = 3
RETRY_BACKOFF_BASE = 30  # seconds (30, 60, 120 for attempts 1, 2, 3)

# Audiobookshelf API for triggering rescans after sync
ABS_API_TOKEN = os.environ.get('ABS_API_TOKEN', '')
ABS_API_URL = os.environ.get('ABS_API_URL', 'http://audiobookshelf-host:13378')

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Track running conversion processes and containers
_state_lock = threading.Lock()
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
        'description': 'Fast legacy/compatibility TTS; retired from quality contention',
        'url_env': 'KOKORO_URL',
        'default_url': 'http://kokoro-tts:8880/v1'
    },
    'vibevoice': {
        'name': 'VibeVoice 1.5B',
        'description': 'Long-form finalist; cfg 2.0 won the pinned blind test (Kaggle or opt-in local CUDA)',
        'url_env': 'VIBEVOICE_URL',
        'default_url': 'http://vibevoice-tts:8010/v1'
    },
    'qwen3': {
        'name': 'Qwen3-TTS 1.7B',
        'description': 'Long-form consistency finalist (Kaggle or opt-in local CUDA)',
        'url_env': 'QWEN3_URL',
        'default_url': 'http://qwen3-tts:8011/v1'
    },
    'pocket': {
        'name': 'Pocket TTS 2.1',
        'description': 'Opt-in free CPU candidate; complete official English voice catalogue',
        'url_env': 'POCKET_URL',
        'default_url': 'http://pocket-tts:8012/v1'
    },
    'kitten': {
        'name': 'KittenTTS 0.8.1',
        'description': 'Opt-in free CPU candidate; eight official preset voices',
        'url_env': 'KITTEN_URL',
        'default_url': 'http://kitten-tts:8013/v1'
    },
    'gemini': {
        'name': 'Gemini 3.1 Flash TTS (free tier only)',
        'description': 'Opt-in Developer API preview; stops on free quota and never falls back to paid',
        'url_env': 'GEMINI_TTS_URL',
        'default_url': 'http://gemini-tts:8014/v1'
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

    # Australian Edge Voices.
    #
    # These are the ONLY working Australian FEMALE narrator in the system, and
    # the best Australian male. VCTK — which supplies every other native accent
    # here — contains just two Australians and both are male, so the corpus
    # cannot cover this and no Piper model exists for en_AU at all (checked:
    # rhasspy/piper-voices ships en_GB and en_US only).
    #
    # Verified rendering English correctly 2026-07-27. Caveat worth knowing:
    # Edge is a Microsoft cloud service, so unlike Piper and Chatterbox these
    # two are NOT local and need internet.
    'en-AU-NatashaNeural': {'name': 'Australian female — Natasha (Edge)', 'accent': 'Australian', 'gender': 'Female', 'engine': 'edge'},
    'en-AU-WilliamNeural': {'name': 'Australian male — William (Edge)', 'accent': 'Australian', 'gender': 'Male', 'engine': 'edge'},

    # Gemini Developer API. Google documents style labels, not regional accent
    # or gender labels. The fixed audiobook prompt requests British English.
    # Achernar passed Dave's long-form gate; the other presets remain auditions
    # until their exact app-path previews are cached and heard.
    'gemini_zephyr': {'name': 'Zephyr — bright (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_puck': {'name': 'Puck — upbeat (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_charon': {'name': 'Charon — informative (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_kore': {'name': 'Kore — firm (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_fenrir': {'name': 'Fenrir — excitable (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_leda': {'name': 'Leda — youthful (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_orus': {'name': 'Orus — firm (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_aoede': {'name': 'Aoede — breezy (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_callirrhoe': {'name': 'Callirrhoe — easy-going (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_autonoe': {'name': 'Autonoe — bright (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_enceladus': {'name': 'Enceladus — breathy (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_iapetus': {'name': 'Iapetus — clear (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_umbriel': {'name': 'Umbriel — easy-going (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_algieba': {'name': 'Algieba — smooth (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_despina': {'name': 'Despina — smooth (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_erinome': {'name': 'Erinome — clear (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_algenib': {'name': 'Algenib — gravelly (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_rasalgethi': {'name': 'Rasalgethi — informative (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_laomedeia': {'name': 'Laomedeia — upbeat (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_achernar': {'name': 'Achernar — soft (Gemini, approved)', 'accent': 'British (prompted)', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_alnilam': {'name': 'Alnilam — firm (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_schedar': {'name': 'Schedar — even (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_gacrux': {'name': 'Gacrux — mature (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_pulcherrima': {'name': 'Pulcherrima — forward (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_achird': {'name': 'Achird — friendly (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_zubenelgenubi': {'name': 'Zubenelgenubi — casual (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_vindemiatrix': {'name': 'Vindemiatrix — gentle (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_sadachbia': {'name': 'Sadachbia — lively (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_sadaltager': {'name': 'Sadaltager — knowledgeable (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},
    'gemini_sulafat': {'name': 'Sulafat — warm (Gemini)', 'accent': 'Prompt-controlled', 'gender': 'Unspecified', 'engine': 'gemini'},

    # ============ AWS POLLY LONG-FORM VOICES ============
    'polly_ruth': {'name': 'Ruth', 'accent': 'American', 'gender': 'Female', 'engine': 'polly'},
    'polly_danielle': {'name': 'Danielle', 'accent': 'American', 'gender': 'Female', 'engine': 'polly'},
    'polly_gregory': {'name': 'Gregory', 'accent': 'American', 'gender': 'Male', 'engine': 'polly'},
    'polly_patrick': {'name': 'Patrick', 'accent': 'American', 'gender': 'Male', 'engine': 'polly'},

    # ============ INWORLD TTS 1.5 VOICES (PREMIUM) ============
    # British
    'inworld_Graham': {'name': 'Graham', 'accent': 'British', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Rupert': {'name': 'Rupert', 'accent': 'British', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Olivia': {'name': 'Olivia', 'accent': 'British', 'gender': 'Female', 'engine': 'inworld'},
    # American — Narration
    'inworld_Blake': {'name': 'Blake', 'accent': 'American', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Elizabeth': {'name': 'Elizabeth', 'accent': 'American', 'gender': 'Female', 'engine': 'inworld'},
    'inworld_Dennis': {'name': 'Dennis', 'accent': 'American', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Ashley': {'name': 'Ashley', 'accent': 'American', 'gender': 'Female', 'engine': 'inworld'},
    'inworld_Luna': {'name': 'Luna', 'accent': 'American', 'gender': 'Female', 'engine': 'inworld'},
    'inworld_Carter': {'name': 'Carter', 'accent': 'American', 'gender': 'Male', 'engine': 'inworld'},
    # Character / dramatic
    'inworld_Dominus': {'name': 'Dominus', 'accent': 'Character', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Hades': {'name': 'Hades', 'accent': 'Character', 'gender': 'Male', 'engine': 'inworld'},
    'inworld_Darlene': {'name': 'Darlene', 'accent': 'American Southern', 'gender': 'Female', 'engine': 'inworld'},

    # ============ CHATTERBOX TURBO (LOCAL, VOICE-CLONED UK NARRATORS) ============
    # voice id MUST equal the wav file stem in chatterbox/voices/
    'uk_male_minter': {'name': 'Arthur (UK, human-cloned)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox'},
    'uk_female_golding': {'name': 'Harriet (UK, human-cloned)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox'},
    'uk_male_yearsley': {'name': 'Edmund (UK, human-cloned)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox'},
    'uk_female_samuel': {'name': 'Beatrice (UK, human-cloned)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox'},
    # --- Top LibriVox narrators (public-domain, human-cloned) ---
    'elizabeth_klett': {'name': 'Elizabeth Klett (literary classics)', 'accent': 'American', 'gender': 'Female', 'engine': 'chatterbox'},
    'karen_savage': {'name': 'Karen Savage (warm, classic novels)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox'},
    'mil_nicholson': {'name': 'Mil Nicholson (expressive, Dickens)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox'},
    'adrian_praetzellis': {'name': 'Adrian Praetzellis (adventure, storyteller)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox'},
    'tadhg_hynes': {'name': 'Tadhg Hynes (rich, Hardy/Dickens)', 'accent': 'Irish', 'gender': 'Male', 'engine': 'chatterbox'},
    'martin_geeson': {'name': 'Martin Geeson (British male, classic prose)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox'},
    'nigel_boydell': {'name': 'Nigel Boydell (British male, characterful)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox'},
    # --- NO ACCENTED VOICES ON CHATTERBOX. THIS IS SETTLED. ---
    #
    # Tried twice, failed twice, on the same underlying cause.
    #
    # Attempt 1: clone from raw VCTK clips. Dave: "those accents are shit."
    # Attempt 2 (2026-07-27): clone from ~20s of smooth continuous prose
    # generated by the native-accent Piper models — on my theory that the first
    # attempt failed because anechoic close-mic VCTK is poor conditioning
    # material. Dave: "you softened the shit out of the voices and made them
    # american... almost all of them have lost their accent."
    #
    # The reference audio was never the variable. Chatterbox is zero-shot: it
    # takes timbre from the reference and PHONETICS from its own training data,
    # which is predominantly American. Feeding it a better-accented reference
    # cannot change that — I had already written exactly this conclusion, then
    # talked myself out of it and shipped without listening. The cost was a
    # round of Dave's time.
    #
    # The Piper VCTK path above also failed by ear and remains only for legacy
    # comparison. Do not add an accented Chatterbox or Piper production voice
    # without materially new evidence and a passed listening sample.
    # ============ TADA (LOCAL/GPU, MOST NATURAL) ============
    'uk_male_minter_tada': {'name': 'Arthur — TADA (most natural)', 'accent': 'British', 'gender': 'Male', 'engine': 'tada'},
    'uk_female_golding_tada': {'name': 'Harriet — TADA (most natural)', 'accent': 'British', 'gender': 'Female', 'engine': 'tada'},
    'uk_male_yearsley_tada': {'name': 'Edmund — TADA (most natural)', 'accent': 'British', 'gender': 'Male', 'engine': 'tada'},
    'uk_female_samuel_tada': {'name': 'Beatrice — TADA (most natural)', 'accent': 'British', 'gender': 'Female', 'engine': 'tada'},
    # ============ CHATTERBOX NANO (LOCAL, SAME UK CLONES, ~3x CPU SPEED) ============
    'uk_male_minter_nano': {'name': 'Arthur (Nano)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox_nano'},
    'uk_female_golding_nano': {'name': 'Harriet (Nano)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox_nano'},
    'uk_male_yearsley_nano': {'name': 'Edmund (Nano)', 'accent': 'British', 'gender': 'Male', 'engine': 'chatterbox_nano'},
    'uk_female_samuel_nano': {'name': 'Beatrice (Nano)', 'accent': 'British', 'gender': 'Female', 'engine': 'chatterbox_nano'},
    # ============ COSYVOICE 3 (KAGGLE-GPU RENDER; previews pre-rendered) ============
    # GPU-only — full-book render happens on Kaggle. Previews are pre-generated
    # (scripts kernel cosyvoice3-previews) and cached in data/previews/.
    'uk_male_minter_cosyvoice': {'name': 'Arthur (CosyVoice)', 'accent': 'British', 'gender': 'Male', 'engine': 'cosyvoice'},
    'uk_female_golding_cosyvoice': {'name': 'Harriet (CosyVoice)', 'accent': 'British', 'gender': 'Female', 'engine': 'cosyvoice'},
    'uk_male_yearsley_cosyvoice': {'name': 'Edmund (CosyVoice)', 'accent': 'British', 'gender': 'Male', 'engine': 'cosyvoice'},
    'uk_female_samuel_cosyvoice': {'name': 'Beatrice (CosyVoice)', 'accent': 'British', 'gender': 'Female', 'engine': 'cosyvoice'},
    # ============ LONG-FORM GPU FINALISTS (LISTENED VOICE ONLY) ============
    # Only Arthur is registered: that is the reference actually heard in the
    # full-chapter audition. Do not imply the other reference voices have passed
    # the audiobook listening gate until their samples have been rendered/heard.
    'uk_male_minter_vibevoice': {'name': 'Arthur — VibeVoice (quality finalist)', 'accent': 'British', 'gender': 'Male', 'engine': 'vibevoice'},
    'uk_male_minter_qwen3': {'name': 'Arthur — Qwen3-TTS (consistency finalist)', 'accent': 'British', 'gender': 'Male', 'engine': 'qwen3'},

    # ============ FREE CPU CANDIDATES (OFFICIAL CATALOGUES) ============
    # Pocket's upstream catalogue does not publish reliable accent/gender
    # metadata for every preset, so do not infer it from a name. Peter, Jasper
    # and Rosie passed the short normalized-input listening screen; all voices
    # remain candidates until their own previews and a long-form gate are heard.
    'pocket_alba': {'name': 'Alba (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_anna': {'name': 'Anna (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_azelma': {'name': 'Azelma (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_bill_boerst': {'name': 'Bill Boerst (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_caro_davy': {'name': 'Caro Davy (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_charles': {'name': 'Charles (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_cosette': {'name': 'Cosette (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_eponine': {'name': 'Eponine (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_eve': {'name': 'Eve (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_fantine': {'name': 'Fantine (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_george': {'name': 'George (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_jane': {'name': 'Jane (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_jean': {'name': 'Jean (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_javert': {'name': 'Javert (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_marius': {'name': 'Marius (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_mary': {'name': 'Mary (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_michael': {'name': 'Michael (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_paul': {'name': 'Paul (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_peter_yearsley': {'name': 'Peter Yearsley (Pocket — heard)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_stuart_bell': {'name': 'Stuart Bell (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'pocket_vera': {'name': 'Vera (Pocket)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'pocket'},
    'kitten_bella': {'name': 'Bella (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_jasper': {'name': 'Jasper (Kitten — heard)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_luna': {'name': 'Luna (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_bruno': {'name': 'Bruno (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_rosie': {'name': 'Rosie (Kitten — heard)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_hugo': {'name': 'Hugo (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_kiki': {'name': 'Kiki (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},
    'kitten_leo': {'name': 'Leo (Kitten)', 'accent': 'English', 'gender': 'Unspecified', 'engine': 'kitten'},

    # ============ DEEPGRAM (CLOUD AURA-2) ============
    'deepgram_orion': {'name': 'Orion — resonant (Deepgram)', 'accent': 'American', 'gender': 'Male', 'engine': 'deepgram'},
    'deepgram_orpheus': {'name': 'Orpheus — smooth (Deepgram)', 'accent': 'American', 'gender': 'Male', 'engine': 'deepgram'},
    'deepgram_arcas': {'name': 'Arcas — warm (Deepgram)', 'accent': 'American', 'gender': 'Male', 'engine': 'deepgram'},
    'deepgram_pandora': {'name': 'Pandora — articulate (Deepgram)', 'accent': 'British', 'gender': 'Female', 'engine': 'deepgram'},
    'deepgram_hyperion': {'name': 'Hyperion — natural (Deepgram)', 'accent': 'Australian', 'gender': 'Male', 'engine': 'deepgram'},
}

# The voice-audition sample lives in ONE place (webapp/voice_sample.py) so the
# Kaggle GPU sample-renderer and this app use byte-identical text.
from voice_sample import SAMPLE_TEXT as PREVIEW_TEXT, sample_text_for as _preview_text_for  # noqa: E402


def _fix_db_permissions():
    """Ensure DB and WAL sidecars have rw permissions (Issue #37 self-healing)."""
    p = DB_PATH if isinstance(DB_PATH, Path) else Path(str(DB_PATH))
    if p.parent.exists():
        for item in p.parent.glob('*.db*'):
            try:
                os.chmod(item, 0o666)
            except Exception:
                pass


def init_db():
    """Initialize SQLite database for job persistence."""
    _fix_db_permissions()
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
                custom_regex TEXT,
                render_target TEXT DEFAULT 'local'
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
            conn.execute("ALTER TABLE jobs ADD COLUMN render_target TEXT DEFAULT 'local'")
        except sqlite3.OperationalError:
            pass
        # 'mp3' = per-chapter files (default), 'm4b' = also build one chaptered
        # M4B after the render. The MP3s are always produced either way.
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN output_format TEXT DEFAULT 'mp3'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN custom_regex TEXT")
        except sqlite3.OperationalError:
            pass
        # 1 = the quality gate actually inspected ASR data for this render.
        # 0 = it ran but had nothing to look at, so the book shipped UNVERIFIED.
        # NULL = predates the column. The distinction matters because the two
        # states used to be written identically as a clean gate (#33).
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN qa_verified INTEGER")
        except sqlite3.OperationalError:
            pass

        # Add preprocess_summary column (migration — UI preprocessing badge)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN preprocess_summary TEXT")
        except sqlite3.OperationalError:
            pass

        # Add narration_profile column (migration — QA Layer 1 per-book profile)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN narration_profile TEXT")
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

        # Where this job came from, and — for a URL ingest — enough about the
        # source to file it as a podcast episode rather than a book.
        #
        # An article is NOT a book. It goes through the book pipeline because
        # that machinery is already correct (chaptering, preprocessing, tagging,
        # sync), but a 12-minute Ars Technica piece sitting on the shelf next to
        # a novel is wrong at the destination, not in the pipeline. ABS has a
        # podcast media type built for exactly this shape — short items, listened
        # to once, grouped by source — so the fix is one column and a different
        # target folder, not a second pipeline (#36).
        for col, col_type in [
            ('source_kind', "TEXT DEFAULT 'book'"),   # 'book' | 'article'
            ('source_url', 'TEXT'),
            ('source_site', 'TEXT'),
            ('source_date', 'TEXT'),
        ]:
            try:
                conn.execute(f'ALTER TABLE jobs ADD COLUMN {col} {col_type}')
            except sqlite3.OperationalError:
                pass

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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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
    if not d.get('tts_engine'):
        d['tts_engine'] = 'kokoro' if (d.get('voice') or '').startswith(('bm_', 'bf_', 'am_', 'af_')) else ('deepgram' if (d.get('voice') or '').startswith('deepgram_') else 'unknown')
    voice = d.get('voice') or ''
    if voice.startswith('deepgram_') or d.get('tts_engine') == 'deepgram':
        pchars = d.get('processed_chars') or 0
        if pchars > 0:
            d['spent_cost'] = f"${(pchars / 1000) * 0.030:.2f}"
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
             tts_speed, newline_mode, title_mode, custom_regex, preprocess_summary, narration_profile, render_target, output_format, qa_verified,
             source_kind, source_url, source_site, source_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            job.get('custom_regex'),
            job.get('preprocess_summary'),
            job.get('narration_profile'),
            job.get('render_target', 'local'),
            job.get('output_format', 'mp3'),
            job.get('qa_verified'),
            # Adding a column to the schema is only half the job: this INSERT
            # names its columns explicitly, so a field missing from THIS list is
            # silently dropped on every save. The end-to-end run caught it —
            # the API answered destination=podcast while the stored row said
            # source_kind='book'. Two sources of truth disagreeing, which is the
            # exact failure shape PLAN-V4 was written about.
            job.get('source_kind', 'book'),
            job.get('source_url'),
            job.get('source_site'),
            job.get('source_date'),
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
                    WHEN status IN ('converting', 'converting PDF', 'converting to audio') OR status LIKE '%Kaggle%' THEN 0
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


def delete_setting(key: str):
    """Remove app setting from database."""
    with get_db() as conn:
        conn.execute('DELETE FROM app_settings WHERE key = ?', (key,))
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

    # Add 50% buffer to ETA (was 20%) to prevent premature watchdog kills
    eta_seconds = (char_count / rate) * 1.5
    # Enforce a minimum ETA of 10 minutes to allow for heavy text preprocessing on large books
    return max(10, int(eta_seconds / 60))

def calculate_price_estimate(engine: str, char_count: int) -> float | None:
    """Calculate known USD API cost; never label an unknown engine free."""
    # Prices per 1,000,000 characters
    PRICING = {
        'kokoro': 0.0,
        'edge': 0.0,
        'polly': 100.0,   # AWS Polly Long-form
        'openai': 15.0,   # Standard
        'openai-hd': 30.0,
        'azure': 16.0     # Neural
    }
    free_engines = {
        'kokoro', 'edge', 'chatterbox', 'chatterbox_nano',
        'tada', 'cosyvoice', 'vibevoice', 'qwen3', 'melotts', 'omnivoice',
        # This adapter is deliberately restricted to an unbilled Gemini API
        # Free Tier project. It has no Vertex or paid-tier fallback.
        'gemini'
    }
    if engine in free_engines:
        return 0.0
    if engine not in PRICING:
        return None
    rate_per_million = PRICING[engine]
    return (char_count / 1_000_000) * rate_per_million



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


def check_disk_heartbeat(job_id: str, output_dirname: str, max_age_minutes: int = 10) -> bool:
    """Check if the job has written any files to disk recently.
    
    Checks both the MP3 output folder and the transcript chunks log.
    If any file has been modified within max_age_minutes, the job is 'Alive'.
    """
    try:
        now = datetime.now().timestamp()
        cutoff = now - (max_age_minutes * 60)

        # 1. Check MP3 output folder
        out_path = OUTPUT_DIR / output_dirname
        if out_path.exists():
            for f in out_path.glob('*'):
                if f.is_file() and f.stat().st_mtime > cutoff:
                    return True

        # 2. Check transcript directory
        trans_path = TRANSCRIPTS_DIR / job_id
        if trans_path.exists():
            for f in trans_path.glob('*'):
                if f.is_file() and f.stat().st_mtime > cutoff:
                    return True
    except Exception:
        pass
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


def get_mp3_duration(path: Path) -> float:
    """Use ffprobe to get the duration of an audio file in seconds."""
    try:
        import subprocess
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', str(path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def verify_book_complete(job_id: str, output_path: Path, total_chapters: int | None,
                         start_chapter: int | None = None,
                         end_chapter: int | None = None,
                         cleaned_up_count: int = 0,
                         expected_override: int | None = None) -> tuple[bool, str]:
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

    # Determine expected chapter count.
    # A raw range span (end-start+1) is WRONG for range jobs: the renderer skips
    # sub-min-words sections (front/back-matter) and clamps to what actually
    # exists, so "chapters 5-13" of a 10-chapter book renders 6 files, not 9.
    # When the renderer told us how many chapters were truly renderable in-range
    # (expected_override, phoned home via the progress relay), trust that instead
    # of the span — that's the only count that can't false-fail. (#: range verify)
    if expected_override and expected_override > 0:
        expected = expected_override
    elif start_chapter and end_chapter:
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
    min_total_mb = 0.001
    total_size_mb = sum(f.stat().st_size for f in output_files) / (1024 * 1024)
    if total_size_mb < min_total_mb:
        return False, f"Total audio only {total_size_mb:.1f}MB — likely corrupted"

    # Check 4: Sanity check total rendered words/duration vs source words
    try:
        job = get_job(job_id)
        if job:
            input_filename = job.get('input_filename')
            is_pdf = job.get('is_pdf')
            epub_path = UPLOAD_DIR / input_filename
            if is_pdf:
                epub_path = UPLOAD_DIR / (input_filename.rsplit('.', 1)[0] + '.epub')

            # Prefer preprocessed EPUB if it exists
            tts_path = epub_path.parent / f"{epub_path.stem}_tts{epub_path.suffix}"
            if tts_path.exists():
                epub_path = tts_path

            if epub_path.exists():
                from chapters import list_renderable_chapters
                ch_list = list_renderable_chapters(epub_path)

                # Sum the word counts of chapters that were supposed to be rendered
                start_ch = start_chapter or 1
                end_ch = end_chapter or len(ch_list)

                expected_words = sum(
                    c['words'] for c in ch_list
                    if start_ch <= c['index'] <= end_ch
                )

                if expected_words > 0:
                    # Calculate total duration of generated MP3 files
                    total_duration = 0.0
                    for f in output_files:
                        total_duration += get_mp3_duration(f)

                    # If duration couldn't be determined, fallback to estimating from file size
                    # at 192kbps (which is the default)
                    if total_duration == 0.0:
                        total_bytes = sum(f.stat().st_size for f in output_files)
                        # 192 kbps = 24,000 bytes/sec
                        total_duration = total_bytes / 24000.0

                    # Speech rate is typically ~130-160 WPM. Let's be very conservative.
                    speed_factor = float(job.get('tts_speed') or 1.0)
                    baseline_wps = 1.5
                    estimated_words = total_duration * (baseline_wps * speed_factor)

                    app.logger.info(
                        f"Job {job_id} sanity check: expected_words={expected_words}, "
                        f"estimated_words={estimated_words:.1f} (duration={total_duration:.1f}s)"
                    )

                    # If we got less than 30% of the expected words, fail.
                    if estimated_words < expected_words * 0.3:
                        return False, (
                            f"Sanity check failed: epub has {expected_words} words in range "
                            f"but audio only has ~{estimated_words:.0f} words ({total_duration:.1f}s)"
                        )
    except Exception as e:
        app.logger.warning(f"Sanity check word count failed: {e}")

    return True, (
        f"Verified: {len(output_files)} files, {total_size_mb:.0f}MB total"
        + (f" ({len(output_files)}/{expected} chapters)" if expected else ""))



def verify_chapter_integrity(job_id):
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
    # Stage 2: EPUB3 with SMIL (Read-Along)
    try:
        input_filename = job.get('input_filename', '')
        if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
            epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
            epub_out = output_path / f"{job['book_name']}.epub"
            chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
            if chunks_log.exists():
                package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
    except Exception as e:
        print(f"Stage 2 (EPUB3) failed: {e}")



    output_files = list(output_path.glob('*.mp3'))
    # pre-sync quality gate: hold a broken render for review instead of shipping it
    _gate_and_sync(job_id, output_path, job['book_name'], len(output_files))
    app.logger.info(f"Recovered completion for job {job_id} with {len(output_files)} files")

    job = get_job(job_id)
    if job:
        record_conversion_metrics(job)
        if job.get('notify_telegram'):
            send_telegram_notification(job, success=True)

    transcript_path = Path(f"/data/transcripts/{job_id}")
    if transcript_path.exists() and transcript_path.is_dir():
        import shutil
        try:
            shutil.rmtree(transcript_path)
            app.logger.info(f"Cleaned up transcript directory: {transcript_path}")
        except Exception as e:
            app.logger.error(f"Failed to clean up transcript directory: {e}")

    return True



def finalize_completed_job(job_id: str) -> bool:
    """Mark an in-flight job completed when output files prove success."""
    job = get_job(job_id)
    if not job: return False

    output_dirname = job.get('output_dirname')
    if not output_dirname: return False

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

    # Renaming happens here - sensible naming
    rename_output_files(output_path, job['book_name'])

    # Try to extract cover if missing
    input_filename = job.get('input_filename', '')
    is_pdf = job.get('is_pdf', False)
    epub_in_name = input_filename if not is_pdf else input_filename.rsplit('.', 1)[0] + '.epub'
    epub_in_path = UPLOAD_DIR / epub_in_name
    extract_epub_cover(epub_in_path, output_path)

    # Generate rich metadata via LLM if configured
    try:
        from llm_metadata import generate_metadata
        metadata_file = output_path / "metadata.json"
        if not metadata_file.exists():
            llm_meta = generate_metadata(epub_in_path)
            if llm_meta:
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(llm_meta, f, indent=2, ensure_ascii=False)
                app.logger.info(f"Generated rich metadata via LLM: {llm_meta.get('title')}")
                append_job_log(job_id, f"Generated LLM metadata: {llm_meta.get('title')}")
    except Exception as e:
        app.logger.warning(f"LLM Metadata generation skipped/failed: {e}")

    output_files = list(output_path.glob('*.mp3'))


    # pre-sync quality gate: hold a broken render for review instead of shipping it
    _gate_and_sync(job_id, output_path, job['book_name'], len(output_files))

    app.logger.info(f"Finalized job {job_id} with {len(output_files)} files")

    # Record metrics
    record_conversion_metrics(get_job(job_id))
    if job.get('notify_telegram'):
        send_telegram_notification(job, success=True)

    transcript_path = Path(f"/data/transcripts/{job_id}")
    if transcript_path.exists() and transcript_path.is_dir():
        import shutil
        try:
            shutil.rmtree(transcript_path)
            app.logger.info(f"Cleaned up transcript directory: {transcript_path}")
        except Exception as e:
            app.logger.error(f"Failed to clean up transcript directory: {e}")

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
            if _recovery_in_progress.get(job_id): continue
            job_id = job['id']
            container_name = job['container_name']
            retry_count = int(job['retry_count'] or 0)

            # If the container is still running, the resume logic will re-attach monitors.
            if check_container_running(container_name):
                continue

            # If conversion actually finished during downtime, output files prove success.
            try:
                if finalize_completed_job(job_id):
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
                        completed_at = NULL,
                        container_name = NULL
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
               OR status LIKE '%Kaggle%'
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


def get_max_concurrent_jobs() -> int:
    """Return max concurrent jobs setting (default: 1, max: 4)."""
    try:
        return max(1, min(4, int(get_setting('max_concurrent_jobs', '1'))))
    except Exception:
        return 1


def start_next_queued_job():
    """Start the next queued job if running job count is below limit.

    Uses _job_claim_lock to prevent race conditions where multiple callers
    (worker loop iterations, API endpoints) could start the same job twice.
    The job status is set to 'converting' BEFORE the thread starts, so any
    concurrent caller will see it as running and skip it.
    """
    with _job_claim_lock:
        if is_queue_paused():
            app.logger.info("Queue is paused; not starting queued jobs")
            return False
        if running_job_count() >= get_max_concurrent_jobs():
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
ETA_KILL_MULTIPLIER = 5      # Kill job if elapsed > N × ETA


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


def _do_recovery(job_id):
    """Background thread to perform chapter-level recovery."""
    import time as time_module
    time_module.sleep(30)  # Brief delay to let engine settle
    try:
        job = get_job(job_id) or {}
        if (job.get('render_target') or 'local') == 'kaggle':
            # Never fall from a GPU-only Kaggle engine into the local converter:
            # that either targets an offline CUDA service or silently changes
            # the execution path. The Kaggle recovery planner skips chapters
            # already banked on disk and merges their QA reports.
            convert_book_kaggle(job_id, job.get('input_filename', ''),
                                job.get('output_dirname', ''), job.get('voice', ''),
                                resume=False, recover_existing=True)
        else:
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

def handle_job_failure(job_id, error_type, error_msg):
    """Handle job failure with smart recovery.

    When the container dies with partial output (some chapters already converted),
    tries chapter-level recovery instead of re-running the entire book.
    Falls back to full job retry if no partial output exists.

    Self-healing: 
    1. Retries local container deaths/timeouts up to MAX_RETRY_COUNT. The
       free-tier Gemini path is explicitly excluded from automatic retries.
    2. Automatically corrects invalid chapter ranges if out-of-range error detected.

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

    # Gemini is intentionally a one-attempt, Free-Tier-only path. A failed
    # request (especially HTTP 429 quota exhaustion) must never be multiplied
    # by the generic container/watchdog retry machinery. Completed passage WAVs
    # remain in /data/gemini_chunks/<job_id>, so a user-initiated retry resumes
    # from cache without re-consuming successful passages.
    if job.get('tts_engine') == 'gemini':
        quota_exhausted = bool(re.search(r'\b429\b|RESOURCE_EXHAUSTED|quota',
                                         error_msg, re.IGNORECASE))
        if quota_exhausted:
            final_error = (
                'Gemini Free Tier quota exhausted. No automatic retry was made. '
                'Retry the job manually after quota is available; completed '
                'passages are cached and will not be requested again.'
            )
        else:
            final_error = (
                f'Gemini request failed and was not automatically retried: {error_msg}. '
                'Completed passages remain cached for a manual retry.'
            )
        with get_db() as conn:
            conn.execute('''
                UPDATE jobs
                SET status = 'failed', error = ?, completed_at = ?
                WHERE id = ?
            ''', (final_error, datetime.now().isoformat(), job_id))
            conn.commit()
        app.logger.error(f"Job {job_id} stopped without Gemini auto-retry: {final_error}")
        append_job_log(job_id, final_error)
        return False

    # --- Self-Healing: Automatic Chapter Range Correction ---
    # 1. Parse the actual ground truth from the tool logs if available
    count_match = re.search(r'Chapters count:\s*(\d+)', error_msg)
    if count_match:
        try:
            actual_total = int(count_match.group(1))
            app.logger.info(f"Self-Healing {job_id}: Found ground truth total chapters: {actual_total}")
            with get_db() as conn:
                conn.execute('UPDATE jobs SET total_chapters = ? WHERE id = ?', (actual_total, job_id))
                # ALWAYS cap end_chapter to ground truth if it's over
                if not job.get('end_chapter') or job['end_chapter'] > actual_total:
                    app.logger.info(f"Self-Healing {job_id}: Capping end_chapter to {actual_total}")
                    append_job_log(job_id, f"Auto-correcting range: capping end_chapter at {actual_total} (based on ground truth)")
                    conn.execute('UPDATE jobs SET end_chapter = ? WHERE id = ?', (actual_total, job_id))
                conn.commit()
            # Refresh local job object
            job = get_job(job_id)
        except: pass

    # 2. Catch: "ValueError: Chapter end index X is out of range." (Fallback if count not found)
    range_error = re.search(r'Chapter end index (\d+) is out of range', error_msg)
    if range_error:
        try:
            max_allowed = int(range_error.group(1)) - 1
            if max_allowed > 0 and (not job.get('end_chapter') or job['end_chapter'] > max_allowed):
                app.logger.info(f"Self-Healing {job_id}: Automatically capping end_chapter to {max_allowed}")
                append_job_log(job_id, f"Auto-correcting range: capping end_chapter at {max_allowed} (based on error index)")
                with get_db() as conn:
                    conn.execute('UPDATE jobs SET end_chapter = ? WHERE id = ?', (max_allowed, job_id))
                    conn.commit()
        except: pass

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
        recovery_thread = threading.Thread(target=_do_recovery, args=(job_id,), daemon=True)
        recovery_thread.start()
        return True

    # No partial output — fall back to full job retry
    if retry_count < MAX_RETRY_COUNT and error_type in ('container_died', 'timeout'):
        delay = RETRY_BACKOFF_BASE * (2 ** retry_count)  # 30s, 60s, 120s
        new_rank = next_queue_rank()

        # CRITICAL: clear container_name, otherwise convert_book's
        # duplicate-start guard sees the stale container reference and aborts
        # every retry (bug found 2026-07-07 — job d67c50ac failed 3/3 retries
        # without ever running). Also remove any stale container so the name
        # can't collide when the retry launches.
        stale = job.get('container_name')
        if stale and re.match(r'^[a-zA-Z0-9_.-]+$', stale):
            subprocess.run(['docker', 'rm', '-f', stale], capture_output=True)

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
                    container_name = NULL,
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
                           current_chapter, progress_percent, output_dirname
                    FROM jobs
                    WHERE status IN ('converting', 'converting PDF', 'converting to audio')
                ''').fetchall()

                for job_row in active_jobs:
                    job = dict(job_row)
                    job_id = job['id']
                    container_name = job['container_name']
                    book_label = (job['book_name'] or '')[:30]
                    process = running_processes.get(job_id)
                    if process:
                        container_running = (process.poll() is None)
                    elif not container_name:
                        # Still PREPARING (lexicon / narration profile / PDF
                        # convert): the container does not exist yet. A job that
                        # never got a container is not a job whose container
                        # died — treating it as death turned any slow
                        # preprocessing into an infinite retry loop the moment
                        # the LLM became a real (slow) dependency (2026-07-25).
                        # Allow a generous grace window, then fail it honestly.
                        _ref = job.get('started_at') or job.get('created_at')
                        try:
                            _mins = (datetime.now() - datetime.fromisoformat(_ref)).total_seconds() / 60 if _ref else 0
                        except Exception:
                            _mins = 0
                        if _mins > PREPARE_GRACE_MINUTES:
                            app.logger.warning(
                                f"Watchdog: {book_label} stuck preparing for {_mins:.0f} min")
                            append_job_log(job_id,
                                           f"Watchdog: still preparing after {_mins:.0f} min "
                                           f"(no container yet) — failing. If an LLM is configured, "
                                           f"check it is reachable and fast enough.")
                            handle_job_failure(job_id, 'prepare_timeout',
                                               f'Stuck in preparation for {_mins:.0f} min without starting a container')
                        continue
                    else:
                        container_running = check_container_running(container_name)

                    # --- Check 1: Container dead ---
                    if not container_running:
                        if finalize_completed_job(job_id):
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
                                # Kill the stuck container or process
                                process = running_processes.get(job_id)
                                if process:
                                    try:
                                        process.terminate()
                                        process.wait(timeout=5)
                                    except Exception:
                                        try:
                                            process.kill()
                                        except Exception:
                                            pass
                                else:
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
                            # --- Self-Healing Heartbeat ---
                            # Before killing, check if the disk is still being written to.
                            # This saves large books from being killed during heavy preprocessing.
                            if check_disk_heartbeat(job_id, job.get('output_dirname', '')):
                                app.logger.info(f"Watchdog: {book_label} exceeded ETA but Disk Heartbeat is ALIVE. Skipping kill.")
                                # Update tracking to avoid immediate re-check
                                if job_id in _watchdog_last_progress:
                                    prev_ch, prev_pct, _ = _watchdog_last_progress[job_id]
                                    _watchdog_last_progress[job_id] = (prev_ch, prev_pct, now)
                                continue

                            app.logger.warning(
                                f"Watchdog: {book_label} running {elapsed:.0f}min, "
                                f"exceeds {ETA_KILL_MULTIPLIER}x ETA ({eta_minutes}min) "
                                f"— killing container")
                            append_job_log(
                                job_id,
                                f"Watchdog: exceeded {ETA_KILL_MULTIPLIER}x ETA "
                                f"({elapsed:.0f}m vs {eta_minutes}m) — killing and retrying")
                            process = running_processes.get(job_id)
                            if process:
                                try:
                                    process.terminate()
                                    process.wait(timeout=5)
                                except Exception:
                                    try:
                                        process.kill()
                                    except Exception:
                                        pass
                            else:
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
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM app_settings WHERE key LIKE 'recovery_lock_%'")
            conn.commit()
            app.logger.info("Cleared stale recovery locks after restart")
    except Exception as e:
        app.logger.warning(f"Could not clear stale recovery locks: {e}")

    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, container_name, status, input_filename, output_dirname, voice
            FROM jobs
            WHERE status IN ('converting', 'converting PDF', 'converting to audio', 'recovering')
               OR status LIKE 'rendering on Kaggle GPU%'
               OR status LIKE 'queued on Kaggle%'
        ''').fetchall()

    resumed = 0
    for row in rows:
        job_id = row['id']
        container_name = row['container_name']
        current_status = row['status']

        if current_status == 'recovering':
            recovery_thread = threading.Thread(target=_do_recovery, args=(job_id,), daemon=True)
            recovery_thread.start()
            resumed += 1
            app.logger.info(f"Resumed recovery for job {job_id}")
        elif current_status.startswith('rendering on Kaggle GPU') or current_status.startswith('queued on Kaggle'):
            input_filename = row['input_filename']
            output_dirname = row['output_dirname']
            voice = row['voice']
            monitor_thread = threading.Thread(
                target=convert_book_kaggle,
                args=(job_id, input_filename, output_dirname, voice),
                kwargs={'resume': True},
                daemon=True
            )
            monitor_thread.start()
            resumed += 1
            app.logger.info(f"Resumed Kaggle monitoring for job {job_id}")
        elif container_name and check_container_running(container_name):
            running_containers[job_id] = container_name
            monitor_thread = threading.Thread(target=monitor_conversion, args=(job_id, container_name), daemon=True)
            monitor_thread.start()
            resumed += 1
            app.logger.info(f"Resumed monitoring for job {job_id} ({container_name})")
        else:
            # 'converting' but the container is gone (crashed/removed on
            # restart, or a cancel/monitor race re-set the status). Do NOT leave
            # it stuck 'converting' — that holds the single MAX_CONCURRENT slot
            # forever and blocks the queue (#14). Fail it so the slot frees and
            # it doesn't silently auto-rerun; the user can retry explicitly.
            with get_db() as c2:
                c2.execute(
                    "UPDATE jobs SET status='failed', container_name=NULL, "
                    "error='container missing after worker restart (recovered)' "
                    "WHERE id=? AND status IN "
                    "('converting','converting PDF','converting to audio')",
                    (job_id,))
            app.logger.warning(
                f"Job {job_id} was '{current_status}' but its container is gone — marked failed to free the queue")

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



def sanitize_filename(name: str) -> str:
    """Sensibly rename book titles to remove special characters and junk tags."""
    # 1. Strip file extension if present
    name = name.rsplit('.', 1)[0] if '.' in name else name
    # 2. Remove common junk tags (case-insensitive)
    name = re.sub(r'(?i)[\\(\\[](retail|epub|v\\d+\\.\\d+|v\\d+|HQ|mq|fixed|re-read|unabridged|audiobook|book)[\\)\\]]', '', name)
    # 3. Clean up specific characters that look like junk or cause issues
    name = name.replace("\'", "").replace("'", "")
    # 4. Replace anything that isnt alphanumeric or dash with a space
    name = re.sub(r'[^a-zA-Z0-9-]', ' ', name)
    # 5. Collapse spaces into a single underscore
    name = re.sub(r'\\s+', '_', name.strip())
    # 6. Final cleanup
    name = re.sub(r'_+', '_', name).strip('_')
    return name or "unknown_book"

def get_epub_toc(epub_path: Path) -> List[Dict[str, Any]]:
    """Extract Table of Contents from EPUB with disk caching."""
    import xml.etree.ElementTree as ET

    # Check Cache
    cache_file = TOC_CACHE_DIR / f"{epub_path.stem}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass

    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            container_xml = zf.read('META-INF/container.xml').decode('utf-8')
            root = ET.fromstring(container_xml)
            rootfile = None
            for rf in root.iter():
                if rf.tag.split('}')[-1] == 'rootfile':
                    rootfile = rf
                    break
            if rootfile is None: return []
            opf_path = rootfile.get('full-path')

            opf_content = zf.read(opf_path).decode('utf-8')
            opf_root = ET.fromstring(opf_content)

            manifest_node = None
            spine_node = None
            for node in opf_root.iter():
                tag = node.tag.split('}')[-1]
                if tag == 'manifest': manifest_node = node
                elif tag == 'spine': spine_node = node

            if manifest_node is None or spine_node is None: return []

            manifest = {item.get('id'): item.get('href') for item in manifest_node if item.tag.split('}')[-1] == 'item'}
            spine = [item.get('idref') for item in spine_node if item.tag.split('}')[-1] == 'itemref']

            chapters = []
            for i, idref in enumerate(spine, 1):
                href = manifest.get(idref)
                if not href: continue

                opf_dir = Path(opf_path).parent
                full_href = str(opf_dir / href).replace('\\\\', '/').replace('./', '')

                try:
                    content = zf.read(full_href).decode('utf-8', errors='ignore')
                    title_match = re.search(r'<title>(.*?)</title>', content, re.I | re.S)
                    title = title_match.group(1).strip() if title_match else f"Chapter {i}"

                    if not title or title.lower() in ['untitled', 'chapter']:
                        h_match = re.search(r'<h[12][^>]*>(.*?)</h[12]>', content, re.I | re.S)
                        if h_match:
                            title = re.sub(r'<[^>]+>', '', h_match.group(1)).strip()

                    chapters.append({'index': i, 'title': title[:100], 'href': full_href})
                except:
                    chapters.append({'index': i, 'title': f"Chapter {i}", 'href': full_href})

            # Save to Cache
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(chapters, f)

            return chapters
    except Exception:
        return []

def index_library_background():
    """Pre-index all EPUBs in library and upload folders periodically."""
    import time
    while True:
        try:
            app.logger.info("Starting library indexing cycle...")
            folders = [LIBRARY_DIR, UPLOAD_DIR]
            count = 0
            for folder in folders:
                if not folder.exists(): continue
                for epub in folder.glob("*.epub"):
                    try:
                        get_epub_toc(epub)
                        count += 1
                    except: pass
            app.logger.info(f"Indexing cycle complete. Processed {count} books.")
        except Exception as e:
            app.logger.error(f"Indexing error: {e}")
        time.sleep(1800) # Every 30 minutes
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
    voice_info = all_voices().get(voice_id, {})
    engine = voice_info.get('engine', 'kokoro')
    ptext = _preview_text_for(engine)

    # CosyVoice is GPU-only (Kaggle-render): its previews are pre-rendered and
    # dropped into PREVIEWS_DIR, never generated on this box. If it isn't cached
    # there's nothing to serve locally — don't fall through and mis-generate.
    if engine == 'cosyvoice':
        return preview_path if preview_path.exists() else None

    try:
        if engine == 'polly':
            # Skip if AWS keys are not set
            if not (get_setting('AWS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')):
                raise Exception("AWS credentials not configured for Polly")

            # Use AWS Polly via tts-proxy
            # Map internal network alias if available, otherwise assume localhost for dev
            proxy_base = os.environ.get('TTS_PROXY_URL', 'http://tts-proxy:8882')
            response = requests.post(
                f"{proxy_base}/j/preview/v1/audio/speech",
                json={
                    "model": "polly",
                    "input": ptext,
                    "voice": voice_id
                },
                timeout=60
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)
        elif engine == 'inworld':
            # Call Inworld TTS API via tts-proxy
            proxy_base = os.environ.get('TTS_PROXY_URL', 'http://tts-proxy:8882')
            inworld_voice_id = voice_id.replace('inworld_', '') if voice_id.startswith('inworld_') else voice_id
            response = requests.post(
                f"{proxy_base}/j/preview/v1/audio/speech",
                json={
                    "model": "inworld",
                    "input": ptext,
                    "voice": f"inworld_{inworld_voice_id}"
                },
                timeout=60
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)
        elif engine == 'edge':
            # edge-tts as a LIBRARY. This used to spawn
            # ghcr.io/p0n1/epub_to_audiobook purely to run its `edge-tts`
            # binary: a container, an image pull and a working docker CLI for
            # what is one HTTP call. It broke completely when the CLI turned out
            # to be missing from the image (2026-07-25). Calling the package
            # directly removes the whole chain.
            import asyncio
            import edge_tts
            app.logger.info(f"Generating EdgeTTS preview for {voice_id}")

            async def _edge():
                await edge_tts.Communicate(ptext, voice_id).save(str(preview_path))

            asyncio.run(_edge())
        elif engine == 'gemini':
            # One explicit free-tier request, then local encoding. The adapter
            # intentionally returns lossless WAV only and never retries.
            response = requests.post(
                f"{GEMINI_TTS_URL}/audio/speech",
                json={
                    "model": "gemini-3.1-flash-tts-preview",
                    "input": ptext,
                    "voice": voice_id,
                    "response_format": "wav",
                    "speed": 1.0,
                },
                timeout=int(os.environ.get('PREVIEW_TIMEOUT', '600')),
            )
            response.raise_for_status()
            proc = subprocess.run(
                ['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 'mp3',
                 '-b:a', '192k', 'pipe:1'],
                input=response.content, capture_output=True, check=False,
            )
            if proc.returncode or not proc.stdout:
                raise RuntimeError('ffmpeg could not encode the Gemini preview')
            part = preview_path.with_suffix('.mp3.part')
            part.write_bytes(proc.stdout)
            os.replace(part, preview_path)
        elif engine in ('chatterbox', 'chatterbox_nano', 'tada', 'vibevoice', 'qwen3',
                        'pocket', 'kitten'):
            # Direct preview from an isolated local engine service.
            # Timeout must exceed the actual CPU synthesis time: chatterbox runs
            # ~1.5 s/word on CPU, so the ~135-word sample takes ~3.5 min. The old
            # 180s cap was SHORTER than that, so every chatterbox sample was
            # generated, timed out, and thrown away — the cache could never fill
            # (2026-07-14). Be generous; this is a background job.
            _url = (VIBEVOICE_URL if engine == 'vibevoice'
                    else QWEN3_URL if engine == 'qwen3'
                    else GEMINI_TTS_URL if engine == 'gemini'
                    else POCKET_URL if engine == 'pocket'
                    else KITTEN_URL if engine == 'kitten'
                    else TADA_URL if engine == 'tada'
                    else CHATTERBOX_NANO_URL if engine == 'chatterbox_nano'
                    else CHATTERBOX_URL)
            response = requests.post(
                f"{_url}/audio/speech",
                json={
                    "model": "tts-1",
                    "input": ptext,
                    "voice": voice_id,
                    "response_format": "mp3"
                },
                timeout=int(os.environ.get('PREVIEW_TIMEOUT', '600'))
            )
            response.raise_for_status()
            with open(preview_path, 'wb') as f:
                f.write(response.content)
        else:
            # Use Kokoro TTS
            response = requests.post(
                f"{KOKORO_URL}/audio/speech",
                json={
                    "model": "kokoro",
                    "input": ptext,
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


def extract_epub_cover(epub_path: Path, output_path: Path):
    """Fallback logic to extract cover image from EPUB if tool missed it."""
    if not epub_path.exists():
        return
    if (output_path / "cover.jpg").exists():
        return

    try:
        from ebooklib import epub
        book = epub.read_epub(str(epub_path), {"ignore_ncx": True})

        cover_item = None
        # 1. Try to find cover via metadata/properties
        for item in book.get_items():
            if isinstance(item, epub.EpubImage):
                # Check for cover property or common id/filename
                iid = (item.id or '').lower()
                ifname = (item.file_name or '').lower()
                if 'cover' in iid or 'cover' in ifname:
                    cover_item = item
                    break

        # 2. Try common filenames if not found
        if not cover_item:
            for item in book.get_items():
                if isinstance(item, epub.EpubImage):
                    ifname = (item.file_name or '').lower()
                    if any(x in ifname for x in ['thumb', 'title', 'folder']):
                        cover_item = item
                        break

        if cover_item:
            with open(output_path / "cover.jpg", 'wb') as f:
                f.write(cover_item.content)
            app.logger.info(f"Extracted fallback cover to {output_path / 'cover.jpg'}")
    except Exception as e:
        app.logger.warning(f"Failed fallback cover extraction: {e}")


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

    Handles both 3-digit (001.mp3 or 001_*.mp3) and 4-digit (0001_*.mp3) filenames.
    """
    existing = set()
    if output_dir.exists():
        for f in output_dir.glob('*.mp3'):
            m = re.match(r'^(\d{3,4})(?:[_\-\.\s]|$)', f.name)
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

    Uses ``--start N --end N`` to convert one chapter at a time.
    Returns the list of chapters that still failed after all retries.
    """
    still_missing = []
    for ch in missing:
        success = False
        for attempt in range(1, MAX_CHAPTER_RETRIES + 1):
            # Build retry command — same as original but targeting a single chapter using --start and --end
            retry_cmd = [c for c in cmd_template]  # shallow copy
            # Remove any existing --start / --end flags if present
            clean = []
            skip_next = False
            for c in retry_cmd:
                if skip_next:
                    skip_next = False
                    continue
                if c in ('--start', '--end'):
                    skip_next = True
                    continue
                clean.append(c)
            clean.extend(['--start', str(ch), '--end', str(ch)])

            app.logger.info(f"Retry chapter {ch} attempt {attempt}/{MAX_CHAPTER_RETRIES}: {' '.join(clean)}")
            append_job_log(job_id, f"Retrying chapter {ch} (attempt {attempt}/{MAX_CHAPTER_RETRIES})")

            # Redirect output to a log file
            log_file_path = Path(LOG_DIR) / f"{job_id}_retry_ch{ch}_attempt{attempt}.log"
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_file_path, 'w', encoding='utf-8')
            qa_path = output_path / 'qa_report.json'
            qa_before = read_qa_report(qa_path)
            process_succeeded = False

            try:
                proc = subprocess.Popen(clean, stdout=log_file, stderr=subprocess.STDOUT)
                running_processes[job_id] = proc
                proc.wait(timeout=timeout_seconds)
                process_succeeded = proc.returncode == 0
                if proc.returncode != 0:
                    log_file.close()
                    err_txt = log_file_path.read_text(encoding='utf-8', errors='ignore') if log_file_path.exists() else ""
                    app.logger.error(f"Retry chapter {ch} failed with return code {proc.returncode}")
                    app.logger.error(f"ERR LOG: {err_txt[:1000]}")
                    append_job_log(job_id, f"Chapter {ch} retry error: {err_txt[:200]}")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                app.logger.warning(f"Retry chapter {ch} attempt {attempt} timed out")
                append_job_log(job_id, f"Chapter {ch} retry timed out")
                continue
            finally:
                if not log_file.closed:
                    log_file.close()
                running_processes.pop(job_id, None)

            # A one-chapter converter run writes a one-chapter qa_report.json.
            # Merge it with the pre-recovery book report instead of allowing it
            # to overwrite evidence for every chapter already rendered.
            qa_after = read_qa_report(qa_path)
            if process_succeeded and qa_after:
                write_qa_report_atomic(
                    qa_path, merge_qa_reports(qa_before, qa_after))
            elif qa_after != qa_before:
                if qa_before:
                    write_qa_report_atomic(qa_path, qa_before)
                else:
                    qa_path.unlink(missing_ok=True)

            # Wait for file system sync
            import time as time_module
            time_module.sleep(5)

            # Check if the chapter file now exists (both 3-digit and 4-digit formats, and .mp3 / .wav)
            ch_files = []
            for ext in ('mp3', 'wav'):
                ch_files.extend(output_path.glob(f'{ch:03d}.{ext}'))
                ch_files.extend(output_path.glob(f'{ch:03d}_*.{ext}'))
                ch_files.extend(output_path.glob(f'{ch:04d}_*.{ext}'))

            if ch_files and all(f.stat().st_size > 1024 for f in ch_files):
                app.logger.info(f"Chapter {ch} recovered on attempt {attempt}")
                append_job_log(job_id, f"Chapter {ch} recovered on attempt {attempt}")
                # keep the UI honest during recovery
                try:
                    done = len(list(output_path.glob('*.mp3')))
                    job_now = get_job(job_id)
                    total = (job_now or {}).get('total_chapters') or 0
                    if total:
                        update_job(job_id, progress_percent=int(done * 100 / total),
                                   current_chapter=ch)
                except Exception:
                    pass
                success = True
                break
            else:
                app.logger.warning(f"Chapter {ch} still missing after attempt {attempt}. Retrying...")
                import time
                time.sleep(10)

        if not success:
            still_missing.append(ch)
            append_job_log(job_id, f"Chapter {ch} FAILED after {MAX_CHAPTER_RETRIES} retries")

    return still_missing


def get_engine_url(tts_engine: str, job_id: str) -> tuple:
    if tts_engine == 'piper':
        # Piper was fully retired after failing its controlled listening gates.
        # Keep this tombstone so an old queued job fails visibly instead of
        # falling through to Kokoro and producing an unwanted audiobook.
        raise ValueError('Piper is retired; choose a currently offered narrator')
    elif tts_engine in ('inworld', 'edge', 'polly', 'deepgram'):
        url = f"{TTS_PROXY_URL}/j/{job_id}/v1" if TTS_PROXY_URL else f"http://tts-proxy:8882/j/{job_id}/v1"
        model = 'deepgram' if tts_engine == 'deepgram' else ('inworld' if tts_engine == 'inworld' else 'tts-1')
        return url, model
    elif tts_engine == 'chatterbox_nano':
        return CHATTERBOX_NANO_URL, 'tts-1'
    elif tts_engine == 'chatterbox':
        return CHATTERBOX_URL, 'tts-1'
    elif tts_engine == 'tada':
        return TADA_URL, 'tts-1'
    elif tts_engine == 'vibevoice':
        return VIBEVOICE_URL, 'microsoft/VibeVoice-1.5B'
    elif tts_engine == 'qwen3':
        return QWEN3_URL, 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'
    elif tts_engine == 'pocket':
        return POCKET_URL, 'pocket-tts-2.1'
    elif tts_engine == 'kitten':
        return KITTEN_URL, 'KittenML/kitten-tts-mini-0.8'
    elif tts_engine == 'gemini':
        return GEMINI_TTS_URL, 'gemini-3.1-flash-tts-preview'
    else:
        url = f"{TTS_PROXY_URL}/j/{job_id}/v1" if TTS_PROXY_URL else KOKORO_URL
        return url, 'kokoro'


def text_profile_for_engine(tts_engine: str) -> str:
    """Return the measured preprocessing contract for an engine family.

    Pocket and Kitten won their controlled A/B only when numbers/currency were
    spoken explicitly. They must not inherit the raw-number modern profile,
    while their neural frontends also must not receive legacy phonetic
    respellings. Keeping this mapping centralized makes preview, first render
    and recovery use the same input contract.
    """
    if tts_engine in ('pocket', 'kitten', 'gemini', 'deepgram'):
        return 'explicit'
    if tts_engine in ('chatterbox', 'chatterbox_nano', 'tada', 'vibevoice', 'qwen3'):
        return 'modern'
    return 'legacy'


def build_retry_cmd_from_job(job: dict) -> list[str]:
    """Reconstruct the convert_book.py command from job metadata.

    Used by the watchdog recovery path when the original cmd variable
    is no longer available (died, process lost).
    """
    job_id = job['id']
    input_filename = job['input_filename']
    output_dirname = job['output_dirname']
    voice = job['voice']
    tts_engine = job.get('tts_engine', 'kokoro')

    epub_filename = input_filename
    if job.get('is_pdf'):
        epub_filename = input_filename.rsplit('.', 1)[0] + '.epub'

    # Prefer the preprocessed _tts copy
    tts_filename = epub_filename.rsplit('.', 1)[0] + '_tts.epub'
    epub_path = UPLOAD_DIR / tts_filename
    if not epub_path.exists():
        epub_path = UPLOAD_DIR / epub_filename

    effective_voice = voice
    if tts_engine == 'kokoro' and job.get('voice2'):
        effective_voice = f"{voice}+{job['voice2']}"

    tts_base_url, tts_model = get_engine_url(tts_engine, job_id)

    output_path = OUTPUT_DIR / output_dirname

    cmd = [
        sys.executable, '/app/scripts/convert_book.py',
        '--epub', str(epub_path),
        '--engine-url', tts_base_url,
        '--voice', voice if tts_engine in ('edge', 'inworld') else effective_voice,
        '--out', str(output_path),
        '--model', tts_model,
        '--text-profile', text_profile_for_engine(tts_engine),
        # Without this the render cannot be verified afterwards: the converter
        # is the only place every engine passes through, so it is where the
        # transcript record has to be written (#33).
        '--job-id', str(job_id),
    ]

    conf_filename = f"search_{job_id}.conf"
    search_conf_path = UPLOAD_DIR / conf_filename
    if search_conf_path.exists():
        cmd.extend(['--search-and-replace-file', str(search_conf_path)])

    if tts_engine == 'tada':
        cmd.append('--denoise')
    if tts_engine == 'vibevoice':
        # Vibe's accepted result was one generation per chapter. The old 3600s
        # HTTP timeout was shorter than the measured 3676s chapter generation.
        cmd.extend(['--chunk-chars', '1000000', '--request-timeout', '21600'])
    elif tts_engine == 'qwen3':
        # Reproduce the accepted audition's sentence-sized passes and 350ms
        # joins; this is a quality parameter, not generic converter trivia.
        cmd.extend(['--chunk-chars', '450', '--join-silence-ms', '350'])
    elif tts_engine == 'gemini':
        # Google warns that 3.1 quality can drift after a few minutes. Pack
        # complete paragraphs to roughly 2–3 minute requests, make one attempt
        # only, and persist successful passages so free-quota exhaustion can
        # resume without paying the request again.
        cache_dir = Path('/data/gemini_chunks') / str(job_id)
        cmd.extend(['--chunk-chars', '2200', '--pack-paragraphs',
                    '--chunk-cache-dir', str(cache_dir),
                    '--max-chunk-attempts', '1', '--request-timeout', '300'])

    _asr = str(get_setting('ASR_VERIFY')
               if get_setting('ASR_VERIFY') is not None
               else os.environ.get('ASR_VERIFY', '1')).strip().lower()
    if _asr not in ('0', 'false', 'no', 'off'):
        qa_model = (get_setting('ASR_VERIFY_MODEL')
                    or os.environ.get('ASR_VERIFY_MODEL') or 'base').strip()
        cmd.extend(['--qa', '--qa-model', qa_model])

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

    # CROSS-PROCESS lock via DB: webapp (resume API) and worker (orphan
    # cleanup/watchdog) are separate processes — an in-memory dict cannot stop
    # them racing (observed 2026-07-08: two recovery threads 4s apart). The DB
    # lock has a 3h staleness takeover so a crashed owner never wedges a job.
    lock_key = f'recovery_lock_{job_id}'
    now_iso = datetime.now().isoformat()
    try:
        with get_db() as conn:
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (lock_key,)).fetchone()
            if row and row['value']:
                try:
                    age = (datetime.now() - datetime.fromisoformat(row['value'])).total_seconds()
                except Exception:
                    age = 999999
                if age < 3 * 3600:
                    app.logger.info(f"Recovery {job_id}: another process holds the recovery lock ({int(age)}s old), skipping")
                    _recovery_in_progress.pop(_recovery_thread_key, None)
                    return
            conn.execute('INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)', (lock_key, now_iso))
            conn.commit()
    except Exception as e:
        app.logger.warning(f"Recovery {job_id}: lock acquisition issue ({e}), proceeding cautiously")

    try:
        _recover_partial_inner(job_id, _recovery_thread_key)
    finally:
        _recovery_in_progress.pop(_recovery_thread_key, None)
        _recovery_in_progress.pop(job_id, None)
        try:
            with get_db() as conn:
                conn.execute('DELETE FROM app_settings WHERE key = ?', (lock_key,))
                conn.commit()
        except Exception:
            pass


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

        # Restart Kokoro before retries to clear memory leak (only if Kokoro is used)
        if job.get('tts_engine') == 'kokoro':
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

    # Same shared completion helper as every other path. This was the THIRD
    # inline re-implementation of gate -> sync -> status, and like the local one
    # it predated the M4B step — so a RECOVERED book shipped without its M4B
    # (2026-07-25). total_chapters is recovery-specific, applied on top.
    outcome = _gate_and_sync(job_id, output_path, book_name, len(output_files))
    update_job(job_id, total_chapters=total_chapters)
    app.logger.info(f"Recovery {job_id}: {outcome} with {len(output_files)} files")
    append_job_log(job_id, f"{'Completed' if outcome == 'completed' else 'Held for review'} "
                           f"with {len(output_files)} chapters (recovery path)")

    job = get_job(job_id)
    if job:
        record_conversion_metrics(job)
        if job.get('status') == 'completed' and job.get('notify_telegram'):
            send_telegram_notification(job, success=True)

    # Start next queued job
    maybe_start_next_queued_job()


def cleanup_small_files(output_dir: Path, min_size_kb: int = 0) -> int:
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


def _abs_credentials():
    """Return (url, token) for the ABS API, DB setting first, env as fallback.

    Settings written through the UI live in app_settings and survive restarts;
    the module-level constants only ever see the environment. Reading the env
    directly is a bug that makes a token saved in Settings do nothing, which is
    exactly what `_trigger_abs_rescan` used to do (#35).
    """
    url = (get_setting('ABS_API_URL') or ABS_API_URL or '').rstrip('/')
    token = get_setting('ABS_API_TOKEN') or ABS_API_TOKEN or ''
    return url, token


def _abs_auth_failed(job_id, where, status):
    """Report an ABS credential failure loudly, once, in the place people look.

    A 401 used to go only to app.logger, so a dead token was invisible: the
    file sync is rsync over SSH and keeps working, the badge stays green, and
    every API-backed feature silently does nothing. If the credential is bad,
    say so on the job (#35).
    """
    msg = (f"ABS {where} FAILED: HTTP {status}. "
           f"The Audiobookshelf API token is rejected — regenerate it in ABS "
           f"(Settings → Users → API token) and save it in Settings here. "
           f"File sync is unaffected (it uses SSH), but covers, rescans and "
           f"library cleanup will not work until this is fixed.")
    app.logger.error(msg)
    if job_id:
        append_job_log(job_id, msg)


def _trigger_abs_rescan(job_id: str | None = None):
    """Trigger an Audiobookshelf library rescan via the ABS API.

    Ensures chapter metadata is regenerated after files are synced, and is the
    only thing that prunes items whose files have gone. Failures never affect
    job status — but they are no longer silent.
    """
    url, token = _abs_credentials()
    if not token:
        if job_id:
            append_job_log(job_id, "ABS rescan skipped: no API token configured "
                                   "(set one in Settings to enable rescans).")
        return False
    try:
        resp = requests.get(
            f"{url}/api/libraries",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code in (401, 403):
            _abs_auth_failed(job_id, "rescan", resp.status_code)
            return False
        if resp.status_code != 200:
            msg = f"ABS rescan: could not list libraries (HTTP {resp.status_code})"
            app.logger.warning(msg)
            if job_id:
                append_job_log(job_id, msg)
            return False
        libraries = resp.json().get('libraries', [])
        for lib in libraries:
            scan_resp = requests.post(
                f"{url}/api/libraries/{lib['id']}/scan",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            app.logger.info(f"ABS: Triggered rescan for library '{lib['name']}': {scan_resp.status_code}")
            if job_id:
                append_job_log(job_id, f"ABS rescan triggered for library '{lib['name']}'")
        return True
    except Exception as e:
        app.logger.warning(f"ABS rescan failed (non-fatal): {e}")
        if job_id:
            append_job_log(job_id, f"ABS rescan failed (non-fatal): {e}")
        return False


def abs_purge_missing_items(job_id: str | None = None):
    """Delete ABS library items whose media files are gone.

    Because the sync is filesystem-level (rsync over SSH), removing a render
    deletes files but leaves ABS's database row behind, flagged isMissing.
    Nothing ever cleaned those up, so every `e2e_proof.sh` run left a ghost —
    seven "The Raven" entries had accumulated by 2026-07-25 (#35).

    Returns (removed, errors). Never raises.
    """
    url, token = _abs_credentials()
    if not token:
        return 0, ['no ABS API token configured']
    hdr = {"Authorization": f"Bearer {token}"}
    removed, errors = 0, []
    try:
        libs = requests.get(f"{url}/api/libraries", headers=hdr, timeout=15)
        if libs.status_code in (401, 403):
            _abs_auth_failed(job_id, "purge", libs.status_code)
            return 0, [f'auth rejected (HTTP {libs.status_code})']
        if libs.status_code != 200:
            return 0, [f'could not list libraries (HTTP {libs.status_code})']

        for lib in libs.json().get('libraries', []):
            items = requests.get(
                f"{url}/api/libraries/{lib['id']}/items",
                headers=hdr, timeout=30,
            )
            if items.status_code != 200:
                errors.append(f"library {lib.get('name')}: HTTP {items.status_code}")
                continue
            for item in items.json().get('results', []):
                # ABS marks an item isMissing when its files vanish from disk.
                if not item.get('isMissing'):
                    continue
                iid = item.get('id')
                rel = item.get('relPath') or iid
                d = requests.delete(f"{url}/api/items/{iid}", headers=hdr, timeout=15)
                if d.status_code in (200, 204):
                    removed += 1
                    app.logger.info(f"ABS: removed missing item {rel}")
                    if job_id:
                        append_job_log(job_id, f"ABS: removed missing item '{rel}'")
                else:
                    errors.append(f"{rel}: HTTP {d.status_code}")
    except Exception as e:
        errors.append(str(e))
    return removed, errors


@app.route('/api/abs/purge-missing', methods=['POST'])
def api_abs_purge_missing():
    """Remove Audiobookshelf items whose files no longer exist."""
    removed, errors = abs_purge_missing_items()
    return jsonify({'removed': removed, 'errors': errors}), (200 if not errors else 207)


def _podcast_folder_name(site: str) -> str:
    """The ABS podcast a given source site's articles belong to.

    Grouping by site rather than dumping everything into one "Articles" bucket
    is what makes the podcast library readable: ABS shows each folder as a
    podcast with its own cover and episode count, so "Ars Technica — 4 episodes"
    behaves like a feed you subscribed to. A single mixed folder would show one
    podcast whose episodes have nothing to do with each other.
    """
    name = sanitize_filename(site or 'Articles').strip() or 'Articles'
    return name[:60]


def _episode_filename(job: dict, book_name: str) -> str:
    """Stable, job-specific episode name that sorts by publication date.

    The job id is intentionally part of the filename.  Podcast episodes from a
    site share one ABS folder, so title/date alone cannot identify which file a
    later "delete everywhere" action owns when an article was converted twice.
    """
    date = (job.get('source_date') or '')[:10]
    title = sanitize_filename(book_name or 'Article').strip() or 'Article'
    stem = f"{date} - {title}" if date else title
    job_id = sanitize_filename(str(job.get('id') or '')).strip()
    suffix = f" [{job_id}]" if job_id else ''
    return f"{stem[:max(1, 120 - len(suffix))]}{suffix}.mp3"


def _legacy_episode_filename(job: dict, book_name: str) -> str:
    """Pre-2026-08-14 article name, used only to remove older exact files."""
    date = (job.get('source_date') or '')[:10]
    title = sanitize_filename(book_name or 'Article').strip() or 'Article'
    stem = f"{date} - {title}" if date else title
    return f"{stem[:120]}.mp3"


def _abs_destination(output_dir: Path, job_id: str | None) -> tuple[str, bool]:
    """Return (remote path, is_article) for this render's Audiobookshelf copy.

    The two libraries want two different SHAPES, which is the part that is easy
    to get wrong. A book library reads one folder as one audiobook, so a book
    syncs to `<audiobooks>/<Book Folder>/` and its chapter MP3s go inside. A
    podcast library reads one folder as one podcast and every audio file
    directly inside it as an episode — so an article syncs its single MP3
    *flat* into `<podcasts>/<Site>/`, with no per-article subfolder. Nesting
    one level deeper looks tidier and is simply not scanned.

    Falls back to the book path whenever anything is unknown — a misfiled
    article is a nuisance, but a book that fails to sync because a podcast
    folder could not be derived is a real loss.
    """
    book_dest = f"{AUDIOBOOKSHELF_DIR}/{output_dir.name}"
    if not job_id or not AUDIOBOOKSHELF_PODCAST_DIR:
        return book_dest, False
    job = get_job(job_id) or {}
    if (job.get('source_kind') or 'book') != 'article':
        return book_dest, False
    podcast = _podcast_folder_name(job.get('source_site') or '')
    return f"{AUDIOBOOKSHELF_PODCAST_DIR}/{podcast}", True


def _stage_episode(output_dir: Path, job: dict, book_name: str) -> Path | None:
    """Copy the render's audio into a staging dir as a single named episode.

    Articles are rendered as one chapter, so the output folder holds one MP3
    with a chapter-ish name plus the bookkeeping files a book needs (cover,
    verification, gate). None of that belongs in a podcast folder, where every
    audio file present becomes an episode. Staging one correctly-named file is
    simpler and safer than a pile of rsync excludes.
    """
    mp3s = sorted(p for p in output_dir.glob('*.mp3') if p.is_file())
    if not mp3s:
        return None
    staging = Path('/tmp') / f"podcast_{job.get('id') or 'ep'}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    if len(mp3s) == 1:
        _copy_as_episode(mp3s[0], staging / _episode_filename(job, book_name),
                         job, book_name)
    else:
        # A long article can still split. Keep them ordered and grouped, since
        # ABS will list each as its own episode.
        base = _episode_filename(job, book_name)[:-4]
        for i, p in enumerate(mp3s, 1):
            _copy_as_episode(p, staging / f"{base} ({i:02d}).mp3", job, book_name)
    return staging


def _copy_as_episode(src: Path, dst: Path, job: dict, book_name: str) -> None:
    """Copy an MP3, retagging it as a podcast episode.

    Audiobookshelf names a podcast from the audio's **album** tag, not from the
    folder. The converter tags every render `album=<book title>`, so the first
    live run produced a podcast literally called "Roku raises streaming stick
    prices by up to 60 percent" containing one episode of itself — and the next
    Ars piece would have created another one-episode podcast beside it, which is
    exactly the clutter this change existed to remove.

    So the episode is retagged here, on the copy, rather than by plumbing
    article-awareness down into the converter: `album` becomes the site (the
    podcast), `title` stays the headline (the episode), and the date carries
    across. The book render is left completely untouched.

    Stream-copies the audio, so this is a tag rewrite, not a re-encode.
    """
    site = job.get('source_site') or 'Articles'
    tags = {
        'album': site,
        'artist': site,
        'album_artist': site,
        'title': book_name,
        'genre': 'Podcast',
        'date': (job.get('source_date') or '')[:10],
        'comment': job.get('source_url') or '',
    }
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-c', 'copy']
    for k, v in tags.items():
        if v:
            cmd += ['-metadata', f'{k}={v}']
    cmd.append(str(dst))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1024:
            return
        app.logger.warning(f"Episode retag failed ({r.returncode}); copying untagged")
    except Exception as e:
        app.logger.warning(f"Episode retag unavailable ({e}); copying untagged")
    # Never lose the episode over a tagging problem.
    shutil.copy2(src, dst)


def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    app.logger.info("DEBUG: Starting copy_to_audiobookshelf")
    ssh_key_src = os.environ.get("SSH_KEY_PATH", "/root/.ssh/id_ed25519")
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    if os.path.exists(ssh_key_src):
        app.logger.info(f"DEBUG: Found source key {ssh_key_src}")
        import subprocess
        subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
        subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
        app.logger.info(f"DEBUG: Prepared temp key {ssh_key_tmp}")
    else:
        app.logger.warning(f"DEBUG: Source key {ssh_key_src} NOT FOUND")

    target = f"{AUDIOBOOKSHELF_USER}@{AUDIOBOOKSHELF_HOST}"
    dest_path, is_article = _abs_destination(output_dir, job_id)
    # An article syncs one flat, named MP3 into the podcast folder; a book
    # syncs its whole folder. `source_dir` is what actually gets rsynced.
    source_dir = output_dir
    if is_article:
        staged = _stage_episode(output_dir, get_job(job_id) or {'id': job_id}, book_name)
        if staged is None:
            app.logger.warning("No MP3 to publish as an episode; syncing as a book")
            dest_path, is_article = f"{AUDIOBOOKSHELF_DIR}/{output_dir.name}", False
        else:
            source_dir = staged

    ssh_args = [
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-F', '/dev/null',
        '-i', ssh_key_tmp,
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
        append_job_log(
            job_id,
            f"Sync start -> {target}:{dest_path}"
            + (" (podcast library — this is an article, not a book)" if is_article else ""))

    try:
        # NO local `import shlex` here. shlex is imported at module level, and a
        # function-local import makes the name local for the WHOLE function —
        # which left the earlier shlex.quote() in rsync_ssh unbound and broke
        # every Audiobookshelf sync with "cannot access free variable 'shlex'".
        # (This function had two duplicate local imports; ruff's F401 autofix
        # removed the first as redundant, which was correct in isolation and
        # fatal in combination. 2026-07-25.)
        remote_mkdir = ' '.join(shlex.quote(x) for x in ['mkdir', '-p', '--', dest_path])
        mkdir_cmd = ['ssh', *ssh_args, target, remote_mkdir]
        mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)
        if mkdir_result.returncode != 0:
            err = (mkdir_result.stderr or mkdir_result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync mkdir failed: {err}")
            return False

        # Auto-sync the REAL cover: extract it from the source epub and drop a
        # cover.jpg into the output folder before rsync. ABS auto-detects a
        # cover.jpg in a book folder and uses it, so the correct art lands with
        # no manual step (otherwise ABS guesses from metadata and gets it wrong).
        try:
            _existing = list(Path(output_dir).glob('cover.*'))
            if not _existing and job_id:
                _job = get_job(job_id) or {}
                _in = _job.get('input_filename', '') or ''
                if _in:
                    _epub_name = _in if not _job.get('is_pdf') else _in.rsplit('.', 1)[0] + '.epub'
                    _epub = UPLOAD_DIR / _epub_name
                    if _epub.exists():
                        _data, _mime = _extract_epub_cover(str(_epub))
                        if _data:
                            _ext = {'image/png': 'png', 'image/webp': 'webp'}.get(_mime or '', 'jpg')
                            cover_path = Path(output_dir) / f'cover.{_ext}'
                            cover_path.write_bytes(_data)
                            append_job_log(job_id, f"Cover extracted from epub -> {cover_path.name}")
        except Exception as _ce:
            if job_id:
                append_job_log(job_id, f"Cover extract skipped: {_ce}")

        # Do NOT ship the EPUB3-with-embedded-audio artefact to Audiobookshelf.
        # It is a third copy of the same audio — a 2.5-hour book produced 12
        # MP3s (166 MB), a 76 MB M4B and a 169 MB epub, so the library folder
        # was 401 MB for 2.5 hours of listening. Audiobookshelf has no use for
        # it either: it is an audiobook library, and the epub only gives the
        # scanner an ebook to parse. Keep it in the working directory for
        # anyone who wants it; don't sync it (#38).
        #
        # Internal bookkeeping files are excluded for the same reason — they
        # are ours, not the listener's.
        #
        # For an article, `source_dir` is the staging folder holding exactly one
        # named MP3, so these excludes are a no-op there — the filtering already
        # happened when the episode was staged.
        cmd = ['rsync', '-av', '-s',
               '--exclude', '*.epub',
               '--exclude', '_presync_gate.json',
               '--exclude', '_verification/',
               '-e', rsync_ssh, f'{source_dir}/', f"{target}:{dest_path}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync failed: {err}")
            return False

        if job_id:
            delivered_audio = len([p for p in source_dir.glob('*.mp3') if p.is_file()])
            update_job(job_id, sync_status='ok', sync_file_count=delivered_audio,
                       sync_timestamp=datetime.now().isoformat())
            append_job_log(job_id, "Sync ok")

            # Automatically trigger library scan in ABS
            abs_url = get_setting('ABS_API_URL') or ABS_API_URL
            abs_token = get_setting('ABS_API_TOKEN') or ABS_API_TOKEN
            if abs_url and abs_token:
                try:
                    # 1. Get libraries
                    resp = requests.get(f"{abs_url.rstrip('/')}/api/libraries",
                                        headers={'Authorization': f'Bearer {abs_token}'},
                                        timeout=10)
                    if resp.status_code == 200:
                        libs = resp.json().get('libraries', [])
                        # 2. Trigger scan for each library (usually just one main one)
                        for lib in libs:
                            scan_url = f"{abs_url.rstrip('/')}/api/libraries/{lib['id']}/scan"
                            requests.post(scan_url, headers={'Authorization': f'Bearer {abs_token}'}, timeout=10)
                        append_job_log(job_id, f"Triggered ABS scan for {len(libs)} libraries")
                except Exception as e:
                    app.logger.warning(f"Failed to trigger ABS scan: {e}")

        return True
    except Exception as e:
        if job_id:
            update_job(job_id, sync_status='failed', sync_error=str(e))
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
        log_file = Path(LOG_DIR) / f"{job_id}_convert.log"
        if log_file.exists():
            try:
                logs = log_file.read_text(encoding='utf-8', errors='replace')
            except Exception:
                logs = ""
        else:
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
        # `current_chapter` is the BOOK-ABSOLUTE index, but total_chapters counts
        # only the chapters in the requested range. Mixing the two made a range
        # render of chapters 2-2 report "Chapter 2 of 1" at 100% while it was
        # still synthesising (2026-07-25). Convert to a range-relative position.
        _range_start = (job or {}).get('start_chapter') or 1
        if current_chapter and (current_chapter - _range_start) > completed:
            completed = current_chapter - _range_start
        if total_chapters:
            completed = max(0, min(completed, total_chapters))

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
                # Only count chunk progress for the currently converting chapter
                # (compare in absolute terms, since chunk_chapter is absolute).
                if (chunk_chapter == current_chapter) and (chunk_chapter == _range_start + completed):
                    frac += max(0.0, (chunk_idx - 1) / chunk_total) / total_chapters
            progress_percent = int(frac * 100)
            if progress_percent == 0 and frac > 0:
                progress_percent = 1
            # A job that is still converting is never 100% — showing "100%" on a
            # running render is worse than showing 99%, because it reads as done.
            progress_percent = min(progress_percent, 99)

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

KAGGLE_KERNELS_DIR = os.environ.get('KAGGLE_KERNELS_DIR', '/app/kaggle_kernels')


def convert_book_kaggle(job_id: str, input_filename: str, output_dirname: str, voice: str,
                        resume: bool = False, recover_existing: bool = False):
    """Render a book on a free Kaggle GPU (chatterbox/tada), then run the same
    completion path as a local conversion (verify, ABS sync, notify)."""
    try:
        import kaggle_render as KR
    except Exception as e:
        update_job(job_id, status='failed', error=f'Kaggle render unavailable: {e}',
                   completed_at=datetime.now().isoformat())
        maybe_start_next_queued_job()
        return

    job = get_job(job_id) or {}
    engine = job.get('tts_engine', 'kokoro')
    # Prefer credentials entered in the UI (persisted in app_settings, shared
    # across webapp/worker via the DB) over any baked-in .env values.
    for k in ('KAGGLE_API_TOKEN', 'KAGGLE_USERNAME'):
        v = get_setting(k)
        if v:
            os.environ[k] = v
    # The one "token" field may hold a newer KGAT access-token OR a classic
    # kaggle.json key — set both env styles so either authenticates.
    if os.environ.get('KAGGLE_API_TOKEN'):
        os.environ.setdefault('KAGGLE_KEY', os.environ['KAGGLE_API_TOKEN'])
    if not KR.kaggle_ready():
        update_job(job_id, status='failed',
                   error='Kaggle not configured on this host (no credentials). Add a Kaggle token to enable cloud GPU render.',
                   completed_at=datetime.now().isoformat())
        append_job_log(job_id, "Kaggle render aborted: no credentials")
        maybe_start_next_queued_job()
        return
    if engine not in KR.render_engines():
        update_job(job_id, status='failed',
                   error=f'{engine} cannot render on Kaggle GPU (supported: {", ".join(KR.render_engines())}).',
                   completed_at=datetime.now().isoformat())
        maybe_start_next_queued_job()
        return

    epub_path = UPLOAD_DIR / input_filename
    output_path = OUTPUT_DIR / output_dirname
    output_path.mkdir(parents=True, exist_ok=True)
    start = job.get('start_chapter') or 1
    end = job.get('end_chapter') or 0

    if not resume:
        update_job(job_id, status='rendering on Kaggle GPU', progress_percent=1)
        append_job_log(job_id, f"Kaggle GPU render start (engine={engine}, voice={voice})")
    else:
        app.logger.info(f"Kaggle: Resuming monitoring for job {job_id}")
        append_job_log(job_id, f"Kaggle: Resuming monitoring (engine={engine}, voice={voice})")

    # Honest coarse progress: Kaggle exposes only queued/running/complete, so we
    # estimate from elapsed vs a projection SCALED BY CHAPTER COUNT (~6 min/chapter
    # on a T4 + ~12 min one-time setup/model-load), and snap to the real chapter
    # count on completion. Still an estimate — true per-chapter needs a call-home.
    n_ch = max(1, (int(end) - int(start) + 1)) if end and int(end) > 0 else \
        max(1, (job.get('total_chapters') or 20) - int(start) + 1)
    proj_min = max(15, 12 + n_ch * 6)

    # The renderer phones home the TRUE count of renderable chapters in the
    # requested range; capture it so verification checks against reality, not the
    # raw range span (which false-fails when a range overshoots the book).
    render_stats = {'total': None}

    def on_status(st, mins, prog=None):
        current = get_job(job_id)
        if current and current.get('status') == 'cancelled':
            raise Exception("Job was cancelled by user")
        base = {'queued': 'queued on Kaggle', 'running': 'rendering on Kaggle GPU'}.get(st, 'rendering on Kaggle GPU')
        # prog is (pct, done, total) phoned home by the kernel, or None.
        done = total = None
        if prog:
            try:
                _p, done, total = prog
                done, total = int(done), int(total)
            except Exception:
                done = total = None
        if total and total > 0:
            render_stats['total'] = total   # true renderable count for verification

        if total and total > 0 and done is not None and done >= 1:
            # A chapter has ACTUALLY completed — bar and ETA are both grounded in
            # the measured rate, so they're trustworthy now.
            pct = min(99, max(1, int(done / total * 100)))
            eta = int((mins / done) * (total - done))   # avg time/chapter so far
            update_job(job_id, status=f"{base} · chapter {min(done + 1, total)}/{total}",
                       progress_percent=pct, eta_minutes=max(0, eta))
        elif total and total > 0:
            # Set up and rendering the FIRST chapter: nothing has finished, so any
            # ETA would be fiction. Show the phase, creep the bar within the first
            # chapter's share only, and show NO ETA (0 -> UI renders "?").
            cap = max(1, int(100 / total) - 1)          # never imply a chapter is done
            pct = min(cap, max(1, int(mins / proj_min * 100)))
            update_job(job_id, status=f"{base} · rendering chapter 1/{total}",
                       progress_percent=pct, eta_minutes=0)
        else:
            # No call-home yet (installing the CUDA stack / loading the model).
            # Coarse elapsed-vs-projection estimate; clearly still "preparing".
            pct = min(95, max(2, int(mins / proj_min * 100)))
            update_job(job_id, status=base, progress_percent=pct, eta_minutes=max(0, proj_min - mins))

    # Split the requested range into per-session batches. A Kaggle session is
    # capped (~9-12h) and commits its outputs ONLY when the kernel finishes —
    # `kaggle kernels output` returns zero files for a running or killed kernel
    # (verified 2026-07-25). So one oversized run burns the weekly quota and
    # returns NOTHING. Each batch completes and banks its chapters instead.
    try:
        import chapters as _ch
        _chapters = _ch.list_renderable_chapters(str(epub_path))
    except Exception as e:
        append_job_log(job_id, f"Kaggle: chapter scan failed ({e}); running as a single session")
        _chapters = []
    batches = KR.plan_batches(_chapters, start or 1, end or 0,
                              rtf=KR.ENGINE_RTF.get(engine, 0.9))
    if recover_existing and _chapters:
        existing = set()
        for f in output_path.glob('*.mp3'):
            m = re.match(r'^(\d+)', f.stem)
            if m:
                existing.add(int(m.group(1)))
        selected = [int(c['index']) for c in _chapters
                    if int(c.get('index', 0)) >= int(start or 1)
                    and (not end or int(c.get('index', 0)) <= int(end))]
        missing = [n for n in selected if n not in existing]
        spans = []
        for n in missing:
            if not spans or n != spans[-1][1] + 1:
                spans.append([n, n])
            else:
                spans[-1][1] = n
        batches = []
        for lo, hi in spans:
            batches.extend(KR.plan_batches(_chapters, lo, hi,
                                           rtf=KR.ENGINE_RTF.get(engine, 0.9)))
        append_job_log(job_id, f"Kaggle recovery: keeping {len(existing)} banked chapter(s); "
                       f"{len(missing)} chapter(s) still need rendering")
    if len(batches) > 1:
        append_job_log(job_id,
                       f"Kaggle: ~{sum(b[2] for b in batches):.1f} GPU-h of audio — splitting into "
                       f"{len(batches)} sessions so each one banks its chapters")

    ok, msg = (True, 'all requested chapters were already banked') if not batches \
        else (False, 'no batches planned')
    for _i, (_bs, _be, _bh) in enumerate(batches, 1):
        _cur = get_job(job_id)
        if _cur and _cur.get('status') == 'cancelled':
            append_job_log(job_id, "Kaggle render stopped: cancelled by user.")
            maybe_start_next_queued_job()
            return
        if len(batches) > 1:
            append_job_log(job_id,
                           f"Kaggle: session {_i}/{len(batches)} — chapters {_bs}-{_be} (~{_bh:.1f} GPU-h)")
        try:
            ok, msg = KR.render_on_kaggle(
                str(epub_path), voice, engine, _bs, _be, str(output_path),
                KAGGLE_KERNELS_DIR, log=lambda m: append_job_log(job_id, m),
                on_status=on_status, resume=(resume and _i == 1))
        except Exception as e:
            current = get_job(job_id)
            if current and current.get('status') == 'cancelled':
                append_job_log(job_id, "Kaggle render loop aborted: job cancelled by user.")
                maybe_start_next_queued_job()
                return
            update_job(job_id, status='failed', error=f'Kaggle render error: {e}',
                       completed_at=datetime.now().isoformat())
            append_job_log(job_id, f"Kaggle render error: {e}")
            maybe_start_next_queued_job()
            return
        if not ok:
            # Earlier batches already banked their chapters; Resume picks up the rest.
            break

    if not ok:
        update_job(job_id, status='failed', error=f'Kaggle render failed: {msg}',
                   completed_at=datetime.now().isoformat())
        append_job_log(job_id, f"Kaggle render failed: {msg}")
        maybe_start_next_queued_job()
        return

    # Same completion tail as the local path.
    rename_output_files(output_path, job.get('book_name') or output_dirname)
    removed = cleanup_small_files(output_path, MIN_CHAPTER_SIZE_KB)
    output_files = list(output_path.glob('*.mp3'))
    is_ok, verify_msg = verify_book_complete(
        job_id, output_path, job.get('total_chapters'),
        start_chapter=job.get('start_chapter'), end_chapter=job.get('end_chapter'),
        cleaned_up_count=removed, expected_override=render_stats.get('total'))
    if not is_ok:
        update_job(job_id, status='failed', error=f'Verification failed: {verify_msg}',
                   completed_at=datetime.now().isoformat())
        maybe_start_next_queued_job()
        return
    outcome = _gate_and_sync(job_id, output_path, job.get('book_name'), len(output_files))
    append_job_log(job_id, f"Kaggle render complete: {len(output_files)} chapters ({msg})")
    job = get_job(job_id)
    if outcome == 'completed' and job and job.get('notify_telegram'):
        send_telegram_notification(job, success=True)
    maybe_start_next_queued_job()


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

    # Cloud GPU render path: delegate to Kaggle instead of a local container.
    _rt_job = get_job(job_id)
    if _rt_job and (_rt_job.get('render_target') or 'local') == 'kaggle':
        return convert_book_kaggle(job_id, input_filename, output_dirname, voice)

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

            # Use the calibre already inside this image. Spawning
            # linuxserver/calibre needed the docker CLI, a bind-mounted host
            # path and an image pull — three ways to fail for a job the local
            # `ebook-convert` does directly. (The CLI was in fact missing from
            # the image, so every PDF upload failed here — 2026-07-25.)
            pdf_cmd = ['ebook-convert', str(UPLOAD_DIR / input_filename),
                       str(UPLOAD_DIR / epub_filename)]
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
            from llm_metadata import generate_lexicon, generate_narration_profile
            from tts_preprocess import preprocess_epub

            # QA Layer 1 (pre-flight): adaptive per-book narration profile +
            # legacy name lexicon. Both merge into one lexicon of replacements.
            lexicon = {}
            profile = {}
            try:
                profile = generate_narration_profile(epub_path) or {}
                if profile.get('form'):
                    append_job_log(job_id, f"Book classified as {profile['form']} (domain: {profile.get('domain')})")
                if profile.get('rules'):
                    lexicon.update(profile['rules'])
                    append_job_log(job_id, f"Narration profile: domain='{profile.get('domain')}', {len(profile['rules'])} rules")
            except Exception as e:
                app.logger.warning(f"Narration profile failed: {e}")
            try:
                names = generate_lexicon(epub_path)
                if names:
                    # profile rules win on conflict
                    for k, v in names.items():
                        lexicon.setdefault(k, v)
                    append_job_log(job_id, f"Name lexicon: {len(names)} terms")
            except Exception as e:
                app.logger.warning(f"Lexicon generation failed: {e}")

            preprocessed_path = epub_path.parent / f"{epub_path.stem}_tts{epub_path.suffix}"
            # tts_engine isn't assigned until later in this function; read the
            # engine from the job here so modern-contract preprocessing actually
            # applies (bug caught running the real worker path 2026-07-08).
            _pjob = get_job(job_id)
            _pengine = (_pjob.get('tts_engine') if _pjob else None) or 'kokoro'
            _text_profile = text_profile_for_engine(_pengine)
            _modern = _text_profile in ('modern', 'explicit')
            _expand_numbers = True if _text_profile == 'explicit' else None
            # Explicit numbers/currency won 4/4 controlled CPU A/Bs. Keep only
            # acronym letter-spacing from the lexicon for that profile so a
            # Pocket/Kitten book cannot acquire legacy phonetic respellings.
            _preprocess_lexicon = lexicon
            if _text_profile == 'explicit':
                from tts_preprocess import _is_letter_spacing
                _preprocess_lexicon = {
                    key: value for key, value in lexicon.items()
                    if _is_letter_spacing(key, value)
                }
            _, files_changed = preprocess_epub(
                epub_path, preprocessed_path,
                lexicon=_preprocess_lexicon, modern=_modern,
                expand_numbers=_expand_numbers)
            # Use preprocessed version for conversion, keep original for reference
            host_input_path = f"{HOST_UPLOAD_DIR}/{preprocessed_path.name}"
            epub_path = preprocessed_path
            summary = f"sanitized + normalized, {files_changed} files changed"
            if lexicon:
                summary += f", {len(lexicon)} pronunciation rules"
            if profile.get('domain'):
                summary += f" (domain: {profile['domain']})"
            update_job(job_id, preprocess_summary=summary)
            try:
                update_job(job_id, narration_profile=json.dumps(profile)[:4000])
            except Exception:
                pass
            append_job_log(job_id, f"Text preprocessed ({summary})")
        except Exception as e:
            app.logger.warning(f"TTS preprocessing failed, using original: {e}")
            update_job(job_id, preprocess_summary=f"failed, original text used: {str(e)[:120]}")
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

        # Bulletproof chapter range validation
        try:
            if not is_pdf:
                toc = get_epub_toc(epub_path)
                max_chapters = len(toc) if toc else 999
                if start_chapter and start_chapter > max_chapters:
                    start_chapter = 1
                if end_chapter and end_chapter > max_chapters:
                    end_chapter = max_chapters
                update_job(job_id, start_chapter=start_chapter, end_chapter=end_chapter)
        except: pass

        # SLOW_ENGINE_MIN_TIMEOUT: chatterbox/tada on CPU run near realtime;
        # polluted ETA metrics produced absurd timeouts (375m for a ~14h book,
        # incident 2026-07-07). Floor the timeout at char_count/4 chars-per-sec.
        if tts_engine in ('chatterbox', 'chatterbox_nano', 'tada', 'vibevoice', 'qwen3',
                          'pocket', 'kitten'):
            floor_seconds = int(char_count / 4.0)
            if timeout_seconds < floor_seconds:
                timeout_seconds = floor_seconds
                append_job_log(job_id, f"Timeout floored to {timeout_seconds//60}m for slow engine {tts_engine}")
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

        tts_base_url, tts_model = get_engine_url(tts_engine, job_id)

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
        output_path = Path(f"/data/audiobooks/{output_dirname}")
        cmd = [
            sys.executable, '/app/scripts/convert_book.py',
            '--epub', str(epub_path),
            '--engine-url', tts_base_url,
            '--voice', voice if tts_engine in ('edge', 'inworld') else effective_voice,
            '--out', str(output_path),
            '--model', tts_model,
            '--text-profile', text_profile_for_engine(tts_engine),
            # THE main render path. Without --job-id the converter cannot write
            # transcript chunks, and the book ships unverifiable (#33). A first
            # attempt at this fix only patched the watchdog's retry builder
            # because the two call sites are indented differently — the live
            # render then proved it by producing no chunks at all.
            '--job-id', str(job_id),
        ]

        # Post-flight ASR check. ON by default.
        #
        # It was written as opt-in on my assumption that Whisper "roughly
        # doubles render time". That was never measured and was wrong.
        # MEASURED on zorin's i5-12400: faster-whisper `base` at int8
        # transcribed 675 s of audio in 33.4 s — 20x realtime. Alice's full
        # 8,829 s costs about 7 minutes against a ~2-hour render, i.e. ~6%.
        #
        # At that price there is no argument for shipping books unverified,
        # which is what #33 was about. Set ASR_VERIFY=0 to opt out.
        _asr = str(get_setting('ASR_VERIFY')
                   if get_setting('ASR_VERIFY') is not None
                   else os.environ.get('ASR_VERIFY', '1')).strip().lower()
        is_article = (job and job.get('source_kind') == 'article') or (char_count < 15000 and _asr != 'force')
        if _asr not in ('0', 'false', 'no', 'off') and not is_article:
            qa_model = (get_setting('ASR_VERIFY_MODEL')
                        or os.environ.get('ASR_VERIFY_MODEL') or 'base').strip()
            cmd.extend(['--qa', '--qa-model', qa_model])
            append_job_log(job_id, f"ASR verification on (whisper '{qa_model}') - "
                                   f"the audio will be transcribed and compared against "
                                   f"the source text. Measured ~20x realtime, so this "
                                   f"adds roughly 6% to the render.")
        elif is_article:
            append_job_log(job_id, "Fast article mode: skipped post-flight ASR verification for instant turnaround.")

        if job and job.get('start_chapter'):
            cmd.extend(['--start', str(job['start_chapter'])])
        if job and job.get('end_chapter'):
            cmd.extend(['--end', str(job['end_chapter'])])

        # Per-job narration speed. This was computed above and then DROPPED —
        # convert_book had no --speed argument at all, so the UI control did
        # nothing on local renders (found by ruff F841, 2026-07-25).
        # Chatterbox Turbo/Nano genuinely have no speed control and ignore the
        # field, so say so rather than implying it worked.
        if tts_speed and float(tts_speed) != 1.0:
            if tts_engine == 'gemini':
                append_job_log(job_id,
                               f"NOTE: speed {tts_speed}x requested, but Gemini pacing is "
                               f"pinned by the heard style prompt; the request remains at 1.0x.")
            elif tts_engine in ('chatterbox', 'chatterbox_nano', 'tada', 'pocket', 'kitten'):
                cmd.extend(['--speed', str(tts_speed)])
                append_job_log(job_id,
                               f"NOTE: speed {tts_speed}x requested, but {tts_engine} has no "
                               f"documented OpenAI-style speed control and will ignore it. "
                               f"Audio will render at the engine's native pace.")
            else:
                cmd.extend(['--speed', str(tts_speed)])
                append_job_log(job_id, f"Narration speed: {tts_speed}x")

        if search_conf_path and search_conf_path.exists():
            cmd.extend(['--search-and-replace-file', str(search_conf_path)])

        if tts_engine == 'tada':
            cmd.append('--denoise')
        if tts_engine == 'vibevoice':
            cmd.extend(['--chunk-chars', '1000000', '--request-timeout', '21600'])
        elif tts_engine == 'qwen3':
            cmd.extend(['--chunk-chars', '450', '--join-silence-ms', '350'])
        elif tts_engine == 'gemini':
            cache_dir = Path('/data/gemini_chunks') / str(job_id)
            cmd.extend(['--chunk-chars', '2200', '--pack-paragraphs',
                        '--chunk-cache-dir', str(cache_dir),
                        '--max-chunk-attempts', '1', '--request-timeout', '300'])

        log_file_path = Path(LOG_DIR) / f"{job_id}_convert.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_file_path, 'w', encoding='utf-8')

        app.logger.info(f"Running conversion: {' '.join(cmd)}")
        append_job_log(job_id, f"Running conversion (engine={tts_engine}, voice={effective_voice})")

        # Start process
        process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
        running_processes[job_id] = process
        running_containers[job_id] = container_name

        # Start progress monitor
        monitor_thread = threading.Thread(target=monitor_conversion, args=(job_id, container_name))
        monitor_thread.daemon = True
        monitor_thread.start()

        # Wait for completion
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        finally:
            log_file.close()
            running_processes.pop(job_id, None)
            running_containers.pop(job_id, None)

        # Combine output for error parsing
        combined_output = ""
        if log_file_path.exists():
            combined_output = log_file_path.read_text(encoding='utf-8', errors='replace')

        # Check results
        output_files = list(output_path.glob('*.mp3')) if output_path.exists() else []

        # Finalize transcript capture (best effort; does not affect job outcome)
        if TTS_PROXY_URL:
            try:
                requests.post(f"{TTS_PROXY_URL}/j/{job_id}/finalize", timeout=10)
            except Exception:
                pass

        if process.returncode == 0 and output_files:
            # --- Chapter completeness check with retry ---
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
            # Stage 2: EPUB3 with SMIL (Read-Along)
            try:
                from epub_generator import package_epub3_with_audio
                input_filename = job.get('input_filename', '')
                if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
                    epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
                    epub_out = output_path / f"{job['book_name']}.epub"
                    chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
                    if chunks_log.exists():
                        package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
            except Exception as e:
                app.logger.error(f"Stage 2 (EPUB3) failed: {e}")



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

            # Quality gate -> M4B -> Audiobookshelf sync -> final status, via the
            # SHARED helper every other render path uses.
            #
            # This block used to re-implement _gate_and_sync inline, so anything
            # added to the shared helper silently skipped local renders — the
            # most common path. The M4B hook landed there and never ran here, so
            # the file only appeared when the watchdog later re-finalised the
            # job, producing a second sync a minute after the book already
            # reported "completed" (caught by the E2E proof, 2026-07-25).
            _outcome = _gate_and_sync(job_id, output_path, job['book_name'], len(output_files))
            _review = _outcome == 'held'
            synced = _outcome == 'completed'

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

            # Status/file_count/completed_at are set by _gate_and_sync above.
            app.logger.info(f"Job {job_id} completed with {len(output_files)} files")
            append_job_log(job_id, f"Completed with {len(output_files)} files")

            # Record conversion metrics for ETA learning
            job = get_job(job_id)
            if job:
                # partial-range jobs pollute chars/sec (char_count covers the
                # whole book) — only learn from full-book conversions
                full = (not job.get('start_chapter') or job['start_chapter'] == 1) and                        (not job.get('end_chapter') or job.get('end_chapter') == job.get('total_chapters'))
                if full:
                    record_conversion_metrics(job)

            # Send Telegram notification if requested (not for held-for-review books)
            if job and not _review and job.get('notify_telegram'):
                send_telegram_notification(job, success=True)

            # Cleanup transcript directory since it's successfully converted and synced
            transcript_path = Path(f"/data/transcripts/{job_id}")
            if transcript_path.exists() and transcript_path.is_dir():
                import shutil
                try:
                    shutil.rmtree(transcript_path)
                    app.logger.info(f"Cleaned up transcript directory: {transcript_path}")
                    append_job_log(job_id, "Cleaned up transcript chunks")
                except Exception as e:
                    app.logger.error(f"Failed to clean up transcript directory: {e}")
        else:
            error_msg = combined_output if combined_output.strip() else 'No output files created'
            app.logger.error(f"Job {job_id} failed: {error_msg[:500]}...")
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
    resp = make_response(render_template('index.html', voices=voices_for_client(), engines=TTS_ENGINES))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp



_ENGINE_HEALTH_CACHE = {'ts': 0, 'data': {}}

def check_engines_health(max_age=20):
    """Probe each engine's availability (cached ~20s). Used to lock the UI
    and to refuse queueing jobs against a dead engine."""
    import time as _t
    now = _t.time()
    if now - _ENGINE_HEALTH_CACHE['ts'] < max_age and _ENGINE_HEALTH_CACHE['data']:
        return _ENGINE_HEALTH_CACHE['data']
    probes = {
        'kokoro': f"{KOKORO_URL.rstrip('/')}/audio/voices",
        'chatterbox': f"{CHATTERBOX_URL.rstrip('/')}/audio/voices",
        'chatterbox_nano': f"{CHATTERBOX_NANO_URL.rstrip('/')}/audio/voices",
        'tada': f"{TADA_URL.rstrip('/')}/audio/voices",
        'vibevoice': f"{VIBEVOICE_URL.rstrip('/')}/audio/voices",
        'qwen3': f"{QWEN3_URL.rstrip('/')}/audio/voices",
        'pocket': f"{POCKET_URL.rstrip('/')}/audio/voices",
        'kitten': f"{KITTEN_URL.rstrip('/')}/audio/voices",
        'gemini': f"{GEMINI_TTS_URL.rstrip('/')}/audio/voices",
    }
    out = {}
    for eng, url in probes.items():
        try:
            r = requests.get(url, timeout=3)
            out[eng] = r.status_code == 200
        except Exception:
            out[eng] = False
    # proxy-backed engines: up if the proxy answers at all
    proxy = os.environ.get('TTS_PROXY_URL', '') or 'http://tts-proxy:8882'
    try:
        requests.get(f"{proxy.rstrip('/')}/healthz", timeout=3)
        proxy_up = True
    except Exception:
        proxy_up = False
    out['edge'] = proxy_up
    out['polly'] = proxy_up and bool(get_setting('AWS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID'))
    out['inworld'] = proxy_up and bool(get_setting('INWORLD_API_KEY') or os.environ.get('INWORLD_API_KEY'))
    out['deepgram'] = proxy_up and bool(get_setting('DEEPGRAM_API_KEY') or os.environ.get('DEEPGRAM_API_KEY'))
    _ENGINE_HEALTH_CACHE['ts'] = now
    _ENGINE_HEALTH_CACHE['data'] = out
    return out


# Engines that need a credential before they can ever synthesise. This is a
# DIFFERENT failure from "offline": an offline engine is a container you can
# start, whereas these cannot work at all until a key is supplied — so the UI
# must not offer their voices as if selecting one might work (#24).
ENGINE_CREDENTIALS = {
    'inworld': ('INWORLD_API_KEY', 'Needs an Inworld API key (Settings → API keys)'),
    'polly': ('AWS_ACCESS_KEY_ID', 'Needs AWS credentials (Settings → API keys)'),
    'gemini': ('GEMINI_API_KEY', 'Needs a key from a dedicated unbilled Google AI Studio Free Tier project'),
    'deepgram': ('DEEPGRAM_API_KEY', 'Needs a Deepgram API key (Settings → API keys)'),
}


def engines_unconfigured():
    """Return {engine: human reason} for engines missing required credentials.

    Kept separate from check_engines_health() on purpose: health answers "is it
    reachable right now", this answers "could it ever work". The UI needs both,
    because the honest message differs — "start the container" vs "add a key".
    """
    missing = {}
    for engine, (setting_key, reason) in ENGINE_CREDENTIALS.items():
        if not (get_setting(setting_key) or os.environ.get(setting_key)):
            missing[engine] = reason
    return missing


@app.route('/api/engines/unconfigured')
def api_engines_unconfigured():
    """Engines that cannot work until credentials are added, with the reason."""
    return jsonify(engines_unconfigured())


# Uploaded reference voices live here; the chatterbox containers bind-mount it
# at /app/voices/custom, so a new WAV is usable without rebuilding the image.
CUSTOM_VOICES_DIR = Path(os.environ.get('CUSTOM_VOICES_DIR', '/data/voices'))

# Generated epubs for URL-ingested articles. Writable, unlike LIBRARY_DIR
# (read-only, and an rsync mirror), and kept out of the ebook library so a
# narrated article never looks like a book you own (#36).
ARTICLES_DIR = Path(os.environ.get('ARTICLES_DIR', '/data/articles'))

# Chatterbox clones from a short reference. Too short and it has nothing to
# work from; too long wastes conditioning and slows every chunk. These bounds
# are advisory — the upload warns rather than refuses, because the only real
# arbiter is how the preview sounds.
REF_MIN_SECONDS = 8
REF_MAX_SECONDS = 45


def _article_default_voice() -> str:
    """Return the configured system narrator, falling back to the settled default."""
    voice = get_setting('default_voice', DEFAULT_VOICE)
    return voice if voice in all_voices() else DEFAULT_VOICE


def _queue_article(meta: dict, options: dict | None = None) -> tuple[dict, int]:
    """Build an article EPUB and enqueue it through the ordinary job path.

    Every capture surface calls this function. In particular, Telegram must
    not insert a partial row and inherit SQLite's legacy Kokoro default while
    the web UI correctly derives Chatterbox Nano from Beatrice.
    """
    options = options or {}
    safe = sanitize_filename(meta['title'])[:80] or 'article'
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    epub_path = ARTICLES_DIR / uuid.uuid4().hex[:8] / f'{safe}.epub'
    from article import article_to_epub
    article_to_epub(meta, epub_path)

    voice = options.get('voice') or _article_default_voice()
    if voice not in all_voices():
        voice = _article_default_voice()
    forwarded = {
        'path': str(epub_path),
        'voice': voice,
        'tts_speed': options.get('tts_speed', DEFAULT_TTS_SPEED),
        # Automatic capture is deliberately local-only. A pasted or messaged
        # article must never select free Kaggle or paid Vast behind the user's
        # back merely because another job used it previously.
        'render_target': 'local',
        'output_format': 'mp3',
        'notify_telegram': bool(options.get('notify_telegram')),
        'source_kind': 'article',
        'source_url': meta.get('url', ''),
        'source_site': meta.get('site', ''),
        'source_date': meta.get('date', ''),
    }
    with app.test_request_context('/api/library/convert', method='POST', json=forwarded):
        response = convert_from_library()
    body = response[0].get_json() if isinstance(response, tuple) else response.get_json()
    status = response[1] if isinstance(response, tuple) else 200
    if status == 200:
        body['article'] = {key: meta[key] for key in (
            'title', 'author', 'site', 'word_count', 'estimated_minutes')}
        body['destination'] = 'podcast'
        body['podcast_folder'] = _podcast_folder_name(meta.get('site', ''))
        # convert_from_library() has copied the generated EPUB into UPLOAD_DIR.
        # The capture copy is staging, not a second archive; retaining it leaked
        # one otherwise-unreachable directory per pasted article.
        try:
            epub_path.unlink(missing_ok=True)
            epub_path.parent.rmdir()
        except OSError:
            pass
    return body, status


def _probe_wav(path: Path) -> dict:
    """Return {seconds, rate, channels} for a WAV, or {} if unreadable."""
    try:
        import wave
        with wave.open(str(path), 'rb') as w:
            frames, rate = w.getnframes(), w.getframerate()
            return {'seconds': round(frames / float(rate), 1) if rate else 0,
                    'rate': rate, 'channels': w.getnchannels()}
    except Exception:
        return {}


@app.route('/api/url/preview', methods=['POST'])
def api_url_preview():
    """Extract a web article and show what WOULD be narrated, without rendering.

    A preview step rather than straight-to-render because extraction quality is
    the failure mode users actually hit — paywalls, JS-built pages, hostile
    markup. Twenty minutes of CPU spent narrating a cookie banner helps nobody,
    and this is the same "never blind trust" principle the rest of the pipeline
    follows (#36).
    """
    from article import fetch_article, ExtractionError
    url = (request.json or {}).get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        meta = fetch_article(url)
    except ExtractionError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected failure reading that page: {e}'}), 500
    # Send back a readable excerpt, not the whole article.
    excerpt = meta['text'][:1200]
    return jsonify({**{k: v for k, v in meta.items() if k != 'text'},
                    'excerpt': excerpt,
                    'truncated': len(meta['text']) > len(excerpt)})


@app.route('/api/url/convert', methods=['POST'])
@app.route('/api/articles/narrate_url', methods=['POST'])
def api_url_convert():
    """Render a web article as audio, via the ordinary book pipeline.

    The article is written to a real epub first. That is the whole trick: every
    downstream stage already understands an epub, so an article is a one-chapter
    book and needs no special case in chaptering, preprocessing, tagging, M4B
    or the Audiobookshelf sync.
    """
    from article import fetch_article, ExtractionError
    data = request.json or {}
    url = (data.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        meta = fetch_article(url)
    except ExtractionError as e:
        return jsonify({'error': str(e)}), 400

    try:
        body, status = _queue_article(meta, data)
    except Exception as e:
        return jsonify({'error': f'Could not build an epub from that article: {e}'}), 500
    return jsonify(body), status


def all_voices() -> dict:
    """VOICES plus any uploaded reference voices, as one dict.

    Uploaded voices are offered on BOTH chatterbox engines because the two
    containers share the same image and the same voices directory — one WAV
    gives you a Turbo narrator and a Nano one. Nano is the default, so it is
    listed first.
    """
    merged = dict(VOICES)
    if not CUSTOM_VOICES_DIR.exists():
        return merged
    for p in sorted(CUSTOM_VOICES_DIR.glob('*.wav')):
        pretty = p.stem.replace('_', ' ').title()
        # setdefault, NOT assignment: a voice curated in VOICES keeps its own
        # name, accent and gender. The accent narrators live in this directory
        # because that is how a WAV reaches the chatterbox container, and they
        # were being relabelled "Custom / your clone" purely as a side effect
        # of where the file sits.
        merged.setdefault(f'{p.stem}_nano', {
            'name': f'{pretty} (your clone, fast)', 'accent': 'Custom',
            'gender': 'Custom', 'engine': 'chatterbox_nano'})
        merged.setdefault(p.stem, {
            'name': f'{pretty} (your clone, Turbo)', 'accent': 'Custom',
            'gender': 'Custom', 'engine': 'chatterbox'})
    return merged


def _preview_is_cached(voice_id: str) -> bool:
    """A voice is audition-ready only when a non-trivial persisted MP3 exists."""
    preview = PREVIEWS_DIR / f"{voice_id}.mp3"
    try:
        return preview.is_file() and preview.stat().st_size > 5000
    except OSError:
        return False


def voices_for_client() -> dict:
    """Voice catalogue annotated with the only readiness claim the UI needs.

    The browser must never turn a Play click into minutes of synthesis. Cold
    generation belongs to the throttled background warmer; the audition UI
    offers only previews already present in the persistent cache.
    """
    return {
        voice_id: {**info, 'preview_cached': _preview_is_cached(voice_id)}
        for voice_id, info in all_voices().items()
    }


@app.route('/api/bookfinder/search', methods=['GET'])
def bookfinder_search():
    """Search OpenBooks for available books to grab."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'results': []})
    try:
        from openbooks_client import search_openbooks_async
        import asyncio
        results = asyncio.run(search_openbooks_async(query, timeout=30.0))
        resp = jsonify({'results': results})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        app.logger.error(f"BookFinder search error: {e}")
        resp = jsonify({'error': str(e), 'results': []})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 500


@app.route('/api/bookfinder/grab', methods=['POST', 'OPTIONS'])
def bookfinder_grab():
    """Download book from OpenBooks, transfer to library, and index."""
    if request.method == 'OPTIONS':
        resp = make_response()
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp
    data = request.get_json(silent=True) or {}
    command = data.get('command', '').strip()
    title = data.get('title', '').strip()
    author = data.get('author', '').strip()
    if not command:
        resp = jsonify({'error': 'No download command provided'})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 400
    try:
        from openbooks_client import grab_and_import_book
        res = grab_and_import_book(command, title=title, author=author)
        resp = jsonify(res)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        app.logger.error(f"BookFinder grab error: {e}")
        resp = jsonify({'error': str(e)})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 500


@app.route('/embed/bookfinder', methods=['GET'])
def bookfinder_embed():
    """Render standalone BookFinder widget for embedding into Calibre-Web or external dashboards."""
    resp = make_response(render_template('bookfinder_embed.html'))
    resp.headers.pop('X-Frame-Options', None)
    resp.headers['Content-Security-Policy'] = "frame-ancestors *"
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/voices/custom', methods=['GET'])
def list_custom_voices():
    """Reference voices uploaded through the UI."""
    out = []
    if CUSTOM_VOICES_DIR.exists():
        for p in sorted(CUSTOM_VOICES_DIR.glob('*.wav')):
            out.append({'id': p.stem, 'bytes': p.stat().st_size, **_probe_wav(p)})
    return jsonify({'voices': out, 'dir': str(CUSTOM_VOICES_DIR)})


@app.route('/api/voices/custom', methods=['POST'])
def upload_custom_voice():
    """Accept a reference WAV and make it available as a cloned narrator.

    Deliberately strict about the container format: chatterbox reads the file
    with `wave`, so an mp3 renamed to .wav fails at synthesis time with an
    error that points nowhere near the upload. Better to refuse it here.
    """
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': 'No file uploaded'}), 400

    raw_name = request.form.get('voice_id') or Path(f.filename).stem
    # Voice ids become filenames and URL fragments; keep them boring.
    voice_id = re.sub(r'[^a-z0-9_]+', '_', raw_name.strip().lower()).strip('_')
    if not voice_id:
        return jsonify({'error': 'Could not derive a usable voice id from that name'}), 400

    CUSTOM_VOICES_DIR.mkdir(parents=True, exist_ok=True)
    dest = CUSTOM_VOICES_DIR / f'{voice_id}.wav'

    tmp = dest.with_suffix('.wav.part')
    try:
        f.save(str(tmp))
        info = _probe_wav(tmp)
        if not info:
            tmp.unlink(missing_ok=True)
            return jsonify({'error': 'That file is not a readable WAV. Export as '
                                     'WAV (PCM) — an MP3 renamed to .wav will not '
                                     'work.'}), 400

        warnings = []
        if info['seconds'] < REF_MIN_SECONDS:
            warnings.append(f"only {info['seconds']}s of audio — {REF_MIN_SECONDS}s or "
                            f"more clones far more reliably")
        if info['seconds'] > REF_MAX_SECONDS:
            warnings.append(f"{info['seconds']}s is longer than needed; "
                            f"{REF_MAX_SECONDS}s is plenty and shorter is faster")
        if info.get('channels', 1) > 1:
            warnings.append('stereo — mono is the safer choice for a voice reference')
        if info.get('rate', 0) < 16000:
            warnings.append(f"{info['rate']} Hz is low; 22 kHz or above is better")

        os.replace(tmp, dest)          # atomic, same reasoning as the M4B (#38)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return jsonify({'error': f'Could not save the reference: {e}'}), 500

    app.logger.info('custom voice uploaded: %s (%ss, %sHz)',
                    voice_id, info.get('seconds'), info.get('rate'))
    # Prepare every healthy local variant immediately, but outside the request
    # and through the same load-aware cache worker used at startup. The voice
    # is not offered in the audition UI until its persisted MP3 exists.
    threading.Thread(
        target=_cache_voice_batch,
        args=([f'{voice_id}_nano', voice_id],),
        daemon=True,
    ).start()
    return jsonify({'status': 'ok', 'voice_id': voice_id, **info,
                    'warnings': warnings,
                    'note': 'Healthy local variants are being cached. They appear '
                            'in Voices only when they are ready to play instantly.'})


@app.route('/api/voices/custom/<voice_id>', methods=['DELETE'])
def delete_custom_voice(voice_id: str):
    safe = re.sub(r'[^a-z0-9_]+', '_', voice_id.lower())
    p = CUSTOM_VOICES_DIR / f'{safe}.wav'
    if not p.exists():
        return jsonify({'error': 'No such custom voice'}), 404
    try:
        p.unlink()
        return jsonify({'status': 'deleted', 'voice_id': safe})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Ordered preference for conversion failover. Piper is deliberately excluded:
# the controlled old/current-runtime + encoding A/B failed pronunciation and
# sound quality. A failed job is preferable to silently producing a bad book.
_ENGINE_FALLBACK_ORDER = ['tada', 'chatterbox', 'kokoro']


def _voice_for_engine(voice, target_engine):
    """Map a voice to the closest voice on target_engine. Human-cloned voices
    exist on BOTH tada and chatterbox under parallel ids (uk_male_minter and
    uk_male_minter_tada), so a tada<->chatterbox failover keeps the same
    'character'. Otherwise fall back to that engine's first registered voice."""
    base = voice
    for suffix in ('_vibevoice', '_qwen3', '_tada', '_nano', '_cosyvoice'):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break
    suffixes = {'vibevoice': '_vibevoice', 'qwen3': '_qwen3',
                'tada': '_tada', 'chatterbox_nano': '_nano',
                'cosyvoice': '_cosyvoice'}
    cand = base + suffixes.get(target_engine, '')
    if cand in VOICES and VOICES[cand].get('engine') == target_engine:
        return cand
    for v, meta in VOICES.items():
        if meta.get('engine') == target_engine:
            return v
    return voice


def pick_engine_with_fallback(preferred_engine, preferred_voice, allow_fallback=True):
    """Return (engine, voice, note). Preferred engine unchanged if healthy.
    Else, if allow_fallback, the next healthy engine in _ENGINE_FALLBACK_ORDER
    with a voice remapped to it; `note` records the substitution for the job
    log. If nothing healthy or fallback disallowed, returns preferred unchanged
    and the caller decides whether to reject."""
    health = check_engines_health()
    if health.get(preferred_engine):
        return preferred_engine, preferred_voice, None
    if not allow_fallback:
        return preferred_engine, preferred_voice, None
    for eng in _ENGINE_FALLBACK_ORDER:
        if eng != preferred_engine and health.get(eng):
            v = _voice_for_engine(preferred_voice, eng)
            return eng, v, f"{preferred_engine} offline — fell back to {eng} (voice {v})"
    return preferred_engine, preferred_voice, None


@app.route('/api/engines/health')
def engines_health():
    return jsonify(check_engines_health())


@app.route('/api/voices')
def list_voices():
    """Return available voices grouped by engine."""
    voices = voices_for_client()
    configured = {
        voice_id: info for voice_id, info in voices.items()
        if info.get('engine') not in engines_unconfigured()
    }
    return jsonify({
        'voices': voices,
        'engines': TTS_ENGINES,
        'cache': {
            'configured_total': len(configured),
            'configured_ready': sum(
                1 for info in configured.values() if info['preview_cached']
            ),
        },
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update system settings/API keys."""
    secret_keys = [
        'AWS_SECRET_ACCESS_KEY', 'AWS_ACCESS_KEY_ID',
        'LLM_API_KEY', 'TELEGRAM_BOT_TOKEN',
        'EVOLUTION_API_KEY', 'ABS_API_TOKEN', 'VASTAI_API_KEY',
        'INWORLD_API_KEY', 'DEEPGRAM_API_KEY', 'KAGGLE_API_TOKEN'
    ]
    config_keys = [
        'ABS_API_URL', 'TELEGRAM_CHAT_ID', 'AWS_REGION',
        'AUTOSCALE_COST_CAP',
        'LLM_API_BASE_URL', 'LLM_MODEL_NAME',
        # Free Kaggle GPU render — username pairs with KAGGLE_API_TOKEN above.
        'KAGGLE_USERNAME',
    ]

    if request.method == 'POST':
        try:
            data = request.json
            for key, value in data.items():
                if value is not None:
                    v = str(value).strip()
                    if v:
                        # Prevent saving masked strings from the frontend over real keys
                        if key in secret_keys and '...' in v:
                            continue
                        set_setting(key, v)
                        if key == 'VASTAI_API_KEY':
                            key_file = Path('/root/.config/vastai/vast_api_key')
                            key_file.parent.mkdir(parents=True, exist_ok=True)
                            key_file.write_text(v)
                    else:
                        delete_setting(key)
                        if key == 'VASTAI_API_KEY':
                            key_file = Path('/root/.config/vastai/vast_api_key')
                            if key_file.exists():
                                key_file.unlink()
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    settings = {}
    for key in (secret_keys + config_keys):
        val = get_setting(key)
        if not val and key in os.environ:
            val = os.environ[key]

        if val:
            if key in secret_keys:
                if len(val) > 10:
                    settings[key] = f"{val[:4]}...{val[-4:]}"
                else:
                    settings[key] = "********...********"
            else:
                settings[key] = val
        else:
            settings[key] = ""

    return jsonify(settings)

@app.route('/api/settings/pronunciations', methods=['GET', 'POST'])
def pronunciations_settings():
    """Read/write global pronunciation rules (regex `search==replace`, one per line).

    Applied to every job via the converter's --search_and_replace_file.
    """
    conf_path = UPLOAD_DIR / 'global_pronunciations.conf'
    if request.method == 'GET':
        try:
            text = conf_path.read_text(encoding='utf-8') if conf_path.exists() else ''
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        return jsonify({'rules': text})

    data = request.get_json(silent=True) or {}
    rules = data.get('rules', '')
    bad = [ln for ln in rules.splitlines()
           if ln.strip() and not ln.strip().startswith('#') and '==' not in ln]
    if bad:
        return jsonify({'error': f"Each rule needs search==replace. Bad lines: {bad[:3]}"}), 400
    try:
        conf_path.write_text(rules, encoding='utf-8')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'saved',
                    'lines': len([ln for ln in rules.splitlines() if ln.strip()])})


@app.route('/api/kaggle/quota')
def kaggle_quota():
    """Free Kaggle GPU-hours used/left this week, for the UI to signpost."""
    try:
        import kaggle_render as KR
        used = KR.gpu_hours_used()
        configured = bool(get_setting('KAGGLE_API_TOKEN')) or KR.kaggle_ready()
        return jsonify({'weekly': KR.WEEKLY_GPU_HOURS, 'used': used,
                        'left': round(max(0.0, KR.WEEKLY_GPU_HOURS - used), 1),
                        'configured': configured})
    except Exception as e:
        return jsonify({'weekly': 30, 'used': 0, 'left': 30, 'configured': False, 'error': str(e)})


@app.route('/api/settings/test_kaggle', methods=['POST'])
def test_kaggle_connection():
    """Verify Kaggle credentials by making a real authenticated API call."""
    try:
        data = request.json or {}
        token = data.get('token') or get_setting('KAGGLE_API_TOKEN') or os.environ.get('KAGGLE_API_TOKEN')
        user = data.get('username') or get_setting('KAGGLE_USERNAME') or os.environ.get('KAGGLE_USERNAME')
        if not token or not user:
            return jsonify({'error': 'Enter both your Kaggle username and API token first.'}), 400
        if '...' in token:  # masked value from the UI; use the stored one
            token = get_setting('KAGGLE_API_TOKEN') or os.environ.get('KAGGLE_API_TOKEN')
        env = dict(os.environ, KAGGLE_API_TOKEN=token, KAGGLE_KEY=token, KAGGLE_USERNAME=user)
        r = subprocess.run(['python', '-m', 'kaggle', 'datasets', 'list', '-m'],
                           capture_output=True, text=True, timeout=30, env=env)
        if r.returncode == 0:
            return jsonify({'status': 'success', 'message': f'Connected to Kaggle as {user}!'})
        msg = (r.stderr or r.stdout or 'unknown error').strip().splitlines()[-1][:160]
        return jsonify({'error': f'Kaggle auth failed: {msg}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/prepare_gemini_preview', methods=['POST'])
def prepare_gemini_preview():
    """Explicitly cache one or more missing Gemini catalogue previews.

    The default remains one request. A caller may explicitly set ``limit`` up
    to ten, matching the separately guarded free-tier daily ceiling. Existing
    files are cache hits and failures stop the loop immediately: no retry.
    """
    data = request.get_json(silent=True) or {}
    try:
        limit = int(data.get('limit', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'limit must be an integer from 1 to 10'}), 400
    if not 1 <= limit <= 10:
        return jsonify({'error': 'limit must be from 1 to 10'}), 400
    gemini_ids = [voice_id for voice_id, info in all_voices().items()
                  if info.get('engine') == 'gemini']
    requested = str(data.get('voice_id') or '').strip()
    if requested:
        if requested not in gemini_ids:
            return jsonify({'error': f'Unknown Gemini voice: {requested}'}), 400
        candidates = [requested]
    else:
        candidates = gemini_ids
    missing = [voice_id for voice_id in candidates if not _preview_is_cached(voice_id)]
    if not missing:
        ready = sum(_preview_is_cached(voice_id) for voice_id in gemini_ids)
        return jsonify({'status': 'cached', 'message': 'Requested Gemini previews are ready.',
                        'ready': ready, 'total': len(gemini_ids), 'generated': []})
    if not os.environ.get('GEMINI_API_KEY', '').strip():
        return jsonify({'error': 'GEMINI_API_KEY is not configured. Add the key from an '
                        'unbilled AI Studio Free Tier project to .env and redeploy.'}), 400
    health = check_engines_health(max_age=0)
    if health.get('gemini') is not True:
        return jsonify({'error': 'The Gemini free-only adapter is not running. Enable '
                        'ENABLE_GEMINI_PROFILE=1 and redeploy.'}), 409
    generated = []
    for voice_id in missing[:limit]:
        preview = get_voice_preview(voice_id)
        if not preview or not _preview_is_cached(voice_id):
            ready = sum(_preview_is_cached(item) for item in gemini_ids)
            return jsonify({'error': f'{voice_id} did not produce a valid preview. No retry '
                            'was made; check the adapter log for the quota/API response.',
                            'generated': generated, 'ready': ready,
                            'total': len(gemini_ids)}), 502
        generated.append(voice_id)
    ready = sum(_preview_is_cached(voice_id) for voice_id in gemini_ids)
    return jsonify({'status': 'generated', 'message': f'Cached {len(generated)} Gemini preview(s).',
                    'generated': generated, 'ready': ready, 'total': len(gemini_ids),
                    'urls': [f'/api/preview/{voice_id}' for voice_id in generated]})


@app.route('/api/settings/test_abs', methods=['POST'])
def test_abs_connection():
    """Test connection to Audiobookshelf."""
    try:
        data = request.json or {}
        url = data.get('url') or get_setting('ABS_API_URL') or os.environ.get('ABS_API_URL')
        token = data.get('token') or get_setting('ABS_API_TOKEN') or os.environ.get('ABS_API_TOKEN')

        if not url or not token:
            return jsonify({'error': 'Missing URL or Token'}), 400

        resp = requests.get(f"{url.rstrip('/')}/api/libraries",
                            headers={'Authorization': f'Bearer {token}'},
                            timeout=10)
        if resp.status_code == 200:
            libs = resp.json().get('libraries', [])
            names = ', '.join(li.get('name', '?') for li in libs) or 'none'
            return jsonify({'status': 'success',
                            'message': f'Connected to ABS. Libraries: {names}'})
        if resp.status_code in (401, 403):
            # Be specific: a rejected token is invisible elsewhere, because the
            # file sync uses SSH and keeps working regardless (#35).
            return jsonify({'error':
                            f'ABS rejected the token (HTTP {resp.status_code}). '
                            f'Generate a new one in Audiobookshelf under '
                            f'Settings → Users → API token, then save it here. '
                            f'Note: book files will still sync without it — the '
                            f'copy is over SSH — but covers, rescans and library '
                            f'cleanup will not work.'}), 400
        return jsonify({'error': f'ABS returned status {resp.status_code}: {resp.text[:100]}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/test_polly', methods=['POST'])
def test_polly_connection():
    """Test connection to Amazon Polly."""
    try:
        data = request.json or {}
        access_key = data.get('access_key') or get_setting('AWS_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = data.get('secret_key') or get_setting('AWS_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
        region = data.get('region') or get_setting('AWS_REGION') or os.environ.get('AWS_REGION', 'us-east-1')

        if not access_key or not secret_key:
            return jsonify({'error': 'Missing AWS Keys'}), 400

        import boto3
        client = boto3.client('polly',
                              aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key,
                              region_name=region)
        # describe voices to test credentials
        resp = client.describe_voices(LanguageCode='en-US')
        if 'Voices' in resp:
            return jsonify({'status': 'success', 'message': 'Connected to AWS Polly!'})
        return jsonify({'error': 'Invalid response from AWS Polly'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/test_inworld', methods=['POST'])
def test_inworld_connection():
    """Test Inworld TTS API key by synthesising a short phrase."""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or get_setting('INWORLD_API_KEY') or os.environ.get('INWORLD_API_KEY', '')
        if not api_key:
            return jsonify({'error': 'No Inworld API key provided'}), 400
        import base64
        resp = requests.post(
            'https://api.inworld.ai/tts/v1/voice',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Basic {api_key}'
            },
            json={
                'text': 'Hello.',
                'voiceId': 'Blake',
                'modelId': 'inworld-tts-1.5-mini',
                'audioConfig': {'audioEncoding': 'MP3'}
            },
            timeout=15
        )
        if resp.status_code == 200:
            return jsonify({'status': 'success', 'message': 'Inworld TTS connected!'})
        return jsonify({'error': f'Inworld returned {resp.status_code}: {resp.text[:100]}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


_DEEPGRAM_BALANCE_CACHE = {}


def _fetch_deepgram_balance(api_key: str, force: bool = False):
    """Fetch Deepgram account email and credit balance with a 30s rate-limit cache."""
    if not api_key:
        return None
    now = time.time()
    cached = _DEEPGRAM_BALANCE_CACHE.get(api_key)
    if not force and cached and (now - cached.get('time', 0) < 30):
        return cached.get('data')
    try:
        t_resp = requests.get(
            'https://api.deepgram.com/v1/auth/token',
            headers={'Authorization': f'Token {api_key}', 'User-Agent': 'EpubToAudiobook/1.0'},
            timeout=10
        )
        email = ''
        if t_resp.status_code == 200:
            email = t_resp.json().get('email', '')

        p_resp = requests.get(
            'https://api.deepgram.com/v1/projects',
            headers={'Authorization': f'Token {api_key}', 'User-Agent': 'EpubToAudiobook/1.0'},
            timeout=10
        )
        if p_resp.status_code != 200:
            res = {'email': email, 'balance': None, 'formatted': None}
            _DEEPGRAM_BALANCE_CACHE[api_key] = {'time': now, 'data': res}
            return res

        projects = p_resp.json().get('projects', [])
        total_balance = 0.0
        currency = 'USD'
        found_balance = False
        for p in projects:
            pid = p.get('project_id')
            if not pid:
                continue
            b_resp = requests.get(
                f'https://api.deepgram.com/v1/projects/{pid}/balances',
                headers={'Authorization': f'Token {api_key}', 'User-Agent': 'EpubToAudiobook/1.0'},
                timeout=10
            )
            if b_resp.status_code == 200:
                b_data = b_resp.json().get('balances', [])
                for b in b_data:
                    amt = b.get('amount')
                    if amt is not None:
                        total_balance += float(amt)
                        currency = b.get('units', 'USD').upper()
                        found_balance = True

        if found_balance:
            res = {
                'email': email,
                'balance': round(total_balance, 2),
                'formatted': f"${total_balance:.2f} {currency}",
                'currency': currency
            }
            _DEEPGRAM_BALANCE_CACHE[api_key] = {'time': now, 'data': res}
            return res
        res = {'email': email, 'balance': None, 'formatted': None}
        _DEEPGRAM_BALANCE_CACHE[api_key] = {'time': now, 'data': res}
        return res
    except Exception as e:
        app.logger.warning(f"Error fetching Deepgram balance: {e}")
        return None


@app.route('/api/settings/test_deepgram', methods=['POST'])
def test_deepgram_connection():
    """Test Deepgram API key and query credit balance."""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or get_setting('DEEPGRAM_API_KEY') or os.environ.get('DEEPGRAM_API_KEY', '')
        if not api_key:
            return jsonify({'error': 'No Deepgram API key provided'}), 400
        bal_info = _fetch_deepgram_balance(api_key)
        if bal_info and bal_info.get('email'):
            email = bal_info['email']
            fmt = bal_info.get('formatted')
            if fmt:
                msg = f"Connected to Deepgram! ({email}) — Credit Balance: {fmt}"
            else:
                msg = f"Connected to Deepgram! ({email})"
            return jsonify({
                'status': 'success',
                'message': msg,
                'email': email,
                'balance': bal_info.get('balance'),
                'formatted': fmt
            })
        return jsonify({'error': 'Failed to authenticate with Deepgram API'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/deepgram_balance', methods=['GET'])
def get_deepgram_balance():
    """Fetch current Deepgram balance for configured API key."""
    api_key = get_setting('DEEPGRAM_API_KEY') or os.environ.get('DEEPGRAM_API_KEY', '')
    if not api_key:
        return jsonify({'configured': False, 'balance': None, 'formatted': None})
    bal_info = _fetch_deepgram_balance(api_key)
    if bal_info:
        return jsonify({'configured': True, **bal_info})
    return jsonify({'configured': True, 'balance': None, 'formatted': None})


@app.route('/api/cloud_status', methods=['GET'])
def get_cloud_status():
    """Return live balances and limits for cloud/API-keyed engines and renderers."""
    # Deepgram
    dg_key = get_setting('DEEPGRAM_API_KEY') or os.environ.get('DEEPGRAM_API_KEY', '')
    dg_info = _fetch_deepgram_balance(dg_key) if dg_key else None

    # Gemini
    gemini_key = os.environ.get('GEMINI_API_KEY') or get_setting('GEMINI_API_KEY', '')
    gemini_enabled = bool(os.environ.get('ENABLE_GEMINI_PROFILE') == '1' or gemini_key)
    gemini_confirmed = bool(os.environ.get('GEMINI_FREE_PROJECT_CONFIRMED') == '1' or gemini_key)

    # Kaggle
    kaggle_user = get_setting('KAGGLE_USERNAME') or os.environ.get('KAGGLE_USERNAME', '')

    # Vast
    vast_enabled = bool(os.environ.get('GPU_RENDER_ENABLED') == '1')

    return jsonify({
        'deepgram': {
            'configured': bool(dg_key),
            'balance': dg_info.get('balance') if dg_info else None,
            'formatted': dg_info.get('formatted') if dg_info else None,
            'email': dg_info.get('email') if dg_info else None
        },
        'gemini': {
            'configured': bool(gemini_key),
            'enabled': gemini_enabled,
            'confirmed': gemini_confirmed,
            'tier': 'Free Tier (10 RPD Cap)' if bool(gemini_key) else 'Unconfigured'
        },
        'kaggle': {
            'configured': bool(kaggle_user),
            'username': kaggle_user
        },
        'vast': {
            'enabled': vast_enabled
        }
    })


@app.route('/api/settings/test_llm', methods=['POST'])
def test_llm_connection():
    """Test generic LLM API connection (Z AI, xAI, Groq, OpenAI)."""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or get_setting('LLM_API_KEY') or os.environ.get('LLM_API_KEY')
        base_url = data.get('base_url') or get_setting('LLM_API_BASE_URL') or os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1')
        model = data.get('model') or get_setting('LLM_MODEL_NAME') or os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

        if not api_key: return jsonify({'error': 'Missing API Key'}), 400
        if not base_url: return jsonify({'error': 'Missing Base URL'}), 400

        # Test by requesting models list
        resp = requests.get(f"{base_url.rstrip('/')}/models",
                            headers={'Authorization': f'Bearer {api_key}'},
                            timeout=10)

        try:
            resp_json = resp.json()
        except Exception:
            resp_json = {}

        # Some APIs return 200 OK but embed the error inside the JSON
        if resp.status_code == 200 and resp_json.get('success') is not False and 'error' not in resp_json and 'msg' not in resp_json:
            models = resp_json.get('data', [])
            model_ids = [m.get('id') for m in models if isinstance(m, dict)]
            if model and model_ids and model not in model_ids:
                return jsonify({'status': 'warning', 'message': f'Connected, but model {model} not found in provider list.'})
            return jsonify({'status': 'success', 'message': 'LLM API is valid!'})

        error_msg = resp_json.get('error', {}).get('message') or resp_json.get('msg') or resp.text[:100]
        return jsonify({'error': f'Invalid API Key or URL (HTTP {resp.status_code}): {error_msg}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
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
        # Queue length is never authority to rent a paid GPU. Kept in the
        # response for compatibility with older frontends.
        'autoscale_enabled': False,
        'cost_cap': float(os.environ.get('AUTOSCALE_COST_CAP', '1.00')),
    })


def gpu_render_enabled() -> bool:
    """Environment-only safety gate for paid Vast.ai GPU use. Default OFF.

    Anything that could spin up a billed cloud GPU MUST check this first.
    It deliberately does not read the unauthenticated settings database: a LAN
    API caller must never be able to arm spending. Enabling requires deliberate
    host access plus a service restart for that specific manual session.
    """
    return os.environ.get('GPU_RENDER_ENABLED', '0').lower() in ('1', 'true', 'yes', 'on')


@app.route('/api/gpu/scale-up', methods=['POST'])
def gpu_scale_up():
    """Manually trigger GPU scale-up (gated: default local, never auto-enable)."""
    if not gpu_render_enabled():
        return jsonify({'error': 'Cloud GPU rendering is OFF (default). It rents a '
                        'paid Vast.ai instance. It can only be armed by a host '
                        'administrator for an explicitly approved manual session.'}), 403
    if not _gpu_manager:
        return jsonify({'error': 'GPU manager not available'}), 503
    if _gpu_manager.state == 'active':
        return jsonify({'status': 'already_active', **_gpu_manager.get_status()})
    if _gpu_manager.state == 'provisioning':
        return jsonify({'status': 'provisioning', **_gpu_manager.get_status()})

    # Run scale-up in background thread to avoid blocking the request
    import threading
    def _do_scale_up():
        _gpu_manager.scale_up(authorized=True)
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
        'kokoro_url': KOKORO_URL
    })



@app.route('/api/jobs/<job_id>/resume', methods=['POST'])
def resume_job(job_id):
    """Resume a failed job with intelligent recovery and optional Narrator switch."""
    data = request.get_json(silent=True) or {}
    new_voice = data.get('voice')

    job = get_job(job_id)
    if not job: return jsonify({'error': 'Job not found'}), 404

    output_path = OUTPUT_DIR / job.get('output_dirname', '')
    has_partial = any(output_path.glob('*.mp3')) if output_path.exists() else False

    with get_db() as conn:
        if new_voice and new_voice in all_voices():
            engine = all_voices()[new_voice].get('engine', 'kokoro')
            name = all_voices()[new_voice]['name']
            conn.execute("""
                UPDATE jobs 
                SET voice = ?, voice_name = ?, tts_engine = ?, 
                    status = ?, container_name = NULL, error = NULL 
                WHERE id = ?
            """, (new_voice, name, engine, 'recovering' if has_partial else 'queued', job_id))
        else:
            conn.execute("""
                UPDATE jobs 
                SET status = ?, container_name = NULL, error = NULL 
                WHERE id = ?
            """, ('recovering' if has_partial else 'queued', job_id))
        conn.commit()

    if has_partial:
        threading.Thread(target=_do_recovery, args=(job_id,), daemon=True).start()
    else:
        threading.Thread(target=maybe_start_next_queued_job, daemon=True).start()

    return jsonify({
        'status': 'success',
        'message': f'Job resumed using {new_voice if new_voice else "original voice"} (' + ('partial recovery' if has_partial else 'full retry') + ')'
    })

@app.route('/api/history')
def get_history():
    """Get completed book and article conversions, newest first."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT * FROM jobs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 100
        ''').fetchall()
        return jsonify([job_to_dict(row) for row in rows])


@app.route('/api/sample/<name>')
def audition_sample(name: str):
    """Serve a one-off audition clip — currently the 1997 A/B pair (#26), so the
    modern-engine number question is settled by ear rather than by argument.
    Allowlisted names only; never an arbitrary path."""
    # Browsers and chat clients treat a URL ending in .mp3 more reliably as
    # playable media. Keep the old extensionless URLs working too.
    if name.endswith('.mp3'):
        name = name[:-4]

    # #27: does chatterbox want pronunciation help at all? Three renders of one
    # sentence — raw, the current SHOUTY-CAPS seed style, and a natural
    # lowercase respelling. The filter that drops respellings for modern
    # engines was justified by "Bay-JING sounded wrong", which may have been
    # the FORMAT rather than the concept. Settled by ear, not argument.
    if name not in ('ab_1997_raw', 'ab_1997_spelled',
                    'ab27_raw', 'ab27_caps', 'ab27_natural',
                    'ab_tada_cpu', 'ab_tada_bf16',
                    'ab_daisy_before', 'ab_daisy_after',
                    'ab_alice_plain', 'ab_alice_aliss', 'ab_alice_alliss',
                    'ab_alice_nano_raw', 'ab_alice_nano_fixed',
                    'ab_pos_first', 'ab_pos_mid', 'ab_pos_other', 'ab_pos_second',
                    'vibe_blind_A', 'vibe_blind_B') \
       and not (name.startswith(('ac_', 'na_', 'tb_', 'cf_', 'eg_', 'xt_', 'me_', 'ov_', 'vctk_', 'cv3_', 'cpu_')) and re.fullmatch(r'[a-z0-9_]+', name)):
        return jsonify({'error': 'Unknown sample'}), 404
    p = PREVIEWS_DIR / f"{name}.mp3"
    if not p.exists():
        return jsonify({'error': 'Not generated yet'}), 404
    return send_file(p, mimetype='audio/mpeg', download_name=p.name,
                     conditional=True)


@app.route('/api/preview/<voice_id>')
def voice_preview(voice_id: str):
    """Stream an already-cached voice preview; a Play click never synthesises."""
    if voice_id not in all_voices():
        return jsonify({'error': 'Voice not found'}), 404

    preview_path = PREVIEWS_DIR / f"{voice_id}.mp3"
    if _preview_is_cached(voice_id):
        return send_file(preview_path, mimetype='audio/mpeg')

    return jsonify({
        'error': 'Preview is still being prepared by the background cache. '
                 'It is not offered in the Voices page until it is ready.'
    }), 425


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

    if voice not in all_voices():
        return jsonify({'error': 'Invalid voice selected'}), 400

    if voice2 and voice2 not in all_voices():
        return jsonify({'error': 'Invalid secondary voice selected'}), 400

    # Create job
    job_id = str(uuid.uuid4())[:8]
    book_name = Path(uploaded_file.filename).stem
    safe_name = sanitize_filename(book_name)

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

    # Validate chapter range against actual book content
    try:
        if not file_ext == '.pdf':
            toc = get_epub_toc(input_path)
            max_chapters = len(toc) if toc else 999
            if start_chapter and start_chapter > max_chapters:
                start_chapter = 1
            if end_chapter and end_chapter > max_chapters:
                end_chapter = max_chapters
    except: pass

    # Create output directory
    output_dirname = f"{safe_name}_{job_id}"
    output_dir = OUTPUT_DIR / output_dirname
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine TTS engine from voice
    tts_engine = all_voices()[voice].get('engine', 'kokoro')

    # Save job to database
    job = {
        'id': job_id,
        'book_name': book_name,
        'voice': voice,
        'voice_name': all_voices()[voice]['name'],
        'voice2': voice2,
        'voice2_name': all_voices().get(voice2, {}).get('name') if voice2 else None,
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
        'queued_count': queued_count,
        'max_concurrent_jobs': get_max_concurrent_jobs(),
    })


@app.route('/api/queue/concurrency', methods=['POST'])
def queue_concurrency():
    """Set maximum concurrent conversion jobs."""
    data = request.get_json(silent=True) or {}
    val = data.get('max_concurrent_jobs')
    try:
        n = max(1, min(4, int(val)))
        set_setting('max_concurrent_jobs', str(n))
        if not is_queue_paused():
            maybe_start_next_queued_job()
        return jsonify({'status': 'ok', 'max_concurrent_jobs': n})
    except Exception as e:
        return jsonify({'error': f'Invalid concurrency value: {e}'}), 400


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


@app.route('/api/jobs/<job_id>/promote', methods=['POST'])
def queue_promote(job_id: str):
    """Promote a queued job to rank 1 (top of queue)."""
    with get_db() as conn:
        conn.execute('UPDATE jobs SET queue_rank = 1 WHERE id = ?', (job_id,))
        rows = conn.execute("SELECT id FROM jobs WHERE status='queued' AND id <> ? ORDER BY COALESCE(queue_rank, 0), created_at", (job_id,)).fetchall()
        for rank, r in enumerate(rows, start=2):
            conn.execute('UPDATE jobs SET queue_rank = ? WHERE id = ?', (rank, r['id']))
        conn.commit()
    return jsonify({'status': 'ok', 'promoted_id': job_id})


@app.route('/api/jobs/<job_id>/move', methods=['POST'])
def queue_move(job_id: str):
    """Move a queued job up (-1) or down (+1) in the queue."""
    data = request.get_json(silent=True) or {}
    direction = int(data.get('direction', -1))

    with get_db() as conn:
        rows = conn.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY COALESCE(queue_rank, 0), created_at").fetchall()
        ids = [r['id'] for r in rows]

        if job_id not in ids:
            return jsonify({'error': 'Job not queued'}), 400

        idx = ids.index(job_id)
        target = idx + direction
        if 0 <= target < len(ids):
            ids[idx], ids[target] = ids[target], ids[idx]
            for rank, jid in enumerate(ids, start=1):
                conn.execute('UPDATE jobs SET queue_rank = ? WHERE id = ?', (rank, jid))
            conn.commit()

    return jsonify({'status': 'ok', 'ordered_ids': ids})


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
                    container_name=NULL,
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


@app.route('/api/jobs/<job_id>/qa')
def job_qa(job_id: str):
    """Surface the ASR QA report for a completed job (#10). Reads whichever
    report the render path wrote: qa_report.json (kaggle/standalone) or
    _verification/audio_verify_sample.json (webapp local sample)."""
    import json as _json
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    outdir = OUTPUT_DIR / (job.get('output_dirname') or '')
    report = None
    for cand in (outdir / 'qa_report.json', outdir / '_verification' / 'audio_verify_sample.json'):
        if cand.exists():
            try:
                report = _json.loads(cand.read_text(encoding='utf-8'))
                break
            except Exception:
                pass
    # pre-sync quality-gate result (why a book was held for review), if any
    gate = None
    _gp = outdir / '_presync_gate.json'
    if _gp.exists():
        try:
            gate = _json.loads(_gp.read_text(encoding='utf-8'))
        except Exception:
            pass

    if not report:
        return jsonify({'available': False, 'gate': gate})
    chapters = report.get('chapters') or ([report] if 'wer' in report else [])
    # Aggregate: worst WER, dropped-word runs (RELIABLE), lexicon suggestions.
    drops, suggestions = [], {}
    worst = 0.0
    for c in chapters:
        worst = max(worst, c.get('wer', 0) or 0)
        for d in (c.get('divergences') or []):
            if d.get('type') == 'drop' and len(d.get('source', [])) >= 3:
                drops.append(' '.join(d['source'])[:80])
        for k, v in (c.get('lexicon_suggestions') or {}).items():
            suggestions[k] = v
    return jsonify({'available': True, 'worst_wer': round(worst, 3),
                    'chapters': len(chapters),
                    'dropped_runs': drops[:12],
                    'suggestions': suggestions,
                    'gate': gate})


@app.route('/api/articles/rss')
@app.route('/rss/podcasts')
@app.route('/rss/articles/<site>')
def article_podcast_rss(site: str = None):
    """Serve converted articles as a standard RSS 2.0 podcast feed (#42)."""
    from article import generate_podcast_rss
    # Reverse proxies may legitimately reach Gunicorn over HTTP. An explicit
    # public origin prevents those internal transport details from leaking
    # into enclosure URLs as http:// links that need a redirect before audio.
    base_url = PUBLIC_BASE_URL or request.host_url.rstrip('/')

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM jobs WHERE source_kind = 'article' AND status = 'completed' ORDER BY created_at DESC"
    rows = conn.execute(query).fetchall()
    conn.close()

    items = []
    for r in rows:
        j = dict(r)
        out_dirname = j.get('output_dirname') or ''
        out_dir = OUTPUT_DIR / out_dirname
        if not out_dir.exists():
            continue

        site_name = j.get('source_site') or 'Articles'
        if site and site.lower() not in site_name.lower():
            continue

        audio_files = list(out_dir.glob('*.mp3')) + list(out_dir.glob('*.m4b'))
        if not audio_files:
            continue
        audio_file = audio_files[0]

        audio_rel_path = url_for(
            'article_audio', job_id=j['id'], filename=audio_file.name)
        items.append({
            'title': j.get('book_name') or audio_file.stem,
            'author': j.get('author') or site_name,
            'site': site_name,
            'url': j.get('source_url') or base_url,
            'audio_url': audio_rel_path,
            'file_size': audio_file.stat().st_size,
            'date_str': j.get('created_at'),
            'guid': j['id'],
            'summary': f"Article from {site_name}: {j.get('book_name')}"
        })

    channel_name = f"Articles - {site}" if site else "Article Narrations"
    rss_xml = generate_podcast_rss(channel_name, items, base_url)
    return Response(rss_xml, mimetype='application/rss+xml')


@app.route('/api/articles/audio/<job_id>/<path:filename>')
def article_audio(job_id: str, filename: str):
    """Public podcast enclosure backed by a completed article job."""
    if Path(filename).name != filename:
        return jsonify({'error': 'Invalid audio filename'}), 400
    job = get_job(job_id)
    if not job or job.get('source_kind') != 'article' or job.get('status') != 'completed':
        return jsonify({'error': 'Article audio not found'}), 404
    outdir = (OUTPUT_DIR / (job.get('output_dirname') or '')).resolve()
    target = (outdir / filename).resolve()
    if target.parent != outdir or target.suffix.lower() not in ('.mp3', '.m4b'):
        return jsonify({'error': 'Invalid audio filename'}), 400
    if not target.is_file():
        return jsonify({'error': 'Article audio not found'}), 404
    mimetype = 'audio/mp4' if target.suffix.lower() == '.m4b' else 'audio/mpeg'
    return send_file(target, mimetype=mimetype, conditional=True,
                     download_name=target.name)


@app.route('/api/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Handle one or more article URLs from the owner Telegram chat (#42)."""
    supplied_secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not TELEGRAM_WEBHOOK_SECRET:
        return jsonify({'error': 'Telegram webhook secret is not configured'}), 503
    if not hmac.compare_digest(supplied_secret, TELEGRAM_WEBHOOK_SECRET):
        return jsonify({'error': 'Invalid Telegram webhook secret'}), 401
    data = request.get_json(silent=True) or {}
    msg = data.get('message') or data.get('channel_post') or {}
    text = (msg.get('text') or msg.get('caption') or '').strip()
    chat_id = (msg.get('chat') or {}).get('id')

    if not text or not chat_id:
        return jsonify({'status': 'ignored'}), 200

    # Telegram's webhook secret proves Telegram sent the request; it does not
    # prove the sender is Dave. Without this owner check, anyone who finds the
    # bot can fill the local CPU queue with arbitrary pages.
    allowed_chat = str(TELEGRAM_CHAT_ID or '').strip()
    if not allowed_chat:
        return jsonify({'error': 'Telegram capture chat is not configured'}), 503
    if not hmac.compare_digest(str(chat_id), allowed_chat):
        app.logger.warning('Ignored Telegram article capture from unapproved chat %s', chat_id)
        return jsonify({'status': 'ignored_chat'}), 200

    entity_urls = [entity.get('url') for entity in
                   ((msg.get('entities') or []) + (msg.get('caption_entities') or []))
                   if entity.get('type') == 'text_link' and entity.get('url')]
    raw_urls = entity_urls + re.findall(r'https?://[^\s]+', text)
    # Telegram can expose the same link both as an entity and in message text.
    # Preserve the user's order while preventing duplicate conversions.
    urls = []
    seen_urls = set()
    for raw_url in raw_urls:
        url = raw_url.rstrip('.,;:!?)]}')
        if url and url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)
    if not urls:
        return jsonify({'status': 'no_url_found'}), 200

    # A Telegram message is limited in size, but keep a hard queue-flood guard
    # as defence in depth. The owner receives an explicit count if links remain.
    max_urls = 20
    omitted = max(0, len(urls) - max_urls)
    urls = urls[:max_urls]
    app.logger.info("Telegram article capture triggered for %d URL(s)", len(urls))

    from article import fetch_article
    jobs = []
    errors = []
    for url in urls:
        try:
            art = fetch_article(url)
            body, status = _queue_article(art, {'notify_telegram': True})
            if status != 200:
                detail = body.get('error') or f'queue returned HTTP {status}'
                raise RuntimeError(detail)
            jobs.append({'url': url, 'job_id': body['job_id'],
                         'title': art['title'], 'site': art.get('site', '')})
        except Exception as e:
            detail = str(e)[:300]
            app.logger.error("Telegram article capture failed for %s: %s", url, detail)
            errors.append({'url': url, 'error': detail})

    if TELEGRAM_BOT_TOKEN and chat_id:
        lines = [f"Article capture: {len(jobs)} queued, {len(errors)} failed."]
        lines.extend(f"✅ {item['title']} ({item['site']})" for item in jobs)
        lines.extend(f"❌ {item['url'][:100]} — {item['error'][:120]}" for item in errors)
        if omitted:
            lines.append(f"⚠️ {omitted} additional link(s) not processed; send another message.")
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                          json={'chat_id': chat_id, 'text': '\n'.join(lines)[:4096]},
                          timeout=5)
        except Exception:
            pass

    # Telegram retries a webhook delivery after a non-2xx response. Article
    # extraction failures are processing results, not webhook-auth failures, so
    # acknowledge the update with 200 to avoid duplicate queue entries.
    result = {
        'status': 'enqueued' if jobs else 'processed_with_errors',
        'enqueued_count': len(jobs),
        'failed_count': len(errors),
        'omitted_count': omitted,
        'jobs': jobs,
        'errors': errors,
    }
    # Preserve the original single-link response fields for existing clients.
    if len(jobs) == 1 and not errors and not omitted:
        result.update({'job_id': jobs[0]['job_id'], 'title': jobs[0]['title']})
    return jsonify(result), 200


@app.route('/api/jobs/<job_id>/qa/apply', methods=['POST'])
def job_qa_apply(job_id: str):
    """Human-in-the-loop 'self-healing' (#7): append a reviewed pronunciation
    fix to the GLOBAL rules. NOT auto-applied — Whisper's guesses are noisy, so
    the user picks which suggestions to keep."""
    data = request.json or {}
    word, repl = (data.get('word') or '').strip(), (data.get('replacement') or '').strip()
    if not word or not repl:
        return jsonify({'error': 'word and replacement required'}), 400
    conf = UPLOAD_DIR / 'global_pronunciations.conf'
    existing = conf.read_text(encoding='utf-8') if conf.exists() else ''
    rule = f"{word}=={repl}"
    if rule in existing:
        return jsonify({'status': 'already present'})
    with open(conf, 'a', encoding='utf-8') as f:
        if existing and not existing.endswith('\n'):
            f.write('\n')
        f.write(rule + '\n')
    return jsonify({'status': 'applied', 'rule': rule})


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
        lines = [ln for ln in (result.stdout or '').splitlines() if 'epub' in ln or 'kokoro' in ln or 'audiobook-' in ln]
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


def _perform_cancel_job(job_id: str, wipe_data: bool = True) -> bool:
    """Internal helper to stop process/container/Kaggle kernel and cancel a job."""
    job = get_job(job_id)
    if not job:
        return False

    if job.get('status') in ('completed', 'cancelled'):
        return False

    # Stop container if running
    container_name = job.get('container_name')
    if container_name:
        try:
            subprocess.run(['docker', 'stop', container_name], capture_output=True, timeout=10)
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True, timeout=10)
        except Exception as e:
            app.logger.warning(f"Could not stop container for {job_id}: {e}")

    # Kill process if tracked
    if job_id in running_processes:
        try:
            running_processes[job_id].kill()
        except Exception:
            pass
        running_processes.pop(job_id, None)

    running_containers.pop(job_id, None)

    # Stop Kaggle kernel
    if str(job.get('status', '')).startswith(('rendering on Kaggle GPU', 'queued on Kaggle', 'recovering (Kaggle GPU)')):
        try:
            import kaggle_render as KR
            user = KR.kaggle_username()
            slug = KR.kernel_slug(job.get('input_filename') or '')
            if user and slug:
                KR.stop_kernel(f"{user}/{slug}", log=lambda m: append_job_log(job_id, m))
        except Exception as e:
            app.logger.warning(f"Could not stop Kaggle kernel for {job_id}: {e}")

    # Wipe partial conversion audio & transcripts if requested
    if wipe_data:
        out_dirname = job.get('output_dirname') or ''
        if out_dirname:
            out_dir = OUTPUT_DIR / out_dirname
            if out_dir.exists():
                try:
                    shutil.rmtree(out_dir)
                except Exception as e:
                    app.logger.warning(f"Could not wipe output dir for {job_id}: {e}")
        trans_dir = Path(f"/data/transcripts/{job_id}")
        if trans_dir.exists():
            try:
                shutil.rmtree(trans_dir)
            except Exception:
                pass

    update_job(job_id,
        status='cancelled',
        error='Cancelled by user',
        completed_at=datetime.now().isoformat()
    )
    return True


@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    data = request.get_json(silent=True) or {}
    wipe_data = data.get('wipe_data', request.args.get('wipe_data', '1') not in ('0', 'false', 'no'))

    ok = _perform_cancel_job(job_id, wipe_data=bool(wipe_data))
    if not ok:
        return jsonify({'error': 'Job cannot be cancelled'}), 400

    return jsonify({'status': 'cancelled', 'job_id': job_id, 'wiped_data': bool(wipe_data)})


@app.route('/api/jobs/batch-reconvert', methods=['POST'])
def batch_reconvert():
    """Enqueue multiple books from history or library for conversion."""
    data = request.get_json(silent=True) or {}
    job_ids = data.get('job_ids') or []
    voice_option = data.get('voice_option', 'keep')
    engine_option = data.get('tts_engine_option', 'keep')

    if not isinstance(job_ids, list) or not job_ids:
        return jsonify({'error': 'job_ids must be a non-empty list'}), 400
    if engine_option != 'keep':
        return jsonify({'error': 'Choose a narrator, not a separate engine. '
                        'Voice and engine cannot be overridden independently.'}), 400

    enqueued = []
    for jid in job_ids:
        job = get_job(jid)
        if not job:
            continue

        voice = job['voice'] if voice_option == 'keep' else (
            get_setting('default_voice', DEFAULT_VOICE) if voice_option == 'default' else voice_option
        )
        voice_info = all_voices().get(voice)
        if not voice_info:
            continue
        engine = voice_info.get('engine', 'chatterbox_nano')

        new_job_id = uuid.uuid4().hex
        safe_name = sanitize_filename(job.get('book_name', 'book'))
        output_dirname = f"{safe_name}_{new_job_id}"

        new_job = {
            'id': new_job_id,
            'book_name': job.get('book_name', 'Untitled'),
            'input_filename': job.get('input_filename', ''),
            'output_dirname': output_dirname,
            'voice': voice,
            'voice_name': voice_info.get('name', voice),
            'tts_engine': engine,
            'status': 'queued',
            'created_at': datetime.now().isoformat(),
            'source_kind': job.get('source_kind', 'book'),
            'is_pdf': job.get('is_pdf', False),
            'start_chapter': job.get('start_chapter', 1),
            'end_chapter': job.get('end_chapter', None),
            'queue_rank': next_queue_rank(),
        }

        # Copy original input file if present
        src_filename = job.get('input_filename', '')
        if src_filename:
            src_file = UPLOAD_DIR / src_filename
            if src_file.exists():
                base_name = src_filename.split('_', 1)[-1] if '_' in src_filename else src_filename
                new_input_name = f"{new_job_id}_{base_name}"
                dst_file = UPLOAD_DIR / new_input_name
                try:
                    shutil.copy2(src_file, dst_file)
                    new_job['input_filename'] = new_input_name
                except Exception as e:
                    app.logger.warning(f"Could not copy input file for batch reconvert: {e}")

        save_job(new_job)
        enqueued.append(new_job_id)

    if enqueued and not is_queue_paused():
        maybe_start_next_queued_job()

    return jsonify({'status': 'ok', 'enqueued_count': len(enqueued), 'job_ids': enqueued})


@app.route('/api/jobs/bulk-action', methods=['POST'])
def bulk_job_action():
    """Bulk manage queued, converting, failed, or cancelled jobs."""
    data = request.get_json(silent=True) or {}
    action = data.get('action')  # 'cancel', 'delete', 'clear_cancelled'
    job_ids = data.get('job_ids') or []
    wipe_data = bool(data.get('wipe_data', True))

    if action not in ('cancel', 'delete', 'clear_cancelled'):
        return jsonify({'error': 'Invalid action'}), 400

    affected = []
    if action == 'cancel':
        for jid in job_ids:
            if _perform_cancel_job(jid, wipe_data=wipe_data):
                affected.append(jid)
    elif action == 'delete':
        for jid in job_ids:
            _perform_cancel_job(jid, wipe_data=wipe_data)
            j = get_job(jid)
            if j:
                inp = UPLOAD_DIR / (j.get('input_filename') or '')
                if inp.exists():
                    try:
                        inp.unlink()
                    except Exception:
                        pass
                with get_db() as conn:
                    conn.execute('DELETE FROM jobs WHERE id = ?', (jid,))
                    conn.commit()
                affected.append(jid)
    elif action == 'clear_cancelled':
        with get_db() as conn:
            rows = conn.execute("SELECT id, output_dirname, input_filename, source_kind FROM jobs WHERE status IN ('cancelled', 'failed')").fetchall()
            for r in rows:
                jid = r['id']
                out_dir = OUTPUT_DIR / (r['output_dirname'] or '')
                if out_dir.exists():
                    shutil.rmtree(out_dir, ignore_errors=True)
                if r['source_kind'] == 'article':
                    inp = UPLOAD_DIR / (r['input_filename'] or '')
                    if inp.exists():
                        inp.unlink(missing_ok=True)
                affected.append(jid)
            conn.execute("DELETE FROM jobs WHERE status IN ('cancelled', 'failed')")
            conn.commit()

    return jsonify({'status': 'ok', 'action': action, 'affected_count': len(affected), 'affected_ids': affected})


@app.route('/api/jobs/<job_id>/retry', methods=['POST'])
def retry_job(job_id: str):
    """Retry a failed or cancelled job.

    Limits retries to 3 attempts to prevent infinite retry loops.
    """
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] not in ('failed', 'cancelled', 'completed'):
        return jsonify({'error': 'Can only retry failed, cancelled, or completed jobs'}), 400

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
    """Download one MP3 directly, or a ZIP when a book has many chapters."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400

    output_dir = OUTPUT_DIR / job['output_dirname']
    if not output_dir.exists():
        return jsonify({'error': 'Output files not found'}), 404

    mp3s = sorted(p for p in output_dir.glob('*.mp3') if p.is_file())
    if not mp3s:
        return jsonify({'error': 'No MP3 files found'}), 404

    # A single-file article (or single-track book) does not need an archive.
    if len(mp3s) == 1:
        return send_file(
            mp3s[0], mimetype='audio/mpeg', as_attachment=True,
            download_name=f"{sanitize_filename(job['book_name']) or 'audio'}.mp3",
        )

    # Multi-chapter MP3 books need one transfer; preserve each chapter file.
    zip_path = UPLOAD_DIR / f"{job['output_dirname']}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for mp3_file in mp3s:
            zf.write(mp3_file, mp3_file.name)

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{job['book_name']}.zip"
    )



@app.route('/api/jobs/<job_id>/audio_files', methods=['GET'])
def get_job_audio_files(job_id: str):
    """Return list of MP3 audio tracks for a completed job for web playback."""
    job = get_job(job_id)
    if not job or not job.get('output_dirname'):
        return jsonify({'error': 'Job not found'}), 404
    out_dir = OUTPUT_DIR / job['output_dirname']
    if not out_dir.exists():
        return jsonify({'error': 'Output directory not found'}), 404

    mp3s = sorted(out_dir.glob('*.mp3'))
    files = [{'filename': f.name, 'url': f'/api/jobs/{job_id}/stream/{f.name}'} for f in mp3s]
    return jsonify({
        'job_id': job_id,
        'book_name': job.get('book_name'),
        'files': files
    })


@app.route('/api/jobs/<job_id>/stream/<filename>', methods=['GET'])
def stream_job_audio(job_id: str, filename: str):
    """Stream specific MP3 audio file for inline web audio player."""
    job = get_job(job_id)
    if not job or not job.get('output_dirname'):
        return jsonify({'error': 'Job not found'}), 404
    out_dir = OUTPUT_DIR / job['output_dirname']
    target_file = (out_dir / filename).resolve()
    try:
        target_file.relative_to(out_dir.resolve())
    except ValueError:
        return jsonify({'error': 'Invalid audio path'}), 400
    if not target_file.exists() or not target_file.is_file():
        return jsonify({'error': 'Audio file not found'}), 404
    return send_file(target_file, mimetype='audio/mpeg')


@app.route('/api/jobs/<job_id>/download_epub', methods=['GET'])
def download_epub_job(job_id: str):
    """Download the generated EPUB file (with Media Overlays)."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400

    output_dir = OUTPUT_DIR / job['output_dirname']
    epub_path = output_dir / f"{job['book_name']}.epub"
    if not epub_path.exists():
        # Fallback to original EPUB in uploads if the generated one is missing
        input_filename = job.get('input_filename', '')
        if input_filename:
            fallback_path = UPLOAD_DIR / input_filename
            if fallback_path.exists():
                epub_path = fallback_path
            else:
                return jsonify({'error': 'EPUB file not found'}), 404
        else:
            return jsonify({'error': 'EPUB file not found'}), 404

    return send_file(
        epub_path,
        mimetype='application/epub+zip',
        as_attachment=True,
        download_name=epub_path.name
    )


@app.route('/api/jobs/<job_id>/sync', methods=['POST'])
def sync_job(job_id: str):
    """Manually sync a completed job to Audiobookshelf."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Allow 'review needed' too — a manual sync is the user overriding a quality
    # hold (the guard never blocks an explicit user action).
    if job['status'] not in ('completed', 'review needed'):
        return jsonify({'error': 'Job not completed'}), 400

    output_dir = OUTPUT_DIR / job['output_dirname']
    if not output_dir.exists():
        return jsonify({'error': 'Output files not found'}), 404

    synced = copy_to_audiobookshelf(output_dir, job['book_name'], job_id=job_id)
    # Clear the review hold once the user has synced it through.
    update_job(job_id, synced_to_abs=synced,
               **({'status': 'completed', 'error': ''} if synced else {}))

    if synced:
        return jsonify({'status': 'synced'})
    else:
        return jsonify({'error': 'Sync failed'}), 500


@app.route('/api/jobs/<job_id>/delete', methods=['DELETE'])
def delete_job(job_id: str):
    """Delete local conversion files; optionally remove the exact ABS copy."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] in ('converting', 'converting PDF', 'converting to audio'):
        return jsonify({'error': 'Cannot delete running job'}), 400

    data = request.get_json(silent=True) or {}
    remove_from_abs = bool(data.get('remove_from_abs'))

    if remove_from_abs and job.get('synced_to_abs'):
        ok, message = _delete_synced_copy(job)
        if not ok:
            return jsonify({'error': message}), 409

    def owned_path(root: Path, name: str) -> Path | None:
        if not name or Path(name).name != name:
            return None
        candidate = (root / name).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate

    input_path = owned_path(UPLOAD_DIR, job.get('input_filename') or '')
    if input_path and input_path.is_file():
        input_path.unlink()
    # Conversion preprocesses an EPUB into a sibling ``*_tts.epub`` and runs
    # the worker against that copy. It is owned by the same job and must leave
    # with the original; otherwise every History deletion leaks one source-sized
    # file in the uploads volume.
    if input_path and input_path.suffix.lower() == '.epub':
        tts_path = owned_path(
            UPLOAD_DIR, f"{input_path.stem}_tts{input_path.suffix}")
        if tts_path and tts_path.is_file():
            tts_path.unlink()

    output_dir = owned_path(OUTPUT_DIR, job.get('output_dirname') or '')
    if output_dir and output_dir.is_dir():
        shutil.rmtree(output_dir)

    zip_path = owned_path(UPLOAD_DIR, f"{job.get('output_dirname')}.zip" if job.get('output_dirname') else '')
    if zip_path and zip_path.is_file():
        zip_path.unlink()

    # Delete from database
    with get_db() as conn:
        conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
        conn.commit()

    return jsonify({'status': 'deleted', 'removed_from_abs': remove_from_abs})


def _delete_synced_copy(job: dict) -> tuple[bool, str]:
    """Remove only files owned by this conversion from the remote ABS host.

    ABS's official DELETE endpoint removes database state but explicitly does
    not delete media files.  Our media was delivered with rsync, so it must be
    removed over the same SSH trust path before ABS is rescanned.
    """
    target = (job.get('sync_target_path') or '').rstrip('/')
    kind = job.get('source_kind') or 'book'
    book_root = (AUDIOBOOKSHELF_DIR or '').rstrip('/')
    podcast_root = (AUDIOBOOKSHELF_PODCAST_DIR or '').rstrip('/')
    if not target:
        return False, 'This conversion has no recorded Audiobookshelf path.'

    paths: list[str] = []
    remove_directory = False
    if kind == 'article':
        if not podcast_root or not target.startswith(podcast_root + '/'):
            return False, 'Refusing to delete an article outside the configured podcast library.'
        count = max(1, int(job.get('sync_file_count') or 1))
        filenames = [_episode_filename(job, job.get('book_name') or 'Article')]
        # Before job ids were added to episode filenames, the title/date pair
        # was the only available exact address. Never try that legacy filename
        # for a newer job: it could belong to an older duplicate conversion.
        if (job.get('completed_at') or '') < '2026-08-14':
            filenames.append(_legacy_episode_filename(job, job.get('book_name') or 'Article'))
        for filename in dict.fromkeys(filenames):
            stem = filename[:-4]
            if count == 1:
                paths.append(f"{target}/{filename}")
            else:
                paths.extend(f"{target}/{stem} ({i:02d}).mp3" for i in range(1, count + 1))
    else:
        expected_suffix = f"_{job.get('id')}"
        if (not book_root or not target.startswith(book_root + '/')
                or not target.endswith(expected_suffix)):
            return False, 'Refusing to delete an ABS folder not uniquely owned by this conversion.'
        paths = [target]
        remove_directory = True

    ssh_key_src = os.environ.get('SSH_KEY_PATH', '/root/.ssh/id_ed25519')
    ssh_key_tmp = '/tmp/id_ed25519_tmp'
    if not os.path.exists(ssh_key_src):
        return False, 'Audiobookshelf SSH key is unavailable.'
    try:
        shutil.copy2(ssh_key_src, ssh_key_tmp)
        os.chmod(ssh_key_tmp, 0o600)
        ssh_args = ['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
                    '-F', '/dev/null', '-i', ssh_key_tmp]
        if AUDIOBOOKSHELF_PORT:
            ssh_args += ['-p', str(AUDIOBOOKSHELF_PORT)]
        target_host = f"{AUDIOBOOKSHELF_USER}@{AUDIOBOOKSHELF_HOST}"
        flag = '-rf' if remove_directory else '-f'
        command = ' '.join(['rm', flag, '--', *[shlex.quote(p) for p in paths]])
        result = subprocess.run(['ssh', *ssh_args, target_host, command],
                                capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return False, (result.stderr or result.stdout or 'remote delete failed').strip()
    except Exception as exc:
        return False, str(exc)

    # A scan removes the vanished podcast episode.  For a book, also remove the
    # exact database item because ABS documents that its DELETE is DB-only.
    _trigger_abs_rescan(job.get('id'))
    if remove_directory:
        _delete_abs_item_for_path(target, job.get('id'))
    return True, 'removed'


def _delete_abs_item_for_path(target: str, job_id: str | None = None) -> bool:
    """Delete the ABS database row whose relPath exactly matches target."""
    url, token = _abs_credentials()
    if not token or not AUDIOBOOKSHELF_DIR:
        return False
    rel = target[len(AUDIOBOOKSHELF_DIR.rstrip('/') + '/'):]
    headers = {'Authorization': f'Bearer {token}'}
    try:
        libs = requests.get(f'{url}/api/libraries', headers=headers, timeout=15)
        if libs.status_code != 200:
            return False
        for lib in libs.json().get('libraries', []):
            if lib.get('mediaType') != 'book':
                continue
            items = requests.get(f"{url}/api/libraries/{lib['id']}/items",
                                 headers=headers, params={'limit': 0, 'minified': 0}, timeout=30)
            if items.status_code != 200:
                continue
            for item in items.json().get('results', []):
                if item.get('relPath') == rel:
                    deleted = requests.delete(f"{url}/api/items/{item['id']}",
                                              headers=headers, timeout=15)
                    return deleted.status_code in (200, 204)
    except Exception as exc:
        if job_id:
            append_job_log(job_id, f'ABS database cleanup failed after media delete: {exc}')
    return False


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
            # Only trust a 'completed' record if the rendered audio still exists.
            # A leftover job row whose output was deleted (or a partial test
            # render that got cleaned up) must NOT keep claiming "Audiobook
            # ready" — the book is really just 'available' to convert again.
            out = (job.get('output_dirname') or '').strip()
            out_dir = OUTPUT_DIR / out if out else None
            if out_dir and out_dir.is_dir() and any(out_dir.glob('*.mp3')):
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

    # Most recently added/modified first, so freshly-grabbed books surface at
    # the top (was alphabetical, which buried new arrivals).
    books.sort(key=lambda x: x.get('modified_ts', 0), reverse=True)
    return jsonify(books)


def llm_configured() -> bool:
    """True if an OpenAI-compatible LLM is set up (settings DB or env)."""
    return bool(get_setting('LLM_API_KEY') or os.environ.get('LLM_API_KEY'))


def _llm_chat(messages, temperature=0, max_tokens=900, timeout=45) -> str:
    """One OpenAI-compatible chat-completions call using the configured LLM
    (local Ollama primary / cloud fallback — same config the pronunciation
    features use). Returns the assistant text; raises if unconfigured or failed
    so the guard treats it as 'unavailable' and falls back to the heuristic."""
    key = get_setting('LLM_API_KEY') or os.environ.get('LLM_API_KEY')
    base = get_setting('LLM_API_BASE_URL') or os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1')
    model = get_setting('LLM_MODEL_NAME') or os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    if not key:
        # Local Ollama is the PRIMARY path (free, private, no key). Its
        # OpenAI-compatible /v1 endpoint ignores the bearer token, so a
        # placeholder is fine. Only raise if neither is configured.
        ollama = get_setting('OLLAMA_URL') or os.environ.get('OLLAMA_URL', '')
        if not ollama:
            raise RuntimeError("no LLM configured")
        base = ollama
        model = get_setting('OLLAMA_MODEL') or os.environ.get('OLLAMA_MODEL') or model
        key = 'ollama'
    r = requests.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages,
              "temperature": temperature, "max_tokens": max_tokens},
        timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def guard_refine_chapters(epub_path, chapters):
    """LLM-guard the chapter classification. Returns
    {'back': set(indices), 'first_body': int, 'last_body': int} or None when the
    guard is unavailable / its result fails a sanity check (caller uses the
    deterministic heuristic). Cached per book so it's one call, not per page-load.
    """
    if not chapters or not llm_configured():
        return None
    cache = TOC_CACHE_DIR / f"{Path(epub_path).stem}.guard.json"
    try:
        if cache.exists():
            d = json.loads(cache.read_text(encoding='utf-8'))
            return {'back': set(d['back']), 'first_body': d['first_body'], 'last_body': d['last_body']}
    except Exception:
        pass
    # Classify only the boundary chapters (front/back matter live at the edges;
    # the middle is body). Smaller prompt = faster + cheaper against the free
    # tier, and robust enough for a fast cloud model. Latency-sensitive UI call,
    # so this uses the configured cloud LLM (Groq) — NOT the Pi-hosted local
    # model, which is reserved for the background guard jobs (per local-llm-reference.md).
    # Tight timeout + small output: a UI call must fail open to the heuristic
    # quickly if the cloud LLM is slow/rate-limited.
    chat = lambda msgs: _llm_chat(msgs, timeout=20, max_tokens=300)
    rng = guard.resolve_body_range(chapters, chat)
    if not rng:
        return None
    first_body, last_body = rng
    # Measured 2026-07-25 on a real book: the LLM correctly moved the START past
    # a copyright page the heuristic would have narrated (2 vs 1), but ran the
    # END three chapters into the back matter (28 vs 25). So trust each where it
    # is actually better — take the LLM's start, but never extend the end past
    # the deterministic body_end_index.
    try:
        det_end = body_end_index(chapters)
        if det_end and last_body > det_end:
            app.logger.info(
                f"Guard: clamping LLM last_body {last_body} -> {det_end} (deterministic)")
            last_body = det_end
    except Exception:
        pass
    back = sorted(c['index'] for c in chapters if c['index'] < first_body or c['index'] > last_body)
    result = {'back': back, 'first_body': first_body, 'last_body': last_body}
    try:
        cache.write_text(json.dumps(result), encoding='utf-8')
    except Exception:
        pass
    result['back'] = set(back)
    return result


def _ollama_available() -> bool:
    return bool(os.environ.get('OLLAMA_URL') or get_setting('OLLAMA_URL'))


def _ollama_chat(messages, timeout=40, max_tokens=200) -> str:
    """Background-job call to the SHARED local Ollama (khpi5). For NON-latency-
    sensitive guard jobs only (per local-llm-reference.md). Hard timeout,
    fail-open — raises on any problem so callers proceed without it."""
    base = (os.environ.get('OLLAMA_URL') or get_setting('OLLAMA_URL') or '').rstrip('/')
    model = os.environ.get('OLLAMA_MODEL') or get_setting('OLLAMA_MODEL') or 'qwen2.5:3b'
    if not base:
        raise RuntimeError("no local Ollama configured")
    r = requests.post(f"{base}/chat/completions",
                      headers={"Content-Type": "application/json"},
                      json={"model": model, "messages": messages, "temperature": 0,
                            "max_tokens": max_tokens, "keep_alive": "24h"},
                      timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# Word-error rate above which a chapter is called garbled.
#
# This was 0.7, which is close to unreachable: at 70% wrong the audio would be
# essentially noise. The FIRST real ASR report (Alice ch1-3, 2026-07-27)
# measured a healthy baseline of 7.8-9.0% WER, and much of that turned out to
# be the apostrophe bug in normalize_words rather than anything audible. So a
# genuinely broken chapter — wrong text, truncated audio, a stuck engine —
# would plausibly sit at 30-40% and sail straight through a 0.7 gate.
#
# 0.35 is set as roughly 4x the measured clean baseline: comfortably above
# normal ASR noise on archaic prose and proper nouns, comfortably below what a
# real failure looks like. Tune with GARBLED_WER once there are more samples;
# this is a first calibration against one book, not a law.
GARBLED_WER = float(os.environ.get('GARBLED_WER', '0.35'))
# These finalists are being promoted specifically because their chapter audio
# passed listening + ASR. Shipping a render without a complete machine-readable
# QA report would silently lower that bar (#33), so they fail closed while the
# older engines retain their current compatibility behaviour.
QUALITY_GATE_REQUIRED_ENGINES = frozenset({'vibevoice', 'qwen3'})


def presync_quality_gate(job_id, output_path):
    """Before syncing a finished render to Audiobookshelf, catch chapters that
    rendered broken so a bad book is HELD for review instead of shipped.

    Deterministic decision (the LLM is never load-bearing): a chapter is flagged
    when its audio is far too short for its text (bytes-per-word << the book's own
    median → truncated/silent) or its ASR word-error is extreme (garbled). A
    local-Ollama call only phrases a human recommendation, fail-open.

    Returns (held: bool, flags: list, summary: str|None). Writes _presync_gate.json.
    """
    import statistics
    output_path = Path(output_path)
    mp3s = sorted(output_path.glob('*.mp3'))
    job = get_job(job_id) or {}
    required = job.get('tts_engine') in QUALITY_GATE_REQUIRED_ENGINES
    if len(mp3s) < 2 and not required:
        return False, [], None      # nothing to compare against; don't block

    wer, words = {}, {}
    qa_path = output_path / 'qa_report.json'
    qa_error = None
    if qa_path.exists():
        try:
            rep = json.loads(qa_path.read_text(encoding='utf-8'))
            for c in rep.get('chapters', []):
                ch = c.get('chapter')
                if ch is not None and isinstance(c.get('wer'), (int, float)) \
                        and int(c.get('n_source') or 0) > 0:
                    wer[int(ch)] = float(c['wer'])
                    words[int(ch)] = int(c['n_source'])
            if required and not isinstance(rep.get('chapters'), list):
                qa_error = 'qa_report.json has no chapters list'
        except Exception as e:
            qa_error = f'qa_report.json is invalid: {str(e)[:120]}'
    elif required:
        qa_error = 'qa_report.json is missing'

    if required:
        rendered = set()
        for f in mp3s:
            m = re.match(r'^(\d+)', f.stem)
            if m:
                rendered.add(int(m.group(1)))
        missing = sorted(rendered - set(wer))
        if not wer and not qa_error:
            qa_error = 'qa_report.json contains zero valid chapter checks'
        elif missing and not qa_error:
            qa_error = ('qa_report.json does not cover rendered chapter(s): ' +
                        ', '.join(map(str, missing[:20])))

    bpw = {}
    for f in mp3s:
        try:
            ch = int(f.stem)
        except ValueError:
            continue
        w = words.get(ch, 0)
        if w > 50:
            bpw[ch] = f.stat().st_size / w
    med = statistics.median(bpw.values()) if bpw else None

    flags = []
    for f in mp3s:
        try:
            ch = int(f.stem)
        except ValueError:
            continue
        w, e = words.get(ch, 0), wer.get(ch)
        if med and w > 200 and ch in bpw and bpw[ch] < 0.25 * med:
            flags.append({'chapter': ch, 'issue': 'truncated', 'words': w,
                          'detail': f'audio is far too short for {w} words of text '
                                    f'({bpw[ch]:.0f} vs median {med:.0f} bytes/word)'})
        elif e is not None and e > GARBLED_WER:
            flags.append({'chapter': ch, 'issue': 'garbled', 'wer': round(e, 3),
                          'detail': f'ASR word-error {e:.0%} — audio does not match the text'})

    if qa_error:
        flags.insert(0, {'chapter': 0, 'issue': 'qa_missing', 'detail': qa_error})
    held = bool(flags)
    summary = qa_error
    if held and _ollama_available():
        summary = guard.explain_gate(flags, _ollama_chat)   # fail-open, non-deciding

    # Did anything actually get INSPECTED? A gate that had no ASR data to look
    # at is not a pass — it is an absence of evidence, and until now the two
    # were written identically as `held: false` (#33). ASR data only exists for
    # engines routed via tts-proxy, so every Chatterbox/TADA book lands here.
    verified = bool(wer) and not qa_error
    unverified_reason = None
    if not verified:
        # Be precise about WHICH half is missing. Since transcript capture moved
        # into the converter, chunks now exist for every engine — so blaming
        # tts-proxy (as this message used to) is no longer true and would send
        # someone to the wrong place. What is still missing is the ASR pass:
        # Whisper has to transcribe the rendered audio to produce qa_report.json,
        # and that only happens when the converter is given --qa.
        chunks_exist = bool(_read_captured_chunks(job_id))
        if qa_error:
            unverified_reason = qa_error
        elif chunks_exist:
            unverified_reason = (
                'the text sent to the engine was recorded, but no ASR pass ran, '
                'so the AUDIO was never compared against it. ASR_VERIFY appears '
                'to be switched off — it is on by default and costs about 6% of '
                'render time.'
            )
        else:
            unverified_reason = (
                'nothing was recorded for this render, so there is no source '
                'text to compare against — check that the converter was given '
                '--job-id'
            )
        append_job_log(
            job_id,
            f"WARNING — QUALITY GATE COULD NOT VERIFY THIS BOOK: {unverified_reason}. "
            f"The book was NOT checked against its source; it is being shipped "
            f"unverified. This is not the same as passing."
        )
        app.logger.warning(f"job {job_id}: presync gate ran unverified ({unverified_reason})")

    try:
        (output_path / '_presync_gate.json').write_text(
            json.dumps({
                'held': held,
                'flags': flags,
                'summary': summary,
                # Explicit, so a consumer can never mistake "nothing to inspect"
                # for "inspected and clean".
                'verified': verified,
                'unverified_reason': unverified_reason,
                'chapters_inspected': len(wer),
            }), encoding='utf-8')
    except Exception:
        pass

    try:
        update_job(job_id, qa_verified=1 if verified else 0)
    except Exception:
        pass

    return held, flags, summary


def _maybe_build_m4b(job_id, output_path, book_name):
    """Build a single chaptered .m4b if this job asked for one.

    Runs BEFORE the Audiobookshelf sync so the .m4b ships with the chapters
    (ABS reads m4b chapter indexes natively). Never fatal: the per-chapter MP3s
    are the real deliverable and are left untouched, so a failure here costs a
    convenience file, not the book.
    """
    job = get_job(job_id) or {}
    if (job.get('output_format') or 'mp3').lower() != 'm4b':
        return None
    try:
        from m4b import build_m4b
        from book_meta import read_book_meta
        append_job_log(job_id, "Building single-file M4B with chapter markers…")

        # Read the epub, exactly as the MP3 tagger does. This used to take the
        # title from the job's filename-derived book_name and the author from
        # the LLM narration profile (which has no author field, so it was
        # always empty) — leaving the M4B strictly worse tagged than the MP3s
        # built from the same source in the same job (#32).
        title, author, extra = book_name or '', job.get('author') or '', {}
        voice = job.get('voice') or ''
        if voice:
            extra['composer'] = f"Narrated by {voice}"
            extra['narrator'] = voice

        epub_name = job.get('input_filename') or ''
        if epub_name:
            src = UPLOAD_DIR / epub_name
            if src.exists():
                bm = read_book_meta(src)
                title = bm.get('title') or title
                author = bm.get('author') or author
                # Everything else the epub gave us. Audiobookshelf reads these,
                # and Dave asked for as much per-book metadata as possible.
                for src_key, tag in (('year', 'date'), ('publisher', 'publisher'),
                                     ('language', 'language'), ('description', 'comment'),
                                     ('series', 'show'), ('series_index', 'episode_id')):
                    if bm.get(src_key):
                        extra[tag] = bm[src_key]
                if author:
                    append_job_log(job_id, f"M4B metadata from epub: '{title}' by {author}"
                                           + (f" ({', '.join(extra)})" if extra else ''))
        if not author:
            append_job_log(job_id, "M4B metadata: no author found in the epub — "
                                   "tagging title only.")
        out = build_m4b(Path(output_path), title=title, author=author, extra=extra)
        if out:
            mb = out.stat().st_size / 1e6
            append_job_log(job_id, f"M4B ready: {out.name} ({mb:.1f} MB)")
        else:
            append_job_log(job_id, "M4B build skipped — keeping the MP3 chapters "
                                   "(see server log for the reason)")
        return out
    except Exception as e:
        app.logger.warning(f"M4B build failed for {job_id}: {e}")
        append_job_log(job_id, f"M4B build failed ({e}) — MP3 chapters are unaffected")
        return None


def _gate_and_sync(job_id, output_path, book_name, file_count):
    """Quality-gate a finished render, then hold-for-review or sync+complete.
    Shared by every render path. Returns 'held' or 'completed'."""
    held, flags, summary = presync_quality_gate(job_id, output_path)
    if held:
        reasons = summary or '; '.join("chapter %s %s" % (f['chapter'], f['issue']) for f in flags)
        update_job(job_id, status='review needed', progress_percent=100,
                   file_count=file_count, error=reasons,
                   completed_at=datetime.now().isoformat())
        append_job_log(job_id, "Held for review — not synced to Audiobookshelf: " + reasons)
        return 'held'
    _maybe_build_m4b(job_id, output_path, book_name)
    synced = copy_to_audiobookshelf(output_path, book_name, job_id=job_id)
    if synced:
        # Tell ABS explicitly rather than leaving it to its filesystem watcher.
        # The watcher fires as soon as the first files land and can read the
        # M4B before it is finished; an explicit scan AFTER everything is in
        # place is both correct and faster to appear (#38). Harmless no-op if
        # no API token is configured — it says so in the job log.
        _trigger_abs_rescan(job_id)
    update_job(job_id, status='completed', file_count=file_count,
               progress_percent=100, synced_to_abs=synced,
               completed_at=datetime.now().isoformat())
    return 'completed'


@app.route('/api/library/toc', methods=['POST'])
def library_toc():
    """Chapter list for the picker — numbered EXACTLY as the converter numbers
    chapters (renderable-only, 1-based), so the number a user picks is the
    chapter that actually renders. Back-matter (Acknowledgments/Notes/Index) is
    flagged so the UI can default the range to the book body."""
    data = request.json or {}
    path_str = data.get('path')
    if not path_str: return jsonify({'error': 'No path'}), 400
    try:
        path = Path(path_str)
        if not path.exists(): return jsonify({'error': 'Not found'}), 404
        if path.suffix.lower() == '.epub':
            chapters = list_renderable_chapters(path)
            # LLM guard refines front/body/back classification when available;
            # otherwise the deterministic heuristic. The UI defaults the range to
            # the book body so "convert the book" excludes copyright pages and
            # trailing citations/index/junk unless the user extends it.
            refined = guard_refine_chapters(path, chapters)
            if refined:
                for c in chapters:
                    c['back_matter'] = c['index'] in refined['back']
                first_body, last_body = refined['first_body'], refined['last_body']
            else:
                first_body, last_body = 1, body_end_index(chapters)
            for c in chapters:
                c.pop('snippet', None)   # internal to the guard, not for the UI
            return jsonify({'chapters': chapters,
                            'first_body_index': first_body,
                            'last_body_index': last_body,
                            'guard': bool(refined)})
        return jsonify({'chapters': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _extract_epub_cover(epub_path):
    """Return (bytes, mimetype) for an epub's cover image, or (None, None).
    Detection order: OPF meta name=cover -> manifest cover-image property ->
    a manifest image whose href looks like a cover -> largest image."""
    import zipfile
    import posixpath
    import re as _re
    try:
        with zipfile.ZipFile(epub_path) as z:
            names = z.namelist()
            # locate the OPF via container.xml
            opf = None
            try:
                cont = z.read('META-INF/container.xml').decode('utf-8', 'ignore')
                m = _re.search(r'full-path="([^"]+\.opf)"', cont)
                if m:
                    opf = m.group(1)
            except Exception:
                pass
            if not opf:
                opf = next((n for n in names if n.lower().endswith('.opf')), None)
            base = posixpath.dirname(opf) if opf else ''
            href = None
            if opf:
                x = z.read(opf).decode('utf-8', 'ignore')
                cover_id = None
                mm = _re.search(r'<meta[^>]+name="cover"[^>]+content="([^"]+)"', x) \
                    or _re.search(r'<meta[^>]+content="([^"]+)"[^>]+name="cover"', x)
                if mm:
                    cover_id = mm.group(1)
                item = None
                if cover_id:
                    item = _re.search(r'<item[^>]+id="%s"[^>]*href="([^"]+)"' % _re.escape(cover_id), x) \
                        or _re.search(r'<item[^>]+href="([^"]+)"[^>]*id="%s"' % _re.escape(cover_id), x)
                if not item:
                    item = _re.search(r'<item[^>]+properties="[^"]*cover-image[^"]*"[^>]*href="([^"]+)"', x) \
                        or _re.search(r'<item[^>]+href="([^"]+)"[^>]*properties="[^"]*cover-image', x)
                if item:
                    href = posixpath.normpath(posixpath.join(base, item.group(1)))
            if not href:
                imgs = [n for n in names if _re.search(r'\.(jpe?g|png|webp)$', n, _re.I)]
                cand = [n for n in imgs if 'cover' in n.lower()]
                pool = cand or imgs
                if pool:
                    href = max(pool, key=lambda n: z.getinfo(n).file_size)
            if not href:
                return None, None
            if href not in names:
                href = next((n for n in names if n.endswith(posixpath.basename(href))), href)
            data = z.read(href)
            ext = href.rsplit('.', 1)[-1].lower()
            mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'webp': 'image/webp'}.get(ext, 'image/jpeg')
            return data, mime
    except Exception:
        return None, None


@app.route('/api/library/cover')
def library_cover():
    """Serve an epub's embedded cover image (GET, for use as <img src>)."""
    path_str = request.args.get('path', '')
    if not path_str:
        return ('', 400)
    try:
        p = Path(path_str).resolve()
        if not str(p).startswith(str(LIBRARY_DIR.resolve())) or not p.exists():
            return ('', 404)
        if p.suffix.lower() != '.epub':
            return ('', 404)
        data, mime = _extract_epub_cover(p)
        if not data:
            return ('', 404)
        from flask import Response
        return Response(data, mimetype=mime, headers={'Cache-Control': 'public, max-age=86400'})
    except Exception:
        return ('', 500)


@app.route('/api/library/preview', methods=['POST'])
def library_preview():
    data = request.json or {}
    file_path_str = data.get('path')
    chapter_index = data.get('chapter_index')

    if not file_path_str:
        return jsonify({'error': 'No path provided'}), 400

    try:
        requested_path = Path(file_path_str).resolve()
        library_base = LIBRARY_DIR.resolve()
        if not str(requested_path).startswith(str(library_base)):
            return jsonify({'error': 'Unauthorized path access'}), 403
    except Exception:
        return jsonify({'error': 'Invalid path'}), 400

    file_path = Path(file_path_str)
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    try:
        preview_text = ''
        chapters = []

        if file_path.suffix.lower() == '.epub':
            # Same renderable numbering as the convert picker so a previewed
            # "chapter 5" is the chapter that renders as 5.
            chapters = list_renderable_chapters(file_path)

            with zipfile.ZipFile(file_path, 'r') as zf:
                if chapter_index:
                    target = next((c for c in chapters if c['index'] == int(chapter_index)), None)
                    if target:
                        content = zf.read(target['href']).decode('utf-8', errors='ignore')
                        text = re.sub(r'<[^>]+>', ' ', content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        preview_text = text[:5000]
                else:
                    # Default: first 3 renderable chapters (front-matter already excluded)
                    content_files = [c['href'] for c in chapters]
                    for cf in content_files[:3]:
                        content = zf.read(cf).decode('utf-8', errors='ignore')
                        text = re.sub(r'<[^>]+>', ' ', content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        preview_text += text + "\n\n"
                        if len(preview_text) > 5000: break
        elif file_path.suffix.lower() == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                preview_text = f.read(5000)

        return jsonify({
            'preview': preview_text[:5000],
            'chapters': [{'index': c['index'], 'title': c['title']} for c in chapters]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/library/estimate_cost', methods=['POST'])
def estimate_cost_api():
    """Estimate cost for a library book conversion."""
    try:
        data = request.get_json() or {}
        path_str = data.get('path')
        voice_id = data.get('voice')

        if not path_str or not voice_id:
            return jsonify({'error': 'Missing path or voice'}), 400

        file_path = Path(path_str)
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        # Get engine from voice_id
        voice_info = all_voices().get(voice_id, {})
        engine = voice_info.get('engine', 'kokoro')

        # Estimate character count
        char_count = estimate_epub_size(file_path)

        # Calculate engine cost (Polly, OpenAI, etc.)
        cost = calculate_price_estimate(engine, char_count)

        gpu_info = None
        # If using Kokoro, report an already-active manually provisioned GPU.
        # Queue length deliberately has no paid-GPU effect.
        if engine == 'kokoro' and QUEUE_RUNNER_ENABLED:
            # The helper is _is_gpu_mode(); `is_gpu_active` never existed, so
            # this raised NameError for any Kokoro cost estimate once the queue
            # was non-empty (caught by ruff F821, 2026-07-25).
            is_already_active = _is_gpu_mode()
            if is_already_active:
                gpu_status = _gpu_manager.get_status() if _gpu_manager else GPUManager.load_status_from_file()
                if gpu_status:
                    gpu_info = {
                        'triggered': True,
                        'reason': 'GPU is currently active',
                        'rate': f"${gpu_status.get('cost_per_hour', 0):.2f}/hr"
                    }

        return jsonify({
            'char_count': char_count,
            'estimated_cost': round(cost, 2) if cost is not None else None,
            'cost_status': 'known' if cost is not None else 'unknown_not_free',
            'engine': engine,
            'gpu_info': gpu_info
        })
    except Exception as e:
        app.logger.error(f"Cost estimation error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/library/convert', methods=['POST'])
def convert_from_library():
    """Start conversion of a book from the library."""
    try:
        import json
        raw_data = request.get_data()

        try:
            data = json.loads(raw_data.decode('utf-8'))
        except:
            data = request.form.to_dict() or {}

        file_path_str = data.get('path', '')
        if not file_path_str:
            return jsonify({'error': 'No path provided', 'received': data}), 400

        file_path = Path(file_path_str)
        voice = data.get('voice', DEFAULT_VOICE)
        voice2 = (data.get('voice2') or '').strip() or None
        custom_regex = (data.get('custom_regex') or '').strip() or None
        newline_mode = data.get('newline_mode', 'double')
        title_mode = data.get('title_mode', 'auto')
        if voice2 and voice2 not in all_voices():
            return jsonify({'error': 'Invalid secondary voice selected'}), 400

        def safe_int(v):
            try: return int(v) if v and str(v).strip() else None
            except: return None

        def safe_float(v, default):
            try: return float(v) if v and str(v).strip() else default
            except: return default

        tts_speed = safe_float(data.get('tts_speed'), DEFAULT_TTS_SPEED)
        start_chapter = safe_int(data.get('start_chapter'))
        end_chapter = safe_int(data.get('end_chapter'))

        if not file_path.exists():
            return jsonify({'error': f'File not found: {file_path}'}), 404

        job_id = str(uuid.uuid4())[:8]
        book_name = file_path.stem
        safe_name = sanitize_filename(book_name)
        file_ext = file_path.suffix.lower()

        input_filename = f"{job_id}_{safe_name}{file_ext}"
        input_path = UPLOAD_DIR / input_filename
        shutil.copy2(file_path, input_path)


        # Validate chapter range against actual book content. Use the SAME
        # renderable count the picker/converter use, so the clamp matches the
        # numbers the user saw.
        try:
            if not file_ext == '.pdf':
                toc = list_renderable_chapters(file_path)
                max_chapters = len(toc) if toc else 999
                if start_chapter and start_chapter > max_chapters:
                    start_chapter = 1
                if end_chapter and end_chapter > max_chapters:
                    end_chapter = max_chapters
        except: pass

        output_dirname = f"{safe_name}_{job_id}"
        tts_engine = all_voices().get(voice, {}).get('engine', 'kokoro')
        render_target = (data.get('render_target') or 'local').lower()
        if render_target not in ('local', 'kaggle'):
            return jsonify({'error': 'Paid GPU cannot be selected by queueing a book. '
                            'Vast provisioning is manual and session-specific; use local '
                            'or free Kaggle for this job.'}), 400
        engine_fallback_note = None
        health = check_engines_health()
        # A stopped local CUDA service says nothing about Kaggle availability.
        # Cloud-capable engines are validated by convert_book_kaggle against its
        # own template registry and credentials; rejecting here made Cosy/new
        # finalist voices impossible to queue for Kaggle.
        if render_target != 'kaggle' and health.get(tts_engine) is False:
            # Opt-in failover: if the caller allows it, substitute the next
            # healthy engine (voice remapped) so the book still runs. Default
            # (no flag) keeps the strict reject so we never silently swap voices.
            if data.get('allow_engine_fallback'):
                new_eng, new_voice, engine_fallback_note = pick_engine_with_fallback(tts_engine, voice)
                if engine_fallback_note:
                    tts_engine, voice = new_eng, new_voice
                else:
                    return jsonify({'error': f'The {tts_engine} engine is offline and no fallback engine is healthy. '
                                    f'Start an engine (e.g. docker compose --profile {tts_engine} up -d).'}), 409
            else:
                # "Offline" and "never configured" need different advice —
                # telling someone to start a container when the real problem is
                # a missing API key sends them down the wrong path (#24).
                _missing = engines_unconfigured().get(tts_engine)
                if _missing:
                    return jsonify({'error': f'The {tts_engine} engine is not configured. {_missing} '
                                    f'Until then its voices cannot render — pick a voice from another engine.'}), 409
                return jsonify({'error': f'The {tts_engine} engine is offline — its service is not running. '
                                f'Start it (e.g. docker compose --profile {tts_engine} up -d), pick a voice from another engine, '
                                f'or resend with allow_engine_fallback to auto-substitute a healthy engine.'}), 409

        save_job({
            'id': job_id,
            'book_name': book_name,
            'input_filename': input_filename,
            'output_dirname': output_dirname,
            'voice': voice,
            'voice_name': all_voices().get(voice, {}).get('name', voice),
            'tts_engine': tts_engine,
            'tts_speed': tts_speed,
            'voice2': voice2,
            'voice2_name': all_voices().get(voice2, {}).get('name') if voice2 else None,
            'custom_regex': custom_regex,
            'newline_mode': newline_mode,
            'title_mode': title_mode,
            'status': 'queued',
            'is_pdf': file_ext == '.pdf',
            'start_chapter': start_chapter,
            'end_chapter': end_chapter,
            'notify_telegram': 1 if data.get('notify_telegram') else 0,
            'notify_whatsapp': 1 if data.get('notify_whatsapp') else 0,
            'render_target': render_target,
            'output_format': (data.get('output_format') or 'mp3').lower(),
            # Set HERE, at creation, not patched on afterwards. The queue runner
            # is kicked off on the next line, so a caller that saved the job and
            # then updated it would be racing its own render — and the field
            # decides where the finished audio is delivered.
            'source_kind': (data.get('source_kind') or 'book').lower(),
            'source_url': data.get('source_url') or '',
            'source_site': data.get('source_site') or '',
            'source_date': data.get('source_date') or '',
        })
        if engine_fallback_note:
            append_job_log(job_id, f"Engine fallback: {engine_fallback_note}")

        threading.Thread(target=maybe_start_next_queued_job, daemon=True).start()
        return jsonify({'status': 'success', 'job_id': job_id,
                        'engine_fallback': engine_fallback_note})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/library/batch-convert', methods=['POST'])
def batch_convert_library():
    """Convert multiple ebooks from library in batch."""
    data = request.get_json(silent=True) or {}
    paths = data.get('paths') or []
    voice_option = data.get('voice_option', DEFAULT_VOICE)
    engine_option = data.get('tts_engine_option', 'keep')

    if not isinstance(paths, list) or not paths:
        return jsonify({'error': 'paths must be a non-empty list'}), 400
    if engine_option != 'keep':
        return jsonify({'error': 'Choose a narrator, not a separate engine. '
                        'Each narrator is bound to the engine that produced its cached preview.'}), 400
    resolved_voice = (get_setting('default_voice', DEFAULT_VOICE)
                      if voice_option in ('default', 'keep') else voice_option)
    if resolved_voice not in all_voices():
        return jsonify({'error': 'Unknown narrator'}), 400

    enqueued = []
    for p_str in paths:
        p = Path(p_str)
        if not p.exists():
            continue

        voice = resolved_voice

        job_id = str(uuid.uuid4())[:8]
        book_name = p.stem
        safe_name = sanitize_filename(book_name)
        file_ext = p.suffix.lower()

        input_filename = f"{job_id}_{safe_name}{file_ext}"
        input_path = UPLOAD_DIR / input_filename
        shutil.copy2(p, input_path)

        output_dirname = f"{safe_name}_{job_id}"
        voice_info = all_voices().get(voice, {})

        job = {
            'id': job_id,
            'book_name': book_name,
            'voice': voice,
            'voice_name': voice_info.get('name', voice) if voice_info else voice,
            'tts_engine': voice_info.get('engine', 'kokoro') if voice_info else 'kokoro',
            'status': 'queued',
            'created_at': datetime.now().isoformat(),
            'input_filename': input_filename,
            'output_dirname': output_dirname,
            'is_pdf': (file_ext == '.pdf'),
            'tts_speed': DEFAULT_TTS_SPEED,
            'source_kind': 'book',
            'queue_rank': next_queue_rank(),
        }
        save_job(job)
        enqueued.append(job_id)

    if enqueued and not is_queue_paused():
        maybe_start_next_queued_job()

    return jsonify({'status': 'ok', 'enqueued_count': len(enqueued), 'job_ids': enqueued})



def _cache_voice_batch(voice_ids):
    """Cache a bounded voice list, waiting for spare host capacity per item."""
    import time
    ncpu = os.cpu_count() or 4
    max_load = float(os.environ.get('VOICE_CACHE_MAX_LOAD') or round(ncpu * 0.6, 1))
    delay = float(os.environ.get('VOICE_CACHE_DELAY', '5'))
    health = check_engines_health(max_age=0)
    allowed = frozenset({'kokoro', 'chatterbox', 'chatterbox_nano', 'tada',
                         'pocket', 'kitten'})
    for voice_id in voice_ids:
        info = all_voices().get(voice_id, {})
        engine = info.get('engine', 'kokoro')
        if engine not in allowed or health.get(engine) is not True:
            continue
        if _preview_is_cached(voice_id):
            continue
        for _ in range(90):
            try:
                if os.getloadavg()[0] <= max_load:
                    break
            except Exception:
                break
            time.sleep(10)
        try:
            get_voice_preview(voice_id)
        except Exception as e:
            app.logger.error(f"Failed to cache voice {voice_id}: {e}")
        time.sleep(delay)


def _cache_all_voices_background():
    """Pre-generate voice samples — THROTTLED.

    This runs on the same box as the TTS engines, and generating a full sample is
    heavy: chatterbox pegs a core for minutes and holds ~4.5GB; kokoro bursts to
    ~400% CPU. Looping flat-out over every voice saturated the NUC (load 8+, swap
    full) — the web UI was starved and engines failed their OWN healthchecks and
    reported "offline" while they were merely too busy to answer (2026-07-14).

    So: wait for the machine to be quiet before each voice, and pause between
    them. A cache that fills slowly is worth a box that stays usable.
    """
    if os.environ.get('VOICE_CACHE_ON_START', '0').lower() not in ('1', 'true', 'yes'):
        app.logger.info("Background voice caching disabled (VOICE_CACHE_ON_START=0)")
        return
    ncpu = os.cpu_count() or 4
    max_load = float(os.environ.get('VOICE_CACHE_MAX_LOAD') or round(ncpu * 0.6, 1))
    delay = float(os.environ.get('VOICE_CACHE_DELAY', '5'))
    app.logger.info(
        f"Starting background voice caching (throttled: max_load={max_load}, delay={delay}s)")
    # Startup maintenance is not authority to call an internet/paid engine or
    # hammer an opt-in/offline evaluation service. Cache only currently healthy
    # free local production families. Other previews remain explicit user
    # actions, where failures/cost are visible rather than hidden at boot.
    auto_cache_engines = frozenset({'kokoro', 'chatterbox', 'chatterbox_nano', 'tada',
                                    'pocket', 'kitten'})
    health = check_engines_health(max_age=0)
    cacheable = [voice_id for voice_id, info in all_voices().items()
                 if info.get('engine', 'kokoro') in auto_cache_engines
                 and health.get(info.get('engine', 'kokoro')) is True]
    _cache_voice_batch(cacheable)
    app.logger.info("Background voice caching complete.")

def background_startup():
    """Execute startup tasks in a background thread."""
    import time
    time.sleep(5)  # Let gunicorn workers initialize
    app.logger.info("Starting background maintenance and queue tasks...")
    threading.Thread(target=index_library_background, daemon=True).start()
    threading.Thread(target=_cache_all_voices_background, daemon=True).start()

    if QUEUE_RUNNER_ENABLED:
        try:
            resume_inflight_jobs()
            start_watchdog()
            start_next_queued_job()
        except Exception as e:
            app.logger.error(f"Background startup error: {e}")



init_db()


def _assert_settings_writable():
    """Fail LOUDLY at startup if settings cannot be persisted.

    On 2026-07-26 every Settings save had been returning "attempt to write a
    readonly database" and nothing said so: `app_settings` was empty, the app
    silently fell back to `.env`, and the UI reported a 400 per attempt with no
    hint of the cause. The actual fault was SQLite's WAL sidecars
    (`jobs.db-wal`, `jobs.db-shm`) being owned by a different uid — the
    database file itself was fine, which is exactly why the error misleads
    (#37).

    One write at boot turns a silent, permanent misconfiguration into a log
    line.
    """
    try:
        with get_db() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS app_settings '
                         '(key TEXT PRIMARY KEY, value TEXT)')
            conn.execute("INSERT OR REPLACE INTO app_settings (key, value) "
                         "VALUES ('_startup_write_check', ?)",
                         (datetime.now().isoformat(),))
            conn.commit()
        app.logger.info('settings store: writable')
    except Exception as e:
        app.logger.error(
            'SETTINGS STORE IS NOT WRITABLE: %s. Nothing saved through the '
            'Settings page will persist and the app will silently fall back to '
            '.env. If this says "readonly database", check the OWNER of '
            'jobs.db-wal and jobs.db-shm - SQLite reports a WAL it cannot '
            'write as a read-only database. See OPERATIONS.md.', e)


def _assert_writable_dirs():
    """Fail loudly at startup if a directory we must write to isn't ours.

    URL ingest shipped broken because `data/articles` had been created on the
    host as uid 1000 while the container runs as 999 — every article render
    died with "Permission denied", but only at CONVERT time, so a preview
    looked perfectly healthy and the feature seemed fine. Same class of fault
    as the WAL sidecars in #37, and the third time ownership has bitten.

    Checked at boot rather than discovered by a user mid-feature.
    """
    for name, d in (('articles (URL ingest)', ARTICLES_DIR),
                    ('custom voices', CUSTOM_VOICES_DIR),
                    ('uploads', UPLOAD_DIR),
                    ('output', OUTPUT_DIR)):
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / '.write_check'
            probe.write_text('ok', encoding='utf-8')
            probe.unlink()
        except Exception as e:
            app.logger.error(
                'DIRECTORY NOT WRITABLE - %s (%s): %s. Whatever uses it will '
                'fail at the point of use, not here. Fix with: docker exec -u 0 '
                '<container> chown -R 999:999 %s', name, d, e, d)


_assert_settings_writable()
_assert_writable_dirs()

if __name__ == '__main__':
    # `DEBUG` was never defined — running app.py directly crashed with
    # NameError (ruff F821). Production uses gunicorn, so this stayed hidden.
    app.run(host='0.0.0.0', port=8881,
            debug=os.environ.get('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes'))

threading.Thread(target=background_startup, daemon=True).start()
