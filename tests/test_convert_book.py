"""Tests for convert_book helpers — notably clean audio concatenation
(the corrupt-MP3-join bug QA #7 exposed: strict decoders stopped after the
first chunk)."""
import io
import wave
import importlib.util
from pathlib import Path

import pytest
import requests

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


def test_chunk_default_retains_legacy_cross_paragraph_packing():
    cb = _load_cb()
    text = "First paragraph ends here.\n\nSecond paragraph begins here."
    assert cb.chunk(text, 200) == [
        "First paragraph ends here. Second paragraph begins here."
    ]


def test_chunk_can_preserve_real_paragraph_boundaries():
    cb = _load_cb()
    text = "First paragraph ends here.\n\nSecond paragraph begins here."
    assert cb.chunk(text, 200, preserve_paragraphs=True) == [
        "First paragraph ends here.",
        "Second paragraph begins here.",
    ]


def test_chunk_can_pack_paragraphs_without_flattening_them():
    cb = _load_cb()
    text = "First paragraph ends here.\n\nSecond paragraph begins here.\n\nThird one."
    assert cb.chunk(text, 60, pack_paragraphs=True) == [
        "First paragraph ends here.\n\nSecond paragraph begins here.",
        "Third one.",
    ]


def test_long_paragraph_pieces_do_not_gain_fake_paragraph_breaks():
    cb = _load_cb()
    text = "This first sentence is deliberately long. This second sentence is long too."
    pieces = cb.chunk(text, 45, pack_paragraphs=True)
    assert '\n\n' not in ''.join(pieces)
    assert ' '.join(pieces) == text


def test_passage_cache_avoids_a_second_network_request(tmp_path, monkeypatch):
    cb = _load_cb()
    calls = []

    class Response:
        content = _wav(1000)
        def raise_for_status(self):
            return None

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(cb.requests, 'post', post)
    first = cb.synth('http://engine/v1', 'voice', 'One sentence.', 100,
                     chunk_cache_dir=tmp_path, max_chunk_attempts=1)
    second = cb.synth('http://engine/v1', 'voice', 'One sentence.', 100,
                      chunk_cache_dir=tmp_path, max_chunk_attempts=1)
    assert first == second
    assert len(calls) == 1, "resuming a completed passage spent quota again"


def test_gemini_http_failure_preserves_safe_detail_without_retry_or_secrets(monkeypatch):
    cb = _load_cb()
    calls = []

    class Response:
        content = b''
        status_code = 503
        reason = 'Service Unavailable'

        def json(self):
            return {
                'detail': (
                    'service_unavailable: temporary model capacity; '
                    'key=AIza012345678901234567890123456789'
                )
            }

        def raise_for_status(self):
            raise requests.HTTPError(
                'generic error for https://adapter/audio/speech?key=do-not-log',
                response=self,
            )

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(cb.requests, 'post', post)
    with pytest.raises(requests.HTTPError) as error:
        cb.synth(
            'http://gemini-tts/v1', 'gemini_achernar', 'One sentence.', 100,
            model=cb._GEMINI_MODEL, max_chunk_attempts=1,
        )

    message = str(error.value)
    assert message.startswith('HTTP 503 Service Unavailable: service_unavailable:')
    assert 'temporary model capacity' in message
    assert '[REDACTED]' in message
    assert 'AIza' not in message
    assert 'do-not-log' not in message
    assert len(calls) == 1, "the observability path must not add an API retry"


def test_gemini_http_failure_ignores_unstructured_response_body():
    cb = _load_cb()

    class Response:
        status_code = 503
        reason = 'Service Unavailable'
        text = '<html>secret proxy diagnostic</html>'

        def json(self):
            raise ValueError('not JSON')

        def raise_for_status(self):
            raise requests.HTTPError('generic error', response=self)

    with pytest.raises(requests.HTTPError) as error:
        cb._raise_for_status_with_safe_detail(Response())
    assert str(error.value) == 'HTTP 503 Service Unavailable'
    assert 'secret proxy diagnostic' not in str(error.value)
