"""Transcript capture must be engine-independent (#33).

Before this, `chunks.jsonl` was written only by tts-proxy. `get_engine_url()`
returns DIRECT urls for chatterbox_nano, chatterbox and tada, so those renders
produced no transcript at all — and the quality gate, having nothing to
inspect, wrote a clean result. No Chatterbox book had ever been verified, and
Nano is the default voice.

Capture now happens in the converter, which every engine passes through.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from convert_book import _capture_chunk  # noqa: E402


def _read(tmp_path, job_id):
    p = Path(tmp_path) / job_id / 'chunks.jsonl'
    if not p.exists():
        return []
    return [json.loads(li) for li in p.read_text(encoding='utf-8').splitlines() if li.strip()]


class TestCapture:
    def test_writes_a_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path))
        _capture_chunk('job123', 1, 'Down the Rabbit-Hole', 'uk_male_minter_nano', 'tts-1')
        recs = _read(tmp_path, 'job123')
        assert len(recs) == 1
        assert recs[0]['text'] == 'Down the Rabbit-Hole'
        assert recs[0]['chapter'] == 1
        assert recs[0]['job_id'] == 'job123'

    def test_schema_matches_what_the_reader_needs(self, tmp_path, monkeypatch):
        # _read_captured_chunks() keys off 'text'; the hash lets a later step
        # detect that the voiced text differs from what was recorded.
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path))
        _capture_chunk('j', 3, 'hello world', 'v', 'm')
        r = _read(tmp_path, 'j')[0]
        for key in ('ts', 'job_id', 'chapter', 'text', 'text_sha256', 'voice', 'model'):
            assert key in r, f'missing {key}'
        assert len(r['text_sha256']) == 64

    def test_appends_across_chunks_and_chapters(self, tmp_path, monkeypatch):
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path))
        for ch in (1, 2):
            for part in ('a', 'b'):
                _capture_chunk('multi', ch, part, 'v', 'm')
        recs = _read(tmp_path, 'multi')
        assert len(recs) == 4
        assert [r['chapter'] for r in recs] == [1, 1, 2, 2]


class TestNeverFatal:
    """A verification record must never be able to fail a render."""

    def test_no_job_id_is_a_silent_noop(self, tmp_path, monkeypatch):
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path))
        _capture_chunk('', 1, 'text', 'v', 'm')
        assert not list(Path(tmp_path).iterdir())

    def test_unwritable_dir_does_not_raise(self, tmp_path, monkeypatch):
        # Point at something that cannot be created; must swallow, not explode.
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path / 'a-file' / 'nested'))
        (tmp_path / 'a-file').write_text('not a directory')
        _capture_chunk('j', 1, 'text', 'v', 'm')   # must not raise

    def test_unicode_survives(self, tmp_path, monkeypatch):
        monkeypatch.setenv('TRANSCRIPTS_DIR', str(tmp_path))
        text = 'Alice’s Evidence — “ORANGE MARMALADE”'
        _capture_chunk('u', 1, text, 'v', 'm')
        assert _read(tmp_path, 'u')[0]['text'] == text
