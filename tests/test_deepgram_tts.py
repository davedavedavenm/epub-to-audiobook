import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tts_proxy'))

os.environ.setdefault('DB_PATH', os.path.join(tempfile.mkdtemp(), 'test.db'))
os.environ.setdefault('UPLOAD_DIR', tempfile.mkdtemp())
os.environ.setdefault('OUTPUT_DIR', tempfile.mkdtemp())
os.environ.setdefault('PREVIEWS_DIR', tempfile.mkdtemp())
os.environ.setdefault('LOG_DIR', tempfile.mkdtemp())
os.environ.setdefault('LIBRARY_DIR', tempfile.mkdtemp())
os.environ.setdefault('TOC_CACHE_DIR', tempfile.mkdtemp())
os.environ.setdefault('TRANSCRIPTS_DIR', tempfile.mkdtemp())
os.environ.setdefault('QUEUE_RUNNER_ENABLED', '0')

from app import VOICES, get_engine_url, text_profile_for_engine, engines_unconfigured
from proxy import _split_for_deepgram, DEEPGRAM_VOICE_MAP


def test_deepgram_voices_registered():
    expected_voices = [
        'deepgram_orion',
        'deepgram_orpheus',
        'deepgram_arcas',
        'deepgram_pandora',
        'deepgram_hyperion',
        'deepgram_angus'
    ]
    for v in expected_voices:
        assert v in VOICES, f"Expected voice {v} in VOICES"
        assert VOICES[v]['engine'] == 'deepgram'
        assert v in DEEPGRAM_VOICE_MAP, f"Expected {v} in DEEPGRAM_VOICE_MAP"


def test_deepgram_engine_url():
    url, model = get_engine_url('deepgram', 'job-test-123')
    assert 'job-test-123' in url or 'tts-proxy' in url
    assert model == 'deepgram'


def test_deepgram_text_profile():
    assert text_profile_for_engine('deepgram') == 'explicit'


def test_deepgram_credentials(monkeypatch):
    monkeypatch.delenv('DEEPGRAM_API_KEY', raising=False)
    unconf = engines_unconfigured()
    assert 'deepgram' in unconf
    assert 'Deepgram API key' in unconf['deepgram']

    monkeypatch.setenv('DEEPGRAM_API_KEY', 'test-key-123')
    unconf_configured = engines_unconfigured()
    assert 'deepgram' not in unconf_configured


def test_split_for_deepgram():
    short_text = "This is a short sentence."
    chunks = _split_for_deepgram(short_text, max_chars=400)
    assert chunks == [short_text]

    long_text = (
        "In the spring of nineteen ninety-seven, Apple was nine weeks from bankruptcy. "
        "Its CEO had been ousted, Steve Jobs had returned, the share price had fallen seventy-one percent, "
        "and the company was burning through one point two billion dollars a year. "
        "Few analysts at Goldman Sachs believed it would survive to see the year two thousand. "
        "What changed was not one decision, but a thousand small ones. "
        "Scott Forstall, Jony Ive, and a young engineer named Nguyen worked eighteen-hour days."
    )
    chunks = _split_for_deepgram(long_text, max_chars=150)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 200
    combined = " ".join(chunks)
    assert "Apple was nine weeks from bankruptcy" in combined
    assert "Scott Forstall" in combined
