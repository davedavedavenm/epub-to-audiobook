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
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from flask import Flask, render_template, request, jsonify, send_file, Response
import requests

# Telegram notification settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

app = Flask(__name__)

# Configuration
KOKORO_URL = os.environ.get('KOKORO_URL', 'http://localhost:8880/v1')
PIPER_URL = os.environ.get('PIPER_URL', 'http://piper-tts:8000/v1')
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/data/uploads'))
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', '/data/audiobooks'))
PREVIEWS_DIR = Path(os.environ.get('PREVIEWS_DIR', '/data/previews'))
DB_PATH = Path(os.environ.get('DB_PATH', '/data/jobs.db'))
APP_VERSION = os.environ.get('APP_VERSION', 'dev')
APP_GIT_SHA = os.environ.get('APP_GIT_SHA', 'unknown')
APP_BUILD_TIME = os.environ.get('APP_BUILD_TIME', 'unknown')
HEALTH_KOKORO_TIMEOUT = int(os.environ.get('HEALTH_KOKORO_TIMEOUT', '8'))
HEALTH_KOKORO_RETRIES = int(os.environ.get('HEALTH_KOKORO_RETRIES', '2'))

# Host paths for Docker volume mounts (where the stack is deployed)
HOST_STACK_DIR = os.environ.get('HOST_STACK_DIR', '/home/dave/stacks/epub-to-audiobook')
STACK_PATH = os.environ.get('STACK_PATH', HOST_STACK_DIR)
HOST_UPLOAD_DIR = f"{HOST_STACK_DIR}/data/uploads"
HOST_OUTPUT_DIR = f"{HOST_STACK_DIR}/data/audiobooks"

# Audiobookshelf integration - copy completed books here
AUDIOBOOKSHELF_DIR = os.environ.get('AUDIOBOOKSHELF_DIR', '')

# OpenBooks/Library directory for browsing available EPUBs
LIBRARY_DIR = Path(os.environ.get('LIBRARY_DIR', '/data/library'))

# Supported ebook formats (converted to EPUB via Calibre)
SUPPORTED_FORMATS = {'.epub', '.pdf', '.mobi', '.azw3', '.fb2', '.txt', '.html', '.htm', '.docx'}

# Default voice when none specified (George Classic - British Male)
DEFAULT_VOICE = 'bm_v0george'

# Auto-retry configuration
MAX_RETRY_COUNT = 3
RETRY_BACKOFF_BASE = 30  # seconds (30, 60, 120 for attempts 1, 2, 3)

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Track running conversion processes and containers
running_processes = {}  # job_id -> subprocess.Popen
running_containers = {}  # job_id -> container_name

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
                queue_rank INTEGER DEFAULT 0
            )
        ''')
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
    return d


def save_job(job: dict):
    """Save or update a job in the database."""
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO jobs
            (id, book_name, voice, voice_name, voice2, voice2_name, tts_engine, status, created_at, started_at,
             completed_at, input_filename, output_dirname, is_pdf, char_count,
             timeout_minutes, total_chapters, current_chapter, current_chapter_name,
             progress_percent, eta_minutes, file_count, error, synced_to_abs, container_name,
             start_chapter, end_chapter, notify_telegram, retry_count, queue_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            job.get('queue_rank', 0)
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
    """Fetch app setting value from database."""
    with get_db() as conn:
        row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default


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
    output_files = list(output_path.glob('*.mp3')) if output_path.exists() else []
    if not output_files:
        return False

    total_chapters = job.get('total_chapters')
    if total_chapters:
        try:
            if len(output_files) < int(total_chapters):
                return False
        except Exception:
            return False
    else:
        progress = job.get('progress_percent') or 0
        if progress < 95:
            return False

    rename_output_files(output_path, job['book_name'])
    output_files = list(output_path.glob('*.mp3'))
    synced = copy_to_audiobookshelf(output_path, job['book_name'])
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
    and marks them as failed so users can retry.

    Queued jobs are preserved so they can resume after restart.
    """
    with get_db() as conn:
        # Handle converting jobs with dead containers
        converting_jobs = conn.execute(
            "SELECT id, container_name FROM jobs WHERE status IN ('converting', 'converting PDF', 'converting to audio')"
        ).fetchall()

        orphan_count = 0
        for job in converting_jobs:
            if not check_container_running(job['container_name']):
                conn.execute('''
                    UPDATE jobs
                    SET status = 'failed',
                        error = 'Container died unexpectedly. Click Retry to restart.',
                        completed_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), job['id']))
                orphan_count += 1
                print(f"Marked orphan converting job {job['id']} as failed")

        if orphan_count > 0:
            conn.commit()
            print(f"Cleaned up {orphan_count} orphan jobs")


# ============ Job Queue Management ============

def is_job_running():
    """Check if any job is currently converting."""
    with get_db() as conn:
        result = conn.execute('''
            SELECT COUNT(*) FROM jobs
            WHERE status IN ('converting', 'converting PDF', 'converting to audio')
        ''').fetchone()
        return result[0] > 0


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
    """Start the next queued job if no job is currently running."""
    if is_queue_paused():
        app.logger.info("Queue is paused; not starting queued jobs")
        return False
    if is_job_running():
        return False

    job = get_next_queued_job()
    if not job:
        return False

    # Start conversion thread
    thread = threading.Thread(
        target=convert_book,
        args=(job['id'], job['input_filename'], job['output_dirname'],
              job['voice'], job.get('is_pdf', False))
    )
    thread.daemon = True
    thread.start()
    app.logger.info(f"Started next queued job: {job['id']}")
    return True


# ============ Auto-Retry Logic ============

def handle_job_failure(job_id, error_type, error_msg):
    """Handle job failure with auto-retry logic.

    Auto-retries jobs that failed due to container_died or timeout errors,
    up to MAX_RETRY_COUNT times with exponential backoff.

    Args:
        job_id: The job ID
        error_type: Type of failure ('container_died', 'timeout', 'other')
        error_msg: Error message to store

    Returns:
        True if job was queued for retry, False if marked as permanently failed
    """
    import time as time_module

    job = get_job(job_id)
    if not job:
        return False

    retry_count = job.get('retry_count', 0)

    # Only auto-retry recoverable errors
    if retry_count < MAX_RETRY_COUNT and error_type in ('container_died', 'timeout'):
        # Calculate backoff delay
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

        # Schedule retry after delay
        def delayed_retry():
            time_module.sleep(delay)
            start_next_queued_job()

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
        return False


# ============ Watchdog Thread ============

def watchdog_loop():
    """Background thread to monitor job health.

    Runs every 60 seconds and checks for:
    - Jobs running longer than 2x their ETA
    - Jobs with dead containers

    Stalled jobs are marked as failed and may be auto-retried.
    """
    import time as time_module

    while True:
        time_module.sleep(60)  # Check every minute

        try:
            with get_db() as conn:
                active_jobs = conn.execute('''
                    SELECT id, container_name, started_at, eta_minutes, book_name
                    FROM jobs
                    WHERE status IN ('converting', 'converting PDF', 'converting to audio')
                ''').fetchall()

                for job in active_jobs:
                    job_id = job['id']
                    container_name = job['container_name']
                    container_running = check_container_running(container_name)

                    if not container_running:
                        if finalize_completed_job_if_outputs_exist(job_id):
                            continue
                        app.logger.warning(f"Watchdog: Job {job_id} ({job['book_name'][:30]}) container died, handling failure")
                        handle_job_failure(job_id, 'container_died', 'Container died unexpectedly (detected by watchdog)')
                        continue

                    eta_minutes = job['eta_minutes']
                    started_at = job['started_at']
                    if eta_minutes and eta_minutes > 0 and started_at:
                        elapsed = (datetime.now() - datetime.fromisoformat(job['started_at'])).total_seconds() / 60
                        if elapsed > (eta_minutes * 2):
                            app.logger.warning(
                                f"Watchdog: Job {job_id} ({job['book_name'][:30]}) running {elapsed:.0f}min, "
                                f"exceeds 2x ETA of {eta_minutes}min - still processing"
                            )

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


def copy_to_audiobookshelf(output_dir: Path, book_name: str) -> bool:
    """Copy completed audiobook to Audiobookshelf library via SSH."""
    if not AUDIOBOOKSHELF_DIR:
        return False

    try:
        dest = f"dave@docker-vm:{AUDIOBOOKSHELF_DIR}/{book_name}"
        ssh_opts = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -F /dev/null -i /root/.ssh/id_ed25519'
        cmd = ['rsync', '-av', '-e', ssh_opts, f'{output_dir}/', dest]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            app.logger.info(f"Copied {book_name} to Audiobookshelf")
            return True
        else:
            app.logger.error(f"Failed to copy to Audiobookshelf: {result.stderr}")
            return False
    except Exception as e:
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
            ['docker', 'logs', container_name],
            capture_output=True, text=True, timeout=5
        )
        logs = result.stderr + result.stdout

        # Parse total chapters
        chapters_match = re.search(r'Chapters count: (\d+)', logs)
        total_chapters = int(chapters_match.group(1)) if chapters_match else None

        # Parse current chapter being processed
        chapter_matches = re.findall(r'Processing chapter (\d+): (\w+)', logs)
        current_chapter = None
        current_chapter_name = None
        if chapter_matches:
            current_chapter = int(chapter_matches[-1][0])
            current_chapter_name = chapter_matches[-1][1].replace('_', ' ')

        # Count completed chapters
        completed = len(re.findall(r'Converted chapter \d+', logs))

        # Calculate progress and ETA
        progress_percent = None
        eta_minutes = None
        if total_chapters and current_chapter:
            progress_percent = int((completed / total_chapters) * 100)

            # Get elapsed time and calculate ETA based on actual progress
            job = get_job(job_id)
            if job and job.get('started_at') and completed > 0:
                started = datetime.fromisoformat(job['started_at'])
                elapsed = (datetime.now() - started).total_seconds()
                time_per_chapter = elapsed / completed
                remaining_chapters = total_chapters - completed
                eta_minutes = int((remaining_chapters * time_per_chapter) / 60)

        # Update job - only include eta_minutes if we calculated it (preserve initial estimate)
        update_kwargs = {
            'total_chapters': total_chapters,
            'current_chapter': current_chapter,
            'current_chapter_name': current_chapter_name,
            'progress_percent': progress_percent,
        }
        if eta_minutes is not None:
            update_kwargs['eta_minutes'] = eta_minutes
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
    update_job(job_id, status='converting', started_at=datetime.now().isoformat())

    host_input_path = f"{HOST_UPLOAD_DIR}/{input_filename}"
    host_output_dir = f"{HOST_OUTPUT_DIR}/{output_dirname}"
    local_input_path = UPLOAD_DIR / input_filename
    epub_path = local_input_path

    try:
        # PDF conversion
        if is_pdf:
            update_job(job_id, status='converting PDF')
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
                return

            host_input_path = host_epub_path
            epub_path = UPLOAD_DIR / epub_filename
            update_job(job_id, status='converting to audio')

        # Calculate timeout and initial ETA using learning algorithm
        char_count = estimate_epub_size(epub_path)
        timeout_seconds = calculate_timeout(char_count)
        job = get_job(job_id)
        tts_engine = job.get('tts_engine', 'kokoro') if job else 'kokoro'
        file_type = 'pdf' if is_pdf else 'epub'
        initial_eta = estimate_eta_minutes(voice, tts_engine, file_type, char_count)
        update_job(job_id, char_count=char_count, timeout_minutes=timeout_seconds // 60, eta_minutes=initial_eta)
        app.logger.info(f"Book has ~{char_count:,} chars, ETA {initial_eta} min, timeout {timeout_seconds // 60} min")

        # Generate unique container name
        container_name = f"audiobook-{job_id}"
        update_job(job_id, container_name=container_name)
        remove_stale_container(container_name)

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
        else:
            # Kokoro (default)
            tts_base_url = 'http://kokoro-tts:8880/v1'
            tts_model = 'kokoro'

        # Run conversion
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
            '--no_prompt'
        ]

        # Add chapter selection if specified
        if job and job.get('start_chapter'):
            cmd.extend(['--chapter_start', str(job['start_chapter'])])
        if job and job.get('end_chapter'):
            cmd.extend(['--chapter_end', str(job['end_chapter'])])

        app.logger.info(f"Running conversion: {' '.join(cmd)}")

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

        # Check results
        output_path = Path(f"/data/audiobooks/{output_dirname}")
        output_files = list(output_path.glob('*.mp3')) if output_path.exists() else []

        if process.returncode == 0 and output_files:
            # Rename files to human-readable format
            job = get_job(job_id)
            rename_output_files(output_path, job['book_name'])

            # Re-count files after renaming
            output_files = list(output_path.glob('*.mp3'))

            # Sync to Audiobookshelf
            synced = copy_to_audiobookshelf(output_path, job['book_name'])

            update_job(job_id,
                status='completed',
                file_count=len(output_files),
                progress_percent=100,
                synced_to_abs=synced,
                completed_at=datetime.now().isoformat()
            )
            app.logger.info(f"Job {job_id} completed with {len(output_files)} files")

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

            # Check if this looks like a container death (retryable)
            if 'killed' in error_msg.lower() or 'died' in error_msg.lower() or 'oom' in error_msg.lower():
                retried = handle_job_failure(job_id, 'container_died', error_msg)
            else:
                # Other errors - not auto-retried
                update_job(job_id, status='failed', error=error_msg, completed_at=datetime.now().isoformat())
                retried = False

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
        retried = handle_job_failure(job_id, 'timeout', error_msg)

        # Send Telegram notification if NOT being retried
        if not retried:
            job = get_job(job_id)
            if job and job.get('notify_telegram'):
                send_telegram_notification(job, success=False)

    except Exception as e:
        update_job(job_id, status='failed', error=str(e), completed_at=datetime.now().isoformat())
        app.logger.error(f"Job {job_id} exception: {e}")
    finally:
        # Start next queued job (one at a time queue system)
        start_next_queued_job()


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
        'queue_rank': next_queue_rank()
    }
    save_job(job)

    # Start conversion only if no other job is running (one at a time)
    if not is_job_running():
        thread = threading.Thread(
            target=convert_book,
            args=(job_id, input_filename, output_dirname, voice, is_pdf)
        )
        thread.daemon = True
        thread.start()
        app.logger.info(f"Started job {job_id} immediately (no queue)")
    else:
        app.logger.info(f"Job {job_id} added to queue (another job is running)")

    return jsonify({'job_id': job_id, 'status': 'queued'})


@app.route('/api/jobs')
def list_jobs():
    """List all conversion jobs."""
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
        start_next_queued_job()
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

    start_next_queued_job()
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
    """Return tail logs for the job container."""
    job = get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    container_name = (job.get('container_name') or '').strip()
    if not container_name:
        return jsonify({'logs': '', 'container': None})
    if not re.match(r'^[a-zA-Z0-9_.-]+$', container_name):
        return jsonify({'error': 'Invalid container name'}), 400

    tail = request.args.get('tail', '120')
    try:
        tail = max(10, min(500, int(tail)))
    except Exception:
        tail = 120

    try:
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(tail), container_name],
            capture_output=True, text=True, timeout=8
        )
        logs = (result.stdout or '') + (result.stderr or '')
        return jsonify({'container': container_name, 'logs': logs[-15000:]})
    except Exception as e:
        return jsonify({'container': container_name, 'logs': '', 'error': str(e)}), 500


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
        'jobs': by_status,
        'docker': docker_summary
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

    # Start conversion only if no other job is running (one at a time)
    if not is_job_running():
        thread = threading.Thread(
            target=convert_book,
            args=(job_id, job['input_filename'], job['output_dirname'], job['voice'], job['is_pdf'])
        )
        thread.daemon = True
        thread.start()
        app.logger.info(f"Started retry job {job_id} immediately")
    else:
        app.logger.info(f"Retry job {job_id} added to queue")

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

    synced = copy_to_audiobookshelf(output_dir, job['book_name'])
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
                title = file_path.stem
                title_lower = title.lower()

                # Check job status
                job_info = job_status_map.get(title_lower, {'status': 'available', 'progress': 0})

                books.append({
                    'title': title,
                    'path': str(file_path),
                    'format': ext.lstrip('.'),
                    'size': file_path.stat().st_size,
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
        'tts_engine': tts_engine,
        'status': 'queued',
        'created_at': datetime.now().isoformat(),
        'input_filename': input_filename,
        'output_dirname': output_dirname,
        'is_pdf': is_pdf,
        'start_chapter': None,
        'end_chapter': None,
        'notify_telegram': notify_telegram,
        'queue_rank': next_queue_rank()
    }
    save_job(job)

    # Start conversion only if no other job is running (one at a time)
    if not is_job_running():
        thread = threading.Thread(
            target=convert_book,
            args=(job_id, input_filename, output_dirname, voice, is_pdf)
        )
        thread.daemon = True
        thread.start()
        app.logger.info(f"Started library job {job_id} immediately")
    else:
        app.logger.info(f"Library job {job_id} added to queue")

    return jsonify({'job_id': job_id, 'status': 'queued'})


# Initialize database on startup
init_db()

# Clean up any orphan jobs from previous runs
cleanup_orphan_jobs()

# Reattach monitors for jobs already running in Docker
resume_inflight_jobs()

# Start watchdog thread to monitor job health
start_watchdog()

# Continue queued work after restart (if nothing is currently running)
start_next_queued_job()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8881, debug=True)
