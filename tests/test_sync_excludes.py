"""The Audiobookshelf sync must not ship working files (#38).

A 2.5-hour book was producing a 401 MB library folder: 12 MP3s (166 MB), a
76 MB M4B, and a 169 MB EPUB3-with-embedded-audio — three copies of the same
audio. Audiobookshelf is an audiobook library; the epub only gave its scanner
an ebook to parse and tripled the disk cost.

Asserting on the rsync command in source is crude, but the failure here is
"someone removes an --exclude", which this catches.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'webapp' / 'app.py'


def _rsync_invocation(src: str) -> str:
    m = re.search(r"cmd = \['rsync'.*?\]", src, re.S)
    assert m, "rsync invocation not found — has copy_to_audiobookshelf moved?"
    return m.group(0)


def test_epub_is_not_synced():
    cmd = _rsync_invocation(APP.read_text(encoding='utf-8'))
    assert '--exclude' in cmd and "'*.epub'" in cmd, \
        'the EPUB3-with-audio artefact would be shipped to Audiobookshelf'


def test_internal_files_are_not_synced():
    cmd = _rsync_invocation(APP.read_text(encoding='utf-8'))
    for artefact in ("_presync_gate.json", "_verification/"):
        assert artefact in cmd, f'{artefact} is internal and should not be synced'


def test_audio_is_still_synced():
    """The exclusions must not have grown teeth."""
    cmd = _rsync_invocation(APP.read_text(encoding='utf-8'))
    for must_not_exclude in ("'*.mp3'", "'*.m4b'", "'cover.jpg'"):
        assert must_not_exclude not in cmd, \
            f'{must_not_exclude} is the deliverable and must reach the library'


def test_mp3_is_excluded_when_m4b_is_present():
    """When an M4B is produced, working MP3s must not be synced alongside it (#38 follow-up)."""
    src = APP.read_text(encoding='utf-8')
    assert "has_m4b = any(source_dir.glob('*.m4b'))" in src
    assert "cmd.extend(['--exclude', '*.mp3'])" in src


def test_abs_rescan_debounces_and_purges_ghosts():
    """ABS rescan must debounce concurrent calls and schedule missing-item purge (#38 follow-up)."""
    src = APP.read_text(encoding='utf-8')
    assert "_last_abs_rescan_time" in src
    assert "abs_purge_missing_items(job_id=job_id)" in src
