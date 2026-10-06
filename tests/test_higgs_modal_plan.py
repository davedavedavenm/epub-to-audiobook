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
    b2 = hp.plan_batches(man, pay, chunk_dir, batch_size=2)
    todo = [(x["slug"], it["i"]) for x in b2 for it in x["items"]]
    assert ("ch01", 1) not in todo and ("ch01", 4) in todo and len(todo) == 5
    assert all(len(x["items"]) <= 2 and len({x["slug"]}) == 1 for x in b2)   # batches never mix chapters


def test_cost_estimate_and_cap_are_sane():
    batches = [{"items": [{"words": 150 * 60}]}]   # one audio hour of words
    est = hp.estimate_usd(batches, containers=1)
    assert 1.0 < est < 1.6                         # ~1.5 GPU-h at $0.80 + one cold start
    assert hp.spent_usd(3600, 0) == round(3600 * hp.L4_USD_PER_S, 2)


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
    assert hr.gate_chunk(w, SR, 105)[0] is True                       # old 0.18 floor let it through
    ok, m = hr.gate_chunk(w, SR, 105, min_s_per_word=0.29)
    assert not ok and "duration" in m["why"]
