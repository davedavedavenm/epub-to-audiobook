"""Articles go to the podcast library, books go to the shelf (#36).

Dave's objection, verbatim, after running an Ars Technica piece through the
pipeline: *"it seemed decent. but not sure it should land in ABS as a book?"*
He was right. The render is fine; the filing was wrong.

The fix is deliberately one field. `source_kind` decides the destination and
nothing else — chaptering, preprocessing, engines, tagging and the M4B path are
all untouched, because an article really is a one-chapter book right up until
the moment it is delivered. These tests pin that boundary in both directions:
an article must not reach the audiobook shelf, and a book must not be diverted
into the podcast folder by a bug in the new code.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import pytest  # noqa: E402


@pytest.fixture()
def app_mod(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, 'AUDIOBOOKSHELF_DIR',
                        '/opt/stacks/audiobookshelf/audiobooks', raising=False)
    monkeypatch.setattr(app_module, 'AUDIOBOOKSHELF_PODCAST_DIR',
                        '/opt/stacks/audiobookshelf/podcasts', raising=False)
    return app_module


def _jobs(app_mod, monkeypatch, job):
    monkeypatch.setattr(app_mod, 'get_job', lambda _id: job)


class TestDestination:
    def test_article_lands_in_the_podcast_library(self, app_mod, monkeypatch):
        _jobs(app_mod, monkeypatch,
              {'source_kind': 'article', 'source_site': 'Ars Technica'})
        path, is_article = app_mod._abs_destination(Path('/out/Some Article'), 'j1')
        assert is_article
        assert path.startswith('/opt/stacks/audiobookshelf/podcasts/')
        # The specific thing Dave objected to.
        assert '/audiobooks/' not in path

    def test_grouped_by_source_site(self, app_mod, monkeypatch):
        """Each site is its own podcast, so ABS shows 'Ars Technica — N episodes'
        rather than one shapeless bucket of unrelated pieces."""
        _jobs(app_mod, monkeypatch,
              {'source_kind': 'article', 'source_site': 'Ars Technica'})
        path, _ = app_mod._abs_destination(Path('/out/Some Article'), 'j1')
        assert path.endswith('/podcasts/Ars Technica')

    def test_podcast_path_is_flat_not_nested(self, app_mod, monkeypatch):
        """The shape difference that is easy to get wrong and silent when wrong.

        A book library reads one FOLDER as one audiobook. A podcast library
        reads one folder as one podcast and the audio files directly inside it
        as episodes — so an extra per-article subfolder is simply not scanned,
        and the episode never appears.
        """
        _jobs(app_mod, monkeypatch,
              {'source_kind': 'article', 'source_site': 'Ars Technica'})
        path, _ = app_mod._abs_destination(Path('/out/Some Article'), 'j1')
        assert 'Some Article' not in path

    def test_book_is_untouched(self, app_mod, monkeypatch):
        _jobs(app_mod, monkeypatch, {'source_kind': 'book'})
        path, is_article = app_mod._abs_destination(Path('/out/Alice'), 'j1')
        assert not is_article
        assert path == '/opt/stacks/audiobookshelf/audiobooks/Alice'

    def test_legacy_job_without_the_column_is_a_book(self, app_mod, monkeypatch):
        """Every job that predates this change has no source_kind. Those are
        books, and must keep syncing exactly where they always did — a migration
        that silently re-files old renders would be far worse than the bug."""
        _jobs(app_mod, monkeypatch, {})
        path, is_article = app_mod._abs_destination(Path('/out/Alice'), 'j1')
        assert not is_article
        assert path == '/opt/stacks/audiobookshelf/audiobooks/Alice'

    def test_no_job_id_falls_back_to_the_book_path(self, app_mod):
        path, is_article = app_mod._abs_destination(Path('/out/Alice'), None)
        assert not is_article
        assert path.endswith('/audiobooks/Alice')

    def test_unset_podcast_dir_falls_back_rather_than_failing(self, app_mod, monkeypatch):
        """If the podcast destination is not configured, an article should still
        SYNC — to the book shelf — instead of failing to be delivered at all.
        Misfiled is a nuisance; undelivered is a lost render."""
        monkeypatch.setattr(app_mod, 'AUDIOBOOKSHELF_PODCAST_DIR', '', raising=False)
        _jobs(app_mod, monkeypatch,
              {'source_kind': 'article', 'source_site': 'Ars Technica'})
        path, is_article = app_mod._abs_destination(Path('/out/Some Article'), 'j1')
        assert not is_article
        assert path.endswith('/audiobooks/Some Article')


class TestEpisodeStaging:
    """Only the audio, exactly once, under a name a human can read."""

    def _render(self, tmp_path, names):
        out = tmp_path / 'Some Article_abc123'
        out.mkdir()
        for n in names:
            (out / n).write_bytes(b'\xff\xfb' + b'0' * 64)
        return out

    def test_stages_only_the_audio(self, app_mod, tmp_path, monkeypatch):
        """A book folder's furniture — cover art, the gate, verification data —
        must not follow an article into a podcast folder, where every audio file
        present becomes an episode and every stray file is clutter."""
        out = self._render(tmp_path, ['0001 - Some Article.mp3'])
        (out / 'cover.jpg').write_bytes(b'x')
        (out / '_presync_gate.json').write_text('{}')
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        staged = app_mod._stage_episode(
            out, {'id': 'j1', 'source_date': '2026-07-27'}, 'Some Article')
        assert staged is not None
        files = sorted(p.name for p in staged.iterdir())
        assert files == ['2026-07-27 - Some Article.mp3']

    def test_episode_name_leads_with_the_date(self, app_mod, monkeypatch):
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        name = app_mod._episode_filename({'source_date': '2026-07-27'}, 'A Title')
        assert name == '2026-07-27 - A Title.mp3'

    def test_missing_date_still_produces_a_valid_name(self, app_mod, monkeypatch):
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        assert app_mod._episode_filename({}, 'A Title') == 'A Title.mp3'

    def test_multi_part_article_stays_ordered(self, app_mod, tmp_path, monkeypatch):
        out = self._render(tmp_path, ['0001 - A.mp3', '0002 - B.mp3'])
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        staged = app_mod._stage_episode(out, {'id': 'j2'}, 'Long Read')
        assert sorted(p.name for p in staged.iterdir()) == \
            ['Long Read (01).mp3', 'Long Read (02).mp3']

    def test_album_tag_becomes_the_site_not_the_headline(self, app_mod, tmp_path,
                                                         monkeypatch):
        """ABS names a podcast from the audio's ALBUM tag, not the folder.

        The converter tags every render album=<book title>, so the first live
        run produced a podcast called 'Roku raises streaming stick prices by up
        to 60 percent' containing one episode of itself — and the next Ars piece
        would have made another one-episode podcast beside it. Precisely the
        clutter this change exists to remove.
        """
        seen = {}

        def fake_run(cmd, **kw):
            for i, tok in enumerate(cmd):
                if tok == '-metadata':
                    k, _, v = cmd[i + 1].partition('=')
                    seen[k] = v
            Path(cmd[-1]).write_bytes(b'\xff\xfb' + b'0' * 4096)
            return type('R', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()

        monkeypatch.setattr(app_mod.subprocess, 'run', fake_run)
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        out = self._render(tmp_path, ['0001 - Roku.mp3'])
        app_mod._stage_episode(
            out,
            {'id': 'j9', 'source_site': 'Ars Technica', 'source_date': '2026-07-24'},
            'Roku raises streaming stick prices by up to 60 percent')
        assert seen['album'] == 'Ars Technica'          # the podcast
        assert seen['title'].startswith('Roku raises')  # the episode

    def test_tagging_failure_still_delivers_the_episode(self, app_mod, tmp_path,
                                                        monkeypatch):
        """A tagging problem must never cost the audio."""
        def boom(*a, **k):
            raise OSError('ffmpeg missing')
        monkeypatch.setattr(app_mod.subprocess, 'run', boom)
        monkeypatch.setattr(app_mod, 'sanitize_filename', lambda s: s, raising=False)
        out = self._render(tmp_path, ['0001 - A.mp3'])
        staged = app_mod._stage_episode(out, {'id': 'j10'}, 'A Title')
        assert [p.name for p in staged.iterdir()] == ['A Title.mp3']

    def test_no_audio_returns_none_so_the_caller_can_fall_back(self, app_mod, tmp_path):
        out = tmp_path / 'empty'
        out.mkdir()
        assert app_mod._stage_episode(out, {'id': 'j3'}, 'Nothing') is None


class TestPodcastFolderName:
    def test_blank_site_gets_a_home(self, app_mod):
        assert app_mod._podcast_folder_name('') == 'Articles'
        assert app_mod._podcast_folder_name(None) == 'Articles'

    def test_path_separators_cannot_escape_the_folder(self, app_mod):
        """The site name comes from a remote page's og:site_name, so it is
        attacker-influenced text being pasted into an rsync destination path."""
        out = app_mod._podcast_folder_name('../../etc')
        assert '/' not in out and '..' not in out

    def test_length_is_bounded(self, app_mod):
        assert len(app_mod._podcast_folder_name('x' * 500)) <= 60
