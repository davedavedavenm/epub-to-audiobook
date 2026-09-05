from __future__ import annotations

import re
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE = ROOT / "fixtures" / "breakneck_ch1_2pages_norm.txt"
OUT_DIR = ROOT / "evaluations" / "new-engines" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def sentence_chunks(text: str) -> list[str]:
    protected = text
    marker = "\ue000"
    for abbrev in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "vs."):
        protected = protected.replace(abbrev, abbrev[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?])\s+", protected)
        if item.strip()
    ]
    return chunks

def render_kokoro(text: str, chunks: list[str]) -> None:
    print("\n=== Rendering Kokoro (bm_george) ===")
    url = "http://localhost:8880/v1/audio/speech"
    mp3_out = OUT_DIR / "kokoro_breakneck_ch1_george.mp3"
    started = time.perf_counter()
    parts = []
    
    for idx, c in enumerate(chunks, 1):
        c_start = time.perf_counter()
        resp = requests.post(
            url,
            json={"input": c, "voice": "bm_george", "response_format": "mp3", "speed": 1.0},
            timeout=30,
        )
        resp.raise_for_status()
        parts.append(resp.content)
        dur = time.perf_counter() - c_start
        print(f"  Kokoro chunk {idx}/{len(chunks)} in {dur:.2f}s ({len(resp.content)} bytes)")

    # Join mp3s
    raw_joined = b"".join(parts)
    mp3_out.write_bytes(raw_joined)
    wall = time.perf_counter() - started
    print(f"Kokoro complete: {mp3_out.name} ({len(raw_joined):,} bytes in {wall:.2f}s)")

def main():
    text = TEXT_FILE.read_text(encoding="utf-8").strip()
    chunks = sentence_chunks(text)
    print(f"Total chunks: {len(chunks)}")
    
    # Try Kokoro if reachable
    try:
        r = requests.get("http://localhost:8880/v1/models", timeout=3)
        if r.status_code == 200:
            render_kokoro(text, chunks)
    except Exception as e:
        print(f"Kokoro not reachable: {e}")

if __name__ == "__main__":
    main()
