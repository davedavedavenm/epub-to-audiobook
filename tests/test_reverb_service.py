import io
from unittest.mock import Mock

from fastapi.testclient import TestClient
import numpy as np
import soundfile as sf

from reverb import server


def test_stock_voice_only_appears_after_model_load(monkeypatch):
    failed_load = Mock(side_effect=RuntimeError('weights unavailable'))
    monkeypatch.setattr(server, 'load_model', failed_load)
    with TestClient(server.app) as client:
        assert client.get('/health').status_code == 503
        assert client.get('/v1/audio/voices').status_code == 503


def test_speech_passes_complete_input_without_altering_stock_defaults(monkeypatch):
    preset = object()
    audio = np.array([0.125, 0.25, 0.5, -0.25], dtype=np.float32)
    model = Mock(sample_rate=24000)
    model.generate.return_value = audio
    monkeypatch.setattr(server, 'load_model', lambda: (model, preset))
    text = 'A first paragraph.\n\nAn ending of which is'
    request = {'input': text, 'voice': server.VOICE_ID, 'response_format': 'wav'}

    with TestClient(server.app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/v1/audio/voices').json()['voices'][0]['id'] == server.VOICE_ID
        response = client.post('/v1/audio/speech', json=request)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'audio/wav'
        with sf.SoundFile(io.BytesIO(response.content)) as wav:
            assert wav.samplerate == 24000
            assert wav.comment == server.ATTRIBUTION
            np.testing.assert_array_equal(wav.read(dtype='float32'), audio)
        assert client.post('/v1/audio/speech', json={**request, 'voice': 'another_voice'}).status_code == 400
        assert client.post('/v1/audio/speech', json={**request, 'input': ' '}).status_code == 400
        assert client.post('/v1/audio/speech', json={**request, 'input': 'x' * 6001}).status_code == 422
        assert client.post('/v1/audio/speech', json={**request, 'response_format': 'opus'}).status_code == 400
        assert client.post('/v1/audio/speech', json={**request, 'speed': 1.1}).status_code == 400
        model.generate.assert_called_once_with(text, preset, language='en', seed=42)


def test_busy_reverb_reports_retry_without_synthesizing(monkeypatch):
    model = Mock()
    monkeypatch.setattr(server, 'load_model', lambda: (model, object()))
    with TestClient(server.app) as client, server._synthesis:
        response = client.post('/v1/audio/speech', json={'input': 'Test.', 'voice': server.VOICE_ID})
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '5'
    model.generate.assert_not_called()
