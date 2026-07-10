#!/usr/bin/env python3
"""OpenBooks websocket bridge: search + download one book.

Usage: openbooks_bridge.py "<query>"          # search, pick best, download
       openbooks_bridge.py "!<raw line>"      # raw download command passthrough

Fixes baked in (2026-07-10):
- GENERIC result scoring (query tokens + epub preference). The old bridge had
  hardcoded Frankenstein-era scoring that mis-ranked everything else.
- PARSE-ERROR FALLBACK: upstream openbooks (unmaintained since 2023) fails to
  parse some IRC servers' result lines (e.g. Ashurbanipal's) and returns them
  in `errors[].line` instead of `books` — a found book was dropped every search
  for days. If no parseable book matches but an error line matches the query,
  we download it RAW. Verified live: the error payload carries the full line.
"""
import asyncio
import json
import os
import re
import sys
import time

import websockets

OPENBOOKS_WS = os.environ.get("OPENBOOKS_WS", "ws://192.168.1.248:6081/ws")
LOCK_FILE = "/tmp/openbooks_cooldown.lock"
COOLDOWN_SECONDS = 60
RECV_TIMEOUT_S = 5
SEARCH_TIMEOUT_S = 25


def _tokens(q: str):
    return [t for t in re.findall(r"[a-z0-9']+", q.lower()) if len(t) > 1]


def _score_text(text_lower: str, toks) -> int:
    score = sum(12 for t in toks if t in text_lower)
    if "epub" in text_lower:
        score += 50
    elif ".mobi" in text_lower or "(mobi" in text_lower:
        score += 10
    if "retail" in text_lower:
        score += 8
    return score


async def _recv_json(ws, timeout_s: int):
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
    except asyncio.TimeoutError:
        return None
    try:
        return json.loads(msg)
    except Exception:
        return None


async def openbooks_download(query: str) -> bool:
    if os.path.exists(LOCK_FILE):
        if time.time() - os.path.getmtime(LOCK_FILE) < COOLDOWN_SECONDS:
            print(f"Cooldown active. Skipping: {query}")
            return True
    with open(LOCK_FILE, "w") as f:
        f.write(str(time.time()))

    try:
        async with websockets.connect(OPENBOOKS_WS) as ws:
            await ws.send(json.dumps({"type": 1, "payload": {}}))
            deadline = time.time() + 15
            while time.time() < deadline:
                resp = await _recv_json(ws, RECV_TIMEOUT_S)
                if resp and resp.get("type") == 1:
                    break
            else:
                print("Handshake timeout", file=sys.stderr)
                return False

            if query.startswith("!"):
                print(f"Sending RAW download command: {query}")
                await ws.send(json.dumps({"type": 3, "payload": {"book": query}}))
                await asyncio.sleep(2)
                return True

            await ws.send(json.dumps({"type": 2, "payload": {"query": query}}))
            toks = _tokens(query)
            start = time.time()
            while time.time() - start < SEARCH_TIMEOUT_S:
                resp = await _recv_json(ws, RECV_TIMEOUT_S)
                if not resp or resp.get("type") != 2:
                    continue

                books = resp.get("books") or []
                scored = []
                for b in books:
                    full = b.get("full") or ""
                    s = _score_text(full.lower(), toks)
                    # require at least half the query tokens to match
                    hits = sum(1 for t in toks if t in full.lower())
                    if toks and hits * 2 < len(toks):
                        continue
                    scored.append((s, full))

                # PARSE-ERROR FALLBACK: unparsed lines still carry the result.
                for e in (resp.get("errors") or []):
                    line = (e or {}).get("line") or ""
                    ll = line.lower()
                    hits = sum(1 for t in toks if t in ll)
                    if toks and hits * 2 >= len(toks):
                        raw = line if line.startswith("!") else None
                        if raw:
                            # slight penalty vs parsed books so parsed wins ties
                            scored.append((_score_text(ll, toks) - 5, raw))
                            print(f"parse-error fallback candidate: {line[:100]}")

                if not scored:
                    return False
                scored.sort(key=lambda x: x[0], reverse=True)
                best = scored[0][1]
                print(f"Downloading: {best[:120]}")
                await ws.send(json.dumps({"type": 3, "payload": {"book": best}}))
                await asyncio.sleep(2)
                return True

            return False
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: openbooks_bridge.py <query>", file=sys.stderr)
        raise SystemExit(2)
    ok = asyncio.run(openbooks_download(sys.argv[1]))
    raise SystemExit(0 if ok else 1)
