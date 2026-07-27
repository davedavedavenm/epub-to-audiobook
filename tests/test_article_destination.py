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
        assert '/podcasts/Ars Technica/' in path

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
