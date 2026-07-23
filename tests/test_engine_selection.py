import os
import sys
import tempfile

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

import app as appmod
from app import get_engine_url
from tts_preprocess import normalize_text_for_tts

JOB_ID = 'testjob123'


def _proxy_or(fallback):
    return f"{appmod.TTS_PROXY_URL}/j/{JOB_ID}/v1" if appmod.TTS_PROXY_URL else fallback


def test_engine_url_kokoro():
    url, model = get_engine_url('kokoro', JOB_ID)
    assert url == _proxy_or(appmod.KOKORO_URL)
    assert model == 'kokoro'


def test_engine_url_piper():
    url, model = get_engine_url('piper', JOB_ID)
    assert url == _proxy_or('http://piper-tts:8000/v1')
    assert model == 'tts-1'


def test_engine_url_chatterbox():
    url, model = get_engine_url('chatterbox', JOB_ID)
    assert url == appmod.CHATTERBOX_URL
    assert model == 'tts-1'


def test_engine_url_tada():
    url, model = get_engine_url('tada', JOB_ID)
    assert url == appmod.TADA_URL
    assert model == 'tts-1'


def test_engine_url_edge():
    url, model = get_engine_url('edge', JOB_ID)
    assert url == _proxy_or(f'http://tts-proxy:8882/j/{JOB_ID}/v1')
    assert model == 'tts-1'


def test_modern_skips_number_spelling_but_keeps_acronym_spacing():
    out = normalize_text_for_tts('The U.S. paid $50 for 5000 units.', modern=True)
    assert 'U S' in out
    assert '$50' in out
    assert 'fifty dollars' not in out
    assert '5000' in out


def test_legacy_spells_numbers_and_expands_abbreviations():
    out = normalize_text_for_tts('Dr. Smith paid $50 in the U.S.', modern=False)
    assert 'Doctor Smith' in out
    assert 'fifty dollars' in out
    assert 'U S' in out


def test_years_spelled_for_both_modern_and_legacy():
    for modern in (True, False):
        out = normalize_text_for_tts('It happened in 1962 and 2003.', modern=modern)
        assert 'nineteen sixty-two' in out
        assert '1962' not in out
        assert 'two thousand three' in out
        assert '2003' not in out
