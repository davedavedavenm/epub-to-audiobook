"""Tests for the opt-in TypeSafe/Jev decision layer (webapp/jevspeak.py).

All tests are offline: Jev is exercised through an injected fake client. The
most important guarantee under test is that with the feature flags OFF the new
entry points are byte-identical to today's behaviour, and that every failure
mode (no key, bad answer, low confidence, exception) falls back to it.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'webapp'))

import jevspeak  # noqa: E402
import tts_preprocess as tp  # noqa: E402


# Realistic book prose containing every ambiguous class the module targets.
BOOK_TEXT = (
    "He cut the cake in 1/2 and gave Dr. Smith a slice at St. Pancras. "
    "It cost £4.50, and the meeting ran 10-12 minutes past No. 4, "
    "while the cable measured 3.5mm and weighed 5kg. "
    "The chapter is marked IV; the author was J. R. R. Tolkien, "
    "who wrote in the 1990s and paid $1.2 billion."
)


class _Recorder:
    """Fake client: maps a span to a choice, and records whether it ran."""
    def __init__(self, choice_for=None, confidence=1.0, raise_on_call=False):
        self.choice_for = choice_for or {}
        self.confidence = confidence
        self.raise_on_call = raise_on_call
        self.calls = []

    def __call__(self, questions, state):
        self.calls.append(questions)
        if self.raise_on_call:
            raise RuntimeError('boom')
        answers = {}
        for qid, question in questions.items():
            info = question['instructions']
            key = info['span'] if 'span' in info else info.get('title')
            choice = self.choice_for.get(key)
            if choice is not None:
                answers[qid] = {'choice': choice, 'confidence': self.confidence,
                                'probabilities': {choice: self.confidence}}
        return answers


def _noop_client():
    return _Recorder()


# --- Feature 1: flag OFF is byte-identical to today -------------------------

def test_off_matches_normalizer_exactly(monkeypatch):
    monkeypatch.delenv('JEV_TTS_NORMALIZATION_ENABLED', raising=False)
    for modern in (True, False):
        for expand in (None, True):
            got = jevspeak.normalize_text_for_tts_jev(
                BOOK_TEXT, modern=modern, expand_numbers=expand)
            want = tp.normalize_text_for_tts(
                BOOK_TEXT, modern=modern, expand_numbers=expand)
            assert got == want, (modern, expand, got, want)


def test_off_never_calls_the_client():
    boom = _Recorder(raise_on_call=True)
    out = jevspeak.normalize_text_for_tts_jev(BOOK_TEXT, enabled=False, client=boom)
    assert boom.calls == []
    assert out == tp.normalize_text_for_tts(BOOK_TEXT)


def test_off_is_identity_for_realistic_corpus():
    corpus = [BOOK_TEXT, "No. 4, IV, 3.5mm, 10-12, 1/2, Dr., £4.50, J. R. R."]
    for text in corpus:
        assert jevspeak.normalize_text_for_tts_jev(text, enabled=False) == \
            tp.normalize_text_for_tts(text)


# --- Feature 1: candidate detection ----------------------------------------

def test_finds_every_ambiguous_class():
    kinds = {c.kind for c in jevspeak.find_normalization_candidates(BOOK_TEXT)}
    assert {'slash', 'currency', 'abbrev', 'range', 'unit', 'roman', 'initials'} <= kinds


def test_candidates_are_non_overlapping_and_ordered():
    candidates = jevspeak.find_normalization_candidates(BOOK_TEXT)
    for earlier, later in zip(candidates, candidates[1:]):
        assert earlier.end <= later.start


def test_spaced_inches_is_not_a_unit():
    # "5 in the morning" must not be read as inches.
    kinds = {c.kind for c in jevspeak.find_normalization_candidates('5 in the morning')}
    assert 'unit' not in kinds


def test_year_range_is_left_to_the_deterministic_rule():
    assert jevspeak.find_normalization_candidates('1914-1918') == []


def test_decades_are_not_unit_candidates():
    # A trailing "s" must not turn a decade into "seconds" (real-book defect:
    # "1980s"/"70s" matched the seconds unit and would be sent to Jev).
    for text in ('Deng Xiaoping governed in the 1980s and 1990s.',
                 'The 1960s and 1970s changed everything.',
                 'The Californian counterculture of the ’70s mattered.'):
        assert all(c.kind != 'unit' for c in
                   jevspeak.find_normalization_candidates(text)), text


def test_real_seconds_still_detected():
    spans = {c.span: c.kind for c in
             jevspeak.find_normalization_candidates('He waited 5s then ran 5m.')}
    assert spans.get('5s') == 'unit' and spans.get('5m') == 'unit'


def test_isbn_hyphen_groups_are_not_ranges():
    # Real-book defect: "978-0-330-47579-2" yielded a bogus range "330-47579".
    assert jevspeak.find_normalization_candidates(
        'ISBN 978-0-330-47579-2 in Adobe Reader format.') == []


def test_roman_needs_canonical_form():
    spans = [c.span for c in jevspeak.find_normalization_candidates('MIX IV VII')]
    assert 'IV' in spans and 'VII' in spans


# --- Feature 1: renderers ---------------------------------------------------

def test_fraction_renderer():
    assert jevspeak._fraction_to_words(1, 2) == 'one half'
    assert jevspeak._fraction_to_words(3, 4) == 'three quarters'
    assert jevspeak._fraction_to_words(5, 8) == 'five eighths'


def test_date_renderer_is_british():
    assert jevspeak._date_uk(9, 11) == 'the ninth of November'


def test_money_renderer():
    assert jevspeak._money_words('£', '4.50') == 'four pounds and fifty pence'
    assert jevspeak._money_words('$', '1') == 'one dollar'


def test_scaled_currency_renderer():
    # Real-book defect: "$36 billion" rendered only the amount, stranding the
    # scale word ("thirty-six dollars billion").
    assert jevspeak._scaled_currency('$', '36', 'billion') == 'thirty-six billion dollars'
    assert jevspeak._scaled_currency('$', '1', 'trillion') == 'one trillion dollars'
    assert jevspeak._scaled_currency('£', '1.2', 'billion') == 'one point two billion pounds'


def test_currency_with_scale_word_keeps_the_scale():
    out = jevspeak.normalize_text_for_tts_jev(
        'It cost $36 billion to build.', enabled=True,
        client=_Recorder({'$36 billion': 'money'}))
    assert 'thirty-six billion dollars' in out
    assert 'dollars billion' not in out


def test_year_range_renders_in_year_style():
    # Real-book defect: abbreviated year ranges read as cardinals
    # ("one thousand nine hundred and nineteen to twenty-one").
    out = jevspeak.normalize_text_for_tts_jev(
        'The IRA of 1919–21 were at the centre.', enabled=True,
        client=_Recorder({'1919–21': 'range'}))
    assert 'nineteen nineteen to twenty-one' in out
    assert 'one thousand' not in out


# --- Feature 1: chosen readings are applied --------------------------------

_CHOICES = {
    '1/2': 'fraction', 'Dr.': 'drive', 'IV': 'numeral', '3.5mm': 'measurement',
    '10-12': 'range', '£4.50': 'literal', 'J. R. R.': 'letters',
    'No.': 'number', '5kg': 'measurement', '$1.2': 'money',
}


def test_applies_chosen_readings():
    text = ("He cut the cake in 1/2 and gave Dr. Smith a slice. "
            "The chapter is marked IV and the cable measured 3.5mm.")
    out = jevspeak.normalize_text_for_tts_jev(
        text, enabled=True, client=_Recorder(_CHOICES))
    assert 'one half' in out
    assert 'Drive' in out
    assert 'four' in out
    assert 'three point five millimetres' in out


def test_abbreviation_can_mean_drive_not_doctor():
    out = jevspeak.normalize_text_for_tts_jev(
        'He lives on Dr. Smith Avenue.', enabled=True, client=_Recorder(_CHOICES))
    assert 'Drive' in out and 'Doctor' not in out


def test_initials_are_spelled_out():
    out = jevspeak.normalize_text_for_tts_jev(
        'J. R. R. Tolkien wrote it.', enabled=True, client=_Recorder(_CHOICES))
    assert 'J R R' in out


def test_currency_literal_reading():
    out = jevspeak.normalize_text_for_tts_jev(
        'It cost £4.50 today.', enabled=True, client=_Recorder(_CHOICES))
    assert 'four point five pounds' in out


# --- Feature 1: failure modes fall back ------------------------------------

def test_empty_answer_falls_back():
    out = jevspeak.normalize_text_for_tts_jev(
        BOOK_TEXT, enabled=True, client=_Recorder({}))
    assert out == tp.normalize_text_for_tts(BOOK_TEXT)


def test_client_exception_falls_back():
    out = jevspeak.normalize_text_for_tts_jev(
        BOOK_TEXT, enabled=True, client=_Recorder(_CHOICES, raise_on_call=True))
    assert out == tp.normalize_text_for_tts(BOOK_TEXT)


def test_low_confidence_answer_is_ignored():
    out = jevspeak.normalize_text_for_tts_jev(
        'He cut it in 1/2.', enabled=True,
        client=_Recorder({'1/2': 'fraction'}, confidence=0.1))
    assert out == tp.normalize_text_for_tts('He cut it in 1/2.')


def test_missing_key_falls_back(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.delenv('TYPESAFE_API_KEY_PATH', raising=False)
    monkeypatch.setattr(jevspeak, 'DEFAULT_KEY_PATHS', ())
    out = jevspeak.normalize_text_for_tts_jev(BOOK_TEXT, enabled=True)
    assert out == tp.normalize_text_for_tts(BOOK_TEXT)


def test_batching_splits_requests(monkeypatch):
    monkeypatch.setenv('JEV_BATCH_SIZE', '2')
    recorder = _Recorder(_CHOICES)
    text = "1/2 Dr. IV 3.5mm 10-12 J. R. R."
    out = jevspeak.normalize_text_for_tts_jev(text, enabled=True, client=recorder)
    assert len(recorder.calls) > 1
    assert 'one half' in out and 'Drive' in out


# --- Feature 2: chapter boundary ranking -----------------------------------

def _chapter(index, title, words, back_matter=False, below=False):
    return {'index': index, 'title': title, 'words': words, 'href': f'{index}.xhtml',
            'snippet': f'Opening words of {title} with real narrative content here.',
            'back_matter': back_matter, 'below_threshold': below}


def _book():
    return [
        _chapter(1, 'Chapter One', 3000),
        _chapter(2, 'Notes', 3000, back_matter=True),
        _chapter(3, 'Dedication', 90, below=True),
        _chapter(4, 'Introduction', 150),
        _chapter(5, 'Chapter Two', 2500),
    ]


def test_boundary_off_is_identity():
    chapters = _book()
    assert jevspeak.refine_boundaries(chapters, 120, enabled=False) is chapters


def test_boundary_no_ambiguity_makes_no_call():
    recorder = _Recorder()
    chapters = [_chapter(1, 'Chapter One', 3000), _chapter(2, 'Chapter Two', 2500)]
    decisions = jevspeak.rank_chapter_boundaries(chapters, 120, enabled=True, client=recorder)
    assert decisions == {}
    assert recorder.calls == []


def test_boundary_decisions_rescue_drop_and_clear():
    titles = {'Notes': 'body', 'Dedication': 'back_matter', 'Introduction': 'body'}
    recorder = _Recorder(titles)
    refined = jevspeak.refine_boundaries(_book(), 120, enabled=True, client=recorder)
    assert [c['title'] for c in refined] == \
        ['Chapter One', 'Notes', 'Introduction', 'Chapter Two']
    assert [c['index'] for c in refined] == [1, 2, 3, 4]
    notes = next(c for c in refined if c['title'] == 'Notes')
    assert notes['back_matter'] is False
    assert all('below_threshold' not in c for c in refined)


def test_boundary_failure_drops_below_threshold_only():
    refined = jevspeak.refine_boundaries(
        _book(), 120, enabled=True, client=_Recorder(raise_on_call=True))
    # Today's behaviour is preserved: below-floor Dedication stays out, the
    # flagged-but-real Notes stays in with its flag intact.
    assert [c['title'] for c in refined] == \
        ['Chapter One', 'Notes', 'Introduction', 'Chapter Two']
    assert next(c for c in refined if c['title'] == 'Notes')['back_matter'] is True


def test_boundary_low_confidence_keeps_heuristic():
    refined = jevspeak.refine_boundaries(
        _book(), 120, enabled=True,
        client=_Recorder({'Notes': 'back_matter'}, confidence=0.2))
    assert any(c['title'] == 'Notes' for c in refined)


# --- chapters.py integration ------------------------------------------------

def _write_epub(path):
    one = " ".join(f"word{n}" for n in range(300))
    two = " ".join(f"ded{n}" for n in range(90))
    opf = """<package><manifest>
    <item id="c1" href="c1.xhtml"/><item id="c2" href="c2.xhtml"/>
    </manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>"""
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('content.opf', opf)
        archive.writestr('c1.xhtml', f'<html><body><h1>One</h1><p>{one}</p></body></html>')
        archive.writestr('c2.xhtml', f'<html><body><h1>Dedication</h1><p>{two}</p></body></html>')


def test_chapters_off_path_is_unchanged(tmp_path):
    import chapters
    epub = tmp_path / 'book.epub'
    _write_epub(epub)
    listing = chapters.list_renderable_chapters(epub)
    assert [c['index'] for c in listing] == [1]
    assert listing[0]['title'] == 'One'
    assert all('below_threshold' not in c for c in listing)


def test_chapters_on_path_gathers_and_refines_below_threshold(tmp_path, monkeypatch):
    import chapters
    epub = tmp_path / 'book.epub'
    _write_epub(epub)

    def fake_refine(chapter_list, min_words, **kwargs):
        kept = [{k: v for k, v in c.items() if k != 'below_threshold'} for c in chapter_list]
        for position, chapter in enumerate(kept, 1):
            chapter['index'] = position
        return kept

    monkeypatch.setattr(jevspeak, 'chapter_boundary_enabled', lambda explicit=None: True)
    monkeypatch.setattr(jevspeak, 'refine_boundaries', fake_refine)
    listing = chapters.list_renderable_chapters(epub)
    assert [c['title'] for c in listing] == ['One', 'Dedication']
    assert all('below_threshold' not in c for c in listing)
