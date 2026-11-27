import hashlib
import io
import json
import threading
import wave
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock

import pytest

from zonos3 import server


def pcm_wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01\x10" * 4410)
    return output.getvalue()


def test_chunking_preserves_all_text_and_bounds_dense_input():
    text = "Dr. Carter narrated the opening.\n\n" + "word " * 340 + "of which is"
    chunks = server.split_text(text)
    assert "".join(chunks) == text
    assert len(chunks) > 1
    assert all(len(c) <= server.NATIVE_CHARS and len(c.split()) <= server.NATIVE_WORDS for c in chunks)
    assert chunks[-1].endswith("of which is")


def test_wav_assembly_uses_all_chunks(monkeypatch):
    raw = pcm_wav()
    native = Mock(return_value=raw)
    monkeypatch.setattr(server, "_native_wav", native)
    text = "A full sentence. " * 110 + "of which is"
    result = server._synthesize(text)
    chunks = [call.args[0] for call in native.call_args_list]
    assert "".join(chunks) == text
    with wave.open(io.BytesIO(result), "rb") as wav:
        assert wav.getparams()[:3] == server.PCM
        assert wav.getnframes() == 4410 * len(chunks) + (44100 // 4) * (len(chunks) - 1)
    with pytest.raises(ValueError, match="Truncated"):
        server._checked_frames(raw[:-2])


def test_http_voice_readiness_and_busy_contract(monkeypatch):
    native = Mock()
    native.poll.return_value = None
    synth = Mock(return_value=pcm_wav())
    monkeypatch.setattr(server, "_synthesize", synth)
    with server.SpeechServer(native, ("127.0.0.1", 0)) as http:
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}"
        request = {"voice": server.VOICE_ID, "input": " Exact input. ", "response_format": "wav"}

        def post(payload):
            return urlopen(Request(base + "/v1/audio/speech", json.dumps(payload).encode()), timeout=3)

        try:
            with urlopen(base + "/v1/audio/voices", timeout=3) as response:
                assert json.load(response) == {"voices": [{"id": server.VOICE_ID}]}
            with post(request) as response:
                assert response.headers["Content-Type"] == "audio/wav"
                assert response.read() == pcm_wav()
            with pytest.raises(HTTPError) as unknown:
                post({**request, "voice": "unknown"})
            assert unknown.value.code == 400
            with http.synth_slot, pytest.raises(HTTPError) as busy:
                post(request)
            assert busy.value.code == 429 and busy.value.headers["Retry-After"] == "5"
            native.poll.return_value = 1
            with pytest.raises(HTTPError) as unavailable:
                urlopen(base + "/v1/audio/voices", timeout=3)
            assert unavailable.value.code == 503
            synth.assert_called_once_with(request["input"])
        finally:
            http.shutdown()
            thread.join()


def test_custom_embedding_identity_and_native_mode(monkeypatch, tmp_path):
    embedding = b'\x93NUMPY' + b'float32 embedding'
    voice_id = 'zonos3_custom_custom_compact_' + hashlib.sha256(embedding).hexdigest()
    asset = tmp_path / f'{voice_id}.npy'
    asset.write_bytes(embedding)
    monkeypatch.setattr(server, 'REFERENCE_DIR', tmp_path)
    native = Mock(return_value=pcm_wav())
    monkeypatch.setattr(server, '_native_wav', native)
    process = Mock()
    process.poll.return_value = None
    with server.SpeechServer(process, ('127.0.0.1', 0)) as http:
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            req = Request(f'http://127.0.0.1:{http.server_port}/v1/audio/speech',
                          json.dumps({'voice': voice_id, 'input': 'Exact text.', 'response_format': 'wav'}).encode())
            with urlopen(req, timeout=3) as response:
                assert response.read() == pcm_wav()
            native.assert_called_once()
            assert native.call_args.args[2] == embedding
            asset.write_bytes(embedding + b'invalid')
            with pytest.raises(HTTPError) as invalid:
                urlopen(req, timeout=3)
            assert invalid.value.code == 400
        finally:
            http.shutdown()
            thread.join()
