"""OpenAI-compatible TTS server for Hume TADA-1B.

Same /v1/audio/speech shape as the other engines so the webapp treats it as
one more engine. Voice-clones from reference wavs in /app/voices (stem = voice
name), using pre-baked transcripts in ref_transcripts.json. CPU by default;
CUDA if available.

Notes baked in from the proven local recipe:
- TADA pulls the Llama-3.2-1B *tokenizer* (Meta-gated). Redirect to the
  byte-identical ungated `unsloth/Llama-3.2-1B` mirror before importing tada.
- ~600-char passes keep long-form prosody while limiting pacing drift.
"""
import io
import os
import re
import glob
import json
import logging
import gc
import threading
import subprocess

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tada-server")

# --- gated-tokenizer redirect (MUST run before importing tada) ---
import transformers
_orig_tok = transformers.AutoTokenizer.from_pretrained
def _tok_patch(name, *a, **k):
    if isinstance(name, str) and name == "meta-llama/Llama-3.2-1B":
        name = "unsloth/Llama-3.2-1B"
    return _orig_tok(name, *a, **k)
transformers.AutoTokenizer.from_pretrained = _tok_patch

VOICES_DIR = os.environ.get("VOICES_DIR", "/app/voices")
CHUNK_CHARS = int(os.environ.get("TADA_CHUNK_CHARS", "600"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
SR = 24000

app = FastAPI()

# One generation at a time: concurrent requests from FastAPI's threadpool
# pile up on CPU (client timeouts leave abandoned generations running),
# ballooning memory until the kernel OOM-kills the server (incident 2026-07-07).
_GEN_LOCK = threading.Lock()
_enc = None
_model = None
_voice_paths = {}
_transcripts = {}


def _load_voices():
    _voice_paths.clear()
    for p in glob.glob(os.path.join(VOICES_DIR, "*.wav")):
        _voice_paths[os.path.splitext(os.path.basename(p))[0]] = p
    tpath = os.path.join(VOICES_DIR, "ref_transcripts.json")
    if os.path.exists(tpath):
        _transcripts.update(json.load(open(tpath)))
    log.info("voices=%s transcripts=%s", list(_voice_paths), list(_transcripts))


def _get_model():
    global _enc, _model
    if _model is None:
        from tada.modules.encoder import Encoder
        from tada.modules.tada import TadaForCausalLM
        log.info("loading TADA-1B on %s (%s) ...", DEVICE, DTYPE)
        _enc = Encoder.from_pretrained("HumeAI/tada-codec", subfolder="encoder").to(DEVICE)
        # low_cpu_mem_usage avoids the ~2x peak-RAM spike during load (loads
        # weights incrementally) — needed to fit on memory-limited hosts.
        try:
            _model = TadaForCausalLM.from_pretrained(
                "HumeAI/tada-1b", dtype=DTYPE, low_cpu_mem_usage=True).to(DEVICE)
        except TypeError:
            _model = TadaForCausalLM.from_pretrained("HumeAI/tada-1b", dtype=DTYPE).to(DEVICE)
        log.info("TADA-1B loaded.")
    return _enc, _model


def _chunk(text):
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?”])\s+", text)
    chunks, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) > CHUNK_CHARS:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return chunks or [text]


def _voice_transcript(name):
    # matched transcript, else empty (TADA still clones timbre without it)
    return _transcripts.get(name, "")


# Natural pause inserted between generation chunks. Chunks split at sentence
# boundaries, but TADA has no long-form mode (per HumeAI/tada docs), so
# hard-concatenating chunks makes abrupt, paceless joins — heard as "weird
# pacing" on long text (2026-07-09). ~250ms reads as a normal sentence gap.
JOIN_SILENCE_MS = int(os.environ.get("TADA_JOIN_SILENCE_MS", "250"))

# Throwaway lead-in absorbing the first-word cold-start; trimmed off after.
LEADIN = os.environ.get("TADA_LEADIN", "Right. ")
LEADIN_ENABLED = os.environ.get("TADA_TRIM_LEADIN", "1") not in ("0", "false", "no")
if not LEADIN_ENABLED:
    LEADIN = ""


def _trim_leadin(arr, sr=SR):
    """Cut the lead-in phrase off the front of an utterance: skip the lead-in
    speech, find the first silence gap, and start the real audio after it.
    Safe fallback: if no clear gap is found, trim a fixed conservative amount
    rather than leaving the spoken lead-in in."""
    try:
        n = arr.shape[0]
        if n < int(0.3 * sr):
            return arr
        win = max(1, int(0.02 * sr))          # 20 ms frames
        peak = float(np.max(np.abs(arr))) or 1.0
        thresh = 0.06 * peak
        start = int(0.18 * sr)                 # lead-in speech is ~>=0.18s
        limit = int(1.2 * sr)                  # only search the first ~1.2s
        i = start
        gap = 0
        need = int(0.05 * sr)                  # 50 ms of quiet = the gap
        while i < min(limit, n):
            frame = arr[i:i + win]
            if float(np.max(np.abs(frame))) < thresh:
                gap += win
                if gap >= need:
                    # real speech resumes after this silence
                    cut = i + win
                    # advance past any trailing quiet
                    while cut < n and float(np.max(np.abs(arr[cut:cut + win]))) < thresh:
                        cut += win
                    return arr[cut:] if cut < n else arr
            else:
                gap = 0
            i += win
        # fallback: no gap found — trim a fixed ~0.45s (typical lead-in length)
        return arr[int(0.45 * sr):]
    except Exception:
        return arr


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
    return {"status": "ok", "device": DEVICE,
            "cuda_available": torch.cuda.is_available(),
            "torch": torch.__version__,
            "torch_cuda": getattr(torch.version, "cuda", None),
            "voices": list(_voice_paths)}


@app.get("/v1/audio/voices")
def list_voices():
    if not _voice_paths:
        _load_voices()
    return {"voices": [{"id": v} for v in sorted(_voice_paths)] + [{"id": "native"}]}


# NATIVE-VOICE BOOTSTRAP ("native" voice id): generate one calibration passage
# UNCONDITIONED so the model speaks in its own preferred voice (heard acting a
# quotation mid-book, it was impeccable — Dave 2026-07-10), then use that
# output as the reference prompt for everything else. Consistency comes from
# conditioning on in-distribution audio, and the reference transcript is
# perfect by construction (we know exactly what it spoke), so alignment cannot
# be wrong. Internals allow prompt=None (prompt_acoustic_features: ...|None).
NATIVE_CAL_TEXT = ("The story begins quietly, as most true stories do. "
                   "By the following spring, everything about the company had changed, "
                   "and the people who built it knew there was no going back.")
_native_prompt = None
_NATIVE_REF_PATH = os.path.join(os.environ.get("HF_HOME", "/tmp"), "tada_native_ref.wav")


def _get_native_prompt(enc, model):
    global _native_prompt
    if _native_prompt is not None:
        return _native_prompt
    if os.path.exists(_NATIVE_REF_PATH):
        data, sr = sf.read(_NATIVE_REF_PATH, dtype="float32")
        aud = torch.from_numpy(np.ascontiguousarray(data[None, :])).to(DEVICE)
        _native_prompt = enc(aud, text=[NATIVE_CAL_TEXT], sample_rate=sr)
        log.info("native voice: loaded cached calibration ref")
        return _native_prompt
    log.info("native voice: generating unconditioned calibration passage...")
    # generate() requires a prompt DATACLASS but its fields may each be None —
    # _generate() then zero-inits acoustic features, i.e. true unconditioned
    # generation (verified against tada/modules/tada.py:1207 + _generate sig).
    from tada.modules.encoder import EncoderOutput
    empty = EncoderOutput(**{f: None for f in EncoderOutput.__dataclass_fields__})
    # generate() prepends the prompt transcript: prompt.text[0] + text, sliced
    # by prompt.text_tokens_len — an empty prompt needs "" / 0 there (v10 fail).
    empty.text = [""]
    empty.text_tokens_len = [0]
    out = model.generate(prompt=empty, text=NATIVE_CAL_TEXT)
    w = out.audio
    while isinstance(w, (list, tuple)):
        w = w[0]
    if hasattr(w, "detach"):
        w = w.detach().cpu().float().numpy()
    arr = np.asarray(w, dtype="float32").reshape(-1)
    sf.write(_NATIVE_REF_PATH, arr, SR)
    aud = torch.from_numpy(np.ascontiguousarray(arr[None, :])).to(DEVICE)
    _native_prompt = enc(aud, text=[NATIVE_CAL_TEXT], sample_rate=SR)
    log.info("native voice: calibration ref built (%.1fs)", len(arr) / SR)
    return _native_prompt


@app.post("/v1/audio/speech")
def speech(req: SpeechReq):
    if not _voice_paths:
        _load_voices()
    if req.voice in ("native", "tada_native"):
        enc, model = _get_model()
        with _GEN_LOCK:
            prompt = _get_native_prompt(enc, model)
    else:
        ref = _voice_paths.get(req.voice) or (next(iter(_voice_paths.values())) if _voice_paths else None)
        if ref is None:
            return JSONResponse({"error": "no reference voices installed"}, status_code=503)
        ref_name = req.voice if req.voice in _voice_paths else os.path.splitext(os.path.basename(ref))[0]

        enc, model = _get_model()
        data, sr = sf.read(ref, dtype="float32")
        data = data[None, :] if data.ndim == 1 else data.T
        aud = torch.from_numpy(np.ascontiguousarray(data)).to(DEVICE)
        prompt = enc(aud, text=[_voice_transcript(ref_name)], sample_rate=sr)

    pieces = []
    with _GEN_LOCK:
        with torch.inference_mode():
            chunks = _chunk(req.input)
            for i, chunk in enumerate(chunks):
                # First-word garble fix: TADA cold-starts badly on the opening
                # word of a generation. Prepend a throwaway lead-in that absorbs
                # the cold-start, then trim it back off at the first silence gap.
                lead = LEADIN if i == 0 else ""
                out = model.generate(prompt=prompt, text=lead + chunk)
                w = out.audio
                while isinstance(w, (list, tuple)):
                    w = w[0]
                if hasattr(w, "detach"):
                    w = w.detach().cpu().float().numpy()
                arr = np.asarray(w, dtype="float32").reshape(-1)
                if lead:
                    arr = _trim_leadin(arr)
                if i > 0 and JOIN_SILENCE_MS > 0:
                    pieces.append(np.zeros(int(SR * JOIN_SILENCE_MS / 1000), dtype="float32"))
                pieces.append(arr)
                del out
        gc.collect()
    audio = np.concatenate(pieces) if pieces else np.zeros(1, dtype="float32")

    buf = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV")
    if (req.response_format or "mp3").lower() == "wav":
        return Response(content=buf.getvalue(), media_type="audio/wav")
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "mp3", "-b:a", "128k", "pipe:1"],
        input=buf.getvalue(), capture_output=True)
    return Response(content=p.stdout, media_type="audio/mpeg")
