"""Private Marcus API contract and the pinned CPU dependency export."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient


def _load(name):
    path = Path(__file__).resolve().parents[1] / "tontaube" / f"{name}.py"
    spec = spec_from_file_location(f"tontaube_{name}", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load("server")


def test_stock_marcus_recipe_and_binary_formats(monkeypatch):
    wav = b"RIFF" + b"1234WAVE" + bytes(40)
    from base64 import b64encode

    def native(path, *, timeout, payload=None):
        if path == "/readyz":
            return {"status": "ready"}
        assert path == "/predict" and timeout == server.NATIVE_TIMEOUT_S
        assert payload == {
            "text": "A short sentence.", "language": "english",
            "tag": "audiobook", "format": "wav", "seed": 42,
        }
        return {"audio_b64": b64encode(wav).decode()}

    monkeypatch.setattr(server.app.state, "native", Mock(poll=lambda: None), raising=False)
    monkeypatch.setattr(server, "_native_json", native)
    monkeypatch.setattr(server, "_encode_mp3", lambda audio: b"id3" if audio == wav else b"")
    client = TestClient(server.app)
    assert client.get("/v1/audio/voices").json() == {"voices": [{"id": server.VOICE_ID}]}
    payload = {"input": "A short sentence.", "voice": server.VOICE_ID, "seed": 12345}
    response = client.post("/v1/audio/speech", json={**payload, "response_format": "wav"})
    assert response.status_code == 200 and response.content == wav
    assert response.headers["content-type"] == "audio/wav"
    response = client.post("/v1/audio/speech", json=payload)
    assert response.status_code == 200 and response.content == b"id3"
    assert response.headers["content-type"] == "audio/mpeg"


def test_unavailable_and_unsupported_requests_do_not_render(monkeypatch):
    monkeypatch.setattr(server.app.state, "native", Mock(poll=lambda: 1), raising=False)
    call = Mock()
    monkeypatch.setattr(server, "_native_json", call)
    client = TestClient(server.app)
    assert client.get("/v1/audio/voices").status_code == 503
    payload = {"input": "A sentence.", "voice": server.VOICE_ID}
    assert client.post("/v1/audio/speech", json=payload).status_code == 503
    for invalid in ({"voice": "other"}, {"speed": 1.5}, {"voice_audio_b64": "YWJj"},
                    {"input": "   "}, {"response_format": "opus"}):
        assert client.post("/v1/audio/speech", json={**payload, **invalid}).status_code == 422
    call.assert_not_called()


def test_cpu_export_preserves_hashes_and_skips_gpu_requirements():
    dependencies = _load("lite_requirements")
    source = (
        "torch==2.9.1 \\\n    --hash=sha256:gpu-wheel\n"
        "nvidia-cutlass-dsl==1.2.3 \\\n    --hash=sha256:gpu-only\n"
        "torchaudio==2.9.1 \\\n    --hash=sha256:gpu-audio\n"
        "transformers==4.57.2 \\\n    --hash=sha256:unchanged\n"
        "vllm==0.16.0\n"
    )
    assert list(dependencies.lite_requirements(source)) == [
        "transformers==4.57.2 \\", "    --hash=sha256:unchanged",
    ]
