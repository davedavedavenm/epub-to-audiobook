#!/usr/bin/env python3
"""Standalone EPUB -> audiobook converter that talks to any OpenAI-compatible
TTS engine over HTTP. Reuses the repo's preprocessing pipeline.

Designed to run ANYWHERE the engine is reachable: locally, or on a free GitHub
Actions runner (16 GB RAM — enough for TADA, unlike the NUC), or against a Vast
GPU. Writes one MP3 per chapter to the output dir.

Usage:
  python scripts/convert_book.py --epub book.epub --engine-url http://localhost:8005/v1 \
      --voice uk_male_minter_tada --out ./audiobook [--start 1 --end 3]
"""
import argparse
import os
import re
import sys
import zipfile
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from tts_preprocess import sanitize_html, normalize_text_for_tts  # noqa: E402
import requests  # noqa: E402


class _P(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.inp = False
    def handle_starttag(self, t, a):
        if t == 'p':
            self.inp = True; self.parts.append('\n\n')
    def handle_endtag(self, t):
        if t == 'p':
            self.inp = False
    def handle_data(self, d):
        if self.inp:
            self.parts.append(d)


def spine_docs(z):
    opf = [n for n in z.namelist() if n.endswith('.opf')][0]
    t = z.read(opf).decode('utf-8', 'ignore')
    base = opf.rsplit('/', 1)[0] + '/' if '/' in opf else ''
    items = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', t))
    items.update({b: a for a, b in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', t)})
    spine = re.findall(r'<itemref[^>]*idref="([^"]+)"', t)
    docs = [base + items[i] for i in spine if i in items and re.search(r'\.x?html?$', items.get(i, ''))]
    return [d for d in docs if d in z.namelist()]


def chapter_text(z, name):
    p = _P(); p.feed(sanitize_html(z.read(name).decode('utf-8', 'ignore')))
    text = re.sub(r'[ \t]+', ' ', ''.join(p.parts)).strip()
    return normalize_text_for_tts(text)


def chunk(text, n):
    text = re.sub(r'\s+', ' ', text)
    sents = re.split(r'(?<=[.!?"”])\s+', text)
    out, cur = [], ''
    for s in sents:
        if cur and len(cur) + len(s) > n:
            out.append(cur); cur = s
        else:
            cur = (cur + ' ' + s).strip()
    if cur:
        out.append(cur)
    return out or [text]


def synth(engine_url, voice, text, chunk_chars):
    import time
    parts = []
    for c in chunk(text, chunk_chars):
        # per-chunk retry: long CPU generations can drop the connection
        for attempt in range(3):
            try:
                r = requests.post(f"{engine_url.rstrip('/')}/audio/speech",
                                  json={"model": "tts-1", "input": c, "voice": voice,
                                        "response_format": "mp3"},
                                  timeout=(15, 3600))
                r.raise_for_status()
                parts.append(r.content)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 2:
                    raise
                print(f"  chunk retry {attempt+1}/2 after error: {str(e)[:80]}", flush=True)
                time.sleep(10 * (attempt + 1))
    return b''.join(parts)   # mp3 frames concatenate fine for playback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epub', required=True, help='path or http(s) URL')
    ap.add_argument('--engine-url', required=True)
    ap.add_argument('--voice', required=True)
    ap.add_argument('--out', default='./audiobook')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=0)
    ap.add_argument('--chunk-chars', type=int, default=280)
    ap.add_argument('--min-words', type=int, default=120,
                    help='skip chapters shorter than this (front-matter)')
    a = ap.parse_args()

    epub = a.epub
    if epub.startswith('http'):
        dst = '/tmp/book.epub'
        urllib.request.urlretrieve(epub, dst); epub = dst

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(epub)
    docs = spine_docs(z)
    idx = 0
    for name in docs:
        text = chapter_text(z, name)
        if len(text.split()) < a.min_words:
            continue
        idx += 1
        if idx < a.start or (a.end and idx > a.end):
            continue
        fn_existing = out / f"{idx:03d}.mp3"
        if fn_existing.exists() and fn_existing.stat().st_size > 10240:
            print(f"[chapter {idx}] already done — skipping (resume)", flush=True)
            continue
        print(f"[chapter {idx}] {len(text.split())} words -> synthesizing", flush=True)
        audio = synth(a.engine_url, a.voice, text, a.chunk_chars)
        fn = out / f"{idx:03d}.mp3"
        fn.write_bytes(audio)
        print(f"[chapter {idx}] wrote {fn} ({len(audio)} bytes)", flush=True)
    print("DONE", flush=True)


if __name__ == '__main__':
    main()
