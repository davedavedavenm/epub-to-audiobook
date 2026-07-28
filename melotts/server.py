"""Small OpenAI-compatible wrapper around the local MeloTTS English model."""

import io
import logging
import os
import subprocess
import threading

import numpy as np
import soundfile as sf
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("melotts-server")

VOICES = ("EN-Default", "EN-US", "EN-BR", "EN_INDIA", "EN-AU")
app = FastAPI()
_model = None
_generation_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        # g2p_en still auto-downloads the pre-NLTK-3.9 resource name. Current
        # NLTK requests the language-suffixed tagger instead, so seed both the
        # tagger and CMU dictionary in our persistent writable cache.
        import nltk

        nltk_dir = os.environ.get("NLTK_DATA", "/data/nltk")
        for resource in ("averaged_perceptron_tagger_eng", "cmudict"):
            nltk.download(resource, download_dir=nltk_dir, quiet=True)

        from melo.api import TTS

        log.info("loading MeloTTS English model on cpu")
        _model = TTS(language="EN", device="cpu")
        log.info("MeloTTS speakers: %s", list(_model.hps.data.spk2id.keys()))
    return _model


def _encode(audio: np.ndarray, sample_rate: int, fmt: str) -> tuple[bytes, str]:
    wav = io.BytesIO()
    sf.write(wav, audio, sample_rate, format="WAV")
    if fmt == "wav":
        return wav.getvalue(), "audio/wav"
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3", "-b:a", "128k", "pipe:1"],
        input=wav.getvalue(),
        capture_output=True,
        check=True,
    )
    return proc.stdout, "audio/mpeg"


class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = "EN-BR"
    response_format: str = "mp3"
    speed: float = 1.0


@app.get("/health")
def health():
    return {"status": "ok", "device": "cpu", "model_loaded": _model is not None, "voices": VOICES}


@app.get("/v1/audio/voices")
def voices():
    return {"voices": [{"id": voice} for voice in VOICES]}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if not req.input.strip():
        return JSONResponse({"error": "input is empty"}, status_code=400)
    if req.voice not in VOICES:
        return JSONResponse({"error": f"unknown voice {req.voice!r}"}, status_code=400)
    if not 0.5 <= req.speed <= 2.0:
        return JSONResponse({"error": "speed must be between 0.5 and 2.0"}, status_code=400)

    model = _get_model()
    speaker_id = model.hps.data.spk2id[req.voice]
    with _generation_lock:
        audio = model.tts_to_file(req.input, speaker_id, speed=req.speed, quiet=True)
    payload, media_type = _encode(audio, model.hps.data.sampling_rate, req.response_format.lower())
    return Response(content=payload, media_type=media_type)
