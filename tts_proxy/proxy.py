import re
import os
import io
import json
import hashlib
import time
import sqlite3
import boto3
import httpx
import asyncio
import functools
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from mutagen.mp3 import MP3
import edge_tts

app = FastAPI()

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
        print(f"Duration error: {e}")
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

def job_dir(job_id: str) -> Path:
    d = STORE_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

async def get_edge_audio(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

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
    
    # Check if this is an Edge voice or specifically requested via engine
    is_edge = voice.endswith("Neural") or payload.get("model") == "edge"
    
    if is_edge:
        print(f"Processing Edge request for voice: {voice}")
        audio_content = await get_edge_audio(text, voice)
    else:
        # Upstream Kokoro/OpenAI
        upstream_url = f"{UPSTREAM_BASE}/audio/speech"
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(upstream_url, json=payload)
        audio_content = r.content

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