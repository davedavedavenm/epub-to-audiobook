"""CPU-only OpenAI-compatible wrapper for Pocket TTS 2.1.

The synthesis calls mirror Kyutai's official API: ``TTSModel.load_model()``,
``get_state_for_audio_prompt()`` and ``generate_audio()``. Only the English
catalogue documented upstream is exposed. Unknown voices fail closed.
"""
import io
import os
import subprocess
import threading

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel


VOICES = (
    "alba", "anna", "azelma", "bill_boerst", "caro_davy", "charles",
    "cosette", "eponine", "eve", "fantine", "george", "jane", "jean",
    "javert", "marius", "mary", "michael", "paul", "peter_yearsley",
    "stuart_bell", "vera",
)
VOICE_SET = frozenset(VOICES)
MODEL_ID = "pocket-tts-2.1"

app = FastAPI()
_lock = threading.Lock()
_model = None
_states = {}


class SpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str
    response_format: str = "mp3"


def _voice_name(voice_id: str) -> str:
    name = voice_id.removeprefix("pocket_")
    if name not in VOICE_SET:
        raise HTTPException(status_code=400, detail=f"Unknown Pocket voice: {voice_id}")
    return name


def _get_model():
    global _model
    if _model is None:
        from pocket_tts import TTSModel
        torch.set_num_threads(int(os.environ.get("POCKET_THREADS", "4")))
        _model = TTSModel.load_model()
    return _model


def _wav_bytes(audio, sample_rate: int) -> bytes:
    values = audio.detach().cpu().float().numpy().reshape(-1)
    out = io.BytesIO()
    sf.write(out, values, sample_rate, format="WAV", subtype="PCM_16")
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
        "status": "ok", "engine": "Pocket TTS", "version": "2.1.0",
        "model": MODEL_ID, "device": "cpu", "cuda_available": torch.cuda.is_available(),
        "voices": list(VOICES), "loaded_voice_states": sorted(_states),
    }


@app.get("/v1/audio/voices")
def voices():
    return {"voices": [{"id": f"pocket_{name}"} for name in VOICES]}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="input must not be empty")
    name = _voice_name(req.voice)
    with _lock:
        model = _get_model()
        state = _states.get(name)
        if state is None:
            state = model.get_state_for_audio_prompt(name)
            _states[name] = state
        audio = model.generate_audio(state, text)
        payload, media_type = _encode(_wav_bytes(audio, model.sample_rate), req.response_format)
    return Response(payload, media_type=media_type)

