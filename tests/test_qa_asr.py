"""Unit tests for QA Layer 2 (ASR verification) — the pure-python alignment
core, tested WITHOUT audio or a Whisper model so the logic is guarded on any
machine (see webapp/qa_asr.py)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location('qa_asr', ROOT / 'webapp' / 'qa_asr.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_clean_match_is_zero_wer():
    q = _load()
    r = q.diff_report("Released in 1997 by the company.", "Released in 1997 by the company.")
    assert r['wer'] == 0.0 and not r['divergences']


def test_digits_vs_spoken_year_do_not_diverge():
    """Modern engines keep raw '1997'; Whisper may emit digits or words — the
    normaliser must treat them the same so we don't cry wolf on every year."""
    q = _load()
    r = q.diff_report("It was 1997.", "It was nineteen ninety-seven.")
    assert r['wer'] == 0.0, f"year formatting produced false divergences: {r['divergences']}"


def test_dropped_number_piece_is_caught():
    """The '1976 heard as nineteen seventy' bug (final digit dropped) must
    surface as a divergence — this is the class QA Layer 2 exists to catch."""
    q = _load()
    r = q.diff_report("Founded in 1976 by Jobs.", "Founded in nineteen seventy by Jobs.")
    assert r['wer'] > 0
    assert any(d['type'] == 'drop' and 'six' in d['source'] for d in r['divergences'])


def test_dropped_sentence_is_caught():
    q = _load()
    r = q.diff_report("alpha bravo charlie delta echo foxtrot", "alpha bravo foxtrot")
    assert any(d['type'] == 'drop' for d in r['divergences'])
    assert r['wer'] >= 0.4


def test_misread_name_yields_lexicon_suggestion():
    q = _load()
    r = q.diff_report("The Huawei device shipped.", "The wawei device shipped.")
    sugg = q.suggest_lexicon(r['divergences'])
    assert sugg.get('huawei') == 'wawei'


def test_short_words_not_suggested():
    """High-precision: trivial 1-2 char subs (ASR noise) must not pollute the
    lexicon."""
    q = _load()
    r = q.diff_report("a cat sat", "a bat sat")
    assert q.suggest_lexicon(r['divergences']) == {}  # 'cat'->'bat' too similar/short-ish
