"""A job field that is saved must come back. Guards a silent-drop bug class.

`save_job` writes an INSERT with an explicit column list. Adding a column to
the schema is therefore only half the work — if the field is not also named in
that INSERT, every save drops it silently and nothing anywhere fails.

That is exactly how the article destination broke: the API answered
`destination: podcast` while the stored row said `source_kind: 'book'`, so the
render would have been filed as a book despite everything upstream being
correct. Two sources of truth disagreeing, with no error — the failure shape
PLAN-V4 exists to eliminate.

This test asserts the round-trip generically, so the next added field is caught
by CI rather than by someone reading a database row at the end of a live run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import pytest  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, 'DB_PATH', str(tmp_path / 'jobs.db'), raising=False)
    app_module.init_db()
    return app_module


def test_article_fields_survive_a_save(db):
    db.save_job({
        'id': 'j-article',
        'book_name': 'Roku raises streaming stick prices',
        'status': 'queued',
        'source_kind': 'article',
        'source_url': 'https://arstechnica.com/gadgets/2026/07/roku/',
        'source_site': 'Ars Technica',
        'source_date': '2026-07-24',
    })
    got = db.get_job('j-article')
    assert got['source_kind'] == 'article'
    assert got['source_site'] == 'Ars Technica'
    assert got['source_date'] == '2026-07-24'
    assert got['source_url'].startswith('https://arstechnica.com/')


def test_a_book_job_defaults_to_book(db):
    db.save_job({'id': 'j-book', 'book_name': 'Alice', 'status': 'queued'})
    assert (db.get_job('j-book') or {}).get('source_kind') == 'book'


def test_every_saved_field_is_persisted(db):
    """The generic guard. If a field can be set on a job it must round-trip;
    otherwise it is decoration that reads back as None."""
    job = {
        'id': 'j-all',
        'book_name': 'X',
        'status': 'queued',
        'voice': 'uk_male_minter_nano',
        'tts_engine': 'chatterbox_nano',
        'render_target': 'local',
        'output_format': 'm4b',
        'source_kind': 'article',
        'source_site': 'Wired',
    }
    db.save_job(job)
    got = db.get_job('j-all')
    dropped = [k for k, v in job.items()
               if k != 'id' and got.get(k) != v]
    assert not dropped, f"fields silently dropped by save_job: {dropped}"
