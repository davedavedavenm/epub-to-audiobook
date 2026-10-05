"""Book Finder hand-off: grabbed EPUB must reach the conversion app's uploads."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))
import openbooks_client as ob  # noqa: E402

FN = "Patrick Radden Keefe - Say Nothing- A True Story of Murder and Memory in Northern Ireland (retail) (epub).epub"


def test_search_terms_from_openbooks_filename():
    assert ob._library_search_terms(FN) == ("Keefe", "Nothing")
    assert ob._library_search_terms("Misha Glenny - McMafia (v5.0).epub") == ("Glenny", "McMafia")
    assert ob._library_search_terms("OnlyATitle.epub") == ("", "OnlyATitle")


def _cp(rc=0, out=""):
    return subprocess.CompletedProcess([], rc, stdout=out, stderr="")


def test_sync_finds_book_in_calibre_library_when_drop_folder_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[0] == "scp":
            remote = cmd[-2]
            if "/calibre-library/" in remote:
                Path(cmd[-1]).write_bytes(b"epub-bytes")
                return _cp(0)
            return _cp(1)  # drop folder: CWA already moved it
        return _cp(0, "/lib/Patrick Radden Keefe/Say Nothing (247)/Say Nothing - Patrick Radden Keefe.epub\n")

    monkeypatch.setattr(ob.subprocess, "run", fake_run)
    monkeypatch.setattr(ob, "OPENBOOKS_CALIBRE_LIBRARY", "/home/dave/docker-apps/calibre-web-automated/calibre-library")
    # the fake find returns a path that must contain calibre-library for the fake scp
    monkeypatch.setattr(ob, "_find_in_calibre_library",
                        lambda f: "/x/calibre-library/Keefe/Say Nothing (247)/Say Nothing - Patrick Radden Keefe.epub")
    assert ob._bg_sync_to_studio(FN, wait_s=1, poll_s=0.01) is True
    assert (tmp_path / FN).read_bytes() == b"epub-bytes"
    # tried both drop-folder locations, including the books/ subfolder OpenBooks really writes to
    scp_targets = [c[-2] for c in calls if c[0] == "scp"]
    assert any("/books/" + FN in t for t in scp_targets)


def test_sync_prefers_drop_folder_and_stops(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    def fake_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"x")
        return _cp(0)

    monkeypatch.setattr(ob.subprocess, "run", fake_run)
    monkeypatch.setattr(ob, "_find_in_calibre_library", lambda f: (_ for _ in ()).throw(AssertionError("must not search")))
    assert ob._bg_sync_to_studio(FN, wait_s=1, poll_s=0.01) is True


def test_sync_gives_up_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(ob.subprocess, "run", lambda cmd, **kw: _cp(1))
    monkeypatch.setattr(ob, "_find_in_calibre_library", lambda f: None)
    assert ob._bg_sync_to_studio(FN, wait_s=0.05, poll_s=0.01) is False
    assert not os.listdir(tmp_path)


def test_hostile_filename_yields_only_alphanumeric_search_terms():
    author, word = ob._library_search_terms("Evil'; rm -rf / - Title; $(reboot) Book.epub")
    assert author.isalnum() and word.isalnum()
    assert not any(c in author + word for c in ";$()'\"`|&/ ")
