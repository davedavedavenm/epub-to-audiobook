"""Free-tier-only OpenAI-compatible adapter for Gemini 3.1 Flash TTS.

This service deliberately has no configurable upstream URL, paid model, batch
route, Vertex route, or retry loop.  The API key must belong to an unbilled
Gemini Developer API project.  When its free quota is exhausted, the original
HTTP failure is returned and the caller pauses; it never falls through to a
billable service.

Official contract (checked 2026-08-15):
https://ai.google.dev/gemini-api/docs/speech-generation
https://ai.google.dev/api/interactions-api
https://ai.google.dev/gemini-api/docs/api-errors
https://ai.google.dev/gemini-api/docs/pricing
https://ai.google.dev/gemini-api/docs/billing
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import threading
import wave
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel


MODEL_ID = "gemini-3.1-flash-tts-preview"
UPSTREAM_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
VOICE_MAP = {
    "gemini_zephyr": "Zephyr", "gemini_puck": "Puck",
    "gemini_charon": "Charon", "gemini_kore": "Kore",
    "gemini_fenrir": "Fenrir", "gemini_leda": "Leda",
    "gemini_orus": "Orus", "gemini_aoede": "Aoede",
    "gemini_callirrhoe": "Callirrhoe", "gemini_autonoe": "Autonoe",
    "gemini_enceladus": "Enceladus", "gemini_iapetus": "Iapetus",
    "gemini_umbriel": "Umbriel", "gemini_algieba": "Algieba",
    "gemini_despina": "Despina", "gemini_erinome": "Erinome",
    "gemini_algenib": "Algenib", "gemini_rasalgethi": "Rasalgethi",
    "gemini_laomedeia": "Laomedeia", "gemini_achernar": "Achernar",
    "gemini_alnilam": "Alnilam", "gemini_schedar": "Schedar",
    "gemini_gacrux": "Gacrux", "gemini_pulcherrima": "Pulcherrima",
    "gemini_achird": "Achird", "gemini_zubenelgenubi": "Zubenelgenubi",
    "gemini_vindemiatrix": "Vindemiatrix", "gemini_sadachbia": "Sadachbia",
    "gemini_sadaltager": "Sadaltager", "gemini_sulafat": "Sulafat",
}
DAILY_REQUEST_CAP = 10
_USAGE_LOCK = threading.Lock()
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


def _client() -> genai.Client:
    """Build the official SDK client with retries explicitly disabled."""
    timeout_ms = int(os.environ.get("GEMINI_REQUEST_TIMEOUT", "300")) * 1000
    return genai.Client(
        api_key=_api_key(),
        http_options=genai_types.HttpOptions(
            timeout=timeout_ms,
            retry_options=genai_types.HttpRetryOptions(attempts=1),
        ),
    )


def _pacific_day() -> str:
    """Gemini RPD resets at midnight Pacific, per Google's rate-limit docs."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def _usage_path() -> Path:
    return Path(os.environ.get("GEMINI_USAGE_DIR", "/data/gemini_usage")) / "requests.json"


def _fresh_usage(day: str) -> dict:
    bootstrap_day = os.environ.get("GEMINI_USAGE_BOOTSTRAP_PACIFIC_DATE", "").strip()
    bootstrap = int(os.environ.get("GEMINI_USAGE_BOOTSTRAP_COUNT", "0")) if day == bootstrap_day else 0
    if not 0 <= bootstrap <= DAILY_REQUEST_CAP:
        raise HTTPException(status_code=503, detail="Invalid Gemini usage bootstrap count")
    return {
        "pacific_date": day,
        "cap": DAILY_REQUEST_CAP,
        "attempts": [
            {"source": "pre-ledger bootstrap", "outcome": "counted"}
            for _ in range(bootstrap)
        ],
    }


def _read_usage() -> dict:
    day = _pacific_day()
    path = _usage_path()
    try:
        usage = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        usage = _fresh_usage(day)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Gemini usage ledger unreadable: {exc}") from exc
    if usage.get("pacific_date") != day:
        usage = _fresh_usage(day)
    usage["cap"] = DAILY_REQUEST_CAP
    usage.setdefault("attempts", [])
    return usage


def _write_usage(usage: dict) -> None:
    path = _usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(usage, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _reserve_request(voice_name: str, text: str) -> tuple[str, int]:
    """Reserve one upstream attempt before sending it; never exceed 10 RPD."""
    with _USAGE_LOCK:
        usage = _read_usage()
        attempts = usage["attempts"]
        if len(attempts) >= DAILY_REQUEST_CAP:
            raise HTTPException(
                status_code=429,
                detail=("Local free-tier guard: all 10 Gemini requests for the current "
                        "Pacific quota day are already accounted for"),
            )
        attempts.append({
            "time": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
            "voice": voice_name,
            "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "outcome": "reserved",
        })
        _write_usage(usage)
        return usage["pacific_date"], len(attempts) - 1


def _record_outcome(day: str, index: int, outcome: str) -> None:
    with _USAGE_LOCK:
        usage = _read_usage()
        if usage.get("pacific_date") == day and index < len(usage["attempts"]):
            usage["attempts"][index]["outcome"] = outcome
            _write_usage(usage)


def _usage_status() -> dict:
    with _USAGE_LOCK:
        usage = _read_usage()
    used = len(usage["attempts"])
    return {"pacific_date": usage["pacific_date"], "used": used,
            "cap": DAILY_REQUEST_CAP, "remaining": DAILY_REQUEST_CAP - used}


def _api_error_detail(exc: genai_errors.APIError) -> str:
    """Keep Google's documented machine code alongside its safe message."""
    error = exc.details.get("error", {}) if isinstance(exc.details, dict) else {}
    classification = exc.status
    if not classification and isinstance(error, dict):
        documented_code = error.get("code")
        if isinstance(documented_code, str):
            classification = documented_code
    message = str(exc.message or "Gemini API error")
    detail = f"{classification}: {message}" if classification else message
    return detail[:500]


def _synth(text: str, voice_name: str) -> bytes:
    style = os.environ.get("GEMINI_TTS_STYLE", DEFAULT_STYLE).strip() or DEFAULT_STYLE
    prompt = f"{style}\n\nTRANSCRIPT:\n{text}"
    # Use the official SDK path from Google's TTS guide. ``output_audio`` is an
    # SDK convenience property, not a raw REST field; using it avoids coupling
    # this adapter to the Interactions API's changing wire representation.
    client = _client()
    usage_day, usage_index = _reserve_request(voice_name, text)
    try:
        interaction = client.interactions.create(
            model=MODEL_ID,
            input=prompt,
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice_name}]},
        )
    except genai_errors.APIError as exc:
        _record_outcome(usage_day, usage_index, f"api_error:{exc.code or 'unknown'}")
        raise HTTPException(
            status_code=exc.code or 502,
            detail=_api_error_detail(exc),
        ) from exc
    except Exception as exc:
        _record_outcome(usage_day, usage_index, "client_error")
        raise HTTPException(status_code=503, detail=f"Gemini request failed: {exc}") from exc
    finally:
        client.close()
    try:
        encoded = interaction.output_audio.data
        pcm = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        _record_outcome(usage_day, usage_index, "invalid_output")
        raise HTTPException(
            status_code=502, detail="Gemini SDK response contained no valid output_audio"
        ) from exc
    result = _wav_from_pcm(pcm)
    _record_outcome(usage_day, usage_index, "success")
    return result


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
        "free_usage": _usage_status(),
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
