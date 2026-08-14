"""Regression guards for the documented VibeVoice same-speaker-turn gate."""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / "scripts" / "kaggle"


def _load_builder():
    sys.path.insert(0, str(KAGGLE))
    try:
        spec = importlib.util.spec_from_file_location(
            "build_vibe_turn_reset_kernel",
            KAGGLE / "build_vibe_turn_reset_kernel.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(KAGGLE))


def _words(value: str) -> int:
    return len(re.sub(r"[^a-z0-9' ]+", " ", value.lower()).split())


def test_vibe_turn_schedules_change_only_same_speaker_boundaries():
    builder = _load_builder()
    paragraphs = builder.fixture_paragraphs()
    fixture = "\n\n".join(paragraphs)
    assert hashlib.sha256(fixture.encode()).hexdigest() == builder.FIXTURE_TEXT_SHA
    assert "draught , and" not in fixture
    assert fixture.count("draught, and") == 1
    source = re.sub(r"\s+", " ", fixture).strip()
    assert hashlib.sha256(source.encode()).hexdigest() == builder.SOURCE_SHA
    assert _words(source) == 1998

    expected_counts = {
        "short_turns": [283, 297, 280, 276, 265, 299, 298],
        "long_turns": [503, 489, 514, 492],
    }
    for schedule, ranges in builder.GROUPS.items():
        segments = builder._groups(paragraphs, ranges)
        assert [_words(segment) for segment in segments] == expected_counts[schedule]
        assert re.sub(r"\s+", " ", " ".join(segments)).strip() == source
        script = "\n".join("Speaker 1: " + segment for segment in segments)
        assert hashlib.sha256(script.encode()).hexdigest() == builder.EXPECTED_SCRIPT_SHA[schedule]
