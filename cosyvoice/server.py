"""CosyVoice 3 — OpenAI-compatible TTS server.

Exposes the same /v1/audio/speech shape as Kokoro-FastAPI / chatterbox so the
webapp and scripts/convert_book.py treat it as just another engine. Clones
voices from reference wavs in /app/voices (file stem = voice name).

GPU-ONLY by design. Measured RTF: ~0.85 on a T4/P100 GPU, but ~10-50x realtime
AND malformed output on CPU (Kaggle Xeon test, 2026-07-24) — so this is only
ever started inside a GPU Kaggle kernel (scripts/kaggle/run_cosyvoice.py), never
as a local Zorin service. See TTS-LANDSCAPE-2026-07.md.

CosyVoice zero-shot needs a transcript of the reference clip, not just the wav.
We Whisper-transcribe each ref once at startup and cache it, so any voice works
without a hand-written transcript.

  GET  /v1/audio/voices  -> {"voices": [{"id": "uk_male_minter"}, ...]}
  POST /v1/audio/speech  -> audio bytes (wav/mp3); body {model, input, voice, response_format}
  GET  /health           -> {"status": "ok", "device": ..., "voices": [...]}
"""
import glob
import io
import logging
import os
import re
import subprocess
import sys
import threading

import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.append(os.environ.get("MATCHA_PATH", "third_party/Matcha-TTS"))
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cosyvoice-server")

VOICES_DIR = os.environ.get("VOICES_DIR", "/app/voices")
MODEL_DIR = os.environ.get("COSYVOICE_MODEL_DIR", "pretrained_models/Fun-CosyVoice3-0.5B")
# CosyVoice 3's prompt signature (see the repo's example.py::cosyvoice3_example).
PROMPT_PREFIX = "You are a helpful assistant.<|endofprompt|>"
# Zero-shot degrades if a single generation is very long; split on sentences.
CHUNK_CHARS = int(os.environ.get("COSYVOICE_CHUNK_CHARS", "300"))

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
app = FastAPI()

# One generation at a time — concurrent CPU/GPU generations pile up and OOM
# (mirrors the chatterbox server's hard-won lesson, incident 2026-07-07).
_GEN_LOCK = threading.Lock()
_model = None
_voice_paths = {}      # stem -> wav path
_voice_prompts = {}    # stem -> transcript of that wav
_asr = None


class SpeechReq(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = ""
    response_format: str = "mp3"


def _load_voices():
    _voice_paths.clear()
    for p in glob.glob(os.path.join(VOICES_DIR, "*.wav")):
        _voice_paths[os.path.splitext(os.path.basename(p))[0]] = p
    log.info("voices: %s", list(_voice_paths))


def _get_asr():
    global _asr
    if _asr is None:
        from faster_whisper import WhisperModel
        _asr = WhisperModel("base", device=DEVICE,
                            compute_type="float16" if DEVICE == "cuda" else "int8")
    return _asr


def _prompt_for(voice: str) -> str:
    """Transcript of the voice's reference clip (Whisper, cached)."""
    if voice not in _voice_prompts:
        asr = _get_asr()
        segs, _ = asr.transcribe(_voice_paths[voice], language="en")
        text = " ".join(s.text for s in segs).strip()
        _voice_prompts[voice] = text
        log.info("ref transcript [%s]: %s", voice, text[:80])
    return _voice_prompts[voice]


def _get_model():
    global _model
    if _model is None:
        log.info("loading CosyVoice 3 on %s ...", DEVICE)
        _model = AutoModel(model_dir=MODEL_DIR)
        log.info("loaded, sample_rate=%d", _model.sample_rate)
    return _model


def _chunk(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= CHUNK_CHARS:
        return [text] if text else []
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?\"]) +", text):
        if cur and len(cur) + len(sent) + 1 > CHUNK_CHARS:
            out.append(cur.strip())
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        out.append(cur.strip())
    return out


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
    voice = req.voice.replace("cosyvoice_", "") if req.voice.startswith("cosyvoice_") else req.voice
    if voice not in _voice_paths:
        return JSONResponse({"error": f"unknown voice {voice!r}; have {list(_voice_paths)}"},
                            status_code=400)
    chunks = _chunk(req.input)
    if not chunks:
        return JSONResponse({"error": "empty input"}, status_code=400)

    ref = _voice_paths[voice]
    prompt = PROMPT_PREFIX + _prompt_for(voice)
    with _GEN_LOCK:
        cv = _get_model()
        pieces = []
        for c in chunks:
            for o in cv.inference_zero_shot(c, prompt, ref, stream=False):
                pieces.append(o["tts_speech"])
        speech = torch.cat(pieces, dim=1).cpu().numpy().squeeze()

    buf = io.BytesIO()
    fmt = (req.response_format or "mp3").lower()
    if fmt == "wav":
        sf.write(buf, speech, cv.sample_rate, format="WAV")
        return Response(buf.getvalue(), media_type="audio/wav")
    # mp3 (default): write wav then transcode via ffmpeg (kept out of the hot path deps)
    sf.write(buf, speech, cv.sample_rate, format="WAV")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
                        "-b:a", "96k", "-f", "mp3", "pipe:1"],
                       input=buf.getvalue(), stdout=subprocess.PIPE, check=True)
    return Response(p.stdout, media_type="audio/mpeg")
