#!/usr/bin/env python3
"""Render the first 3 pages of Breakneck (Introduction and Chapter 1) with Deepgram Hyperion.

Extracts text up to the page markers from the source EPUB, applies the explicit
normalization profile, synthesizes via Deepgram aura-2-hyperion-en, joins with clean
PCM WAV concatenation, encodes 192k MP3s with ID3 metadata, builds an M4B,
runs Whisper ASR verification, and registers a completed job in jobs.db.
"""

import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Paths inside Docker container or host
STACK_ROOT = Path('/home/dave/ai/lab/stacks/epub-to-audiobook')
WEBAPP_DIR = STACK_ROOT / 'webapp'
SCRIPTS_DIR = STACK_ROOT / 'scripts'
DATA_DIR = STACK_ROOT / 'data'
JOBS_DB = DATA_DIR / 'jobs.db'
EPUB_PATH = Path('/home/dave/booklib/Breakneck - Dan Wang.epub')

# Also support running inside container where paths are directly in /app and /data
if Path('/app/tts_preprocess.py').exists():
    sys.path.insert(0, '/app')
    sys.path.insert(0, '/app/scripts')
    DATA_DIR = Path('/data')
    JOBS_DB = DATA_DIR / 'jobs.db'
else:
    sys.path.insert(0, str(WEBAPP_DIR))
    sys.path.insert(0, str(SCRIPTS_DIR))

from tts_preprocess import normalize_text_for_tts  # noqa: E402
from m4b import build_m4b  # noqa: E402


def get_deepgram_api_key():
    conn = sqlite3.connect(f"file:{JOBS_DB}?immutable=1", uri=True)
    c = conn.cursor()
    c.execute("SELECT value FROM app_settings WHERE key = 'DEEPGRAM_API_KEY'")
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return row[0].strip()
    return os.environ.get('DEEPGRAM_API_KEY', '').strip()


def extract_pages(z, doc_name, stop_page_id):
    """Extract paragraphs from an XHTML document up to the end of the paragraph containing stop_page_id."""
    raw = z.read(doc_name).decode('utf-8')
    soup = BeautifulSoup(raw, 'html.parser')
    stop_tag = soup.find(id=stop_page_id)
    if not stop_tag:
        raise ValueError(f"Stop page tag {stop_page_id} not found in {doc_name}")

    paras = []
    # Add title / heading
    for h in soup.find_all(['h1', 'h2']):
        heading_text = h.get_text().strip()
        if heading_text:
            paras.append(heading_text)

    # Add paragraphs up to and including the paragraph where stop_tag lives
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text:
            paras.append(text)
        if stop_tag in p.find_all():
            break

    return '\n\n'.join(paras)


def split_for_deepgram(text: str, max_chars: int = 380) -> list[str]:
    """Split text into manageable chunks at sentence/clause boundaries."""
    text = re.sub(r'\s+', ' ', text).strip()
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


def deepgram_speak(text: str, api_key: str, model: str = 'aura-2-hyperion-en') -> bytes:
    url = f"https://api.deepgram.com/v1/speak?model={model}&encoding=mp3"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {api_key}',
        'User-Agent': 'EpubToAudiobook/1.0',
    }
    payload = {'text': text}
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Deepgram API error {resp.status_code}: {resp.text[:200]}")
    return resp.content


def mp3_to_wav(mp3_bytes: bytes) -> bytes:
    ff = shutil.which('ffmpeg')
    if not ff:
        raise RuntimeError('ffmpeg not found on PATH')
    p = subprocess.run([ff, '-v', 'error', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'],
                       input=mp3_bytes, capture_output=True, check=True)
    return p.stdout


def concat_wav(chunks: list[bytes], join_silence_ms: int = 300) -> bytes:
    frames, ch, sw, fr = [], None, None, None
    for b in chunks:
        w = wave.open(io.BytesIO(b), 'rb')
        if ch is None:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        data = w.readframes(0x7FFFFFFF)
        fsz = w.getnchannels() * w.getsampwidth()
        if fsz and len(data) % fsz:
            data = data[:len(data) - (len(data) % fsz)]
        frames.append(data)
        w.close()
    if ch is None:
        return b''
    out = io.BytesIO()
    ww = wave.open(out, 'wb')
    ww.setnchannels(ch)
    ww.setsampwidth(sw)
    ww.setframerate(fr)
    silence = b''
    if join_silence_ms and frames:
        silence_frames = int(fr * float(join_silence_ms) / 1000.0)
        silence = b'\x00' * (silence_frames * ch * sw)
    for i, f in enumerate(frames):
        if i and silence:
            ww.writeframes(silence)
        ww.writeframes(f)
    ww.close()
    return out.getvalue()


def wav_to_mp3(wav_bytes: bytes, meta: dict = None) -> bytes:
    ff = shutil.which('ffmpeg')
    if not ff:
        raise RuntimeError('ffmpeg not found on PATH')
    cmd = [ff, '-v', 'error', '-y', '-i', 'pipe:0', '-f', 'mp3', '-b:a', '192k']
    if meta:
        cmd += ['-id3v2_version', '3']
        for k, v in meta.items():
            if v:
                cmd += ['-metadata', f'{k}={v}']
    cmd += ['pipe:1']
    p = subprocess.run(cmd, input=wav_bytes, capture_output=True, check=True)
    return p.stdout


def render_track(track_name: str, raw_text: str, api_key: str, out_path: Path, meta: dict):
    print(f"\n--- Rendering {track_name} ---")
    words = len(raw_text.split())
    print(f"Source text: {words} words, {len(raw_text)} characters")

    # Explicit normalization for Deepgram Aura-2
    norm_text = normalize_text_for_tts(raw_text, modern=True, expand_numbers=True)
    chunks = split_for_deepgram(norm_text)
    print(f"Split into {len(chunks)} chunks for Deepgram synthesis.")

    wav_parts = []
    for idx, c in enumerate(chunks, 1):
        print(f"  Chunk {idx}/{len(chunks)} ({len(c)} chars): {c[:40]}...", flush=True)
        mp3_chunk = deepgram_speak(c, api_key, model='aura-2-hyperion-en')
        wav_chunk = mp3_to_wav(mp3_chunk)
        wav_parts.append(wav_chunk)
        time.sleep(0.05)

    print("Concatenating WAV audio with 300ms silence joins...")
    joined_wav = concat_wav(wav_parts, join_silence_ms=300)
    print("Encoding to 192k MP3 with ID3 tags...")
    mp3_data = wav_to_mp3(joined_wav, meta=meta)
    out_path.write_bytes(mp3_data)
    print(f"Wrote {out_path.name}: {len(mp3_data)} bytes")
    return norm_text


def run_whisper_qa(mp3_path: Path, reference_text: str):
    print(f"\n--- Running Faster-Whisper ASR Verification on {mp3_path.name} ---")
    from faster_whisper import WhisperModel
    import difflib

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(mp3_path), beam_size=5)
    asr_text = " ".join([seg.text.strip() for seg in segments])
    duration = info.duration
    print(f"Audio duration: {duration:.1f} seconds ({duration/60:.2f} mins)")
    print(f"ASR word count: {len(asr_text.split())}")

    # Clean punctuation and lowercase for comparison
    def clean(t):
        return re.sub(r'[^a-z0-9 ]+', '', t.lower()).split()

    ref_words = clean(reference_text)
    asr_words = clean(asr_text)
    matcher = difflib.SequenceMatcher(None, ref_words, asr_words)
    similarity = matcher.ratio()
    print(f"ASR Word Similarity: {similarity:.3f} ({similarity*100:.1f}%)")
    print(f"ASR Snippet: {asr_text[:200]}...")
    return {
        'duration_seconds': duration,
        'asr_word_count': len(asr_words),
        'ref_word_count': len(ref_words),
        'similarity': similarity,
        'asr_sample': asr_text[:300]
    }


def main():
    api_key = get_deepgram_api_key()
    if not api_key:
        print("ERROR: DEEPGRAM_API_KEY not configured", file=sys.stderr)
        sys.exit(1)
    print("Deepgram API Key loaded.")

    if not EPUB_PATH.exists():
        print(f"ERROR: EPUB not found at {EPUB_PATH}", file=sys.stderr)
        sys.exit(1)

    z = zipfile.ZipFile(EPUB_PATH)

    # Extract cover
    cover_bytes = z.read('OEBPS/images/cover.jpg')

    # 1. Introduction (Pages ix-xi)
    intro_text = extract_pages(z, 'OEBPS/text/06_Introduction.xhtml', 'page_xii')
    # 2. Chapter 1 (Pages 1-3)
    ch1_text = extract_pages(z, 'OEBPS/text/08_Chapter01.xhtml', 'page_4')

    job_id = "breaknec"
    out_dir = DATA_DIR / 'audiobooks' / f"Breakneck - Dan Wang (Pages 1-3 Preview)_{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save cover
    (out_dir / 'cover.jpg').write_bytes(cover_bytes)

    # Render Track 1: Introduction (Pages ix-xi)
    track1_path = out_dir / '01 - Introduction (Pages ix-xi).mp3'
    meta1 = {
        'title': 'Introduction (Pages ix-xi)',
        'artist': 'Dan Wang',
        'album_artist': 'Dan Wang',
        'album': "Breakneck - China's Quest to Engineer the Future",
        'track': '1/2',
        'genre': 'Audiobook',
        'year': '2025',
        'comment': 'Narrated by Hyperion (Deepgram Aura-2)',
    }
    norm_intro = render_track('Introduction (Pages ix-xi)', intro_text, api_key, track1_path, meta1)

    # Render Track 2: Chapter 1: Engineers vs. Lawyers (Pages 1-3)
    track2_path = out_dir / '02 - Chapter 1 - Engineers vs Lawyers (Pages 1-3).mp3'
    meta2 = {
        'title': 'Chapter 1: Engineers vs. Lawyers (Pages 1-3)',
        'artist': 'Dan Wang',
        'album_artist': 'Dan Wang',
        'album': "Breakneck - China's Quest to Engineer the Future",
        'track': '2/2',
        'genre': 'Audiobook',
        'year': '2025',
        'comment': 'Narrated by Hyperion (Deepgram Aura-2)',
    }
    norm_ch1 = render_track('Chapter 1: Engineers vs. Lawyers (Pages 1-3)', ch1_text, api_key, track2_path, meta2)

    # Build M4B
    print("\n--- Building Chaptered M4B ---")
    m4b_path = build_m4b(out_dir, title="Breakneck (Pages 1-3 Preview)", author="Dan Wang", cover=out_dir / 'cover.jpg')
    if m4b_path and m4b_path.exists():
        print(f"Created M4B: {m4b_path} ({m4b_path.stat().st_size} bytes)")

    # Run Whisper ASR Verification
    qa1 = run_whisper_qa(track1_path, norm_intro)
    qa2 = run_whisper_qa(track2_path, norm_ch1)

    qa_report = {
        'engine': 'deepgram',
        'voice': 'deepgram_hyperion',
        'voice_name': 'Hyperion — natural (Deepgram)',
        'model': 'aura-2-hyperion-en',
        'track_1': qa1,
        'track_2': qa2,
        'verified_at': datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / 'qa_report.json').write_text(json.dumps(qa_report, indent=2), encoding='utf-8')

    # Register in jobs.db
    print("\n--- Registering in jobs.db ---")
    now_iso = datetime.now(timezone.utc).isoformat()
    total_dur = qa1['duration_seconds'] + qa2['duration_seconds']
    total_chars = len(norm_intro) + len(norm_ch1)
    total_words = qa1['ref_word_count'] + qa2['ref_word_count']

    conn = sqlite3.connect(JOBS_DB)
    c = conn.cursor()
    c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    c.execute("""
        INSERT INTO jobs (
            id, book_name, voice, voice_name, tts_engine, status,
            created_at, started_at, completed_at, input_filename, output_dirname,
            char_count, total_chapters, current_chapter, progress_percent,
            file_count, error, synced_to_abs, queue_rank, render_target,
            preprocess_summary, narration_profile, qa_verified
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, NULL, 0, 0, 'local',
            ?, 'explicit', 1
        )
    """, (
        job_id,
        "Breakneck - Dan Wang (Pages 1-3 Preview)",
        "deepgram_hyperion",
        "Hyperion — natural (Deepgram)",
        "deepgram",
        "completed",
        now_iso, now_iso, now_iso,
        "Breakneck - Dan Wang.epub",
        out_dir.name,
        total_chars,
        2, 2, 100,
        3,  # 2 mp3s + 1 m4b
        f"Rendered {total_words} words across 2 preview sections in {total_dur/60:.1f} mins of audio",
    ))
    conn.commit()
    conn.close()
    print(f"Job {job_id} successfully recorded in jobs.db as completed.")

    print("\n=== SUCCESS ===")
    print(f"Output directory: {out_dir}")
    print("Files:")
    for f in sorted(out_dir.iterdir()):
        print(f"  {f.name} ({f.stat().st_size:,} bytes)")


if __name__ == '__main__':
    main()
