"""OpenAI-compatible, GPU-only VibeVoice 1.5B adapter.

Runtime provenance matters here: Microsoft still publishes the weights, but
disabled its TTS inference package. This adapter therefore imports the audited
community fork pinned in Dockerfile while loading only the official Microsoft
checkpoint. One HTTP request is one complete chapter; chunking Vibe into the
legacy 280-character passes destroys the long-form behaviour we are evaluating.
"""
import gc
import glob
import io
import logging
import os
import threading

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vibevoice-server")

MODEL_ID = os.environ.get("VIBEVOICE_MODEL", "microsoft/VibeVoice-1.5B")
VOICES_DIR = os.environ.get("VOICES_DIR", "/app/voices")
MAX_CHARS = int(os.environ.get("VIBEVOICE_MAX_CHARS", "250000"))
CFG_SCALE = float(os.environ.get("VIBEVOICE_CFG_SCALE", "1.3"))
DDPM_STEPS = int(os.environ.get("VIBEVOICE_DDPM_STEPS", "10"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI()
_lock = threading.Lock()
_processor = None
_model = None
_voices = {}


def _scan_voices():
    _voices.clear()
    for pattern in (os.path.join(VOICES_DIR, "*.wav"),
                    os.path.join(VOICES_DIR, "custom", "*.wav")):
        for path in glob.glob(pattern):
            _voices[os.path.splitext(os.path.basename(path))[0]] = path


def _voice_stem(voice):
    stem = voice
    if stem.endswith("_vibevoice"):
        stem = stem[:-len("_vibevoice")]
    return stem


def _load():
    global _processor, _model
    if DEVICE != "cuda":
        raise RuntimeError("VibeVoice production adapter requires CUDA")
    if _model is None:
        from vibevoice.modular.modeling_vibevoice_inference import (
            VibeVoiceForConditionalGenerationInference,
        )
        from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

        dtype_name = os.environ.get("VIBEVOICE_DTYPE", "float16").lower()
        dtype = torch.bfloat16 if dtype_name in ("bf16", "bfloat16") else torch.float16
        log.info("loading %s on CUDA (%s, SDPA)", MODEL_ID, dtype)
        _processor = VibeVoiceProcessor.from_pretrained(MODEL_ID)
        _model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            MODEL_ID, torch_dtype=dtype, device_map="cuda", attn_implementation="sdpa")
        _model.eval()
        _model.set_ddpm_inference_steps(num_steps=DDPM_STEPS)
    return _processor, _model


class SpeechReq(BaseModel):
    model: str = MODEL_ID
    input: str
    voice: str
    response_format: str = "mp3"
    seed: int = 12345


@app.on_event("startup")
def startup():
    _scan_voices()


@app.get("/health")
def health():
    body = {"status": "ok" if DEVICE == "cuda" else "unavailable",
            "device": DEVICE, "model": MODEL_ID, "loaded": _model is not None,
            "runtime": "vibevoice-community@07cb79feadd2d3fd7f47530d4c964a12857936a0",
            "weights": "microsoft/VibeVoice-1.5B", "voices": sorted(_voices)}
    return JSONResponse(body, status_code=200 if DEVICE == "cuda" else 503)


@app.get("/v1/audio/voices")
def voices():
    if DEVICE != "cuda":
        return JSONResponse({"error": "CUDA unavailable"}, status_code=503)
    return {"voices": [{"id": f"{v}_vibevoice"} for v in sorted(_voices)]}


@app.post("/v1/audio/speech")
def speech(req: SpeechReq):
    text = (req.input or "").strip()
    if not text:
        return JSONResponse({"error": "input is empty"}, status_code=400)
    if len(text) > MAX_CHARS:
        return JSONResponse({"error": f"chapter exceeds VibeVoice limit ({len(text)} > {MAX_CHARS} chars)"},
                            status_code=413)
    _scan_voices()
    stem = _voice_stem(req.voice)
    ref = _voices.get(stem)
    if not ref:
        return JSONResponse({"error": f"unknown voice {req.voice!r}"}, status_code=404)

    with _lock:
        processor, model = _load()
        torch.manual_seed(req.seed)
        torch.cuda.manual_seed_all(req.seed)
        inputs = processor(text=[f"Speaker 1: {text}"], voice_samples=[[ref]],
                           padding=True, return_tensors="pt",
                           return_attention_mask=True)
        inputs = {k: (v.to("cuda") if torch.is_tensor(v) else v) for k, v in inputs.items()}
        with torch.inference_mode():
            outputs = model.generate(
                **inputs, max_new_tokens=None, cfg_scale=CFG_SCALE,
                tokenizer=processor.tokenizer,
                generation_config={"do_sample": False}, is_prefill=True, verbose=True)
        if not outputs.speech_outputs or outputs.speech_outputs[0] is None:
            return JSONResponse({"error": "model returned no audio"}, status_code=500)
        wav = outputs.speech_outputs[0]
        if hasattr(wav, "detach"):
            wav = wav.detach().cpu().float().numpy()
        audio = np.asarray(wav, dtype="float32").reshape(-1)
        del outputs, inputs
        gc.collect()
        torch.cuda.empty_cache()

    buf = io.BytesIO()
    sf.write(buf, audio, 24000, format="WAV")
    if (req.response_format or "mp3").lower() == "wav":
        return Response(buf.getvalue(), media_type="audio/wav")
    import subprocess
    enc = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3",
                          "-b:a", "192k", "pipe:1"], input=buf.getvalue(), capture_output=True)
    if enc.returncode != 0:
        return JSONResponse({"error": "ffmpeg encode failed"}, status_code=500)
    return Response(enc.stdout, media_type="audio/mpeg")
