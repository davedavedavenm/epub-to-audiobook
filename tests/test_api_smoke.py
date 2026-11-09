"""Smoke tests for the Flask API endpoints.

Uses the Flask test client — no server, no Docker, no TTS engines needed.
"""
import os
import sys
import tempfile
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

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get('/api/health')
    assert r.status_code in (200, 503)
    data = r.get_json()
    assert 'webapp' in data or 'status' in data


def test_version(client):
    r = client.get('/api/version')
    assert r.status_code == 200
    data = r.get_json()
    assert 'version' in data


def test_voices(client):
    r = client.get('/api/voices')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, (list, dict))


def test_jobs_list(client):
    r = client.get('/api/jobs')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)


def test_queue_status(client):
    r = client.get('/api/queue/status')
    assert r.status_code == 200
    data = r.get_json()
    assert 'queued' in data or 'running' in data or 'paused' in data


def test_settings_get(client):
    r = client.get('/api/settings')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)


def test_library_list(client):
    r = client.get('/api/library')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, (list, dict))


def test_library_dedup_and_clean_titles(client, tmp_path, monkeypatch):
    import app as appmod

    lib_dir = tmp_path / 'library'
    up_dir = tmp_path / 'uploads'
    lib_dir.mkdir()
    up_dir.mkdir()
    monkeypatch.setattr(appmod, 'LIBRARY_DIR', lib_dir)
    monkeypatch.setattr(appmod, 'UPLOAD_DIR', up_dir)

    # Multi-format bundle (should collapse to 1 entry preferring .epub)
    (lib_dir / 'Chuck Klosterman - The Nineties- A Book.epub').write_bytes(b'epub-bytes')
    (lib_dir / 'Chuck Klosterman - The Nineties- A Book.azw3').write_bytes(b'azw3-bytes')
    (lib_dir / 'Chuck Klosterman - The Nineties- A Book.mobi').write_bytes(b'mobi-bytes')

    # Tag & case variants (should collapse to 1 entry with cleaned title)
    (lib_dir / 'Helen Czerski - Storm in a Teacup- The Physics of Everyday Life (retail) (epub).epub').write_bytes(b'12345')
    (lib_dir / 'Helen Czerski - Storm in a Teacup (v5.0) (US).epub').write_bytes(b'123')

    # Series volumes (must NOT collapse into each other)
    (lib_dir / 'Zach Bohannon - Empty Bodies (Book 1) (retail).epub').write_bytes(b'b1')
    (lib_dir / 'Zach Bohannon - Empty Bodies (Book 2) (retail).epub').write_bytes(b'b2')
    (lib_dir / 'Will Durant - The Age of Napoleon (The Story of Civilization, Volume XI).epub').write_bytes(b'v11')
    (lib_dir / 'Will Durant - The Age of Reason Begins (The Story of Civilization, Volume VII).epub').write_bytes(b'v7')

    # Standalone grabbed book in uploads vs per-job upload copy
    (up_dir / 'Zeinab Badawi - An African History of Africa (retail) (epub).epub').write_bytes(b'badawi')
    (up_dir / 'a1b2c3d4_Internal_Job_Copy.epub').write_bytes(b'jobcopy')
    (up_dir / 'Some_Book_tts.epub').write_bytes(b'ttscopy')

    r = client.get('/api/library')
    assert r.status_code == 200
    books = r.get_json()
    titles = [b['title'] for b in books]

    # Klosterman appears once as epub
    klosterman = [b for b in books if 'Klosterman' in b['title']]
    assert len(klosterman) == 1
    assert klosterman[0]['format'] == 'epub'

    # Czerski appears once without (retail) (epub) junk tags
    czerski = [b for b in books if 'Czerski' in b['title']]
    assert len(czerski) == 1
    assert '(retail)' not in czerski[0]['title'].lower()
    assert '(epub)' not in czerski[0]['title'].lower()

    # Series books remain distinct
    bohannon = [b for b in books if 'Bohannon' in b['title']]
    assert len(bohannon) == 2
    durant = [b for b in books if 'Durant' in b['title']]
    assert len(durant) == 2

    # Standalone grabbed book in UPLOAD_DIR is surfaced, internal job copies are excluded
    assert any('Badawi' in t for t in titles)
    assert not any('Internal' in t for t in titles)
    assert not any('_tts' in t for t in titles)


def test_gpu_status(client):
    r = client.get('/api/gpu/status')
    assert r.status_code in (200, 403)


def test_convert_requires_body(client):
    r = client.post('/api/convert', data={}, content_type='multipart/form-data')
    assert r.status_code in (400, 422, 500)


def test_job_not_found(client):
    r = client.get('/api/jobs/nonexistent-id-12345/logs')
    assert r.status_code in (404, 200)


def test_library_batch_convert(client):
    r_empty = client.post('/api/library/batch-convert', json={
        'paths': [],
        'voice_option': 'default',
        'tts_engine_option': 'keep'
    })
    assert r_empty.status_code == 400

    r_valid = client.post('/api/library/batch-convert', json={
        'paths': ['non_existent_book.epub'],
        'voice_option': 'default',
        'tts_engine_option': 'keep'
    })
    assert r_valid.status_code == 200
    data = r_valid.get_json()
    assert data['status'] == 'ok'
    assert data['enqueued_count'] == 0

    r_mismatched = client.post('/api/library/batch-convert', json={
        'paths': ['non_existent_book.epub'],
        'voice_option': 'default',
        'tts_engine_option': 'kokoro'
    })
    assert r_mismatched.status_code == 400
    assert 'Choose a narrator' in r_mismatched.get_json()['error']

