"""Minimal OpenAI-compatible TTS server for Chatterbox Turbo.

Exposes the same /v1/audio/speech shape as Kokoro-FastAPI so the existing
webapp can treat it as just another engine. Clones voices from reference
wavs in /app/voices (file stem = voice name). CPU by default; uses CUDA
automatically if available.

Endpoints:
  GET  /v1/audio/voices           -> {"voices": [{"id": "uk_male_minter"}, ...]}
  POST /v1/audio/speech           -> audio bytes (mp3/wav)
       body: {model, input, voice, response_format}
  GET  /health                    -> {"status": "ok", "device": ...}
"""
import io
import os
import re
import glob
import logging

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chatterbox-server")

VOICES_DIR = os.environ.get("VOICES_DIR", "/app/voices")
# Turbo degrades past ~300 chars/generation — chunk below that on sentence
# boundaries (see LOW-COST-TTS.md).
CHUNK_CHARS = int(os.environ.get("CHATTERBOX_CHUNK_CHARS", "280"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI()
_model = None
_voice_paths = {}


def _load_voices():
    _voice_paths.clear()
    for p in glob.glob(os.path.join(VOICES_DIR, "*.wav")):
        _voice_paths[os.path.splitext(os.path.basename(p))[0]] = p
    log.info("voices: %s", list(_voice_paths))


def _get_model():
    global _model
    if _model is None:
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        log.info("loading Chatterbox Turbo on %s ...", DEVICE)
        _model = ChatterboxTurboTTS.from_pretrained(device=DEVICE)
    return _model


def _chunk(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?”])\s+", text)
    chunks, cur = [], ""
    for s in sents:
        if cur and len(cur) + 1 + len(s) > CHUNK_CHARS:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return chunks or [text]


class SpeechReq(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = ""
    response_format: str = "mp3"


@app.on_event("startup")
def _startup():
    _load_voices()


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE, "voices": list(_voice_paths)}


@app.get("/v1/audio/voices")
def list_voices():
    if not _voice_paths:
        _load_voices()
    return {"voices": [{"id": v} for v in sorted(_voice_paths)]}


@app.post("/v1/audio/speech")
def speech(req: SpeechReq):
    if not _voice_paths:
        _load_voices()
    ref = _voice_paths.get(req.voice)
    if ref is None:
        # fall back to any voice so a bad name doesn't hard-fail a book
        if not _voice_paths:
            return JSONResponse({"error": "no reference voices installed"}, status_code=503)
        ref = next(iter(_voice_paths.values()))
        log.warning("voice %r not found; using %s", req.voice, ref)

    model = _get_model()
    pieces = []
    for chunk in _chunk(req.input):
        wav = model.generate(chunk, audio_prompt_path=ref)
        arr = wav.detach().cpu().numpy().astype("float32").reshape(-1)
        pieces.append(arr)
    audio = np.concatenate(pieces) if pieces else np.zeros(1, dtype="float32")

    fmt = (req.response_format or "mp3").lower()
    buf = io.BytesIO()
    if fmt == "wav":
        sf.write(buf, audio, model.sr, format="WAV")
        media = "audio/wav"
    else:
        # soundfile has no mp3 encode on all platforms; write wav then let
        # ffmpeg (present in image) transcode via a temp pipe
        import subprocess
        sf.write(buf, audio, model.sr, format="WAV")
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3", "-b:a", "128k", "pipe:1"],
            input=buf.getvalue(), capture_output=True)
        return Response(content=p.stdout, media_type="audio/mpeg")
    return Response(content=buf.getvalue(), media_type=media)
