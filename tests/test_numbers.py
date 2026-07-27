"""Numbers, decades and suffixes are spoken, not spelt out as symbols.

Dave, 2026-07-27: *"sometimes numbers are provided with a suffix of k to denote
thousands. This should be reflected."* Chasing that turned up a cluster of
related defects in the same area, all of which reached real books.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from tts_preprocess import normalize_text_for_tts  # noqa: E402


def modern(t):
    return normalize_text_for_tts(t, modern=True)


def legacy(t):
    return normalize_text_for_tts(t, modern=False)


class TestKSuffix:
    """The reported bug: '50k' was read as 'fifty kay' on every engine."""

    def test_k_becomes_thousand(self):
        for f in (modern, legacy):
            assert 'fifty thousand' in f('It cost 50k pounds.')
            assert 'two hundred and fifty thousand' in f('Around 250k users.') \
                or 'two hundred fifty thousand' in f('Around 250k users.')

    def test_uppercase_k_too(self):
        assert 'fifty thousand' in modern('It cost 50K.')

    def test_decimal_k(self):
        out = modern('a 12.5k word essay')
        assert 'twelve point five thousand' in out

    def test_screen_resolutions_are_not_thousands(self):
        """4K and 8K are resolutions. The >=10 rule excludes them without
        needing to enumerate every one."""
        assert '4K display' in modern('a 4K display')
        assert '8K' in modern('an 8K screen')

    def test_kilometres_survive(self):
        assert '10km' in modern('a 10km run')

    def test_standalone_k_words_untouched(self):
        assert 'K2' in modern('the K2 summit')
        assert 'vitamin K' in modern('vitamin K deficiency')


class TestDecades:
    def test_plural_is_english(self):
        """'nineteen eightys' shipped in every book mentioning a decade."""
        out = legacy('the 1980s were odd')
        assert 'nineteen eighties' in out
        assert 'eightys' not in out

    def test_apostrophe_form_is_not_a_possessive(self):
        """Fixed for BOTH engine classes, because it is not decade spelling —
        it repairs damage the YEAR rule does, and modern runs the year rule.
        Left alone, modern said "nineteen eighty's"."""
        for f in (modern, legacy):
            out = f("the 1980's were odd")
            assert 'nineteen eighties' in out
            assert "eighty's" not in out

    def test_bare_decade_left_raw_for_modern(self):
        """MODERN-ENGINE CONTRACT. Spelling a bare decade for modern is a
        plain-number transform and needs an ear test first; a regression guard
        enforces it."""
        assert '1990s' in modern('It was the 1990s.')

    def test_turn_of_century(self):
        assert 'eighteen hundreds' in legacy('back in the 1800s')

    def test_twenties_and_thirties(self):
        assert 'nineteen twenties' in legacy('the 1920s')
        assert 'nineteen thirties' in legacy('the 1930s')


class TestModernThousandsComma:
    """A thousands comma is a comma, and engines pause at commas.

    The 2026-07-08 'stilted and weird' fix stripped the comma num2words emits
    and never touched the one already in the source text, so modern engines —
    which render every book — still met it.
    """

    def test_comma_removed_for_modern(self):
        out = modern('She had 3,400 followers.')
        assert '3,400' not in out
        assert '3400' in out

    def test_multiple_groups(self):
        out = modern('A population of 1,250,000 people.')
        assert ',' not in out.split('population of')[1].split(' people')[0]

    def test_legacy_still_spells_it_out(self):
        assert 'three thousand four hundred' in legacy('She had 3,400 followers.')

    def test_ordinary_commas_are_untouched(self):
        out = modern('He waited, then left, then returned.')
        assert out.count(',') == 2


class TestDecimals:
    def test_decimal_percent_is_spoken(self):
        out = legacy('about 12.5% of them')
        assert 'twelve point five percent' in out
        assert '12.5' not in out


class TestNothingRegressed:
    def test_years_still_spelled(self):
        assert 'nineteen ninety seven' in modern('In 1997.')
        assert 'nineteen ninety-seven' in legacy('In 1997.')

    def test_year_ranges_still_get_to(self):
        assert 'nineteen fourteen to nineteen eighteen' in modern('the 1914-1918 war')

    def test_compound_hyphen_rule_still_applies(self):
        assert 'daisy chain' in modern('making a daisy-chain')
