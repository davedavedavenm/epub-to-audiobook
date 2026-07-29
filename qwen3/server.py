"""OpenAI-compatible, GPU-only Qwen3-TTS 1.7B Base adapter."""
import gc
import glob
import io
import json
import logging
import os
import threading

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from qwen_tts import Qwen3TTSModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("qwen3-tts-server")

MODEL_ID = os.environ.get("QWEN3_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
VOICES_DIR = os.environ.get("VOICES_DIR", "/app/voices")
TRANSCRIPTS_FILE = os.environ.get("QWEN3_REF_TRANSCRIPTS", "/app/ref_transcripts.json")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
app = FastAPI()
_lock = threading.Lock()
_model = None
_voices = {}
_transcripts = {}
_prompts = {}


def _scan():
    _voices.clear()
    for pattern in (os.path.join(VOICES_DIR, "*.wav"),
                    os.path.join(VOICES_DIR, "custom", "*.wav")):
        for path in glob.glob(pattern):
            _voices[os.path.splitext(os.path.basename(path))[0]] = path
    if os.path.exists(TRANSCRIPTS_FILE):
        with open(TRANSCRIPTS_FILE, encoding="utf-8") as f:
            _transcripts.update(json.load(f))


def _stem(voice):
    return voice[:-len("_qwen3")] if voice.endswith("_qwen3") else voice


def _load():
    global _model
    if DEVICE != "cuda":
        raise RuntimeError("Qwen3-TTS production adapter requires CUDA")
    if _model is None:
        dtype_name = os.environ.get("QWEN3_DTYPE", "float16").lower()
        dtype = torch.bfloat16 if dtype_name in ("bf16", "bfloat16") else torch.float16
        log.info("loading %s on CUDA (%s, SDPA)", MODEL_ID, dtype)
        _model = Qwen3TTSModel.from_pretrained(
            MODEL_ID, device_map="cuda:0", dtype=dtype, attn_implementation="sdpa")
    return _model


class SpeechReq(BaseModel):
    model: str = MODEL_ID
    input: str
    voice: str
    response_format: str = "mp3"
    seed: int = 12345


@app.on_event("startup")
def startup():
    _scan()


@app.get("/health")
def health():
    body = {"status": "ok" if DEVICE == "cuda" else "unavailable", "device": DEVICE,
            "model": MODEL_ID, "loaded": _model is not None,
            "runtime": "QwenLM/Qwen3-TTS@022e286b98fbec7e1e916cb940cdf532cd9f488e",
            "voices": sorted(_voices)}
    return JSONResponse(body, status_code=200 if DEVICE == "cuda" else 503)


@app.get("/v1/audio/voices")
def voices():
    if DEVICE != "cuda":
        return JSONResponse({"error": "CUDA unavailable"}, status_code=503)
    usable = [v for v in sorted(_voices) if _transcripts.get(v)]
    return {"voices": [{"id": f"{v}_qwen3"} for v in usable]}


@app.post("/v1/audio/speech")
def speech(req: SpeechReq):
    text = (req.input or "").strip()
    if not text:
        return JSONResponse({"error": "input is empty"}, status_code=400)
    _scan()
    stem = _stem(req.voice)
    ref = _voices.get(stem)
    ref_text = _transcripts.get(stem)
    if not ref or not ref_text:
        return JSONResponse({"error": f"voice {req.voice!r} has no matched reference transcript"},
                            status_code=404)
    with _lock:
        model = _load()
        prompt = _prompts.get(stem)
        if prompt is None:
            prompt = model.create_voice_clone_prompt(
                ref_audio=ref, ref_text=ref_text, x_vector_only_mode=False)
            _prompts[stem] = prompt
        torch.manual_seed(req.seed)
        torch.cuda.manual_seed_all(req.seed)
        wavs, sr = model.generate_voice_clone(
            text=text, language="English", voice_clone_prompt=prompt,
            max_new_tokens=4096, do_sample=True, top_k=50, top_p=1.0,
            temperature=0.9, repetition_penalty=1.05,
            subtalker_dosample=True, subtalker_top_k=50, subtalker_top_p=1.0,
            subtalker_temperature=0.9)
        if not wavs:
            return JSONResponse({"error": "model returned no audio"}, status_code=500)
        audio = np.asarray(wavs[0], dtype="float32").reshape(-1)
        del wavs
        gc.collect()
        torch.cuda.empty_cache()
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    if (req.response_format or "mp3").lower() == "wav":
        return Response(buf.getvalue(), media_type="audio/wav")
    import subprocess
    enc = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3",
                          "-b:a", "192k", "pipe:1"], input=buf.getvalue(), capture_output=True)
    if enc.returncode != 0:
        return JSONResponse({"error": "ffmpeg encode failed"}, status_code=500)
    return Response(enc.stdout, media_type="audio/mpeg")
