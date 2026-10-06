"""Higgs runner audio gates on synthetic signals (no GPU, no vllm)."""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["FISH_BASE"] = tempfile.mkdtemp()

import higgs_colab_runner as hr  # noqa: E402
import higgs_prep as hp  # noqa: E402

SR = 24000


def speechlike(seconds, amp=0.2, tail=0.4):
    """Noise-modulated tone with a natural fade-out tail."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    sig = amp * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    sig += 0.02 * rng.standard_normal(n)
    env = np.ones(n)
    k = min(int(tail * SR), n)
    if k:
        env[-k:] = np.linspace(1, 0.0, k)
    ramp = min(int(0.2 * SR), n)
    env[:ramp] = np.linspace(0, 1, ramp) ** 3   # real Higgs clips start near-silent
    return (sig * env).astype(np.float32)


def test_good_chunk_passes():
    ok, m = hr.gate_chunk(speechlike(8), SR, words=22)
    assert ok, m


def test_abrupt_end_is_rejected():
    w = speechlike(8, tail=0.0)          # loud right up to the last sample
    ok, m = hr.gate_chunk(w, SR, words=22)
    assert not ok and m["why"] == "abrupt end"


def test_clipping_and_silence_and_duration_are_rejected():
    clipped = np.clip(speechlike(8, amp=2.0), -1, 1)
    assert hr.gate_chunk(clipped, SR, 22)[1]["why"] == "health/clipping"
    assert hr.gate_chunk(np.zeros(SR * 5, dtype=np.float32), SR, 12)[1]["why"] == "health/clipping"
    assert "duration" in hr.gate_chunk(speechlike(40), SR, words=10)[1]["why"]
    assert "duration" in hr.gate_chunk(speechlike(1.0), SR, words=60)[1]["why"]
    assert hr.gate_chunk(speechlike(0.3), SR, 2)[1]["why"] == "too short"


def test_trim_keeps_pad_and_fades_edges():
    w = np.concatenate([np.zeros(SR), speechlike(2), np.zeros(SR)]).astype(np.float32)
    out = hr.trim_and_fade(w, SR)
    assert 2.0 < len(out) / SR < 2.6
    assert abs(out[0]) < 1e-6 and abs(out[-1]) < 1e-6


def test_gap_rule_matches_prep_module():
    for a, b in [({"para": 1}, {"para": 1}), ({"para": 1}, {"para": 2}),
                 ({"para": 0, "heading": True}, {"para": 1, "heading": True}),
                 ({"para": 1}, None)]:
        assert hr.gap_after(a, b) == hp.gap_after(a, b)


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg not installed")
def test_gain_only_hits_target_without_clipping(tmp_path):
    w = speechlike(6, amp=0.05)
    scaled, gain = hr.gain_only(w, SR, tmp_path / "x.wav")
    assert abs(scaled).max() <= 10 ** (-2 / 20) + 1e-3
    assert -12 <= gain <= 12


# --- end-to-end loop against a fake vLLM server (no GPU) -------------------

class _FakeProc:
    def poll(self):
        return None

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg not installed")
def test_runner_loop_end_to_end_with_fake_server(tmp_path, monkeypatch):
    import io
    import json
    import zipfile

    import requests
    import soundfile as sf

    sys.path.insert(0, str(ROOT / "tests"))
    from test_fish_lane import _make_epub  # reuse the mini-EPUB builder
    import fish_bundle

    epub = tmp_path / "b.epub"
    _make_epub(epub)
    bundle = tmp_path / "as_bundle.zip"
    fish_bundle.build_bundle(epub, bundle, engine="higgs")

    base = Path(hr.BASE)
    for f in base.glob("*"):
        if f.is_file():
            f.unlink()
    for d in ("payloads", "wavs", "out", "refs", "transcripts"):
        __import__("shutil").rmtree(base / d, ignore_errors=True)
    (base / "out").mkdir()
    (base / "wavs").mkdir()
    __import__("shutil").copy(bundle, base / "as_bundle.zip")

    calls = {"n": 0, "seeds": []}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        calls["seeds"].append(json["seed"])
        words = len(json["input"].split())
        # first call of each chunk (seed 42) ends abruptly; the re-roll (seed 43) is clean,
        # so a passing run proves the abrupt-end gate triggers a re-roll.
        w = speechlike(max(1.5, words * 0.4), tail=0.0 if json["seed"] == 42 else 0.4)
        buf = io.BytesIO()
        sf.write(buf, w, SR, format="WAV")

        class R:
            content = buf.getvalue()

            def raise_for_status(self):
                pass
        return R()

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(hr, "bootstrap_env", lambda: None)
    monkeypatch.setattr(hr, "start_server", lambda: hr._SRV.__setitem__("proc", _FakeProc()))
    hr.main()

    mf = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    st = json.loads((base / "as_state.json").read_text())
    assert st["completed"] == [c["slug"] for c in mf["chapters"]]
    for c in mf["chapters"]:
        mp3 = base / "out" / f"{mf['book_tag']}_{c['slug']}_{mf['voice_tag']}.mp3"
        assert mp3.exists() and mp3.stat().st_size > 5000, mp3
        assert st["progress"][c["slug"]] == c["sents"]           # progress counts CHUNKS
        assert st["meta"][c["slug"]]["warns"] == 0               # every re-roll came out clean
    assert 43 in calls["seeds"] and calls["seeds"].count(42) == calls["seeds"].count(43)
    with zipfile.ZipFile(bundle) as z:
        assert "payloads/ch01.json" in z.namelist()
