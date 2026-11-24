"""Expose only the stock Marcus recipe through the internal speech API."""
from base64 import b64decode
from binascii import Error as Base64Error
from contextlib import asynccontextmanager
from http.client import HTTPException as TransportError
import json
import logging
import os
import subprocess
import sys
from threading import Lock
from typing import Literal
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

VOICE_ID = "tontaube_marcus_audition"
NATIVE = "http://127.0.0.1:18082"
NATIVE_TIMEOUT_S = 890
MAX_INPUT_CHARS = 4096
LOG = logging.getLogger("uvicorn.error")
_SPEECH_SLOT = Lock()
_NATIVE_HTTP = build_opener(ProxyHandler({}))


@asynccontextmanager
async def lifespan(app):
    settings = {
        **os.environ,
        "TTS_BACKEND": "lite",
        "LITE_DEVICE": "cpu",
        "TTS_MODEL_REPO_ID": "TontaubeAI/TontaubeV1.1-int4",
        "TTS_MODEL_REVISION": "2cff8331a357cdd50b05c823f5172eaa3ac6c121",
        "VIBEVOICE_MODEL_PATH": (
            "/data/cache/tontaube/vibevoice-acoustic-tokenizer/"
            "c00898d257e6b46004e3e2866a47534085fb685a"
        ),
        "DEFAULT_VOICE": "/opt/tontaube/voices/samples/Marcus.mp3",
        "ENABLE_VERBALIZATION": "0",
        "MOSSFORMER2_POSTPROCESS_DEFAULT": "0",
        "MAX_INFLIGHT_REQUESTS": "1",
    }
    native = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "serve", "--host", "127.0.0.1", "--port", "18082"],
        cwd="/opt/tontaube",
        env=settings,
    )
    app.state.native = native
    try:
        yield
    finally:
        if native.poll() is None:
            native.terminate()
            try:
                native.wait(timeout=12)
            except subprocess.TimeoutExpired:
                native.kill()
                native.wait()


app = FastAPI(
    lifespan=lifespan,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "tts-1"
    input: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    voice: Literal["tontaube_marcus_audition"]
    response_format: Literal["mp3", "wav"] = "mp3"
    speed: Literal[1.0] = 1.0
    # OpenAI-style callers may send a seed. The stock route always uses 42.
    seed: int | None = None

    @field_validator("input")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("input must contain speech text")
        return value


def _native_json(path, *, timeout, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(NATIVE + path, data, {"Content-Type": "application/json"})
    with _NATIVE_HTTP.open(request, timeout=timeout) as response:
        return json.load(response)


def _require_ready():
    native = getattr(app.state, "native", None)
    if native is None or native.poll() is not None:
        raise HTTPException(503, "Marcus runtime is unavailable")
    try:
        if _native_json("/readyz", timeout=2).get("status") == "ready":
            return
    except (OSError, TransportError, ValueError, AttributeError):
        pass
    raise HTTPException(503, "Marcus runtime is loading")


@app.get("/v1/audio/voices")
def voices():
    _require_ready()
    return {"voices": [{"id": VOICE_ID}]}


def _synthesize(input_text):
    try:
        upstream = _native_json(
            "/predict",
            timeout=NATIVE_TIMEOUT_S,
            payload={"text": input_text, "language": "english", "tag": "audiobook",
                     "format": "wav", "seed": 42},
        )
        audio = b64decode(upstream["audio_b64"], validate=True)
        if len(audio) <= 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("invalid native WAV")
        return audio
    except (TimeoutError, HTTPError) as exc:
        LOG.warning("Marcus native synthesis failed: %s", type(exc).__name__)
        status = 504 if isinstance(exc, TimeoutError) else 502
        raise HTTPException(status, "Marcus could not complete synthesis") from exc
    except (OSError, TransportError, Base64Error, KeyError, TypeError, ValueError) as exc:
        LOG.warning("Marcus native synthesis failed: %s", type(exc).__name__)
        raise HTTPException(502, "Marcus did not return a valid WAV") from exc


def _encode_mp3(audio):
    try:
        encoded = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-i", "pipe:0",
             "-c:a", "libmp3lame", "-b:a", "96k", "-f", "mp3", "pipe:1"],
            input=audio,
            capture_output=True,
            check=True,
            timeout=30,
        )
        if encoded.stdout:
            return encoded.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("Marcus MP3 encoding failed: %s", type(exc).__name__)
    raise HTTPException(502, "Marcus MP3 encoding failed")


@app.post("/v1/audio/speech")
def speech(request: SpeechRequest):
    _require_ready()
    if not _SPEECH_SLOT.acquire(blocking=False):
        raise HTTPException(503, "Marcus is already rendering a passage")
    try:
        audio = _synthesize(request.input)
        if request.response_format == "wav":
            return Response(audio, media_type="audio/wav")
        return Response(_encode_mp3(audio), media_type="audio/mpeg")
    finally:
        _SPEECH_SLOT.release()
