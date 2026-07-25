"""All-caps emphasis must not be read as an initialism (#34).

Heard by ear in the Alice in Wonderland render: the source says
`labelled "ORANGE MARMALADE"` and Chatterbox Nano mangled it, because nothing
in the pipeline normalised case and modern TTS treats all-caps as letters.

The rule under test: acronyms appear as SINGLE tokens in normal-case prose,
emphasis appears in RUNS. So two or more consecutive all-caps words get
sentence case, and a lone CEO/FBI/NASA is never touched.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from tts_preprocess import _normalize_caps_runs, normalize_text_for_tts  # noqa: E402


class TestTheBugItself:
    def test_orange_marmalade(self):
        src = 'it was labelled "ORANGE MARMALADE", but to her disappointment'
        assert 'Orange marmalade' in _normalize_caps_runs(src)
        assert 'ORANGE' not in _normalize_caps_runs(src)

    def test_other_alice_labels(self):
        assert 'Drink me' in _normalize_caps_runs('a bottle marked DRINK ME')
        assert 'Eat me' in _normalize_caps_runs('the cake said EAT ME')


class TestAcronymsSurvive:
    """The whole reason the rule keys off runs rather than single tokens."""

    def test_lone_acronyms_untouched(self):
        src = 'the CEO said the FBI and NASA agreed'
        assert _normalize_caps_runs(src) == src

    def test_adjacent_acronyms_untouched(self):
        # No vowels => initialism => spell it out, don't wordify it.
        assert _normalize_caps_runs('the BBC NHS report') == 'the BBC NHS report'
        assert _normalize_caps_runs('NASA JPL confirmed') == 'NASA JPL confirmed'

    def test_single_caps_word_untouched(self):
        # Needs world knowledge to resolve; deliberately left to the LLM
        # classifier rather than guessed at here.
        assert _normalize_caps_runs('He said NO. Then left.') == 'He said NO. Then left.'

    def test_dotted_acronyms_still_spell_out(self):
        # The existing dotted-acronym contract must not regress. (Bare "CEO"
        # is NOT auto-spelled — that comes from the lexicon, not a rule — so
        # the guarantee here is only that the new pass leaves it alone.)
        out = normalize_text_for_tts('He left the U.S. yesterday.', modern=True)
        assert 'U S' in out

    def test_new_pass_leaves_bare_acronym_intact(self):
        out = normalize_text_for_tts('The CEO left.', modern=True)
        assert 'CEO' in out


class TestRomanNumerals:
    def test_chapter_numeral_preserved(self):
        assert _normalize_caps_runs('CHAPTER VIII. The Queen') == 'Chapter VIII. The Queen'

    def test_all_numeral_run_untouched(self):
        assert _normalize_caps_runs('part IV II') == 'part IV II'


class TestBoilerplate:
    def test_gutenberg_licence_header(self):
        got = _normalize_caps_runs('THE FULL PROJECT GUTENBERG LICENSE')
        assert got == 'The full project gutenberg license'

    def test_legal_shouting(self):
        assert _normalize_caps_runs('WARRANTY OR DAMAGES apply') == 'Warranty or damages apply'


class TestPunctuationAndShape:
    def test_hyphen_and_apostrophe_runs(self):
        assert _normalize_caps_runs("DON'T PANIC now") == "Don't panic now"

    def test_normal_prose_unchanged(self):
        src = 'She took down a jar from one of the shelves as she passed.'
        assert _normalize_caps_runs(src) == src

    def test_title_case_unchanged(self):
        src = 'The Pool of Tears'
        assert _normalize_caps_runs(src) == src
