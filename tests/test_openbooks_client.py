"""Book Finder thin HTTP proxy tests (delegates search/grab to docker-vm:8095)."""
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))
import openbooks_client as ob  # noqa: E402


def _fake_resp(status=200, json_data=None, chunks=None):
    resp = Mock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.raise_for_status = Mock()
    if status >= 400:
        resp.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    if json_data is not None:
        resp.json.return_value = json_data
    if chunks is not None:
        resp.iter_content.return_value = list(chunks)
    return resp


def test_search_books_proxies_http_query(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        return _fake_resp(200, {"results": [{"title": "Dune", "author": "Frank Herbert", "command": "!Bsk Dune.epub"}]})

    monkeypatch.setattr(ob.requests, "get", fake_get)
    monkeypatch.setattr(ob, "BOOK_FINDER_URL", "http://192.168.1.113:8095")

    assert ob.search_books("   ") == []
    res = ob.search_books("Dune")
    assert len(res) == 1 and res[0]["title"] == "Dune"
    assert calls[0][0] == "http://192.168.1.113:8095/api/bookfinder/search"
    assert calls[0][1] == {"q": "Dune"}


def test_bg_sync_to_uploads_fetches_via_http_and_sanitizes_filename(tmp_path, monkeypatch):
    def fake_get(url, params=None, stream=False, timeout=None):
        assert url.endswith("/api/bookfinder/file")
        assert params == {"book_id": 312}
        return _fake_resp(200, chunks=[b"EPUB-", b"BYTES"])

    monkeypatch.setattr(ob.requests, "get", fake_get)
    monkeypatch.setattr(ob, "BOOK_FINDER_URL", "http://192.168.1.113:8095")

    ok = ob._bg_sync_to_uploads(
        book_id=312,
        filename="../../evil/Careless People (retail).epub",
        upload_dir=tmp_path,
        wait_s=1,
        poll_s=0.01,
    )
    assert ok is True
    expected = tmp_path / "Careless People (retail).epub"
    assert expected.is_file() and expected.read_bytes() == b"EPUB-BYTES"
    assert not (tmp_path.parent / "evil").exists()


def test_safe_upload_dest_blocks_traversal_and_bad_extensions(tmp_path):
    dest = ob._safe_upload_dest(tmp_path, "../../nested/script.txt")
    assert dest.parent == tmp_path.resolve()
    assert dest.suffix == ".epub"


def test_grab_and_import_book_posts_and_spawns_background_fetch(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target=None, kwargs=None, daemon=None):
            started.append((target, kwargs, daemon))

        def start(self):
            started.append(("started",))

    monkeypatch.setattr(ob.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        ob.requests,
        "post",
        lambda url, json=None, timeout=None: _fake_resp(
            200,
            {
                "status": "success",
                "filename": "Dune.epub",
                "title": "Dune",
                "author": "Frank Herbert",
                "calibre_id": 999,
                "ingested": True,
                "library_url": "https://library.magnusfamily.co.uk/book/999",
            },
        ),
    )

    out = ob.grab_and_import_book("!Bsk Dune.epub", title="Dune", author="Frank Herbert")
    assert out["status"] == "success"
    assert out["calibre_id"] == 999
    assert started[0][0] is ob._bg_sync_to_uploads
    assert started[0][1] == {"book_id": 999, "filename": "Dune.epub"}
    assert started[1] == ("started",)


def test_grab_requires_command():
    with pytest.raises(ValueError):
        ob.grab_and_import_book("   ")
