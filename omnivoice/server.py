"""OpenAI-compatible CPU service for OmniVoice voice-design accents."""

import io
import logging
import os
import subprocess
import threading

import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("omnivoice-server")

DEVICE = os.environ.get("OMNIVOICE_DEVICE", "cpu")
DTYPE_NAME = os.environ.get("OMNIVOICE_DTYPE", "float32")
DTYPE = getattr(torch, DTYPE_NAME)
MODEL_ID = os.environ.get("OMNIVOICE_MODEL", "k2-fsa/OmniVoice")
NUM_STEP = int(os.environ.get("OMNIVOICE_NUM_STEP", "32"))
torch.set_num_threads(int(os.environ.get("OMNIVOICE_THREADS", "6")))

VOICE_INSTRUCTIONS = {
    # OmniVoice validates every comma-separated item against a fixed upstream
    # vocabulary. Keep these exact: prose descriptions are rejected, not merely
    # ignored (the valid list lives in docs/voice-design.md upstream).
    "british-female": "female, young adult, british accent",
    "british-male": "male, middle-aged, british accent",
    "australian-female": "female, young adult, australian accent",
    "australian-male": "male, middle-aged, australian accent",
    "indian-female": "female, young adult, indian accent",
    "indian-male": "male, middle-aged, indian accent",
}

app = FastAPI()
_model = None
_generation_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        from omnivoice.models.omnivoice import OmniVoice

        log.info("loading %s on %s as %s", MODEL_ID, DEVICE, DTYPE_NAME)
        _model = OmniVoice.from_pretrained(MODEL_ID, device_map=DEVICE, dtype=DTYPE)
        log.info("OmniVoice loaded at %s Hz", _model.sampling_rate)
    return _model


def _encode(audio, sample_rate: int, fmt: str) -> tuple[bytes, str]:
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
    voice: str = "british-female"
    response_format: str = "mp3"
    speed: float = 1.0


@app.get("/health")
def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "dtype": DTYPE_NAME,
        "model_loaded": _model is not None,
        "voices": list(VOICE_INSTRUCTIONS),
    }


@app.get("/v1/audio/voices")
def voices():
    return {"voices": [{"id": voice} for voice in VOICE_INSTRUCTIONS]}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    if not req.input.strip():
        return JSONResponse({"error": "input is empty"}, status_code=400)
    instruction = VOICE_INSTRUCTIONS.get(req.voice)
    if instruction is None:
        return JSONResponse({"error": f"unknown voice {req.voice!r}"}, status_code=400)
    if not 0.5 <= req.speed <= 2.0:
        return JSONResponse({"error": "speed must be between 0.5 and 2.0"}, status_code=400)

    model = _get_model()
    with _generation_lock:
        audio = model.generate(
            text=req.input,
            language="English",
            instruct=instruction,
            speed=req.speed,
            num_step=NUM_STEP,
            normalize_text=False,
        )[0]
    payload, media_type = _encode(audio, model.sampling_rate, req.response_format.lower())
    return Response(content=payload, media_type=media_type)
