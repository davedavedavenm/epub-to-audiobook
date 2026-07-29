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
import io
import json
import os
import re
import sys
import wave
import shutil
import zipfile
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from tts_preprocess import sanitize_html, normalize_text_for_tts  # noqa: E402
# Shared chapter numbering — the SAME function the web UI's picker uses, so the
# chapter number a user selects is exactly the chapter that renders here.
from chapters import spine_docs, renderable_wordcount, _title_for  # noqa: E402
from book_meta import read_book_meta  # noqa: E402
import requests  # noqa: E402

# Optional adaptive pronunciation (QA Layer 1) — same as the app. Needs an LLM
# configured (LLM_API_KEY env). Without it, falls back to a small seed dict so
# common place/brand names still get help. This closes the gap where standalone
# script conversions (e.g. Apple in China) skipped pronunciation entirely.
# Seed pronunciations live in ONE place (webapp/lexicon.py) so the voice-audition
# sample and a real render use the identical dictionary.
from lexicon import SEED_PRONUNCIATION  # noqa: E402

_LEXICON = {}
_MODERN = True   # this script only drives the modern engines
_SEARCH_REPLACE_RULES = []

def load_search_and_replace(path):
    rules = []
    if not path or not os.path.exists(path):
        return rules
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '==' in line:
                    pattern, replacement = line.split('==', 1)
                    try:
                        compiled = re.compile(pattern)
                        rules.append((compiled, replacement))
                    except Exception as e:
                        print(f"Warning: invalid regex pattern '{pattern}' in {path}: {e}", flush=True)
    except Exception as e:
        print(f"Warning: failed to load search and replace file {path}: {e}", flush=True)
    return rules


def apply_search_and_replace(text, rules):
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def build_lexicon(epub_path):
    lex = dict(SEED_PRONUNCIATION)
    try:
        from llm_metadata import generate_narration_profile, generate_lexicon
        prof = generate_narration_profile(Path(epub_path)) or {}
        lex.update(prof.get('rules', {}))
        lex.update(generate_lexicon(Path(epub_path)) or {})
        if prof.get('form'):
            print(f"book form: {prof['form']} (domain: {prof.get('domain')})", flush=True)
        print(f"pronunciation rules: {len(lex)} ({'LLM+seed' if prof.get('rules') else 'seed only — set LLM_API_KEY for adaptive'})", flush=True)
    except Exception as e:
        print(f"pronunciation: seed dict only ({e})", flush=True)
    return lex


def apply_lexicon(text, lex):
    for word in sorted(lex, key=len, reverse=True):
        text = re.sub(r'\b' + re.escape(word) + r'\b', lex[word], text, flags=re.IGNORECASE)
    return text


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


def chapter_text(z, name):
    p = _P(); p.feed(sanitize_html(z.read(name).decode('utf-8', 'ignore')))
    text = re.sub(r'[ \t]+', ' ', ''.join(p.parts)).strip()
    text = normalize_text_for_tts(text, modern=_MODERN)
    # Modern engines read real words natively; phonetic respellings ("Bay-JING")
    # make them worse (heard "bay...zhing"). For modern, keep ONLY acronym
    # letter-spacing rules ("CEO" -> "C E O" — heard "see you" otherwise);
    # other misreads go to the QA loop with targeted natural spellings.
    if _LEXICON:
        from tts_preprocess import _is_letter_spacing
        lex = _LEXICON if not _MODERN else {
            k: v for k, v in _LEXICON.items() if _is_letter_spacing(k, v)}
        if lex:
            text = apply_lexicon(text, lex)
    if _SEARCH_REPLACE_RULES:
        text = apply_search_and_replace(text, _SEARCH_REPLACE_RULES)
    return text


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


def _concat_wav(chunks, join_silence_ms=0):
    """Concatenate WAV byte-chunks at the SAMPLE level via stdlib wave — one
    clean, fully-decodable stream. Concatenating encoded MP3 bytes instead
    leaves corrupt frame headers at every join: players tolerate them but
    strict decoders (ffmpeg/PyAV, and audiobook players' seek/duration) hit
    "Header missing / Invalid data" and stop early (found proving QA #7 —
    a 27-min chapter decoded to 19 words). WAV concat avoids that entirely."""
    # STREAMING-WAV SAFE: some engines (kokoro) return a WAV whose size fields are
    # a placeholder (nframes = 0x7FFFFFFF) because the length isn't known up front.
    # Trusting that count made stdlib `wave` try to write a >4GB header
    # (struct.error) and the render died. Read the ACTUAL bytes, never the declared
    # frame count, and let the writer compute the real length.
    frames, ch, sw, fr = [], None, None, None
    for b in chunks:
        w = wave.open(io.BytesIO(b), 'rb')
        if ch is None:
            ch, sw, fr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        data = w.readframes(0x7FFFFFFF)          # returns only the real bytes present
        fsz = w.getnchannels() * w.getsampwidth()
        if fsz and len(data) % fsz:
            data = data[:len(data) - (len(data) % fsz)]
        frames.append(data)
        w.close()
    if ch is None:
        return b''
    out = io.BytesIO()
    ww = wave.open(out, 'wb')
    ww.setnchannels(ch)                          # set individually — never copy the
    ww.setsampwidth(sw)                          # source's placeholder nframes
    ww.setframerate(fr)
    silence = b''
    if join_silence_ms and frames:
        # PCM silence between independently generated passages. Qwen's accepted
        # audiobook audition used 350 ms; keeping this in the canonical
        # converter makes local, Kaggle and recovery renders byte-structurally
        # equivalent instead of hiding the pacing decision in one notebook.
        silence_frames = int(fr * float(join_silence_ms) / 1000.0)
        silence = b'\x00' * (silence_frames * ch * sw)
    for i, f in enumerate(frames):
        if i and silence:
            ww.writeframes(silence)
        ww.writeframes(f)
    ww.close()
    return out.getvalue()


def _to_mp3(wav_bytes, denoise=False, meta=None):
    """Encode a clean WAV to MP3 with one ffmpeg pass (single stream, correct
    framing). With denoise=True, applies afftdn (adaptive FFT denoiser) to
    knock down steady neural-vocoder hiss (TADA) without gutting speech — see
    issue #8. *meta* (title/album/artist/album_artist/track/genre) is written as
    ID3v2 tags so Audiobookshelf can group the files and order/name the chapters.
    Returns None if ffmpeg isn't on PATH — caller keeps the WAV."""
    ff = shutil.which('ffmpeg')
    if not ff:
        return None
    cmd = [ff, '-v', 'error', '-i', 'pipe:0']
    if denoise:
        # GENTLE: only shave the quiet hiss floor. The previous aggressive
        # setting (nf=-25) stripped highs and made TADA sound like a phone call
        # (Dave, 2026-07-08). nr=6/nf=-45 removes steady hiss without dulling
        # speech. Tune via issue #8.
        cmd += ['-af', 'afftdn=nr=6:nf=-45']
    cmd += ['-f', 'mp3', '-b:a', '192k']
    if meta:
        cmd += ['-id3v2_version', '3']
        for k, v in meta.items():
            if v:
                cmd += ['-metadata', f'{k}={v}']
    cmd += ['pipe:1']
    p = subprocess.run(cmd, input=wav_bytes, capture_output=True)
    return p.stdout if p.returncode == 0 and p.stdout else None


def _ensure_wav(data: bytes) -> bytes:
    """Return WAV bytes, transcoding if the engine ignored response_format=wav.

    We ask every engine for WAV so chunks join losslessly at the sample level,
    but not all of them honour it — the Edge path returns MP3 regardless, which
    made `_concat_wav` die with "file does not start with RIFF id" and meant
    Edge could never render a book at all, only previews (found by the E2E
    proof, 2026-07-25). Rather than special-case one engine, normalise whatever
    comes back: any engine that returns a non-WAV container now works.
    """
    if data[:4] == b'RIFF':
        return data
    ff = shutil.which('ffmpeg')
    if not ff:
        raise RuntimeError('engine returned non-WAV audio and ffmpeg is unavailable to convert it')
    p = subprocess.run([ff, '-v', 'error', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'],
                       input=data, capture_output=True)
    if p.returncode != 0 or p.stdout[:4] != b'RIFF':
        raise RuntimeError(f'could not convert engine audio to WAV: {p.stderr[:200]!r}')
    return p.stdout


def _capture_chunk(job_id, chapter_idx, text, voice, model):
    """Record the text we are about to voice, for post-flight verification.

    This used to be written ONLY by tts-proxy, so it existed only for engines
    routed through it. `get_engine_url()` returns direct URLs for
    chatterbox_nano, chatterbox and tada — the quality engines — which meant no
    Chatterbox book had ever been ASR-verified, and Nano is the default voice.
    The quality gate then wrote a clean result because it had nothing to
    inspect (#33).

    Capturing here, at the one place every render passes through, makes the
    record engine-independent. Same path and same schema as the proxy's writer,
    so `_read_captured_chunks()` needs no changes. Never fatal: a verification
    record must not be able to fail a render.
    """
    if not job_id:
        return
    try:
        import hashlib
        # `or` rather than a get() default: the worker sets TRANSCRIPTS_DIR to
        # an EMPTY STRING, and os.environ.get returns '' for that, not the
        # fallback. Path('') / job_id is a *relative* path, so the records
        # would land in the process's cwd and the verifier would never see
        # them — a silent no-op that looked exactly like the bug being fixed.
        base = os.environ.get('TRANSCRIPTS_DIR') or '/data/transcripts'
        d = Path(base) / job_id
        d.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "job_id": job_id,
            "chapter": chapter_idx,
            "text": text,
            "text_sha256": hashlib.sha256((text or '').encode('utf-8', 'replace')).hexdigest(),
            "model": model,
            "voice": voice,
            "source": "converter",
        }
        with (d / 'chunks.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  (chunk capture failed, non-fatal: {e})", flush=True)


def synth(engine_url, voice, text, chunk_chars, chapter_idx=1, model='tts-1', speed=1.0,
          job_id=None, request_timeout=3600, join_silence_ms=0):
    """Render text to a CLEAN single audio stream. Requests WAV per chunk (so
    chunks join losslessly at the sample level) and returns WAV bytes; the
    caller encodes one MP3 from that."""
    import time
    parts = []
    chunks = chunk(text, chunk_chars)
    total_chunks = len(chunks)
    for chunk_idx, c in enumerate(chunks, 1):
        print(f"Processing chapter-{chapter_idx}_chunk_{chunk_idx}_of_{total_chunks}", flush=True)
        # Record BEFORE synthesis: what we asked to be voiced is the thing the
        # verifier compares the audio against.
        _capture_chunk(job_id, chapter_idx, c, voice, model)
        # per-chunk retry: long CPU generations can drop the connection
        for attempt in range(3):
            try:
                r = requests.post(f"{engine_url.rstrip('/')}/audio/speech",
                                  json={"model": model, "input": c, "voice": voice,
                                        "response_format": "wav", "speed": speed,
                                        # Stable across retry/recovery. New engines use
                                        # it; existing Pydantic shims ignore the field.
                                        "seed": 12345 + ((chapter_idx - 1) * 1000) + (chunk_idx - 1)},
                                  timeout=(15, request_timeout))
                r.raise_for_status()
                parts.append(_ensure_wav(r.content))
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt == 2:
                    raise
                print(f"  chunk retry {attempt+1}/2 after error: {str(e)[:80]}", flush=True)
                time.sleep(10 * (attempt + 1))
    return _concat_wav(parts, join_silence_ms=join_silence_ms)


def sanitize_filename(name):
    # Keep alphanumeric, dashes, underscores, spaces
    name = re.sub(r'[^a-zA-Z0-9_\-\s]', '', name)
    # Replace spaces or multiple dashes with single underscore
    name = re.sub(r'[\s\-]+', '_', name)
    return name.strip('_')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epub', required=True, help='path or http(s) URL')
    ap.add_argument('--engine-url', required=True)
    ap.add_argument('--voice', required=True)
    ap.add_argument('--out', default=None,
                    help='output dir (default: <repo>/data/audiobooks/<book>, the canonical location)')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=0)
    ap.add_argument('--chunk-chars', type=int, default=280)
    ap.add_argument('--request-timeout', type=int, default=3600,
                    help='per-generation HTTP read timeout in seconds. Long-form engines '
                         'can legitimately need more than one hour for one chapter.')
    ap.add_argument('--join-silence-ms', type=int, default=0,
                    help='PCM silence inserted between generated chunks (0 = none)')
    ap.add_argument('--min-words', type=int, default=120,
                    help='skip chapters shorter than this (front-matter)')
    ap.add_argument('--denoise', action='store_true',
                    help='apply afftdn denoise on encode (knocks down TADA hiss, issue #8)')
    ap.add_argument('--qa', action='store_true',
                    help='QA Layer 2: ASR-verify each chapter locally (needs faster-whisper)')
    ap.add_argument('--qa-model', default='base', help='whisper model size for --qa (tiny/base/small)')
    ap.add_argument('--progress-url', default='', help='POST real per-chapter progress here (e.g. an ntfy.sh topic) so a remote UI can show true progress, not an estimate')
    ap.add_argument('--search-and-replace-file', default=None,
                    help='Path to a file containing search==replace rules (one per line) to apply to text')
    ap.add_argument('--model', default='tts-1',
                    help='TTS model name to send in request')
    ap.add_argument('--job-id', default='',
                    help='job id; when set, the text sent to the engine is recorded to '
                         '$TRANSCRIPTS_DIR/<job-id>/chunks.jsonl so the post-flight ASR '
                         'check has something to compare against. Without it a render '
                         'cannot be verified (#33).')
    ap.add_argument('--speed', type=float, default=1.0,
                    help='playback rate sent to the engine (OpenAI `speed`). '
                         'Honoured by Kokoro, Piper, Edge and CosyVoice. '
                         'Chatterbox Turbo/Nano IGNORE it — that model has no '
                         'speed control; use CHATTERBOX_EXAGGERATION / '
                         'CHATTERBOX_CFG_WEIGHT for its pacing instead.')
    a = ap.parse_args()

    # Load search and replace rules if specified
    global _SEARCH_REPLACE_RULES
    if a.search_and_replace_file:
        _SEARCH_REPLACE_RULES = load_search_and_replace(a.search_and_replace_file)

    # modern voice-clone engines read numbers/years natively; skip spelling.
    modern = ('_tada' in a.voice) or (a.voice.startswith('uk_') and '_tada' not in a.voice) or a.chunk_chars >= 280
    global _MODERN
    _MODERN = modern

    epub = a.epub
    if epub.startswith('http'):
        dst = '/tmp/book.epub'
        urllib.request.urlretrieve(epub, dst); epub = dst

    # Canonical output: <repo>/data/audiobooks/<book>/ (see README "Where do I
    # find my audiobooks?"). Keeps every conversion path in one known place.
    if a.out:
        out = Path(a.out)
    else:
        book_label = Path(a.epub.split('?')[0]).stem or 'book'
        out = Path(__file__).resolve().parents[1] / 'data' / 'audiobooks' / book_label
    out.mkdir(parents=True, exist_ok=True)
    print(f"output dir: {out}", flush=True)
    global _LEXICON
    _LEXICON = build_lexicon(epub)
    z = zipfile.ZipFile(epub)
    docs = spine_docs(z)

    # Book title/author for ID3 tags — Audiobookshelf needs these (plus a track
    # number and per-file title) to group the files as one book and order/name
    # the chapters. Without them chapter navigation is broken (the files carry no
    # metadata otherwise).
    # ONE reader for this, shared with the webapp's M4B builder. When these
    # were two separate implementations the M4B silently lost the author (#32).
    book_meta = read_book_meta(a.epub)
    book_title = book_meta.get('title') or Path(a.epub).stem
    book_author = book_meta.get('author', '')

    def _post_progress(done, total, current):
        if not a.progress_url:
            return
        try:
            import json as _json
            body = _json.dumps({"done": done, "total": total, "current": current,
                                "pct": int(done * 100 / total) if total else 0}).encode()
            req = urllib.request.Request(a.progress_url, data=body,
                                         headers={"Content-Type": "application/json", "Title": "render-progress"})
            urllib.request.urlopen(req, timeout=8).read()
        except Exception as e:
            print(f"[progress] post failed (non-fatal): {str(e)[:60]}", flush=True)

    # Pre-count renderable chapters (>= min_words, within range) so progress is
    # a real fraction, not an estimate. Preprocessing is cheap vs synthesis.
    total_render, _c = 0, 0
    for name in docs:
        if renderable_wordcount(z, name) < a.min_words:
            continue
        _c += 1
        if _c < a.start or (a.end and _c > a.end):
            continue
        total_render += 1
    print(f"Chapters count: {total_render}", flush=True)
    print(f"renderable chapters: {total_render}", flush=True)
    _post_progress(0, total_render, 0)

    idx = 0
    done_render = 0
    qa_reports = []
    for name in docs:
        # Renderable decision + numbering via the shared function so file numbers
        # match the UI picker exactly. TTS text (with lexicon) is built after.
        if renderable_wordcount(z, name) < a.min_words:
            continue
        idx += 1
        if idx < a.start or (a.end and idx > a.end):
            continue

        ctitle = _title_for(z.read(name).decode('utf-8', 'ignore'), f"Chapter {idx}")
        clean_title = sanitize_filename(ctitle)
        suffix = f"_{clean_title}" if clean_title else ""

        text = chapter_text(z, name)
        # resume: accept a prior .mp3 OR .wav for this chapter
        fn = None
        for ext in ('mp3', 'wav'):
            # Match 3-digit flat, 3-digit with name, or 4-digit with name
            matches = (list(out.glob(f"{idx:03d}.{ext}")) +
                       list(out.glob(f"{idx:03d}_*.{ext}")) +
                       list(out.glob(f"{idx:04d}_*.{ext}")))
            if matches and matches[0].stat().st_size > 10240:
                fn = matches[0]
                break
        if fn:
            print(f"[chapter {idx}] already done — skipping (resume)", flush=True)
            print(f"Processing chapter {idx}: {ctitle}", flush=True)
            print(f"Converted chapter {idx}", flush=True)
        else:
            print(f"Processing chapter {idx}: {ctitle}", flush=True)
            print(f"[chapter {idx}] {len(text.split())} words -> synthesizing", flush=True)
            meta = {'title': ctitle, 'album': book_title, 'artist': book_author,
                    'album_artist': book_author, 'genre': 'Audiobook',
                    'track': f"{done_render + 1}/{total_render}"}
            wav = synth(a.engine_url, a.voice, text, a.chunk_chars, chapter_idx=idx,
                        model=a.model, speed=a.speed, job_id=a.job_id,
                        request_timeout=a.request_timeout,
                        join_silence_ms=a.join_silence_ms)
            mp3 = _to_mp3(wav, denoise=a.denoise, meta=meta)
            if mp3:
                fn = out / f"{idx:03d}{suffix}.mp3"
                fn.write_bytes(mp3)
            else:
                fn = out / f"{idx:03d}{suffix}.wav"
                fn.write_bytes(wav)
                print(f"[chapter {idx}] ffmpeg not found — wrote clean WAV instead of MP3", flush=True)
            print(f"Converted chapter {idx}", flush=True)
            print(f"[chapter {idx}] wrote {fn} ({fn.stat().st_size} bytes)", flush=True)
        # QA Layer 2 (opt-in): ASR-verify what we just rendered against source.
        if a.qa:
            try:
                from qa_asr import verify_chapter
                rep = verify_chapter(fn, text, model_size=a.qa_model)
                qa_reports.append({'chapter': idx,
                                   'wer': rep['wer'], 'flagged': rep['flagged'],
                                   'n_source': rep['n_source'], 'n_heard': rep['n_heard'],
                                   'divergences': rep['divergences'][:30],
                                   'lexicon_suggestions': rep['lexicon_suggestions']})
                print(f"[chapter {idx}] QA {'FLAGGED' if rep['flagged'] else 'ok'} "
                      f"WER={rep['wer']} divergences={len(rep['divergences'])}", flush=True)
            except Exception as e:
                print(f"[chapter {idx}] QA skipped ({str(e)[:120]})", flush=True)
        done_render += 1
        _post_progress(done_render, total_render, idx)
    if a.qa and qa_reports:
        agg = {}
        for r in qa_reports:
            agg.update(r.get('lexicon_suggestions') or {})
        report = {'book': str(a.epub), 'voice': a.voice,
                  'flagged_chapters': [r['chapter'] for r in qa_reports if r['flagged']],
                  'chapters': qa_reports, 'lexicon_suggestions': agg}
        (out / 'qa_report.json').write_text(__import__('json').dumps(report, indent=2), encoding='utf-8')
        print(f"QA report -> {out/'qa_report.json'} "
              f"(flagged {len(report['flagged_chapters'])}/{len(qa_reports)} chapters)", flush=True)
        if agg:
            print(f"QA lexicon suggestions (add to a book lexicon): {agg}", flush=True)
    print("DONE", flush=True)


if __name__ == '__main__':
    main()
