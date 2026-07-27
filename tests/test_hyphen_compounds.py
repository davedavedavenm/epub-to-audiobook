"""Hyphenated compounds must not be read with a pause inside them.

Dave, on a TADA render of the rabbit-hole paragraph (2026-07-27):
*"'daisychain' was 'daisy.....chain'"*.

Modern voice-clone engines treat an intra-word hyphen as a clause break, so one
compound word arrives as two with a gap between them. `tts_preprocess` already
documented this exact behaviour — "feeding them a human pronunciation guide like
Coo-per-TEE-no makes them read the hyphens as pauses" — but only ever acted on
it for lexicon respellings. The identical hyphen arriving in the SOURCE TEXT was
unguarded, and ordinary prose is full of them.

The interesting half of this is what must NOT change: the non-modern lexicon
path uses hyphens as syllable separators, so the rule is modern-only; and a
digit hyphen is a range or an identifier, not a compound.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from tts_preprocess import normalize_text_for_tts  # noqa: E402


def modern(t: str) -> str:
    return normalize_text_for_tts(t, modern=True)


def legacy(t: str, lexicon=None) -> str:
    return normalize_text_for_tts(t, lexicon=lexicon, modern=False)


class TestTheReportedBug:
    def test_daisy_chain_becomes_one_spoken_phrase(self):
        out = modern('the pleasure of making a daisy-chain would be worth it')
        assert 'daisy chain' in out
        assert 'daisy-chain' not in out

    def test_other_ordinary_compounds(self):
        for src, want in [
            ('a half-hearted attempt', 'half hearted'),
            ('an ill-tempered lobster', 'ill tempered'),
            ('the well-known rule', 'well known'),
            ('a good-natured person', 'good natured'),
        ]:
            assert want in modern(src), src


class TestWhatMustNotChange:
    def test_year_ranges_gain_a_spoken_to(self):
        """Found while adding the compound rule, and pre-existing.

        Years are spelled out before the hyphen rule runs, so '1914-1918' had
        been becoming 'nineteen fourteen-nineteen eighteen' — a hyphen the
        engine pauses at, and no 'to' anywhere, so the range read as two bare
        years. Ranges are now resolved while they are still digits.
        """
        out = modern('the war of 1914-1918 was long')
        assert 'nineteen fourteen to nineteen eighteen' in out

    def test_range_rule_is_narrow_enough_to_be_safe(self):
        """Only year-to-year. A score or a part number is not a range."""
        assert ' to ' not in modern('they won 3-1 in the final')

    def test_identifiers_keep_their_hyphen(self):
        assert 'COVID-19' in modern('the COVID-19 pandemic changed things')

    def test_em_dash_still_becomes_a_clause_break(self):
        """Real dashes ARE pauses. Only intra-word hyphens are not."""
        out = modern('she paused — and then went on')
        assert '—' in out

    def test_legacy_lexicon_respellings_survive(self):
        """The dumb-engine path spells pronunciation with hyphens. Applying the
        compound rule universally would flatten every one of them, which is why
        it is gated on `modern`."""
        out = legacy('We went to Cupertino today', lexicon={'Cupertino': 'Coo-per-TEE-no'})
        assert 'Coo-per-TEE-no' in out

    def test_legacy_source_hyphens_are_left_alone(self):
        assert 'daisy-chain' in legacy('making a daisy-chain in the sun')


class TestInteractionWithExistingRules:
    def test_caps_run_normalisation_still_works(self):
        """#34's fix and this one both touch hyphenated text; neither should
        break the other."""
        out = modern('a jar labelled ORANGE MARMALADE sat there')
        assert 'ORANGE MARMALADE' not in out

    def test_hyphenated_caps_run(self):
        out = modern('the sign read WELL-KNOWN BRAND on it')
        assert 'WELL-KNOWN' not in out
