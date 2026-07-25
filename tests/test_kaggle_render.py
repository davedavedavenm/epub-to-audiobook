"""Guards for the Kaggle GPU render backend (webapp/kaggle_render.py)."""
import os
import sys
import datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import kaggle_render as K


def test_kernel_source_substitutes_knobs():
    tmpl = 'VOICE  = "uk_male_minter"\nSTART  = 1\nEND    = 0\n'
    out = K.render_kernel_source(tmpl, "uk_female_golding", 5, 6)
    assert 'VOICE  = "uk_female_golding"' in out
    assert 'START  = 5' in out and 'END    = 6' in out
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
