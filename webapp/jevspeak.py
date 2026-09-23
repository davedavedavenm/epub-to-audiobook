"""TypeSafe/Jev decision layer for TTS text preparation — opt-in, default OFF.

Two independent, feature-flagged uses of TypeSafe's Jev model
(https://docs.typesafe.ai, model ``jev-latest``). Both are **fail-safe**: any
API error, timeout, malformed reply, or low-confidence answer leaves the input
exactly as the existing code would have produced it. When a flag is off the
entry points return their input unchanged, so the feature costs nothing and
changes nothing unless explicitly enabled.

1. TTS text normalization — ``JEV_TTS_NORMALIZATION_ENABLED``
   Regex finds the genuinely ambiguous spans a TTS engine misreads
   ("1/2", "Dr.", "No. 4", "IV", "3.5mm", "10-12", "£4.50", dotted initials).
   ONE batched Jev ``choice`` request decides how each span should be read in
   its surrounding sentence; code then applies the chosen spoken form. This is
   the "select instead of generate / pre-parsed value extraction" pattern.
   Deterministic classes (years, decades, ordinals, plain money on legacy
   engines) stay in code and are never sent to the model.

2. Chapter/section boundary ranking — ``JEV_CHAPTER_BOUNDARY_ENABLED``
   The existing heuristics (a word-count floor, a back-matter title regex) are
   ambiguous near the threshold and for titles that look like apparatus. Only
   ambiguous candidates are sent, as one batched Jev ``choice`` request, so the
   common case stays free.

Secrets: the API key is read from ``TYPESAFE_API_KEY``, else
``TYPESAFE_API_KEY_PATH``, else ``~/.mcpproxy/secrets/typesafe-api-key.txt``.
It is never logged or written to any artifact.

See JEVSPEAK.md for config, cost, failure behaviour and rollback.
"""
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import requests

from tts_preprocess import (
    _decimal_to_words,
    _number_to_words,
    _ordinal_to_words,
    _year_to_words,
    normalize_text_for_tts,
)

DEFAULT_API_URL = 'https://api.typesafe.ai/v1/systemone'
DEFAULT_MODEL = 'jev-latest'
DEFAULT_KEY_PATHS = (
    Path.home() / '.mcpproxy' / 'secrets' / 'typesafe-api-key.txt',
    Path(r'C:\Users\Dave\.mcpproxy\secrets\typesafe-api-key.txt'),
)


# ---------------------------------------------------------------------------
# Configuration (read at call time so tests and the app can override freely)
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, '') or default)
    except (TypeError, ValueError):
        return default


def tts_normalization_enabled(explicit: Optional[bool] = None) -> bool:
    """True when the Jev normalization pass may run (default OFF)."""
    return _env_flag('JEV_TTS_NORMALIZATION_ENABLED') if explicit is None else bool(explicit)


def chapter_boundary_enabled(explicit: Optional[bool] = None) -> bool:
    """True when Jev may rank ambiguous chapter boundaries (default OFF)."""
    return _env_flag('JEV_CHAPTER_BOUNDARY_ENABLED') if explicit is None else bool(explicit)


def min_confidence() -> float:
    """Below this Choice confidence the deterministic behaviour is kept."""
    return _env_float('JEV_MIN_CONFIDENCE', 0.55)


def jev_scan_floor(min_words: int) -> int:
    """Word floor used to gather below-threshold chapter candidates when enabled."""
    return min(min_words, _env_int('JEV_CANDIDATE_MIN_WORDS', 40))


def _api_key() -> str:
    key = (os.environ.get('TYPESAFE_API_KEY') or '').strip()
    if key:
        return key
    path = (os.environ.get('TYPESAFE_API_KEY_PATH') or '').strip()
    candidates = ([Path(path)] if path else []) + list(DEFAULT_KEY_PATHS)
    for candidate in candidates:
        try:
            if candidate.is_file():
                value = candidate.read_text(encoding='utf-8').strip()
                if value:
                    return value
        except OSError:
            continue
    return ''


# ---------------------------------------------------------------------------
# Jev client
# ---------------------------------------------------------------------------

# A client is any callable (questions, state) -> answers map. Tests inject a
# fake; production uses the HTTP endpoint below. ``ask_jev`` never raises.
JevClient = Callable[[dict, str], dict]


def ask_jev(questions: dict, state: str, *, client: Optional[JevClient] = None,
            timeout: Optional[float] = None) -> dict:
    """Evaluate ``questions`` against ``state``; return the answers map.

    Returns ``{}`` on any failure (missing key, network error, bad status,
    malformed body) so callers fall back to the existing behaviour.
    """
    if not questions:
        return {}
    if client is not None:
        try:
            answers = client(questions, state)
        except Exception as exc:  # noqa: BLE001 - fail-safe by contract
            logging.warning('jevspeak: injected client failed (%s); falling back',
                            type(exc).__name__)
            return {}
        return answers if isinstance(answers, dict) else {}

    key = _api_key()
    if not key:
        logging.warning('jevspeak: no TypeSafe API key configured; falling back')
        return {}

    url = os.environ.get('TYPESAFE_API_URL', DEFAULT_API_URL)
    model = os.environ.get('TYPESAFE_MODEL', DEFAULT_MODEL)
    if timeout is None:
        timeout = _env_float('JEV_TIMEOUT_SECONDS', 30.0)
    payload = {'state': state, 'model': model, 'questions': questions}
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    # The docs recommend exponential backoff on 429/529. Retries are bounded and
    # only for transient statuses; anything else fails over immediately.
    attempts = max(1, _env_int('JEV_MAX_ATTEMPTS', 2))
    retry_statuses = {429, 500, 502, 503, 504, 529}
    for attempt in range(attempts):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            body = resp.json()
            answers = body.get('answers') if isinstance(body, dict) else None
            return answers if isinstance(answers, dict) else {}
        except requests.HTTPError as exc:
            status = getattr(exc.response, 'status_code', None)
            if status in retry_statuses and attempt + 1 < attempts:
                time.sleep(0.5 * (2 ** attempt))
                continue
            logging.warning('jevspeak: Jev HTTP %s; falling back', status)
            return {}
        except Exception as exc:  # noqa: BLE001 - optional feature, must never raise
            logging.warning('jevspeak: Jev request failed (%s); falling back',
                            type(exc).__name__)
            return {}
    return {}


def _ask_batched(questions: dict, state: str, *, client: Optional[JevClient] = None) -> dict:
    """Send questions in bounded batches, one HTTP request per batch."""
    batch_size = max(1, _env_int('JEV_BATCH_SIZE', 40))
    items = list(questions.items())
    answers: dict = {}
    for start in range(0, len(items), batch_size):
        chunk = dict(items[start:start + batch_size])
        answers.update(ask_jev(chunk, state, client=client))
    return answers


# ---------------------------------------------------------------------------
# Feature 1 — TTS text normalization
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """One ambiguous span awaiting a reading decision."""
    cid: str
    kind: str
    start: int
    end: int
    span: str
    sentence: str
    criteria: dict
    render: Callable[[str], Optional[str]]


_MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December')
_ROMAN_VALUES = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}

# Spoken unit names for attached measurements ("5kg" -> "five kilograms").
_UNIT_WORDS = {
    'kg': 'kilograms', 'g': 'grams', 'mg': 'milligrams', 'km': 'kilometres',
    'cm': 'centimetres', 'mm': 'millimetres', 'ml': 'millilitres', 'l': 'litres',
    'GB': 'gigabytes', 'MB': 'megabytes', 'KB': 'kilobytes', 'TB': 'terabytes',
    'mph': 'miles per hour', 'kph': 'kilometres per hour', 'Hz': 'hertz',
    'kHz': 'kilohertz', 'MHz': 'megahertz', 'GHz': 'gigahertz', 'kW': 'kilowatts',
    'kWh': 'kilowatt hours', 'ft': 'feet', 'in': 'inches', 'lb': 'pounds',
    'oz': 'ounces', 'm': 'metres', 's': 'seconds', 'h': 'hours',
}

# Currency major/minor unit names, keyed by symbol.
_CURRENCY_UNITS = {
    '$': ('dollar', 'dollars', 'cent', 'cents'),
    '£': ('pound', 'pounds', 'penny', 'pence'),
    '€': ('euro', 'euros', 'cent', 'cents'),
}


def _number_words(value: str) -> str:
    """Integer or decimal digits -> spoken words (no thousands commas)."""
    if '.' in value:
        return _decimal_to_words(value)
    try:
        return _number_to_words(int(value))
    except ValueError:
        return value


def _fraction_to_words(numerator: int, denominator: int) -> Optional[str]:
    if denominator <= 0:
        return None
    if denominator == 2:
        denom = 'half' if numerator == 1 else 'halves'
    elif denominator == 4:
        denom = 'quarter' if numerator == 1 else 'quarters'
    else:
        denom = _ordinal_to_words(denominator) + ('' if numerator == 1 else 's')
    return f"{_number_to_words(numerator)} {denom}"


def _date_uk(first: int, second: int) -> Optional[str]:
    """Render a day/month pair in British style; None if it cannot be a date."""
    if 1 <= second <= 12 and 1 <= first <= 31:
        day, month = first, second
    elif 1 <= first <= 12 and 1 <= second <= 31:
        day, month = second, first
    else:
        return None
    return f"the {_ordinal_to_words(day)} of {_MONTHS[month - 1]}"


def _money_words(symbol: str, amount: str) -> Optional[str]:
    amount = amount.replace(',', '')
    major_one, major_many, minor_one, minor_many = _CURRENCY_UNITS[symbol]
    whole_s, dot, fraction = amount.partition('.')
    try:
        whole = int(whole_s or 0)
    except ValueError:
        return None
    if dot and 1 <= len(fraction) <= 2:
        minor = int(fraction.ljust(2, '0'))
        parts = []
        if whole or not minor:
            parts.append(f"{_number_to_words(whole)} {major_one if whole == 1 else major_many}")
        if minor:
            parts.append(f"{_number_to_words(minor)} {minor_one if minor == 1 else minor_many}")
        return ' and '.join(parts)
    words = _decimal_to_words(amount) if dot else _number_to_words(whole)
    unit = major_one if (not dot and whole == 1) else major_many
    return f"{words} {unit}"


def _scaled_currency(symbol: str, amount: str, scale: str) -> Optional[str]:
    """'$36' + 'billion' -> 'thirty-six billion dollars'.

    A currency amount followed by a scale word is a magnitude, not pounds-and-
    pence: the earlier code rendered only ``$36`` and left "billion" stranded
    ("thirty-six dollars billion"). The scale word is part of the span and the
    unit is plural because the scale always exceeds one.
    """
    amount = amount.replace(',', '')
    _, major_many, _, _ = _CURRENCY_UNITS[symbol]
    whole_s, dot, _ = amount.partition('.')
    try:
        whole = int(whole_s or 0)
    except ValueError:
        return None
    words = _decimal_to_words(amount) if dot else _number_to_words(whole)
    return f"{words} {scale.lower()} {major_many}"


def _literal_currency(symbol: str, amount: str) -> Optional[str]:
    amount = amount.replace(',', '')
    major_one, major_many, _, _ = _CURRENCY_UNITS[symbol]
    whole_s, dot, _ = amount.partition('.')
    try:
        whole = int(whole_s or 0)
    except ValueError:
        return None
    if dot:
        # Spoken decimals drop trailing zeros: "£4.50" -> "four point five".
        amount = amount.rstrip('0').rstrip('.') or '0'
        words = _decimal_to_words(amount)
    else:
        words = _number_to_words(whole)
    unit = major_one if (not dot and whole == 1) else major_many
    return f"{words} {unit}"


def _roman_to_int(text: str) -> Optional[int]:
    total, previous = 0, 0
    for char in reversed(text):
        value = _ROMAN_VALUES.get(char)
        if value is None:
            return None
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def _int_to_roman(value: int) -> str:
    table = ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'),
             (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'),
             (5, 'V'), (4, 'IV'), (1, 'I'))
    out = []
    for number, numeral in table:
        while value >= number:
            out.append(numeral)
            value -= number
    return ''.join(out)


def _is_canonical_roman(span: str) -> Optional[int]:
    value = _roman_to_int(span)
    if value is None or value <= 0:
        return None
    return value if _int_to_roman(value) == span else None


# Sentence extraction: expand to the nearest sentence boundaries around a span.
_SENT_END = re.compile(r'[.!?](?:["”’\'\)\]]*)')


def _sentence_for(text: str, start: int, end: int, max_len: int = 240) -> str:
    left = 0
    for match in _SENT_END.finditer(text, 0, start):
        left = match.end()
    match = _SENT_END.search(text, end)
    right = match.end() if match else len(text)
    sentence = text[left:right].strip()
    if len(sentence) > max_len:
        half = max_len // 2
        sentence = text[max(left, start - half):min(right, end + half)].strip()
    return sentence


def _make(kind: str, match: re.Match, text: str, criteria: dict,
          render: Callable[[str], Optional[str]]) -> Candidate:
    return Candidate(
        cid='', kind=kind, start=match.start(), end=match.end(),
        span=match.group(0), sentence=_sentence_for(text, match.start(), match.end()),
        criteria=criteria, render=render,
    )


_SLASH_RE = re.compile(r'(?<![\w/])(\d{1,4})/(\d{1,4})(?![\w/])')
_SLASH_CRITERIA = {
    'fraction': 'A fraction, spoken as numerator then denominator, e.g. one half, three quarters',
    'date': 'A calendar date, spoken in British style, e.g. the second of January',
    'ratio': 'A ratio or score, spoken with "to", e.g. three to two',
    'leave': 'None of these; leave the characters for the engine to read',
}


def _find_slash(text: str) -> Iterable[Candidate]:
    for match in _SLASH_RE.finditer(text):
        first, second = int(match.group(1)), int(match.group(2))
        if second == 0:
            continue

        def render(choice, first=first, second=second):
            if choice == 'fraction':
                return _fraction_to_words(first, second)
            if choice == 'date':
                return _date_uk(first, second)
            if choice == 'ratio':
                return f"{_number_to_words(first)} to {_number_to_words(second)}"
            return None

        yield _make('slash', match, text, _SLASH_CRITERIA, render)


_CURRENCY_RE = re.compile(
    r'([£$€])(\d[\d,]*\.?\d*)(?:[ \t]*(hundred|thousand|million|billion|trillion))?',
    re.IGNORECASE)
_CURRENCY_CRITERIA = {
    'money': 'An amount of money, spoken as pounds and pence (or dollars and cents)',
    'literal': 'A bare decimal number followed by the currency unit, e.g. four point five pounds',
    'leave': 'Leave the characters for the engine to read',
}
_CURRENCY_SCALE_CRITERIA = {
    'money': 'An amount of money, spoken as the number, the scale word and the currency '
             'unit, e.g. thirty-six billion dollars',
    'literal': 'The number read as a bare decimal, followed by the scale word and the '
               'currency unit',
    'leave': 'Leave the characters for the engine to read',
}


def _find_currency(text: str) -> Iterable[Candidate]:
    for match in _CURRENCY_RE.finditer(text):
        symbol, amount = match.group(1), match.group(2)
        scale = (match.group(3) or '').lower() or None
        criteria = _CURRENCY_SCALE_CRITERIA if scale else _CURRENCY_CRITERIA

        def render(choice, symbol=symbol, amount=amount, scale=scale):
            if scale:
                if choice in ('money', 'literal'):
                    return _scaled_currency(symbol, amount, scale)
                return None
            if choice == 'money':
                return _money_words(symbol, amount)
            if choice == 'literal':
                return _literal_currency(symbol, amount)
            return None

        yield _make('currency', match, text, criteria, render)


# Only the genuinely ambiguous abbreviations get a question. The rest are
# deterministic and stay in tts_preprocess.
_ABBREV_SPECS = (
    (re.compile(r'\bDr(?![A-Za-z])\.?'),
     {'doctor': 'The title Doctor', 'drive': 'The road, Drive', 'leave': 'Leave the characters'},
     {'doctor': 'Doctor', 'drive': 'Drive'}),
    (re.compile(r'\bSt(?![A-Za-z])\.?'),
     {'saint': 'The title Saint', 'street': 'The road, Street', 'leave': 'Leave the characters'},
     {'saint': 'Saint', 'street': 'Street'}),
    (re.compile(r'\bNo(?![A-Za-z])\.?(?=\s*\d)'),
     {'number': 'The abbreviation for Number, as in No. 4', 'no': 'The word "no"',
      'leave': 'Leave the characters'},
     {'number': 'Number', 'no': 'No'}),
)


def _find_abbrev(text: str) -> Iterable[Candidate]:
    for pattern, criteria, words in _ABBREV_SPECS:
        for match in pattern.finditer(text):
            def render(choice, words=words):
                return words.get(choice)
            yield _make('abbrev', match, text, criteria, render)


_ROMAN_RE = re.compile(r'(?<![A-Za-z0-9])([IVXLCDM]{2,7})(?![A-Za-z0-9])')
_ROMAN_CRITERIA = {
    'numeral': 'A roman numeral, spoken as its value, e.g. IV is four',
    'letters': 'Individual letters, spelled out, e.g. I V',
    'leave': 'Leave the characters for the engine to read',
}


def _find_roman(text: str) -> Iterable[Candidate]:
    for match in _ROMAN_RE.finditer(text):
        span = match.group(1)
        value = _is_canonical_roman(span)
        if value is None:
            continue

        def render(choice, span=span, value=value):
            if choice == 'numeral':
                return _number_to_words(value)
            if choice == 'letters':
                return ' '.join(span)
            return None

        yield _make('roman', match, text, _ROMAN_CRITERIA, render)


# Attached only ("3.5mm", "5kg"): a spaced "5 in the morning" must never be
# mistaken for inches.
_UNIT_RE = re.compile(
    r'(?<![\w.])(\d+(?:\.\d+)?)(kWh|kHz|MHz|GHz|mph|kph|kg|mg|ml|mm|cm|km|'
    r'GB|MB|KB|TB|Hz|kW|ft|lb|oz|in|g|l|m|s|h)(?![A-Za-z0-9])')
_UNIT_CRITERIA = {
    'measurement': 'A measurement, spoken as the number then the unit name, e.g. five kilograms',
    'letters': 'The unit read out as letters, e.g. K G',
    'leave': 'Leave the characters for the engine to read',
}


def _is_decade_shorthand(number: str, unit: str) -> bool:
    """True for a decade written as a year/2-digit shorthand plus ``s``.

    "1980s" and "the '70s" both end in the seconds unit letter, but a decade is
    a deterministic class the normalizer owns and must never be sent to Jev as a
    measurement ("one thousand nine hundred and eighty seconds"). A short
    duration like "5s" is still a genuine measurement.
    """
    if unit != 's' or not number.isdigit():
        return False
    value = int(number)
    if len(number) == 4:
        return 1000 <= value <= 2099
    return len(number) == 2 and 20 <= value <= 99


def _find_unit(text: str) -> Iterable[Candidate]:
    for match in _UNIT_RE.finditer(text):
        number, unit = match.group(1), match.group(2)
        word = _UNIT_WORDS.get(unit)
        if not word:
            continue
        if _is_decade_shorthand(number, unit):
            continue

        def render(choice, number=number, unit=unit, word=word):
            if choice == 'measurement':
                return f"{_number_words(number)} {word}"
            if choice == 'letters':
                return ' '.join(unit)
            return None

        yield _make('unit', match, text, _UNIT_CRITERIA, render)


# The lookarounds also exclude a hyphen: a numeric range is a standalone token,
# so an ISBN-style hyphen group ("978-0-330-47579-2") must not yield "330-47579".
_RANGE_RE = re.compile(
    r'(?<![\w.\-])(\d+(?:\.\d+)?)[ \t]?[-–—][ \t]?(\d+(?:\.\d+)?)(?![\w.\-])')
_RANGE_CRITERIA = {
    'range': 'A range, spoken with "to", e.g. ten to twelve',
    'sequence': 'Two separate numbers read in sequence, e.g. ten twelve',
    'leave': 'Leave the characters for the engine to read',
}


def _range_part(value: str) -> str:
    """Render one end of a range, using year style for a 4-digit year.

    "1919–21" must read "nineteen nineteen to twenty-one", not the cardinal
    "one thousand nine hundred and nineteen to twenty-one" — the earlier code
    sent every part through ``_number_words`` and got abbreviated year ranges
    audibly wrong.
    """
    if len(value) == 4 and value.isdigit() and 1000 <= int(value) <= 2099:
        return _year_to_words(value)
    return _number_words(value)


def _find_range(text: str) -> Iterable[Candidate]:
    for match in _RANGE_RE.finditer(text):
        first_s, second_s = match.group(1), match.group(2)
        # Full four-digit year ranges are already handled deterministically;
        # skip them here. Abbreviated year ranges ("1919–21") fall through and
        # are rendered in year style by ``_range_part``.
        if first_s.isdigit() and second_s.isdigit():
            first, second = int(first_s), int(second_s)
            if 1000 <= first <= 2099 and 1000 <= second <= 2099:
                continue
        # Leading zeros mean a phone/part number, not a range.
        if first_s.startswith('0') or second_s.startswith('0'):
            continue

        def render(choice, first_s=first_s, second_s=second_s):
            if choice == 'range':
                return f"{_range_part(first_s)} to {_range_part(second_s)}"
            if choice == 'sequence':
                return f"{_range_part(first_s)} {_range_part(second_s)}"
            return None

        yield _make('range', match, text, _RANGE_CRITERIA, render)


_INITIALS_RE = re.compile(r'\b([A-Z])\.(?:[ \t]?([A-Z])\.)+')
_INITIALS_CRITERIA = {
    'letters': 'The letters of the initials, spelled out, e.g. J R R',
    'leave': 'Leave the characters for the engine to read',
}


def _find_initials(text: str) -> Iterable[Candidate]:
    for match in _INITIALS_RE.finditer(text):
        letters = re.findall(r'[A-Z]', match.group(0))

        def render(choice, letters=letters):
            if choice == 'letters':
                return ' '.join(letters)
            return None

        yield _make('initials', match, text, _INITIALS_CRITERIA, render)


_FINDERS = (_find_slash, _find_currency, _find_abbrev, _find_roman,
            _find_unit, _find_range, _find_initials)


def find_normalization_candidates(text: str) -> list:
    """All ambiguous spans in ``text``, non-overlapping, in reading order.

    Overlaps are resolved by earliest start (and longest at the same start);
    the first match wins, so a currency symbol is never also read as a range.
    """
    found = []
    for finder in _FINDERS:
        found.extend(finder(text))
    found.sort(key=lambda c: (c.start, -(c.end - c.start)))
    kept = []
    for candidate in found:
        if kept and candidate.start < kept[-1].end:
            continue
        kept.append(candidate)
    for index, candidate in enumerate(kept):
        candidate.cid = f'c{index}'
    return kept


def _state_for(candidates: list) -> str:
    seen, sentences = set(), []
    for candidate in candidates:
        if candidate.sentence not in seen:
            seen.add(candidate.sentence)
            sentences.append(candidate.sentence)
    return '\n'.join(sentences)[:_env_int('JEV_STATE_MAX_CHARS', 8000)]


def _normalization_questions(candidates: list) -> dict:
    questions = {}
    for candidate in candidates:
        questions[candidate.cid] = {
            'type': 'choice',
            'instructions': {
                'span': candidate.span,
                'sentence': candidate.sentence,
                'question': (f"How should the span `{candidate.span}` be read aloud "
                             "in this sentence? Choose the reading a narrator should use."),
            },
            'criteria': candidate.criteria,
        }
    return questions


def _apply_choices(text: str, candidates: list, answers: dict,
                   threshold: float) -> str:
    out = text
    for candidate in sorted(candidates, key=lambda c: c.start, reverse=True):
        answer = answers.get(candidate.cid)
        if not isinstance(answer, dict):
            continue
        choice = answer.get('choice')
        if choice not in candidate.criteria:
            continue
        try:
            confidence = float(answer.get('confidence') or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < threshold:
            continue
        rendered = candidate.render(choice)
        if not rendered or rendered == candidate.span:
            continue
        out = out[:candidate.start] + rendered + out[candidate.end:]
    return out


def normalize_text_for_tts_jev(text: str, lexicon: dict = None, modern: bool = False,
                               expand_numbers: Optional[bool] = None, *,
                               enabled: Optional[bool] = None,
                               client: Optional[JevClient] = None) -> str:
    """Drop-in replacement for ``normalize_text_for_tts`` with an optional Jev pass.

    When the feature is disabled (the default) this is exactly
    ``normalize_text_for_tts`` — byte-identical output. When enabled, ambiguous
    spans are resolved by Jev first, then the deterministic normalizer runs.
    """
    if not tts_normalization_enabled(enabled):
        return normalize_text_for_tts(text, lexicon=lexicon, modern=modern,
                                      expand_numbers=expand_numbers)

    candidates = find_normalization_candidates(text)
    cap = max(0, _env_int('JEV_MAX_CANDIDATES', 60))
    if candidates and cap:
        candidates = candidates[:cap]
        answers = _ask_batched(_normalization_questions(candidates),
                               _state_for(candidates), client=client)
        if answers:
            text = _apply_choices(text, candidates, answers, min_confidence())
    return normalize_text_for_tts(text, lexicon=lexicon, modern=modern,
                                  expand_numbers=expand_numbers)


# ---------------------------------------------------------------------------
# Feature 2 — chapter/section boundary ranking
# ---------------------------------------------------------------------------

BOUNDARY_CRITERIA = {
    'body': "A real chapter or part of the book's main content that a listener expects to hear",
    'front_matter': 'Front matter such as cover, title page, dedication, contents or copyright',
    'back_matter': 'Back matter such as acknowledgements, notes, bibliography, index or about the author',
}


def _boundary_ambiguous(chapter: dict, min_words: int) -> bool:
    """Only near-threshold or title-flagged sections are worth a Jev question."""
    if chapter.get('below_threshold'):
        return True
    if chapter.get('back_matter'):
        return True
    return chapter.get('words', 0) < min_words * 1.5


def rank_chapter_boundaries(chapters: list, min_words: int, *,
                            enabled: Optional[bool] = None,
                            client: Optional[JevClient] = None) -> dict:
    """Decide ``body`` / ``front_matter`` / ``back_matter`` for ambiguous sections.

    Returns ``{position_in_list: {'choice', 'confidence', 'probabilities'}}``.
    Returns ``{}`` when disabled, when nothing is ambiguous, or on any failure —
    the caller then keeps the existing heuristic result.
    """
    if not chapter_boundary_enabled(enabled):
        return {}
    candidates = [(index, chapter) for index, chapter in enumerate(chapters)
                  if _boundary_ambiguous(chapter, min_words)]
    cap = max(0, _env_int('JEV_MAX_CHAPTER_CANDIDATES', 40))
    candidates = candidates[:cap]
    if not candidates:
        return {}

    questions = {}
    for index, chapter in candidates:
        questions[f'b{index}'] = {
            'type': 'choice',
            'instructions': {
                'title': chapter.get('title') or '',
                'words': chapter.get('words'),
                'opening': (chapter.get('snippet') or '')[:300],
                'question': "Is this section part of the book's main body, or is it front or back matter?",
            },
            'criteria': BOUNDARY_CRITERIA,
        }
    state = '\n\n'.join(f"{chapter.get('title') or ''}: {(chapter.get('snippet') or '')[:200]}"
                        for _, chapter in candidates)
    answers = _ask_batched(questions, state, client=client)

    decisions = {}
    for index, _chapter in candidates:
        answer = answers.get(f'b{index}')
        if not isinstance(answer, dict) or answer.get('choice') not in BOUNDARY_CRITERIA:
            continue
        try:
            confidence = float(answer.get('confidence') or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        decisions[index] = {
            'choice': answer['choice'],
            'confidence': confidence,
            'probabilities': answer.get('probabilities') or {},
        }
    return decisions


def apply_boundary_decisions(chapters: list, decisions: dict, *,
                             min_conf: Optional[float] = None) -> list:
    """Keep/drop sections from Jev decisions and renumber the survivors.

    Sections with no confident decision keep today's behaviour: a below-threshold
    section stays dropped, everything else stays kept.
    """
    if min_conf is None:
        min_conf = min_confidence()
    kept = []
    for index, chapter in enumerate(chapters):
        decision = decisions.get(index)
        if decision and decision['confidence'] >= min_conf:
            if decision['choice'] in ('front_matter', 'back_matter'):
                continue
            if decision['choice'] == 'body' and chapter.get('back_matter'):
                chapter = {**chapter, 'back_matter': False}
        elif chapter.get('below_threshold'):
            continue
        kept.append(chapter)
    renumbered = []
    for position, chapter in enumerate(kept, 1):
        item = {key: value for key, value in chapter.items() if key != 'below_threshold'}
        item['index'] = position
        renumbered.append(item)
    return renumbered


def refine_boundaries(chapters: list, min_words: int, *,
                      enabled: Optional[bool] = None,
                      client: Optional[JevClient] = None) -> list:
    """Refine a chapter list with Jev. Identity when disabled (byte-identical)."""
    if not chapter_boundary_enabled(enabled):
        return chapters
    decisions = rank_chapter_boundaries(chapters, min_words, enabled=True, client=client)
    return apply_boundary_decisions(chapters, decisions)
