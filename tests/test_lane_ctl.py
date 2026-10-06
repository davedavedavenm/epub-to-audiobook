"""khpi5 lane controller: session parsing, checkpoint pull/upload (no Colab needed)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lane_ctl", ROOT / "scripts" / "khpi5-lane" / "lane_ctl.py")
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)

SESSIONS_OUT = """
[colab] A new version of Colab CLI is available: 0.7.4 (current: 0.7.2)
[colab] Run 'colab update' to update.
[lane-fish1] gpu-l4-s-kkb-ass1a1-abc | Hardware: L4 | Shape: Standard | Variant: GPU
[?] gpu-l4-s-kkb-ass1b0-def | Hardware: L4 | Shape: Standard | Variant: GPU
[colab] No active sessions found on server.
"""


def test_list_sessions_ignores_cli_notices(monkeypatch):
    monkeypatch.setattr(lc, "colab", lambda *a, **k: SESSIONS_OUT)
    assert lc.list_sessions() == ["lane-fish1", "?"]     # an orphaned "[?]" VM still counts: it bills


def test_ckpt_name_regex_is_strict():
    ok = ["ckpt_ch03_0001-0010.tgz", "ckpt_ch12_0011-0040.tgz"]
    bad = ["ckpt_ch03_1-10.tgz", "../ckpt_ch03_0001-0010.tgz", "ckpt_ch03_0001-0010.tgz;rm", "x.mp3"]
    assert all(lc.CKPT_RE.match(n) for n in ok)
    assert not any(lc.CKPT_RE.match(n) for n in bad)


def test_pull_ckpts_downloads_only_new_valid_names(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "JOBS", tmp_path)
    (tmp_path / "t1" / "out").mkdir(parents=True)
    (tmp_path / "t1" / "out" / "ckpt_ch03_0001-0010.tgz").write_bytes(b"have")
    calls = []

    def fake_colab(*a, **k):
        calls.append(a)
        Path(a[4]).write_bytes(b"x")
        return ""
    monkeypatch.setattr(lc, "colab", fake_colab)
    payload = {"state": {"ckpts": ["ckpt_ch03_0001-0010.tgz", "ckpt_ch03_0011-0020.tgz", "evil;name.tgz"]}}
    assert lc.pull_ckpts("t1", "lane-t1", payload) == 1
    assert [Path(c[4]).name for c in calls] == ["ckpt_ch03_0011-0020.tgz"]


def test_pull_ckpts_survives_a_failed_download(tmp_path, monkeypatch):
    monkeypatch.setattr(lc, "JOBS", tmp_path)

    def boom(*a, **k):
        raise RuntimeError("VM gone")
    monkeypatch.setattr(lc, "colab", boom)
    assert lc.pull_ckpts("t2", "lane-t2", {"state": {"ckpts": ["ckpt_ch01_0001-0010.tgz"]}}) == 0


def test_only_unbanked_chapters_are_uploaded_to_the_next_vm(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    for n in ("ckpt_ch03_0001-0010.tgz", "ckpt_ch03_0011-0020.tgz", "ckpt_ch04_0001-0010.tgz", "notes.txt"):
        (out / n).write_bytes(b"x")
    # chapters 3 is banked already, only ch04 is left to render
    got = [f.name for f in lc.ckpts_to_upload(tmp_path, {"ch04"})]
    assert got == ["ckpt_ch04_0001-0010.tgz"]
    assert len(lc.ckpts_to_upload(tmp_path, None)) == 3         # fresh job: everything present
    assert json.dumps(got)
