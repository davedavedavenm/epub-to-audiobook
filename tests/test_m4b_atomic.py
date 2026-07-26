"""The M4B must be published atomically, and carry full metadata (#38, #32).

Audiobookshelf watches the library folder. Writing the .m4b straight to its
final path let the watcher scan it mid-write, read a truncated file, log
"Invalid data found when processing input" and mark the book invalid — a state
nothing ever re-checks, so a perfectly good book stayed broken.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import m4b  # noqa: E402

SRC = (Path(__file__).resolve().parents[1] / 'webapp' / 'm4b.py').read_text(encoding='utf-8')


class TestAtomicPublish:
    def test_ffmpeg_writes_to_a_temp_name(self):
        assert "tmp_out = out_path.with_name(out_path.name + '.part')" in SRC, \
            'ffmpeg must not write directly to the published path'
        assert "'-f', 'mp4', str(tmp_out)" in SRC, \
            'the ffmpeg output argument must be the temp path'

    def test_publish_uses_atomic_replace(self):
        assert 'os.replace(tmp_out, out_path)' in SRC, \
            'publishing must be an atomic rename, not a copy or a direct write'

    def test_temp_file_is_cleaned_up_on_failure(self):
        fail_block = SRC[SRC.index('if r.returncode != 0'):]
        assert 'tmp_out' in fail_block[:400], \
            'a failed render must not leave a .part file behind'

    def test_temp_name_is_a_sibling(self):
        """rename(2) is only atomic within one filesystem."""
        assert 'with_name(' in SRC and 'with_suffix' not in SRC.split('tmp_out =')[1][:80], \
            'the temp file must sit beside the destination, not elsewhere'


class TestMetadata:
    def test_extra_metadata_is_emitted(self):
        out = m4b.build_ffmetadata(
            [('Chapter I', 10.0)],
            title="Alice's Adventures in Wonderland",
            author='Lewis Carroll',
            extra={'date': '1865', 'publisher': 'Macmillan', 'language': 'en'},
        )
        assert 'artist=Lewis Carroll' in out
        assert 'album_artist=Lewis Carroll' in out
        assert 'date=1865' in out
        assert 'publisher=Macmillan' in out
        assert 'language=en' in out

    def test_empty_extra_values_are_skipped(self):
        out = m4b.build_ffmetadata([('C1', 1.0)], title='T', author='A',
                                   extra={'date': '', 'publisher': None})
        assert 'date=' not in out
        assert 'publisher=' not in out

    def test_chapter_marks_still_correct(self):
        out = m4b.build_ffmetadata([('One', 10.0), ('Two', 5.0)], title='T')
        starts = re.findall(r'START=(\d+)', out)
        ends = re.findall(r'END=(\d+)', out)
        assert starts == ['0', '10000']
        assert ends == ['10000', '15000']
