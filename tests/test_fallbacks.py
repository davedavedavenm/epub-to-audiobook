"""Functional tests for the fallback chains (#6). Local, no network."""
import os
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_llm():
    # ensure NO LLM is configured so we exercise the seed-floor path
    for k in list(os.environ):
        if k.startswith('LLM_'):
            os.environ.pop(k, None)
    os.environ['DB_PATH'] = str(ROOT / 'tests' / '_nonexistent_.db')
    spec = importlib.util.spec_from_file_location('llm_metadata', ROOT / 'webapp' / 'llm_metadata.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_narration_profile_degrades_to_seed_floor_without_llm():
    """No LLM configured must yield a usable seed profile, NOT {} — so a book
    still gets Cupertino/Beijing/etc right with zero external dependencies."""
    m = _load_llm()
    prof = m.generate_narration_profile(Path('does-not-exist.epub'))
    assert prof and prof.get('rules'), "narration profile collapsed to empty without LLM (#6)"
    assert 'Cupertino' in prof['rules'], "seed floor missing known-hard names (#6)"
    assert prof.get('form') in ('fiction', 'nonfiction')
    assert prof.get('is_fiction') in (True, False)


def test_fallback_settings_env_only():
    m = _load_llm()
    assert m._fallback_settings() is None       # nothing configured
    os.environ['LLM_FALLBACK_API_KEY'] = 'x'
    try:
        fb = m._fallback_settings()
        assert fb and fb['LLM_API_KEY'] == 'x'
    finally:
        os.environ.pop('LLM_FALLBACK_API_KEY', None)
