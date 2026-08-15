"""Regression guards for the bounded IndexTTS-2.5 Kaggle audition."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "kaggle" / "build_indextts25_gate.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_indextts25_gate", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_index_gate_is_pinned_private_t4_and_no_paid_or_asr_path(tmp_path, monkeypatch):
    builder = _load_builder()
    monkeypatch.setattr(builder, "OUT", tmp_path)
    assert builder.main() == 0
    metadata = json.loads((tmp_path / "kernel-metadata.json").read_text())
    source = (tmp_path / "run_indextts25_gate.py").read_text()
    assert metadata["is_private"] is True
    assert metadata["enable_gpu"] is True
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert "NvidiaTeslaP100" not in source
    assert '"paid_compute": False' in source
    assert '"asr_used": False' in source
    assert "faster-whisper" not in source
    assert builder.INDEX_COMMIT in source
    assert builder.MODEL_REVISION in source
    assert builder.ARTHUR_SHA256 in source


def test_index_gate_stages_one_sentence_safe_corrected_arm():
    builder = _load_builder()
    raw, prepared = builder.source_texts()
    assert raw != prepared
    assert "$1.2 billion" in raw and "52%" in raw and "£24.6 billion" in raw
    assert "one point two billion dollars" in prepared
    assert "fifty two percent" in prepared
    assert "twenty four point six billion pounds" in prepared
    assert "one point five gigawatts" in prepared
    assert "1.5 gigawatts" not in prepared
    assert 'assert len(segments) == 9' in builder.KERNEL
    assert 'tts.split_text_by_tokens(segment, 120, lang_prefix) == [segment]' in builder.KERNEL
    assert '"segment_policy": "complete sentences; one infer call per sentence"' in builder.KERNEL
    assert '"sentence_boundary_fix": True' in builder.KERNEL
