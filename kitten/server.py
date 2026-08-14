"""CPU-only OpenAI-compatible wrapper for KittenTTS 0.8.1.

Uses the official ``KittenTTS(...).generate(text, voice=...)`` interface and
exposes exactly the eight presets documented for the 0.8.1 release.
"""
import io
import os
import subprocess
import threading

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel


VOICES = ("Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo")
VOICE_MAP = {name.lower(): name for name in VOICES}
MODEL_ID = "KittenML/kitten-tts-mini-0.8"
SAMPLE_RATE = 24000

app = FastAPI()
_lock = threading.Lock()
_model = None


class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str
    response_format: str = "mp3"


def _voice_name(voice_id: str) -> str:
    name = voice_id.removeprefix("kitten_").lower()
    if name not in VOICE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown Kitten voice: {voice_id}")
    return VOICE_MAP[name]


def _get_model():
    global _model
    if _model is None:
        from kittentts import KittenTTS
        # PyTorch requires this before eager/JIT/autograd work. Bounding
        # intra-op threads avoids oversubscribing the shared product host:
        # https://docs.pytorch.org/docs/stable/generated/torch.set_num_threads.html
        torch.set_num_threads(int(os.environ.get("KITTEN_THREADS", "4")))
        _model = KittenTTS(MODEL_ID)
    return _model


def _wav_bytes(audio) -> bytes:
    out = io.BytesIO()
    sf.write(out, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return out.getvalue()


def _encode(wav: bytes, output_format: str) -> tuple[bytes, str]:
    if output_format.lower() == "wav":
        return wav, "audio/wav"
    if output_format.lower() != "mp3":
        raise HTTPException(status_code=400, detail="response_format must be mp3 or wav")
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3", "-b:a", "192k", "pipe:1"],
        input=wav, capture_output=True, check=False,
    )
    if proc.returncode or not proc.stdout:
        raise HTTPException(status_code=500, detail="ffmpeg MP3 encoding failed")
    return proc.stdout, "audio/mpeg"


@app.get("/health")
def health():
    return {
        "status": "ok", "engine": "KittenTTS", "version": "0.8.1",
        "model": MODEL_ID, "device": "cpu", "cuda_available": False,
        "voices": list(VOICES), "model_loaded": _model is not None,
    }


@app.get("/v1/audio/voices")
def voices():
    return {"voices": [{"id": f"kitten_{name.lower()}"} for name in VOICES]}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="input must not be empty")
    name = _voice_name(req.voice)
    with _lock:
        audio = _get_model().generate(text, voice=name)
        payload, media_type = _encode(_wav_bytes(audio), req.response_format)
    return Response(payload, media_type=media_type)
