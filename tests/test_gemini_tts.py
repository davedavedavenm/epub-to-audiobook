import base64
import importlib.util
import io
import wave
from pathlib import Path

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gemini_tts_server', ROOT / 'gemini' / 'server.py')
gemini = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gemini)


class FakeResponse:
    def __init__(self, status=200, body=None, text=''):
        self.status_code = status
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


def test_adapter_is_pinned_to_developer_api_free_path():
    source = (ROOT / 'gemini' / 'server.py').read_text(encoding='utf-8')
    assert gemini.UPSTREAM_URL.startswith('https://generativelanguage.googleapis.com/')
    assert 'aiplatform.googleapis.com' not in source
    assert 'vertex' not in source.lower().replace('vertex route', '')
    assert 'batchGenerateContent' not in source
    assert gemini.MODEL_ID == 'gemini-3.1-flash-tts-preview'


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
    body = {
        'status': 'completed',
        'steps': [{
            'type': 'model_output',
            'content': [{
                'type': 'audio',
                'data': base64.b64encode(pcm).decode('ascii'),
                'mime_type': 'audio/l16',
                'sample_rate': 24000,
                'channels': 1,
            }],
        }],
    }
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(body=body)

    monkeypatch.setattr(gemini.requests, 'post', post)
    result = gemini._synth('Exact transcript.', 'Achernar')
    assert len(calls) == 1
    assert calls[0][0][0] == gemini.UPSTREAM_URL
    assert calls[0][1]['headers']['x-goog-api-key'] == 'free-project-key'
    assert calls[0][1]['json']['model'] == 'gemini-3.1-flash-tts-preview'
    assert calls[0][1]['json']['response_format'] == {'type': 'audio'}
    assert calls[0][1]['json']['generation_config']['speech_config'] == [
        {'voice': 'Achernar'}
    ]
    with wave.open(io.BytesIO(result), 'rb') as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 2400


def test_sdk_only_output_audio_field_is_not_mistaken_for_raw_rest(monkeypatch):
    """The official reference marks output_audio as SDK-added; accepting it
    here would regress the adapter back to the shape that discarded the first
    successful raw REST generation."""
    body = {'status': 'completed', 'output_audio': {'data': 'AAAA'}}
    with pytest.raises(HTTPException) as error:
        gemini._pcm_from_interaction(body)
    assert error.value.status_code == 502
    assert 'no inline audio' in error.value.detail


def test_multiple_documented_audio_blocks_are_concatenated():
    first = b'\x01\x00' * 3
    second = b'\x02\x00' * 2
    body = {
        'status': 'completed',
        'steps': [{
            'type': 'model_output',
            'content': [
                {'type': 'audio', 'mime_type': 'audio/l16',
                 'data': base64.b64encode(first).decode('ascii')},
                {'type': 'audio', 'mime_type': 'audio/l16',
                 'data': base64.b64encode(second).decode('ascii')},
            ],
        }],
    }
    assert gemini._pcm_from_interaction(body) == first + second


def test_quota_failure_is_returned_without_retry(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'free-project-key')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_ID', 'dedicated-free-project')
    monkeypatch.setenv('GEMINI_FREE_PROJECT_CONFIRMED', '1')
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return FakeResponse(429, {'error': {'message': 'Free quota exhausted'}})

    monkeypatch.setattr(gemini.requests, 'post', post)
    with pytest.raises(HTTPException) as error:
        gemini._synth('Exact transcript.', 'Achernar')
    assert error.value.status_code == 429
    assert 'Free quota exhausted' in error.value.detail
    assert len(calls) == 1


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
