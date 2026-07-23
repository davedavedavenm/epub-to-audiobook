"""Smoke tests for the Flask API endpoints.

Uses the Flask test client — no server, no Docker, no TTS engines needed.
"""
import os
import sys
import json
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


def test_gpu_status(client):
    r = client.get('/api/gpu/status')
    assert r.status_code in (200, 403)


def test_convert_requires_body(client):
    r = client.post('/api/convert', data={}, content_type='multipart/form-data')
    assert r.status_code in (400, 422, 500)


def test_job_not_found(client):
    r = client.get('/api/jobs/nonexistent-id-12345/logs')
    assert r.status_code in (404, 200)
