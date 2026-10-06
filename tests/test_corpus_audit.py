import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import corpus_audit as ca  # noqa: E402
from test_fish_lane import _make_epub  # noqa: E402


def test_audit_folder_reports_pass_and_a_crash_as_data(tmp_path):
    _make_epub(tmp_path / "good.epub")
    (tmp_path / "broken.epub").write_bytes(b"not a zip")
    res = ca.audit_folder(str(tmp_path))
    by = {r["file"]: r for r in res}
    assert by["good.epub"]["ok"] is True and by["good.epub"]["chapters"] == 3
    assert by["broken.epub"]["crash"] and not by["broken.epub"]["ok"]
    text = ca.summarise(res)
    assert "2 books: PASS 1" in text and "CRASHED 1" in text
