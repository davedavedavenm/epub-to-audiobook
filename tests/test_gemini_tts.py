import base64
import importlib.util
import io
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from google.genai import errors as genai_errors


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gemini_tts_server', ROOT / 'gemini' / 'server.py')
gemini = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gemini)


class FakeInteractions:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


class FakeClient:
    def __init__(self, result=None, error=None):
        self.interactions = FakeInteractions(result=result, error=error)
        self.closed = False

    def close(self):
        self.closed = True


def test_adapter_is_pinned_to_developer_api_free_path():
    source = (ROOT / 'gemini' / 'server.py').read_text(encoding='utf-8')
    assert gemini.UPSTREAM_URL.startswith('https://generativelanguage.googleapis.com/')
    assert 'aiplatform.googleapis.com' not in source
    assert 'vertex' not in source.lower().replace('vertex route', '')
    assert 'batchGenerateContent' not in source
    assert gemini.MODEL_ID == 'gemini-3.1-flash-tts-preview'
    requirements = (ROOT / 'gemini' / 'requirements.txt').read_text(encoding='utf-8')
    assert 'google-genai==2.18.1' in requirements


def test_key_without_explicit_free_project_confirmation_is_refused(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'possibly-paid-project-key')
    monkeypatch.delenv('GEMINI_FREE_PROJECT_CONFIRMED', raising=False)
    with pytest.raises(HTTPException) as error:
        gemini._api_key()
    assert error.value.status_code == 503
    assert 'GEMINI_FREE_PROJECT_CONFIRMED=1' in error.value.detail


def test_one_request_returns_valid_24khz_mono_wav(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    pcm = b'\x00\x00' * 2400
    interaction = SimpleNamespace(
        output_audio=SimpleNamespace(data=base64.b64encode(pcm).decode('ascii'))
    )
    client = FakeClient(result=interaction)
    monkeypatch.setattr(gemini, '_client', lambda: client)
    result = gemini._synth('Exact transcript.', 'Achernar')
    assert len(client.interactions.calls) == 1
    call = client.interactions.calls[0]
    assert call['model'] == 'gemini-3.1-flash-tts-preview'
    assert call['response_format'] == {'type': 'audio'}
    assert call['generation_config']['speech_config'] == [
        {'voice': 'Achernar'}
    ]
    assert client.closed is True
    with wave.open(io.BytesIO(result), 'rb') as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 2400


def test_missing_sdk_output_audio_is_rejected(monkeypatch):
    client = FakeClient(result=SimpleNamespace(output_audio=None))
    monkeypatch.setattr(gemini, '_client', lambda: client)
    with pytest.raises(HTTPException) as error:
        gemini._synth('Exact transcript.', 'Achernar')
    assert error.value.status_code == 502
    assert 'output_audio' in error.value.detail


def test_official_sdk_client_has_exactly_one_attempt(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(gemini.genai, 'Client', factory)
    gemini._client()
    options = captured['http_options']
    assert options.retry_options.attempts == 1
    assert options.timeout == 300_000


def test_quota_failure_is_returned_without_retry(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    api_error = genai_errors.APIError(
        429, {'error': {'message': 'Free quota exhausted', 'status': 'RESOURCE_EXHAUSTED'}}
    )
    client = FakeClient(error=api_error)
    monkeypatch.setattr(gemini, '_client', lambda: client)
    with pytest.raises(HTTPException) as error:
        gemini._synth('Exact transcript.', 'Achernar')
    assert error.value.status_code == 429
    assert 'Free quota exhausted' in error.value.detail
    assert len(client.interactions.calls) == 1
    assert client.closed is True


def test_paid_or_unknown_model_is_rejected_before_synthesis(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    request = gemini.SpeechRequest(
        model='gemini-2.5-pro-tts', input='Hello.', voice='gemini_achernar'
    )
    with pytest.raises(HTTPException) as error:
        gemini.speech(request)
    assert error.value.status_code == 400


def test_input_cap_prevents_accidental_long_generation(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    request = gemini.SpeechRequest(
        model=gemini.MODEL_ID,
        input='x' * (gemini.MAX_INPUT_CHARS + 1),
        voice='gemini_achernar',
    )
    with pytest.raises(HTTPException) as error:
        gemini.speech(request)
    assert error.value.status_code == 413
