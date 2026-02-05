#!/usr/bin/env python3
"""OpenAI-compatible TTS proxy with transcript capture.

The conversion container is launched with:
  OPENAI_BASE_URL=http://tts-proxy:8882/j/<job_id>/v1

The proxy forwards requests to Kokoro and logs exact input texts to:
  /data/transcripts/<job_id>/chunks.jsonl
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

UPSTREAM_BASE = os.environ.get("TTS_UPSTREAM_BASE", "http://kokoro-tts:8880/v1").rstrip("/")
STORE_ROOT = Path(os.environ.get("TRANSCRIPTS_DIR", "/data/transcripts"))
STORE_ROOT.mkdir(parents=True, exist_ok=True)

_re_ws = re.compile(r"\s+")
_re_punct = re.compile(r"[^\w\s]+", flags=re.UNICODE)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def job_dir(job_id: str) -> Path:
    d = STORE_ROOT / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


async def upstream_get(path: str) -> Response:
    url = f"{UPSTREAM_BASE}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))


@app.get("/healthz")
async def healthz():
    return {"ok": True, "upstream": UPSTREAM_BASE}


@app.get("/j/{job_id}/v1/models")
async def models(job_id: str):
    return await upstream_get("models")


@app.get("/j/{job_id}/v1/audio/voices")
async def voices(job_id: str):
    return await upstream_get("audio/voices")


@app.post("/j/{job_id}/v1/audio/speech")
async def audio_speech(job_id: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    text = payload.get("input") or payload.get("text") or ""
    if not isinstance(text, str):
        text = str(text)

    d = job_dir(job_id)
    chunks_path = d / "chunks.jsonl"
    strict = normalize_strict(text)
    loose = normalize_loose(text)

    append_jsonl(
        chunks_path,
        {
            "ts": _now_iso(),
            "job_id": job_id,
            "text": text,
            "text_sha256": sha256_hex(text),
            "strict": strict,
            "strict_sha256": sha256_hex(strict),
            "loose": loose,
            "loose_sha256": sha256_hex(loose),
            "model": payload.get("model"),
            "voice": payload.get("voice"),
        },
    )

    upstream_url = f"{UPSTREAM_BASE}/audio/speech"
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(upstream_url, json=payload)

    ct = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, status_code=r.status_code, media_type=ct)


@app.post("/j/{job_id}/finalize")
async def finalize(job_id: str):
    d = job_dir(job_id)
    chunks_path = d / "chunks.jsonl"
    if not chunks_path.exists():
        return JSONResponse({"ok": False, "error": "no chunks captured"}, status_code=404)

    raw_all: list[str] = []
    strict_all: list[str] = []
    loose_all: list[str] = []
    n = 0

    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("text") or ""
            raw_all.append(t)
            strict_all.append(obj.get("strict") or normalize_strict(t))
            loose_all.append(obj.get("loose") or normalize_loose(t))
            n += 1

    raw_join = "\n".join(raw_all)
    strict_join = "\n".join(strict_all)
    loose_join = "\n".join(loose_all)

    out = {
        "ok": True,
        "job_id": job_id,
        "chunks": n,
        "raw_sha256": sha256_hex(raw_join),
        "strict_sha256": sha256_hex(strict_join),
        "loose_sha256": sha256_hex(loose_join),
        "created_at": _now_iso(),
    }

    (d / "finalize.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
