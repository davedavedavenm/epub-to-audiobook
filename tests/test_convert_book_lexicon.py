import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "webapp"))

import convert_book  # noqa: E402


def test_seed_fallback_is_not_reported_as_llm(capsys, monkeypatch):
    fallback = SimpleNamespace(
        generate_narration_profile=lambda _path: {
            "form": "fiction",
            "domain": "general",
            "rules": {"CEO": "C E O"},
            "notes": ["seed-only (no LLM configured)"],
        },
        generate_lexicon=lambda _path: {},
    )
    monkeypatch.setitem(sys.modules, "llm_metadata", fallback)

    convert_book.build_lexicon("unused.epub")

    output = capsys.readouterr().out
    assert "seed only" in output
    assert "LLM+seed" not in output


def test_real_llm_profile_is_reported_as_llm(capsys, monkeypatch):
    adaptive = SimpleNamespace(
        generate_narration_profile=lambda _path: {
            "form": "fiction",
            "domain": "general",
            "rules": {"Xyzzy": "ziz-ee"},
            "notes": [],
        },
        generate_lexicon=lambda _path: {},
    )
    monkeypatch.setitem(sys.modules, "llm_metadata", adaptive)

    convert_book.build_lexicon("unused.epub")

    assert "LLM+seed" in capsys.readouterr().out
