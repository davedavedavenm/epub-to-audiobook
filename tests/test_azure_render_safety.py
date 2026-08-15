import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "render_azure_accent_samples.py"
SPEC = importlib.util.spec_from_file_location("azure_render", SCRIPT)
azure_render = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(azure_render)


def test_gate_requires_explicit_focused_unique_voices():
    with pytest.raises(RuntimeError, match="between one and three"):
        azure_render._validate_gate([], "text", 4_000)
    with pytest.raises(RuntimeError, match="between one and three"):
        azure_render._validate_gate(["a", "b", "c", "d"], "text", 4_000)
    with pytest.raises(RuntimeError, match="Duplicate"):
        azure_render._validate_gate(["a", "a"], "text", 4_000)


def test_gate_fails_before_synthesis_when_character_budget_is_exceeded():
    with pytest.raises(RuntimeError, match="Refusing estimated 30"):
        azure_render._validate_gate(["a", "b", "c"], "0123456789", 29)
    assert azure_render._validate_gate(["a", "b"], "0123456789", 20) == (["a", "b"], 20)


def test_ssml_escapes_source_text_and_mp3_check_rejects_trivial_data():
    payload = azure_render._ssml("A & B < C", "en-IE", "en-IE-ConnorNeural")
    assert b"A &amp; B &lt; C" in payload
    assert b"en-IE-ConnorNeural" in payload
    assert not azure_render._looks_like_mp3(b"ID3" + b"x" * 100)
    assert azure_render._looks_like_mp3(b"ID3" + b"x" * 50_000)
