import re
import os
import io
import json
import hashlib
import time
import sqlite3
import base64
import logging
import boto3
import httpx
import asyncio
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from mutagen.mp3 import MP3
import edge_tts

app = FastAPI()
logger = logging.getLogger("tts_proxy")

DB_PATH = Path(os.environ.get("DB_PATH", "/data/jobs.db"))
UPSTREAM_BASE = os.environ.get("TTS_UPSTREAM_BASE", "http://kokoro-tts:8880/v1").rstrip("/")
STORE_ROOT = Path(os.environ.get("TRANSCRIPTS_DIR", "/data/transcripts"))
STORE_ROOT.mkdir(parents=True, exist_ok=True)

_re_ws = re.compile(r"\s+")
_re_punct = re.compile(r"[^\w\s]+", flags=re.UNICODE)

def get_audio_duration(audio_bytes: bytes) -> float:
    try:
        audio_file = io.BytesIO(audio_bytes)
        mp3 = MP3(audio_file)
        return mp3.info.length
    except Exception as e:
        logger.error(f"Duration error: {e}")
        return 0.0

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()

def normalize_strict(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join([ln.rstrip() for ln in s.split("\n")])
    s = _re_ws.sub(" ", s).strip()
    return s

def normalize_loose(s: str) -> str:
    s = s.casefold()
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _re_punct.sub(" ", s)
    s = _re_ws.sub(" ", s).strip()
    return s

_SAFE_JOB_ID = re.compile(r'^[a-zA-Z0-9_\-]+$')

def job_dir(job_id: str) -> Path:
    if not _SAFE_JOB_ID.match(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id")
    d = STORE_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def get_setting(key: str, default=None):
    try:
        if not DB_PATH.exists():
            return os.environ.get(key, default)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
            if row:
                return row['value']
    except Exception as e:
        logger.error(f"Error fetching setting {key}: {e}")
    return os.environ.get(key, default)

async def get_edge_audio(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

async def get_polly_audio(text: str, voice: str) -> bytes:
    access_key = get_setting('AWS_ACCESS_KEY_ID')
    secret_key = get_setting('AWS_SECRET_ACCESS_KEY')
    region = get_setting('AWS_REGION', 'us-east-1')

    if not access_key or not secret_key:
        raise Exception("AWS Credentials missing for Polly")

    loop = asyncio.get_event_loop()
    client = await loop.run_in_executor(
        None,
        lambda: boto3.client(
            'polly',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
    )

    # Map our internal IDs to Polly Voice IDs if necessary
    # webapp uses polly_ruth, polly_danielle etc.
    polly_voice = voice.replace('polly_', '').capitalize()

    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.synthesize_speech(
                Text=text,
                VoiceId=polly_voice,
                OutputFormat='mp3',
                Engine='neural'
            )
        )
    except Exception as e:
        err_msg = str(e)
        if "selected engine: neural" in err_msg:
            # Try long-form (some newer voices like Patrick only support this)
            try:
                logger.info(f"Fallback to long-form engine for voice: {polly_voice}")
                response = await loop.run_in_executor(
                    None,
                    lambda: client.synthesize_speech(
                        Text=text,
                        VoiceId=polly_voice,
                        OutputFormat='mp3',
                        Engine='long-form'
                    )
                )
            except Exception as e2:
                if "selected engine: long-form" in str(e2):
                    logger.info(f"Fallback to standard engine for voice: {polly_voice}")
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.synthesize_speech(
                            Text=text,
                            VoiceId=polly_voice,
                            OutputFormat='mp3',
                            Engine='standard'
                        )
                    )
                else:
                    raise e2
        else:
            raise e

    return response['AudioStream'].read()

def _split_for_inworld(text: str, max_chars: int = 1900) -> list[str]:
    """Split text into chunks at sentence boundaries to respect Inworld's 2000-char limit."""
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ''
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ''
            while len(sentence) > max_chars:
                chunks.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            current = sentence
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = (current + ' ' + sentence).lstrip()
        else:
            if current:
                chunks.append(current.strip())
            current = sentence
    if current:
        chunks.append(current.strip())
    return chunks


async def _inworld_chunk(text: str, voice_id: str, api_key: str) -> bytes:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {api_key}'
    }
    payload = {
        'text': text,
        'voiceId': voice_id,
        'modelId': 'inworld-tts-1.5-mini',
        'audioConfig': {'audioEncoding': 'MP3', 'sampleRateHertz': 24000}
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post('https://api.inworld.ai/tts/v1/voice', json=payload, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Inworld API error {r.status_code}: {r.text[:200]}")
    data = r.json()
    return base64.b64decode(data.get('audioContent', ''))


async def get_inworld_audio(text: str, voice: str) -> bytes:
    api_key = get_setting('INWORLD_API_KEY') or os.environ.get('INWORLD_API_KEY', '')
    if not api_key:
        raise Exception("Inworld API key not configured")
    # Strip inworld_ prefix to get the raw API voice ID (e.g. inworld_Blake -> Blake)
    voice_id = voice.replace('inworld_', '') if voice.startswith('inworld_') else voice
    chunks = _split_for_inworld(text)
    parts = [await _inworld_chunk(chunk, voice_id, api_key) for chunk in chunks]
    return b''.join(parts)


DEEPGRAM_VOICE_MAP = {
    'deepgram_orion': 'aura-2-orion-en',
    'deepgram_orpheus': 'aura-2-orpheus-en',
    'deepgram_arcas': 'aura-2-arcas-en',
    'deepgram_pandora': 'aura-2-pandora-en',
    'deepgram_hyperion': 'aura-2-hyperion-en',
    'deepgram_angus': 'aura-angus-en',
}


def _split_for_deepgram(text: str, max_chars: int = 400) -> list[str]:
    """Split text into manageable narrative chunks at sentence or clause boundaries."""
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ''
    for sentence in sentences:
        if len(sentence) > max_chars:
            clauses = re.split(r'(?<=[;:\u2014])\s+', sentence)
            for clause in clauses:
                if len(current) + len(clause) + 1 <= max_chars:
                    current = (current + ' ' + clause).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = clause
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = (current + ' ' + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


async def _deepgram_chunk(text: str, model_id: str, api_key: str) -> bytes:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {api_key}',
        'User-Agent': 'EpubToAudiobook/1.0'
    }
    url = f"https://api.deepgram.com/v1/speak?model={model_id}&encoding=mp3"
    payload = {'text': text}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Deepgram API error {r.status_code}: {r.text[:200]}")
    return r.content


async def get_deepgram_audio(text: str, voice: str) -> bytes:
    api_key = get_setting('DEEPGRAM_API_KEY') or os.environ.get('DEEPGRAM_API_KEY', '')
    if not api_key:
        raise Exception("Deepgram API key not configured")

    model_id = DEEPGRAM_VOICE_MAP.get(voice, voice)
    if model_id.startswith('deepgram_'):
        model_id = model_id.replace('deepgram_', '')
    if not model_id.startswith('aura-') and not model_id.startswith('aura-2-'):
        model_id = 'aura-2-orion-en'

    chunks = _split_for_deepgram(text)
    parts = []
    for c in chunks:
        audio_chunk = await _deepgram_chunk(c, model_id, api_key)
        parts.append(audio_chunk)
    return b''.join(parts)


@app.post("/j/{job_id}/v1/audio/speech")
async def audio_speech(job_id: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    text = payload.get("input") or payload.get("text") or ""
    voice = payload.get("voice", "")
    d = job_dir(job_id)
    chunks_path = d / "chunks.jsonl"

    # Check if this is an Edge, Polly, Inworld, or Deepgram voice
    is_edge = voice.endswith("Neural") or payload.get("model") == "edge"
    is_polly = voice.startswith("polly_") or payload.get("model") == "polly"
    is_inworld = voice.startswith("inworld_") or payload.get("model") == "inworld"
    is_deepgram = (
        voice.startswith("deepgram_")
        or voice.startswith("aura-")
        or payload.get("model") == "deepgram"
    )

    try:
        if is_deepgram:
            logger.info(f"Processing Deepgram request for voice: {voice}")
            audio_content = await get_deepgram_audio(text, voice)
        elif is_inworld:
            logger.info(f"Processing Inworld request for voice: {voice}")
            audio_content = await get_inworld_audio(text, voice)
        elif is_edge:
            logger.info(f"Processing Edge request for voice: {voice}")
            audio_content = await get_edge_audio(text, voice)
        elif is_polly:
            logger.info(f"Processing Polly request for voice: {voice}")
            audio_content = await get_polly_audio(text, voice)
        else:
            target_base = UPSTREAM_BASE
            upstream_url = f"{target_base}/audio/speech"
            async with httpx.AsyncClient(timeout=None) as client:
                r = await client.post(upstream_url, json=payload)
            if r.status_code != 200:
                logger.error(f"Upstream error: {r.status_code} - {r.text}")
                raise HTTPException(status_code=r.status_code, detail=f"Upstream error: {r.text}")
            audio_content = r.content
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    duration = get_audio_duration(audio_content)
    append_jsonl(
        chunks_path,
        {
            "ts": _now_iso(),
            "job_id": job_id,
            "text": text,
            "text_sha256": sha256_hex(text),
            "strict": normalize_strict(text),
            "loose": normalize_loose(text),
            "model": payload.get("model"),
            "voice": voice,
            "duration_s": duration
        }
    )

    return Response(content=audio_content, status_code=200, media_type="audio/mpeg")

@app.post("/j/{job_id}/finalize")
async def finalize(job_id: str):
    d = job_dir(job_id)
    out = {"ok": True, "job_id": job_id, "created_at": _now_iso()}
    (d / "finalize.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out

@app.get("/healthz")
async def healthz():
    return {"ok": True}
