"""Free-tier-only OpenAI-compatible adapter for Gemini 3.1 Flash TTS.

This service deliberately has no configurable upstream URL, paid model, batch
route, Vertex route, or retry loop.  The API key must belong to an unbilled
Gemini Developer API project.  When its free quota is exhausted, the original
HTTP failure is returned and the caller pauses; it never falls through to a
billable service.

Official contract (checked 2026-08-15):
https://ai.google.dev/gemini-api/docs/speech-generation
https://ai.google.dev/api/interactions-api
https://ai.google.dev/gemini-api/docs/pricing
https://ai.google.dev/gemini-api/docs/billing
"""
from __future__ import annotations

import base64
import io
import os
import wave

import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel


MODEL_ID = "gemini-3.1-flash-tts-preview"
UPSTREAM_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
VOICE_MAP = {"gemini_achernar": "Achernar"}
MAX_INPUT_CHARS = 3_200
DEFAULT_STYLE = (
    "Read aloud in a warm, natural, engaging audiobook style. Use British "
    "English pronunciation and a steady, unhurried pace. Keep the narrator "
    "consistent. Speak the transcript exactly as written; do not add, omit, "
    "paraphrase, introduce, or comment on it."
)

app = FastAPI()


class SpeechRequest(BaseModel):
    model: str = MODEL_ID
    input: str
    voice: str
    response_format: str = "wav"
    speed: float = 1.0
    seed: int | None = None


def _api_key() -> str:
    # The Gemini API does not expose billing tier through this inference call.
    # Require an explicit operator acknowledgement made only after AI Studio
    # shows this key's dedicated project as Free. The unbilled project is the
    # actual no-charge boundary; this flag prevents accidental omission of that
    # verification, but does not pretend to cryptographically prove it.
    if os.environ.get("GEMINI_FREE_PROJECT_CONFIRMED", "0").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        raise HTTPException(
            status_code=503,
            detail=("Gemini adapter refuses requests until AI Studio shows the "
                    "dedicated project as Free and "
                    "GEMINI_FREE_PROJECT_CONFIRMED=1 is set"),
        )
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    project_id = os.environ.get("GEMINI_FREE_PROJECT_ID", "").strip()
    if not project_id:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_FREE_PROJECT_ID is required for the confirmed Free project",
        )
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured for the free-tier project",
        )
    return key


def _wav_from_pcm(pcm: bytes) -> bytes:
    if not pcm or len(pcm) % 2:
        raise HTTPException(status_code=502, detail="Gemini returned invalid PCM audio")
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(pcm)
    return out.getvalue()


def _error_detail(response: requests.Response) -> str:
    try:
        body = response.json()
        message = body.get("error", {}).get("message")
        if message:
            return str(message)[:500]
    except Exception:
        pass
    return (response.text or f"HTTP {response.status_code}")[:500]


def _pcm_from_interaction(body: dict) -> bytes:
    """Extract inline L16 from the raw REST Interaction response.

    Google's SDK adds an ``output_audio`` convenience property, but the raw
    REST resource returns model output in ``steps[].content[]``.  Pinning the
    parser to that documented wire shape prevents a successful generation from
    being discarded merely because an SDK-only field is absent.
    """
    blocks: list[bytes] = []
    for step in body.get("steps", []):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if not isinstance(content, dict) or content.get("type") != "audio":
                continue
            mime_type = content.get("mime_type")
            sample_rate = content.get("sample_rate")
            channels = content.get("channels")
            if mime_type not in {None, "audio/l16"}:
                raise HTTPException(
                    status_code=502,
                    detail=f"Gemini returned unexpected audio format: {mime_type}",
                )
            if sample_rate not in {None, 24_000} or channels not in {None, 1}:
                raise HTTPException(
                    status_code=502,
                    detail=("Gemini returned unexpected PCM layout: "
                            f"sample_rate={sample_rate}, channels={channels}"),
                )
            encoded = content.get("data")
            if not isinstance(encoded, str) or not encoded:
                continue
            try:
                blocks.append(base64.b64decode(encoded, validate=True))
            except Exception as exc:
                raise HTTPException(
                    status_code=502, detail="Gemini returned invalid base64 audio"
                ) from exc
    pcm = b"".join(blocks)
    if not pcm:
        status = body.get("status", "unknown")
        raise HTTPException(
            status_code=502,
            detail=f"Gemini REST interaction contained no inline audio (status={status})",
        )
    return pcm


def _synth(text: str, voice_name: str) -> bytes:
    style = os.environ.get("GEMINI_TTS_STYLE", DEFAULT_STYLE).strip() or DEFAULT_STYLE
    prompt = f"{style}\n\nTRANSCRIPT:\n{text}"
    payload = {
        "model": MODEL_ID,
        "input": prompt,
        "response_format": {
            "type": "audio",
            "mime_type": "audio/l16",
            "sample_rate": 24_000,
            "delivery": "inline",
        },
        "generation_config": {
            "speech_config": [{"voice": voice_name}],
        },
    }
    # Exactly one request. In particular, 429/503 are not retried here: a
    # preview model's free quota is a stop condition, not permission to hammer.
    try:
        upstream = requests.post(
            UPSTREAM_URL,
            headers={
                "x-goog-api-key": _api_key(),
                "Content-Type": "application/json",
                "Api-Revision": "2026-05-20",
            },
            json=payload,
            timeout=(15, int(os.environ.get("GEMINI_REQUEST_TIMEOUT", "300"))),
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise HTTPException(status_code=503, detail=f"Gemini request failed: {exc}") from exc
    if upstream.status_code != 200:
        raise HTTPException(status_code=upstream.status_code, detail=_error_detail(upstream))
    return _wav_from_pcm(_pcm_from_interaction(upstream.json()))


@app.get("/health")
def health():
    configured = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    project_id = os.environ.get("GEMINI_FREE_PROJECT_ID", "").strip()
    free_project_confirmed = os.environ.get(
        "GEMINI_FREE_PROJECT_CONFIRMED", "0"
    ).strip().lower() in {
        "1", "true", "yes", "on"
    }
    body = {
        "status": (
            "ok" if configured and project_id and free_project_confirmed else "unconfigured"
        ),
        "engine": "Gemini Developer API TTS",
        "model": MODEL_ID,
        "configured": configured,
        "project_id": project_id or None,
        "free_project_confirmed": free_project_confirmed,
        "billing_tier_validation": "operator-confirmed in AI Studio; not exposed by inference API",
        "upstream": "generativelanguage.googleapis.com",
        "voices": list(VOICE_MAP),
        "max_input_chars": MAX_INPUT_CHARS,
        "automatic_retries": 0,
    }
    return JSONResponse(
        body,
        status_code=200 if configured and project_id and free_project_confirmed else 503,
    )


@app.get("/v1/audio/voices")
def voices():
    _api_key()
    return {"voices": [{"id": voice_id} for voice_id in VOICE_MAP]}


@app.post("/v1/audio/speech")
def speech(req: SpeechRequest):
    text = req.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="input must not be empty")
    if len(text) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"input exceeds the free-only passage cap of {MAX_INPUT_CHARS} characters",
        )
    if req.model != MODEL_ID:
        raise HTTPException(status_code=400, detail=f"Only {MODEL_ID} is allowed")
    if req.voice not in VOICE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown Gemini voice: {req.voice}")
    if req.response_format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Gemini adapter returns WAV only")
    if req.speed != 1.0:
        raise HTTPException(status_code=400, detail="Gemini speed is controlled by the fixed style prompt")
    return Response(_synth(text, VOICE_MAP[req.voice]), media_type="audio/wav")
