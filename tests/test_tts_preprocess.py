"""Tests for the mandatory TTS preprocessing pipeline (see PREPROCESSING.md).

The endnote/decimal cases are regressions found in a real book (Abundance,
ch.3): endnote markers after curly quotes leaked through, and the upstream
--remove_endnotes flag corrupted decimals and alphanumerics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import tts_preprocess as tp


# --- Stage 2: unicode cleanup ---

def test_unicode_hairspace():
    assert tp.normalize_unicode_for_tts('a b') == 'a b'


def test_unicode_nbsp():
    assert tp.normalize_unicode_for_tts('a b') == 'a b'


def test_unicode_soft_hyphen_removed():
    assert tp.normalize_unicode_for_tts('cob­bles') == 'cobbles'


def test_unicode_zero_width_removed():
    assert tp.normalize_unicode_for_tts('a​b') == 'ab'


# --- Stage 2: flattened endnote digits ---

def test_endnote_after_word():
    assert tp._ENDNOTE_AFTER_WORD_RE.sub('', 'inflation.33 But') == 'inflation. But'


def test_endnote_after_curly_quote():
    assert tp._ENDNOTE_AFTER_QUOTE_RE.sub('', 'virtue.”35 He') == 'virtue.” He'


def test_decimal_never_touched():
    assert tp._ENDNOTE_AFTER_WORD_RE.sub('', 'cost $2.58 billion') == 'cost $2.58 billion'


def test_decimal_with_trailing_endnote():
    assert tp._ENDNOTE_AFTER_WORD_RE.sub('', '$2.58 billion.36 By') == '$2.58 billion. By'


def test_alphanumeric_never_touched():
    assert tp._ENDNOTE_AFTER_WORD_RE.sub('', 'vitamin B12 helps') == 'vitamin B12 helps'


def test_bracketed_reference():
    assert tp._ENDNOTE_BRACKETED_RE.sub('', 'text[12] more') == 'text more'


# --- Stage 2: currency with scale words ---

def test_currency_scale_order():
    out = tp.normalize_text_for_tts('It cost $33 billion to build.')
    assert 'thirty-three billion dollars' in out


def test_currency_plain():
    out = tp.normalize_text_for_tts('He paid $50 for it.')
    assert 'fifty dollars' in out


# --- Stage 1: structural sanitizer ---

SAMPLE_HTML = '''<html><body>
<p>Spending rose fivefold.<sup><a href="notes.xhtml#n33">33</a></sup> But the size</p>
<p>the epitome of virtue.”<a epub:type="noteref" href="#n35">35</a> He laughed</p>
<p>for $2.58 billion.<a href="#n36">36</a> By 2023</p>
<p>Normal <a href="http://x.com">link text</a> stays, and <sup>note</sup> with a word stays.</p>
<aside epub:type="footnote" id="n33"><p>The footnote body text.</p></aside>
</body></html>'''


def _sanitized():
    return tp.sanitize_html(SAMPLE_HTML)


def test_sanitize_sup_digit_removed():
    assert '33' not in _sanitized()


def test_sanitize_noteref_removed():
    assert '>35<' not in _sanitized()


def test_sanitize_digit_link_removed():
    assert '>36<' not in _sanitized()


def test_sanitize_note_body_removed():
    assert 'footnote body' not in _sanitized()


def test_sanitize_normal_link_kept():
    assert 'link text' in _sanitized()


def test_sanitize_word_sup_kept():
    assert '<sup>note</sup>' in _sanitized()


def test_sanitize_decimal_kept():
    assert '$2.58' in _sanitized()


# --- End to end text pipeline ---

def test_pipeline_endnote_and_numbers():
    out = tp.normalize_text_for_tts('It cost $2.58 billion.36 By 2023, some 50% agreed.')
    assert '36' not in out
    assert 'fifty percent' in out


def test_year_2000s_natural():
    # regression: 2000 was read "twenty hundred", 2001 "twenty oh one"
    assert tp._year_to_words('2000') == 'two thousand'
    assert tp._year_to_words('2001') == 'two thousand one'
    assert tp._year_to_words('2009') == 'two thousand nine'
    # 2010+ and 19xx keep the "twenty ten" / "nineteen ..." style
    assert 'twenty' in tp._year_to_words('2019')
    assert 'nineteen' in tp._year_to_words('1994')


# --- stilted-numbers regression (2026-07-14) -------------------------------
# num2words returns "three thousand, four hundred". Every TTS engine reads that
# comma as a PAUSE, so numbers came out broken-up and stilted. Dave heard it and
# called it "stilted and weird". Numbers must be ONE flowing phrase.

def test_spelled_numbers_have_no_commas():
    from tts_preprocess import _number_to_words
    for n in (3400, 230000, 1234567, 101):
        assert ',' not in _number_to_words(n), f"comma in spelled number {n}"


def test_large_number_in_prose_is_not_broken_up():
    from tts_preprocess import normalize_text_for_tts
    out = normalize_text_for_tts("scaled from 3,400 workers", modern=False)
    assert 'three thousand four hundred' in out, out
    assert 'thousand,' not in out, out


def test_year_reads_naturally_for_dumb_engines():
    from tts_preprocess import normalize_text_for_tts
    out = normalize_text_for_tts("In the spring of 1997, Apple", modern=False)
    assert 'nineteen ninety-seven' in out, out
    assert 'one thousand' not in out, out


# --- years are spelled for EVERY engine (A/B verdict, 2026-07-14, #26) --------
# Reversed the old modern-engine ban: the "pause" that got year-spelling banned
# was caused by num2words' COMMA, not by the spelling. Dave A/B'd raw vs spelled
# on chatterbox and judged spelled better.

def test_years_are_spelled_for_modern_engines_too():
    from tts_preprocess import normalize_text_for_tts
    out = normalize_text_for_tts("In the spring of 1997, and again in 2001.", modern=True)
    # No hyphen on modern from 2026-07-27 — the engine pauses at one. Spelled is
    # still spelled, which is what this test exists to protect.
    assert 'nineteen ninety seven' in out, out
    assert 'two thousand one' in out, out
    assert '1997' not in out, out


def test_modern_still_keeps_raw_currency_and_percent():
    # NOT judged by ear yet — must stay raw until A/B'd (#26).
    from tts_preprocess import normalize_text_for_tts
    out = normalize_text_for_tts("roughly 52% of $1.2 billion", modern=True)
    assert '52%' in out and '$1.2' in out, out
