"""End-to-end integration test for the conversion pipeline (PLAN-V3 #11).

Runs the REAL `scripts/convert_book.py` against a REAL epub, with a mock TTS
server standing in for the engine — so the epub parsing, chapter detection,
chunking, HTTP contract, audio concatenation, MP3 encoding and ID3 tagging are
all exercised together. Every unit around this was already covered; what kept
breaking this year was the wiring BETWEEN them.

The mock speaks the same OpenAI-compatible shape as every real engine
(`POST /v1/audio/speech` -> audio bytes), which is exactly the contract a new
engine has to satisfy, so this doubles as the spec for adding one.

Skips (never fails) when ffmpeg is missing, since that is an environment
problem, not a regression.
"""
import io
import json
import shutil
import struct
import subprocess
import sys
import threading
import wave
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which('ffmpeg')
pytestmark = pytest.mark.skipif(not FFMPEG, reason='ffmpeg not available')

CHAPTERS = [
    ('Chapter One', 'The first chapter has enough words to clear the minimum '
                    'word count that the converter applies when it decides '
                    'which documents are real chapters worth narrating. ' * 8),
    ('Chapter Two', 'The second chapter is likewise padded so that it survives '
                    'the front and back matter filtering and reaches the '
                    'text to speech engine as a genuine body chapter. ' * 8),
]


def _sine_wav(seconds=0.4, sr=24000, freq=220.0):
    """A short real tone — not silence, so the encoder has something to do."""
    import math
    frames = bytearray()
    for i in range(int(sr * seconds)):
        frames += struct.pack('<h', int(12000 * math.sin(2 * math.pi * freq * i / sr)))
    buf = io.BytesIO()
    w = wave.open(buf, 'wb')
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(bytes(frames))
    w.close()
    return buf.getvalue()


class _TTSHandler(BaseHTTPRequestHandler):
    """Minimal stand-in for a TTS engine."""

    def do_POST(self):
        if not self.path.endswith('/audio/speech'):
            self.send_error(404)
            return
        n = int(self.headers.get('Content-Length') or 0)
        try:
            json.loads(self.rfile.read(n) or b'{}')       # must be valid JSON
        except Exception:
            self.send_error(400)
            return
        body = _sine_wav()
        self.send_response(200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):                                      # /audio/voices probe
        body = json.dumps({'voices': [{'id': 'test_voice'}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                             # keep pytest output clean
        pass


def _make_epub(path: Path):
    """A minimal but valid EPUB 2 with two body chapters."""
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip')
        z.writestr('META-INF/container.xml',
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>')
        items, refs = [], []
        for i, (title, text) in enumerate(CHAPTERS, 1):
            name = f'chap{i}.xhtml'
            z.writestr(f'OEBPS/{name}',
                       f'<?xml version="1.0" encoding="utf-8"?>'
                       f'<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                       f'<title>{title}</title></head><body>'
                       f'<h1>{title}</h1><p>{text}</p></body></html>')
            items.append(f'<item id="c{i}" href="{name}" media-type="application/xhtml+xml"/>')
            refs.append(f'<itemref idref="c{i}"/>')
        z.writestr('OEBPS/content.opf',
                   '<?xml version="1.0" encoding="utf-8"?>'
                   '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
                   'unique-identifier="id"><metadata '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>Integration Test Book</dc:title>'
                   '<dc:creator>Test Author</dc:creator>'
                   '<dc:identifier id="id">urn:uuid:test</dc:identifier>'
                   '</metadata><manifest>' + ''.join(items) +
                   '</manifest><spine>' + ''.join(refs) + '</spine></package>')


@pytest.fixture()
def tts_server():
    srv = HTTPServer(('127.0.0.1', 0), _TTSHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{srv.server_port}/v1'
    srv.shutdown()


def test_convert_book_end_to_end(tmp_path, tts_server):
    """The whole pipeline: epub in, tagged per-chapter MP3s out."""
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    out = tmp_path / 'out'
    out.mkdir()

    r = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'convert_book.py'),
         '--epub', str(epub), '--engine-url', tts_server,
         '--voice', 'test_voice', '--out', str(out),
         '--chunk-chars', '200', '--min-words', '20'],
        capture_output=True, text=True, timeout=600,
        env={**__import__('os').environ, 'PYTHONPATH': str(ROOT / 'webapp')})

    assert r.returncode == 0, f'converter failed:\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}'

    mp3s = sorted(out.glob('*.mp3'))
    assert len(mp3s) == len(CHAPTERS), (
        f'expected {len(CHAPTERS)} chapter files, got {[p.name for p in mp3s]}')
    for p in mp3s:
        assert p.stat().st_size > 1000, f'{p.name} is suspiciously small'

    # Each file must be a single decodable stream — the corrupt-join bug (QA #7)
    # produced files that played only the first chunk.
    probe = subprocess.run([FFMPEG, '-v', 'error', '-i', str(mp3s[0]),
                            '-f', 'null', '-'], capture_output=True, text=True)
    assert probe.returncode == 0, f'first chapter does not decode cleanly: {probe.stderr[:400]}'


def test_chapter_mp3s_carry_id3_tags(tmp_path, tts_server):
    """Audiobookshelf needs title/album/track to group and order chapters."""
    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    out = tmp_path / 'out'
    out.mkdir()
    subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'convert_book.py'),
         '--epub', str(epub), '--engine-url', tts_server,
         '--voice', 'test_voice', '--out', str(out),
         '--chunk-chars', '200', '--min-words', '20'],
        capture_output=True, text=True, timeout=600,
        env={**__import__('os').environ, 'PYTHONPATH': str(ROOT / 'webapp')})

    mp3 = sorted(out.glob('*.mp3'))[0]
    meta = subprocess.run([FFMPEG, '-i', str(mp3)], capture_output=True, text=True).stderr
    low = meta.lower()
    assert 'title' in low, f'no title tag:\n{meta[:600]}'
    assert 'album' in low, f'no album tag (ABS groups by album):\n{meta[:600]}'


def test_m4b_built_from_rendered_chapters(tmp_path, tts_server):
    """The M4B path over real rendered chapters: index, timings, metadata."""
    sys.path.insert(0, str(ROOT / 'webapp'))
    from m4b import build_m4b

    epub = tmp_path / 'book.epub'
    _make_epub(epub)
    out = tmp_path / 'out'
    out.mkdir()
    subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'convert_book.py'),
         '--epub', str(epub), '--engine-url', tts_server,
         '--voice', 'test_voice', '--out', str(out),
         '--chunk-chars', '200', '--min-words', '20'],
        capture_output=True, text=True, timeout=600,
        env={**__import__('os').environ, 'PYTHONPATH': str(ROOT / 'webapp')})

    built = build_m4b(out, title='Integration Test Book', author='Test Author')
    assert built and built.exists(), 'm4b was not produced'

    info = subprocess.run([FFMPEG, '-i', str(built)], capture_output=True, text=True).stderr
    assert 'Chapter #' in info, f'm4b has no chapter index:\n{info[:800]}'
    assert info.count('Chapter #') == len(CHAPTERS), (
        f'expected {len(CHAPTERS)} chapters in the index:\n{info[:800]}')
    assert 'Integration Test Book' in info, 'title metadata missing from m4b'
