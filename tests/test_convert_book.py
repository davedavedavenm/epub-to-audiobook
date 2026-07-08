"""Tests for convert_book helpers — notably clean audio concatenation
(the corrupt-MP3-join bug QA #7 exposed: strict decoders stopped after the
first chunk)."""
import io
import wave
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_cb():
    import sys
    sys.path.insert(0, str(ROOT / 'webapp'))       # convert_book imports tts_preprocess
    spec = importlib.util.spec_from_file_location('convert_book', ROOT / 'scripts' / 'convert_book.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _wav(nframes, sr=24000):
    buf = io.BytesIO()
    w = wave.open(buf, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes(b'\x00\x00' * nframes)
    w.close()
    return buf.getvalue()


def test_concat_wav_produces_one_decodable_stream():
    """Two WAV chunks must join into a single clean WAV whose frame count is
    the SUM — the whole point vs. concatenating MP3 bytes (which leaves corrupt
    frame headers so decoders stop after chunk 1)."""
    cb = _load_cb()
    joined = cb._concat_wav([_wav(1000), _wav(1500)])
    w = wave.open(io.BytesIO(joined), 'rb')
    assert w.getnframes() == 2500, "concatenated WAV lost frames — join is not clean"
    assert w.getframerate() == 24000
    # fully readable end-to-end (no decode error partway)
    assert len(w.readframes(w.getnframes())) == 2500 * 2


def test_concat_wav_empty_is_safe():
    cb = _load_cb()
    assert cb._concat_wav([]) == b''
