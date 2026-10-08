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


def test_ordinal_word_vs_digit_not_a_divergence():
    """Whisper writes 'the 14th century' where the audio said 'fourteenth' —
    that must NOT flag (found while proving #7 on real zorin audio)."""
    q = _load()
    r = q.diff_report("by the fourteenth century, certainly by the fifteenth.",
                      "by the 14th century, certainly by the 15th.")
    assert r['wer'] == 0.0, f"ordinal word/digit produced false divergences: {r['divergences']}"


def test_decade_digits_vs_spoken_decade_do_not_diverge():
    """Whisper writes '1930s' / '60s'; as_prep's text says 'nineteen thirties' / 'sixties'. Seen as a
    false 3-word 'drop' in the per-chunk audit of the Armed Struggle Preface (2026-10-07)."""
    q = _load()
    r = q.diff_report("during the nineteen thirties, nineteen forties and sixties",
                      "during the 1930s, 1940s and 60s")
    assert r['wer'] == 0.0, r['divergences']


def test_accented_irish_names_are_one_token_each():
    """'Seán MacStiofáin' tokenised as 'se n macstiof in' and a complete name list looked like
    dropped words against Whisper's spelling (Armed Struggle ch.3, 2026-10-07)."""
    q = _load()
    assert q.normalize_words("Seán MacStiofáin, Ó Brádaigh") == ['sean', 'macstiofain', 'o', 'bradaigh']
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import chunk_asr_audit as ca
    r = ca.audit_chunk("included Seán MacStiofáin, Ruree oh Brawdee and Daithi O’Connell. All three",
                       "included Sean McSteafon, Ruré Obradi, and Deithi O'Connell. All three")
    assert not r["bad"], r


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


def test_known_asr_name_error_does_not_yield_pronunciation_suggestion():
    """Dave heard Huawei correctly in both Q8 clips while Whisper disagreed.
    That machine error must never become a lexicon change suggestion."""
    q = _load()
    r = q.diff_report("The Huawei device shipped.", "The wawei device shipped.")
    sugg = q.suggest_lexicon(r['divergences'])
    assert 'huawei' not in sugg


def test_short_words_not_suggested():
    """High-precision: trivial 1-2 char subs (ASR noise) must not pollute the
    lexicon."""
    q = _load()
    r = q.diff_report("a cat sat", "a bat sat")
    assert q.suggest_lexicon(r['divergences']) == {}  # 'cat'->'bat' too similar/short-ish


def test_respelled_names_and_uk_spelling_are_not_drops():
    """Chunk text carries the pronunciation lexicon's respellings; Whisper writes the real names and
    US spelling. Armed Struggle ch.1 fill (2026-10-08): 'Shin Fayn organisation' and 'Kummun na Bann'
    failed the word check on every seed although the audio was complete."""
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import chunk_asr_audit as ca
    r = ca.audit_chunk("a political adjunct to the Shin Fayn organisation.",
                       "a political adjunct to the Sinn Fein organization.")
    assert not r["bad"] and r["tail"] == 0, r
    r = ca.audit_chunk("By nineteen twenty-two little, apparently, had changed: The Kummun na Bann.",
                       "By 1922, little apparently had changed. The Cumann na mBan.")
    assert not r["bad"], r



def test_a_differently_spelled_ending_is_not_a_truncation_but_a_cut_off_is():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import chunk_asr_audit as ca
    ok = ca.audit_chunk("had changed: The Kummun na Bann...", "had changed the Kumanna ban.")
    assert not ok["bad"] and ok["tail_unheard"] < 3, ok
    cut = ca.audit_chunk("I managed to block the inside door...", "I managed to block.")   # ch.4 #156, real
    assert cut["bad"] and cut["tail_unheard"] == 3, cut
