"""Pure parts of the Modal Higgs book runner: planning, resume, cost cap, V3 assembly (no modal, no GPU)."""
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import higgs_assemble as ha  # noqa: E402
import higgs_book_plan as hp  # noqa: E402

SR = 24000


def _book(tmp_path, chunk_counts=(5, 3)):
    man = {"book_tag": "bk", "chapters": []}
    pay = {}
    for n, cnt in enumerate(chunk_counts, 1):
        slug = f"ch{n:02d}"
        man["chapters"].append({"slug": slug, "index": n, "title": f"T{n}"})
        pay[slug] = {"chunks": [{"text": f"text {k}", "words": 40, "para": k // 2} for k in range(cnt)]}
    z = tmp_path / "b.zip"
    with zipfile.ZipFile(z, "w") as zz:
        zz.writestr("manifest.json", json.dumps(man))
        for slug, p in pay.items():
            zz.writestr(f"payloads/{slug}.json", json.dumps(p))
    return z


def test_plan_resumes_and_never_regenerates(tmp_path):
    man, pay = hp.load_bundle(_book(tmp_path))
    chunk_dir = tmp_path / "chunks"
    b = hp.plan_batches(man, pay, chunk_dir, batch_size=2)
    assert sum(len(x["items"]) for x in b) == 8
    (chunk_dir / "ch01").mkdir(parents=True)
    for i in (1, 2, 3):
        (chunk_dir / "ch01" / f"{i:04d}.wav").write_bytes(b"x")
        (chunk_dir / "ch01" / f"{i:04d}.json").write_text(json.dumps({"key": hp.chunk_key(f"text {i - 1}")}))
    b2 = hp.plan_batches(man, pay, chunk_dir, batch_size=2)
    todo = [(x["slug"], it["i"]) for x in b2 for it in x["items"]]
    assert ("ch01", 1) not in todo and ("ch01", 4) in todo and len(todo) == 5
    assert all(len(x["items"]) <= 2 and len({x["slug"]}) == 1 for x in b2)   # batches never mix chapters


def test_cost_estimate_and_cap_are_sane():
    batches = [{"items": [{"words": 150 * 60}]}]   # one audio hour of words
    est = hp.estimate_usd(batches, containers=1)
    assert 1.3 < est < 1.8                         # ~1.6 GPU-h at $0.80 + one cold start + CPU/memory
    assert hp.spent_usd(3600, 0) == round(3600 * hp.L4_USD_PER_S * hp.OVERHEAD, 2)
    rows = [{"object_id": "ap-1", "cost": "0.93"}, {"object_id": "ap-1", "cost": "0.09"},
            {"object_id": "ap-2", "cost": "5"}]
    assert hp.metered_usd(rows, "ap-1") == 1.02


def _tone(seconds):
    t = np.arange(int(seconds * SR)) / SR
    w = (0.2 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    return np.concatenate([np.zeros(int(0.3 * SR), dtype=np.float32), w, np.zeros(int(0.3 * SR), dtype=np.float32)])


def test_v3_overlaps_inside_a_paragraph_and_gaps_across():
    a, b = _tone(2.0), _tone(2.0)
    same = ha.assemble([a, b], [{"para": 1}, {"para": 1}], SR)
    diff = ha.assemble([a, b], [{"para": 1}, {"para": 2}], SR)
    single = len(ha.shape(a, SR))
    assert len(same) == 2 * single - int(ha.XFADE_S * SR)                 # overlapped: no silence added
    assert len(diff) == 2 * single + int(ha.PARA_GAP_S * SR)              # 0.45 s between paragraphs
    heading = ha.assemble([a, b], [{"para": 1, "heading": True}, {"para": 1}], SR)
    assert len(heading) == len(diff)                                      # a heading is always followed by a gap
    assert abs(same[0]) < 1e-6                                           # faded in, no click


def test_missing_chunk_is_skipped_and_gain_respects_peak():
    out = ha.assemble([_tone(1.0), None, _tone(1.0)], [{"para": 1}] * 3, SR)
    assert len(out) > 0
    assert ha.loudness_gain_db(-26.0, -3.0) == 1.0         # +6 dB wanted, peak ceiling allows only +1
    assert ha.loudness_gain_db(-14.0, -10.0) == -6.0
    assert ha.loudness_gain_db(None, None) == 0.0


def test_pace_outliers_catch_the_real_truncated_chunk():
    # Armed Struggle Preface: median ~0.368 s/word; chunk 23 had 105 words in 29.2 s (18 words lost)
    rows = [(i, 60, 60 * 0.37) for i in range(1, 20)] + [(23, 105, 29.2), (24, 1, 0.9), (25, 50, 50 * 0.7)]
    out = hp.pace_outliers(rows)
    assert 23 in out and 25 in out          # truncated (too fast) and babble/loop (too slow)
    assert 24 not in out                    # one-word heading ignored
    assert hp.pace_outliers([(1, 60, 22.0), (2, 60, 22.0)]) == []   # too few chunks to judge


def test_gate_floor_is_configurable():
    import os
    import tempfile
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())
    import higgs_colab_runner as hr
    t = np.arange(int(29.2 * SR)) / SR
    w = (0.2 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    k = int(0.4 * SR)
    w[-k:] *= np.linspace(1, 0, k)
    w[:int(0.2 * SR)] *= np.linspace(0, 1, int(0.2 * SR)) ** 3
    assert hr.gate_chunk(w, SR, 105, min_rolloff_hz=None)[0] is True  # old 0.18 floor let it through
    ok, m = hr.gate_chunk(w, SR, 105, min_s_per_word=0.29, min_rolloff_hz=None)
    assert not ok and "duration" in m["why"]


def test_resume_rejects_audio_rendered_from_other_text_or_sampling(tmp_path):
    man, pay = hp.load_bundle(_book(tmp_path, chunk_counts=(2,)))
    d = tmp_path / "chunks" / "ch01"
    d.mkdir(parents=True)
    (d / "0001.wav").write_bytes(b"x")                     # legacy wav, no sidecar -> not trusted
    (d / "0002.wav").write_bytes(b"x")
    (d / "0002.json").write_text(json.dumps({"key": hp.chunk_key("OLD text before the fix")}))
    todo = [it["i"] for b in hp.plan_batches(man, pay, tmp_path / "chunks") for it in b["items"]]
    assert todo == [1, 2]
    (d / "0002.json").write_text(json.dumps({"key": hp.chunk_key("text 1", "t1.0")}))
    todo = [it["i"] for b in hp.plan_batches(man, pay, tmp_path / "chunks", recipe="t0.8") for it in b["items"]]
    assert todo == [1, 2]                                  # same text, different sampling -> re-render
    (d / "0002.json").write_text(json.dumps({"key": hp.chunk_key("text 1", "t0.8")}))
    todo = [it["i"] for b in hp.plan_batches(man, pay, tmp_path / "chunks", recipe="t0.8") for it in b["items"]]
    assert todo == [1]


def _band_noise(seconds, cutoff_hz, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[f > cutoff_hz] = 0
    spec *= 1 / np.sqrt(1 + f / 300.0)                     # speech-like tilt
    w = np.fft.irfft(spec, n).astype(np.float32)
    w *= 0.1 / np.sqrt(np.mean(w ** 2))
    k = int(0.4 * SR)
    w[-k:] *= np.linspace(1, 0, k)
    w[:k] *= np.linspace(0, 1, k)
    return w


def test_muffled_take_is_rejected_and_full_band_take_passes():
    import os
    import tempfile
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())
    import higgs_colab_runner as hr
    ok, m = hr.gate_chunk(_band_noise(20, 2200), SR, 55)  # rolls off like Preface chunks 2-5 (1.8-2.5 kHz)
    assert not ok and m["why"] == "muffled" and m["roll"] < hr.MIN_ROLLOFF_HZ
    ok, m = hr.gate_chunk(_band_noise(20, 8000), SR, 55)  # Cillian reference rolls off at ~4.7 kHz
    assert ok and m["roll"] > hr.MIN_ROLLOFF_HZ, m
    assert hr.gate_chunk(_band_noise(1.5, 2200), SR, 1)[1].get("roll") is None   # too short to judge
    muffled = hr.attempt_score(False, {"why": "muffled", "roll": 2200})
    assert hr.attempt_score(False, {"why": "muffled", "roll": 3000}) < muffled < 99
    assert hr.attempt_score(True, {}) == 0


def test_take_penalty_ranks_missing_words_worst_and_ignores_soft_endings():
    import os
    import tempfile
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())
    import higgs_colab_runner as hr
    clean = {"end": 0.3, "start": 0.01, "roll": 4600, "sim": 0.95, "asr_bad": False}
    assert hr.take_penalty(clean) == (0, "")              # 0.3 end ratio: complete per ASR, not re-rolled
    words, _ = hr.take_penalty({**clean, "asr_bad": True, "asr_tail": 8, "asr_cover": 0.88})
    voice, _ = hr.take_penalty({**clean, "sim": 0.813})
    muffled, _ = hr.take_penalty({**clean, "roll": 2200})
    cut, why = hr.take_penalty({**clean, "end": 1.9})
    assert words > voice > muffled > cut > 0 and why == "cut-off end"
    assert hr.take_penalty({"why": "duration 9.0s for 105 words"})[0] == 99.0


def test_split_sentences_keeps_closing_quotes():
    assert ha.split_sentences("It was “done.” Then the IRA ceasefires of nineteen ninety-four! And?") == \
        ["It was “done.”", "Then the IRA ceasefires of nineteen ninety-four!", "And?"]


def test_chunk_asr_audit_catches_the_real_preface_failures():
    sys.path.insert(0, str(ROOT / "webapp"))
    import chunk_asr_audit as ca
    # modal t0.8 chunk 18: stopped after "1994 and 1990"
    text = ("It details the IRA's role in a process involving milestones such as the nineteen ninety-three "
            "Anglo-Irish Joint Declaration, the IRA ceasefires of nineteen ninety-four and nineteen "
            "ninety-seven and the nineteen ninety-eight Belfast Agreement.")
    heard = ("It details the IRA's role in a process involving milestones such as the 1993 Anglo-Irish Joint "
             "Declaration, the IRA ceasefires of 1994 and 1990")
    r = ca.audit_chunk(text, heard)
    assert r["bad"] and r["tail"] >= 3
    # modal t1.0 chunk 20: a whole sentence skipped mid-chunk, then the chunk ended normally
    text2 = ("and the nineteen ninety-eight Belfast Agreement. This section also offers the first fully "
             "researched consideration of why the IRA so dramatically shifted ground during the peace process "
             "of the nineteen nineties.")
    heard2 = "and the 1993. During the peace process of the 1990s."
    r2 = ca.audit_chunk(text2, heard2)
    assert r2["bad"] and r2["drops"]
    ok = ca.audit_chunk(text, heard + "7 and the 1998 Belfast Agreement.")
    assert not ok["bad"], ok
