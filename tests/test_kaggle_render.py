"""Guards for the Kaggle GPU render backend (webapp/kaggle_render.py)."""
import os
import sys
import datetime as dt
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import kaggle_render as K


def test_kernel_source_substitutes_knobs():
    tmpl = 'APP_REF = ""\nVOICE  = "uk_male_minter"\nSTART  = 1\nEND    = 0\n'
    sha = 'a' * 40
    out = K.render_kernel_source(tmpl, "uk_female_golding", 5, 6, app_ref=sha)
    assert 'VOICE  = "uk_female_golding"' in out
    assert 'START  = 5' in out and 'END    = 6' in out
    assert f'APP_REF = "{sha}"' in out
    # full-book: end<=0 stays 0
    assert 'END    = 0' in K.render_kernel_source(tmpl, "x", 1, 0)


def test_metadata_shapes():
    assert K.dataset_metadata("dave", "epub-b", "B")["id"] == "dave/epub-b"
    km = K.kernel_metadata("dave", "render-b", "dave/epub-b")
    assert km["dataset_sources"] == ["dave/epub-b"] and km["enable_gpu"] and km["is_private"]


def test_status_parsing():
    assert K.parse_status("KernelWorkerStatus.COMPLETE") == "complete"
    assert K.parse_status("...ERROR") == "error"
    assert K.parse_status("RUNNING") == "running"
    assert K.parse_status("QUEUED") == "queued"


def test_quota_math_trailing_7_days():
    now = dt.datetime.now(dt.timezone.utc)
    st = {"runs": [
        {"ended": now.isoformat(), "hours": 2.5},
        {"ended": (now - dt.timedelta(days=9)).isoformat(), "hours": 5},  # outside window
    ]}
    assert K.gpu_hours_used(st, now) == 2.5
    assert K.gpu_hours_left(st) == round(K.WEEKLY_GPU_HOURS - 2.5, 2)


def test_only_gpu_engines_allowed():
    ok, msg = K.render_on_kaggle("/x.epub", "v", "kokoro", 1, 0, "/out", "/k")
    assert not ok and "kokoro" in msg


def test_slug_collapses_consecutive_dashes():
    assert K._slug("Breakneck - Dan Wang") == "breakneck-dan-wang"
    assert K._slug("A - B - C") == "a-b-c"
    assert K._slug("hello---world") == "hello-world"


def test_finalist_rtf_is_measured_value():
    assert K.ENGINE_RTF['vibevoice'] == 2.266
    assert K.ENGINE_RTF['qwen3'] == 2.056


def test_qa_reports_merge_across_kaggle_sessions(tmp_path):
    dst = tmp_path / 'qa_report.json'
    src = tmp_path / 'incoming.json'
    dst.write_text(json.dumps({'chapters': [
        {'chapter': 1, 'wer': 0.02, 'flagged': False}],
        'flagged_chapters': [], 'lexicon_suggestions': {'A': 'a'}}))
    src.write_text(json.dumps({'chapters': [
        {'chapter': 2, 'wer': 0.2, 'flagged': True}],
        'flagged_chapters': [2], 'lexicon_suggestions': {'B': 'b'}}))
    K._merge_qa_report(src, dst)
    merged = json.loads(dst.read_text())
    assert [c['chapter'] for c in merged['chapters']] == [1, 2]
    assert merged['flagged_chapters'] == [2]
    assert merged['lexicon_suggestions'] == {'A': 'a', 'B': 'b'}


def test_finalist_kaggle_ref_fails_closed_without_full_deployed_sha(tmp_path, monkeypatch):
    (tmp_path / 'run_vibevoice.py').write_text('APP_REF = ""\nVOICE = "v"\nSTART = 1\nEND = 0\n')
    monkeypatch.setattr(K, 'kaggle_username', lambda: 'dave')
    monkeypatch.setenv('APP_GIT_SHA', 'abc1234')
    ok, msg = K.render_on_kaggle('/x.epub', 'v', 'vibevoice', 1, 1,
                                 str(tmp_path / 'out'), str(tmp_path))
    assert not ok
    assert '40-character commit' in msg
