import os
import sys
import uuid
import tempfile
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))

os.environ.setdefault('DB_PATH', os.path.join(tempfile.mkdtemp(), 'test.db'))
os.environ.setdefault('UPLOAD_DIR', tempfile.mkdtemp())
os.environ.setdefault('OUTPUT_DIR', tempfile.mkdtemp())
os.environ.setdefault('PREVIEWS_DIR', tempfile.mkdtemp())
os.environ.setdefault('LOG_DIR', tempfile.mkdtemp())
os.environ.setdefault('LIBRARY_DIR', tempfile.mkdtemp())
os.environ.setdefault('TOC_CACHE_DIR', tempfile.mkdtemp())
os.environ.setdefault('TRANSCRIPTS_DIR', tempfile.mkdtemp())
os.environ.setdefault('QUEUE_RUNNER_ENABLED', '0')

from app import (
    get_db,
    save_job,
    get_job,
    update_job,
    queued_job_count,
    running_job_count,
    cleanup_orphan_jobs,
)


def make_job(status='queued'):
    return {
        'id': uuid.uuid4().hex,
        'book_name': 'Test Book',
        'voice': 'af_bella',
        'tts_engine': 'kokoro',
        'status': status,
        'created_at': datetime.now().isoformat(),
        'input_filename': 'test.epub',
        'output_dirname': 'test-output',
    }


@pytest.fixture(autouse=True)
def clean_jobs():
    with get_db() as conn:
        conn.execute('DELETE FROM jobs')
        conn.commit()
    yield


def test_job_lifecycle():
    job = make_job('queued')
    save_job(job)

    assert get_job(job['id'])['status'] == 'queued'

    update_job(job['id'], status='converting')
    assert get_job(job['id'])['status'] == 'converting'

    update_job(job['id'], status='completed', completed_at=datetime.now().isoformat())
    assert get_job(job['id'])['status'] == 'completed'


def test_cancelled_job_stays_cancelled_after_recovery():
    job = make_job('cancelled')
    save_job(job)
    update_job(job['id'], status='cancelled')

    cleanup_orphan_jobs()

    assert get_job(job['id'])['status'] == 'cancelled'


def test_queue_counting():
    for status in ['queued', 'queued']:
        save_job(make_job(status))
    for status in ['converting', 'converting PDF', 'completed', 'failed', 'cancelled']:
        save_job(make_job(status))

    assert queued_job_count() == 2
    assert running_job_count() == 2


def test_cancel_wipes_partial_conversion_data(tmp_path):
    from pathlib import Path
    from app import _perform_cancel_job, OUTPUT_DIR

    job = make_job('converting')
    job['output_dirname'] = 'test_cancel_out'
    save_job(job)

    # Create dummy output directory
    out_dir = Path(OUTPUT_DIR) / 'test_cancel_out'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'chapter1.mp3').write_text('dummy audio')

    assert out_dir.exists()

    _perform_cancel_job(job['id'], wipe_data=True)

    assert get_job(job['id'])['status'] == 'cancelled'
    assert not out_dir.exists()

