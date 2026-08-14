"""Text preprocessing for TTS conversion.

Two layers, both applied to a `_tts.epub` copy before the converter runs:

1. Structural sanitization (HTML level, via BeautifulSoup):
   - Endnote/footnote reference markers: <sup> digits, epub:type="noteref"
     anchors, pure-digit internal links. These survive text-level regexes
     because they sit in their own tags until the converter flattens them.
   - Note bodies: epub:type footnote/endnote/rearnote asides and sections.
   - Unicode junk: soft hyphens, zero-width chars, exotic spaces.

2. Text normalization (text-segment level):
   - Numbers with commas: 1,000,000 -> one million
   - Currency: $50 -> fifty dollars, £100 -> one hundred pounds
   - Ordinals: 1st, 2nd, 3rd -> first, second, third
   - Chapter/part headings: Chapter 1 -> Chapter One
   - Common abbreviations: Dr. -> Doctor, Mr. -> Mister, etc.
   - Percentages: 50% -> fifty percent
   - Decades: 1990s -> nineteen nineties
   - Leftover flattened endnote digits after sentence punctuation
     (safe patterns that never touch decimals like $2.58)

Because this runs here, the upstream converter's --remove_endnotes flag must
NOT be used: its regex strips digits after any letter/period, which corrupts
decimals ("$2.58" -> "$2.") and alphanumerics ("B12" -> "B"), while missing
markers after curly quotes ('consultant."35').

--------------------------------------------------------------------------
MODERN-ENGINE CONTRACT (chatterbox / tada), passed as `modern=True`
--------------------------------------------------------------------------
Modern neural voice-clone engines have their own text frontends (TADA is
Llama-based) that read plain numbers, years, decades, and dates CORRECTLY.
Spelling them out is a hack for dumb engines (Kokoro/Piper) that actively
HURTS the good ones: "1976" -> "nineteen seventy-six" makes the model pause
before the final digit, so "six" sounds like a detached endnote number
("1976" heard as "1970...6"). Three separate incidents came from this class
of over-normalization (dash->comma, comma-number spelling, year spelling).

The rule (revised 2026-07-09 to MINIMAL-for-modern after three separate
"helper hurts the modern engine" bugs — year-spelling, dash->comma, and
phonetic respellings like "Coo-per-TEE-no" heard as broken syllables):
  * modern=True  -> get ONLY: structural cleanup (endnotes, unicode), acronym
                    letter-spacing (U.S. -> U S, so it says the letters), and
                    dash/ellipsis spacing.
  * modern=True  -> SKIP everything else: number/year/decade/large-int
                    spelling, currency/%/ordinal/heading expansion, word-abbrev
                    expansion (Dr./St./No./p.), and the phonetic-respelling
                    lexicon. Modern LLM-based engines read real text natively;
                    every one of these blanket transforms has either been
                    redundant or actively wrong on them.
Genuine per-book misreads on a modern engine are caught by the QA loop
(ASR verification -> targeted natural spellings), NOT by adding another regex
here. Each skipped transform below sits under `if not modern:`.
"""
import re
import zipfile
import shutil
import tempfile
import logging
from pathlib import Path

try:
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    # EPUB xhtml parsed with the tolerant HTML parser on purpose
    warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logging.warning("beautifulsoup4 not installed. Structural EPUB sanitization disabled.")

# num2words is optional — gracefully degrade if not installed
try:
    from num2words import num2words
    HAS_NUM2WORDS = True
except ImportError:
    HAS_NUM2WORDS = False

# NLTK for sentence tokenization
try:
    import nltk
    # Ensure the punkt tokenizer is available
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False
    logging.warning("nltk not installed. Sentence tokenization will degrade to basic regex.")


def _number_to_words(n: int, lang: str = 'en') -> str:
    """Convert integer to words, with fallback if num2words unavailable.

    STRIP THE COMMAS num2words inserts. It returns "three thousand, four hundred"
    — and every TTS engine reads that comma as a PAUSE, so a plain number comes
    out broken-up and stilted ("three thousand… four hundred"). Dave heard exactly
    this and called it "stilted and weird" (2026-07-14). The words alone are
    unambiguous and read as one natural phrase. Affects every large number in
    every book, so it is worth being blunt about.
    """
    if HAS_NUM2WORDS:
        return num2words(n, lang=lang).replace(',', '')
    return str(n)


def _ordinal_to_words(n: int, lang: str = 'en') -> str:
    """Convert ordinal number to words."""
    if HAS_NUM2WORDS:
        return num2words(n, to='ordinal', lang=lang).replace(',', '')
    # Fallback for common ordinals
    suffixes = {1: 'first', 2: 'second', 3: 'third'}
    if n in suffixes:
        return suffixes[n]
    return f"{n}th"


def _pluralise_number_word(w: str) -> str:
    """'eighty' -> 'eighties', 'hundred' -> 'hundreds'.

    Naive `+ 's'` gave "nineteen eightys" for `1980s` on every book that
    mentioned a decade. English pluralises a terminal -y to -ies.
    """
    return w[:-1] + 'ies' if w.endswith('y') else w + 's'


def _decade_to_words(year_str: str) -> str:
    """`1980` (from '1980s'/"1980's") -> 'nineteen eighties'."""
    year = int(year_str)
    if not (1000 <= year <= 2099):
        return _pluralise_number_word(_number_to_words(year)) if HAS_NUM2WORDS else year_str + 's'
    prefix, suffix = int(year_str[:2]), int(year_str[2:])
    if suffix == 0:
        return f"{_number_to_words(prefix)} hundreds"
    return f"{_number_to_words(prefix)} {_pluralise_number_word(_number_to_words(suffix))}"


def _decimal_to_words(num_str: str) -> str:
    """'12.5' -> 'twelve point five'. Digits after the point are read one by
    one, which is how a decimal is actually spoken."""
    if not HAS_NUM2WORDS:
        return num_str
    whole, _, frac = num_str.partition('.')
    words = _number_to_words(int(whole or 0))
    if frac:
        digits = ' '.join(_number_to_words(int(d)) for d in frac)
        words = f"{words} point {digits}"
    return words


def _year_to_words(year_str: str) -> str:
    """Convert a 4-digit year to its spoken word equivalent (e.g., 1962 -> nineteen sixty-two)."""
    try:
        year = int(year_str)
        if 1000 <= year <= 2099:
            # 2000-2009 read as "two thousand [n]" (natural for audiobooks);
            # "twenty hundred" / "twenty oh one" are wrong/awkward.
            if 2000 <= year <= 2009:
                if year == 2000:
                    return "two thousand"
                return f"two thousand {_number_to_words(year % 100)}"
            if year % 100 == 0:
                return f"{_number_to_words(year // 100)} hundred"
            else:
                prefix = year // 100
                suffix = year % 100
                prefix_words = _number_to_words(prefix)
                if suffix < 10:
                    return f"{prefix_words} oh {_number_to_words(suffix)}"
                else:
                    return f"{prefix_words} {_number_to_words(suffix)}"
    except Exception:
        pass
    return year_str


# epub:type / role values that mark note reference links and note bodies
_NOTEREF_TYPES = {'noteref'}
_NOTEREF_ROLES = {'doc-noteref'}
_NOTE_BODY_TYPES = {'footnote', 'footnotes', 'endnote', 'endnotes',
                    'rearnote', 'rearnotes'}
_NOTE_BODY_ROLES = {'doc-footnote', 'doc-endnote', 'doc-endnotes'}

_PURE_DIGIT_RE = re.compile(r'^\[?\d{1,4}\]?$')


def _attr_tokens(tag, name):
    """Return an attribute's value as a set of whitespace-split tokens."""
    # A tag decomposed earlier in the same pass (e.g. child of a removed
    # aside) has attrs=None; treat it as attribute-less.
    if not getattr(tag, 'attrs', None):
        return set()
    val = tag.attrs.get(name)
    if not val:
        return set()
    if isinstance(val, (list, tuple)):
        return set(val)
    return set(str(val).split())


def sanitize_html(html: str) -> str:
    """Structurally remove footnote/endnote apparatus from one HTML document.

    Works on the markup rather than extracted text, so it is immune to
    quote styles and publisher formatting quirks. Conservative by design:
    only removes elements that are unambiguously note markers or bodies.
    """
    soup = BeautifulSoup(html, 'lxml')

    # 1. Note bodies: <aside epub:type="footnote">, role="doc-endnote", etc.
    for tag in soup.find_all(True):
        if (_attr_tokens(tag, 'epub:type') & _NOTE_BODY_TYPES
                or _attr_tokens(tag, 'role') & _NOTE_BODY_ROLES):
            tag.decompose()

    # 2. Note reference anchors: epub:type="noteref" / role="doc-noteref"
    for a in soup.find_all('a'):
        if (_attr_tokens(a, 'epub:type') & _NOTEREF_TYPES
                or _attr_tokens(a, 'role') & _NOTEREF_ROLES):
            a.decompose()

    # 3. Superscripts whose visible text is just a (bracketed) number
    for sup in soup.find_all('sup'):
        if getattr(sup, 'decomposed', False):
            continue
        if _PURE_DIGIT_RE.match(sup.get_text(strip=True) or ''):
            sup.decompose()

    # 4. Internal links whose visible text is just a (bracketed) number
    #    (endnote markers in EPUBs without semantic markup or <sup> tags)
    for a in soup.find_all('a', href=True):
        if getattr(a, 'decomposed', False):
            continue
        if _PURE_DIGIT_RE.match(a.get_text(strip=True) or ''):
            a.decompose()

    return str(soup)


# Unicode characters that confuse TTS engines
_UNICODE_SPACES_RE = re.compile("[   -   　]")
_UNICODE_INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
_UNICODE_LINE_SEP_RE = re.compile("[  ]")

# Flattened endnote digits after sentence punctuation. Fixed-width
# lookbehinds ensure decimals are never touched: a digit before the
# period ("$2.58") fails the [a-zA-Z] / quote requirement.
_ENDNOTE_AFTER_WORD_RE = re.compile(r'(?<=[a-zA-Z][.!?])\d{1,4}(?=\s|$)')
_ENDNOTE_AFTER_QUOTE_RE = re.compile(r'(?<=[.!?][”’"\'])\d{1,4}(?=\s|$)')
_ENDNOTE_BRACKETED_RE = re.compile(r'\[\d{1,4}\]')


def normalize_unicode_for_tts(text: str) -> str:
    """Replace/remove unicode whitespace and invisible chars that trip TTS."""
    text = _UNICODE_SPACES_RE.sub(' ', text)
    text = _UNICODE_INVISIBLE_RE.sub('', text)
    text = _UNICODE_LINE_SEP_RE.sub(' ', text)
    return text


# Roman numerals are all-caps but are neither emphasis nor acronyms. Leaving
# them alone keeps "Chapter VIII" working; sentence-casing would give "Viii".
_ROMAN = re.compile(r'^[IVXLCDM]+$')

# All-caps tokens that really are read as words, not spelled out. Kept short
# and deliberate — this is a floor, not an attempt at completeness.
_CAPS_WORD_ACRONYMS = {'NASA', 'ASCII', 'NATO', 'LASER', 'RADAR', 'SCUBA', 'UNICEF'}


def _keep_as_is(core: str) -> bool:
    """True if this all-caps token should survive a run untouched.

    Three ways to earn that: a known word-acronym (NASA), a roman numeral
    (VIII), or no vowels at all (JPL, BBC, NHS). The vowel test is the useful
    one — an unpronounceable token is an initialism and *should* be spelled
    out, whereas anything with vowels is a word being shouted.
    """
    if not core:
        return False
    if core in _CAPS_WORD_ACRONYMS or _ROMAN.match(core):
        return True
    return len(core) <= 5 and not set(core) & set('AEIOU')


def _sentence_case_run(run: str) -> str:
    """'ORANGE MARMALADE' -> 'Orange marmalade', per word.

    Acronyms embedded in a run are preserved individually, so 'NASA JPL' does
    not become 'Nasa jpl'. A genuinely unknown vowel-bearing acronym inside a
    run will still be downcased — that ambiguity needs world knowledge and is
    the job of the LLM classifier in #34, not of a regex.
    """
    words = run.split()
    out, first_done = [], False
    for w in words:
        core = re.sub(r'[^A-Z]', '', w)
        if _keep_as_is(core):
            out.append(w)
        elif not first_done:
            out.append(w.capitalize())
            first_done = True
        else:
            out.append(w.lower())
    return ' '.join(out)


def _normalize_caps_runs(text: str) -> str:
    """Downcase runs of 2+ all-caps words; leave lone acronyms untouched.

    Why a *run* is the right unit: an acronym is a single token embedded in
    normal-case prose ("the CEO said"), whereas emphasis and signage come in
    stretches ("ORANGE MARMALADE", "DRINK ME", "THE FULL PROJECT GUTENBERG
    LICENSE"). Requiring two consecutive tokens means CEO, BBC and FBI cannot
    be hit by this rule at all, which is what makes it safe to apply to every
    engine.

    Single all-caps tokens are deliberately NOT touched here: distinguishing
    "WHO" the organisation from "WHO" the shouted question needs world
    knowledge, and that belongs in the LLM classifier (#34), not a regex.
    """
    def repl(m):
        run = m.group(0)
        # If every token independently earns preservation (all acronyms, all
        # roman numerals, or a mix), leave the run exactly as written.
        if all(_keep_as_is(re.sub(r'[^A-Z]', '', w)) for w in run.split()):
            return run
        return _sentence_case_run(run)

    # Two or more consecutive words of 2+ capitals, allowing internal
    # apostrophes and hyphens (DON'T, WELL-KNOWN).
    return re.sub(r"\b[A-Z][A-Z'’\-]{1,}(?:\s+[A-Z][A-Z'’\-]{1,})+\b", repl, text)


def _is_letter_spacing(word: str, repl: str) -> bool:
    """True if `repl` is just `word`'s letters spaced out (an acronym reading:
    "CEO" -> "C E O", "U.S." -> "U S"). The only lexicon class safe for modern
    engines — plain words, no phonetic respelling."""
    w = re.sub(r'[^A-Za-z]', '', word).upper()
    r = re.sub(r'[^A-Za-z]', '', repl).upper()
    return bool(w) and w == r and ' ' in repl.strip()


def normalize_text_for_tts(text: str, lexicon: dict = None, modern: bool = False) -> str:
    """Apply all TTS normalization rules to a text string."""

    # === Unicode cleanup (before anything else looks at the text) ===
    text = normalize_unicode_for_tts(text)

    # === Leftover endnote markers already flattened into the text ===
    text = _ENDNOTE_AFTER_WORD_RE.sub('', text)
    text = _ENDNOTE_AFTER_QUOTE_RE.sub('', text)
    text = _ENDNOTE_BRACKETED_RE.sub('', text)

    # === Apply Custom Lexicon Replacements (phonetic respellings) ===
    # SKIP for modern voice-clone engines. They read real words (Beijing,
    # Cupertino, iPhones) correctly on their own; feeding them a human
    # pronunciation guide like "Coo-per-TEE-no" / "Bay-JING" makes them read the
    # hyphens as pauses and the syllables literally — "coo per tee no",
    # "bay...zhing" (Dave, 2026-07-09). Same class as the year-spelling and
    # dash-comma hacks: helpers for dumb engines HURT modern models. Genuine
    # misreads on a modern engine are handled by the QA loop (targeted, natural
    # spellings), NOT by blanket respelling here. MODERN-ENGINE CONTRACT.
    # EXCEPTION for modern: acronym LETTER-SPACING rules ("CEO" -> "C E O") are
    # allowed — the replacement is plain words, not a respelling, and modern
    # engines DO misread undotted initialisms ("CEO" heard as "see you",
    # Dave 2026-07-10). This is the one lexicon class that helps every engine.
    if lexicon:
        active = lexicon if not modern else {
            k: v for k, v in lexicon.items() if _is_letter_spacing(k, v)}
        # Sort keys by length descending so longer phrases are matched first
        for word in sorted(active.keys(), key=len, reverse=True):
            phonetic = active[word]
            # Word boundaries avoid replacing parts of other words; keep
            # case-SENSITIVE for letter-spacing rules on modern (must not turn
            # the word "ceo…"-like lowercase text into letters).
            flags = 0 if modern else re.IGNORECASE
            pattern = r'\b' + re.escape(word) + r'\b'
            text = re.sub(pattern, phonetic, text, flags=flags)

    # === All-caps emphasis -> normal case (helps EVERY engine) ===
    # Modern TTS treats an all-caps token as an initialism. Books use capitals
    # for labels, signage and emphasis, so "ORANGE MARMALADE" was rendered as
    # something between a spelling-out and a mangling (#34, heard by ear in
    # Alice in Wonderland).
    #
    # The signal that separates the two cases: ACRONYMS APPEAR AS SINGLE TOKENS
    # in normal-case surroundings, EMPHASIS APPEARS AS RUNS. So a run of two or
    # more capitalised words is emphasis and gets sentence case, while a lone
    # CEO / NASA / BBC is left completely alone.
    text = _normalize_caps_runs(text)

    # === Abbreviations (must come before period-related rules) ===
    # Acronyms read letter-by-letter — helps EVERY engine (else "U.S." -> "us").
    acronym_abbrev = {
        r'\bU\.S\.A\.': 'U S A',
        r'\bU\.S\.': 'U S',
        r'\bU\.K\.': 'U K',
        r'\bU\.N\.': 'U N',
        r'\bE\.U\.': 'E U',
        r'\bD\.C\.': 'D C',
        r'\bB\.C\.': 'B C',
        r'\bA\.D\.': 'A D',
    }
    for pattern, replacement in acronym_abbrev.items():
        text = re.sub(pattern, replacement, text)

    # Word-expansion abbreviations: SKIP for modern engines. They read "Dr.",
    # "e.g." natively, and blind expansion MISFIRES on real prose ("Main St."
    # -> "Main Saint", "No." -> "Number", "p." -> "page"). MODERN-ENGINE
    # CONTRACT: minimal normalization for modern; genuine misreads go to the QA
    # loop, not a blanket dictionary (proactive audit 2026-07-09).
    if not modern:
        word_abbrev = {
            r'\bDr\.': 'Doctor', r'\bMr\.': 'Mister', r'\bMrs\.': 'Missus',
            r'\bMs\.': 'Ms', r'\bProf\.': 'Professor', r'\bSt\.': 'Saint',
            r'\bGen\.': 'General', r'\bSgt\.': 'Sergeant', r'\bCpl\.': 'Corporal',
            r'\bLt\.': 'Lieutenant', r'\bCol\.': 'Colonel', r'\bCapt\.': 'Captain',
            r'\bGov\.': 'Governor', r'\bSen\.': 'Senator', r'\bRep\.': 'Representative',
            r'\bvs\.': 'versus', r'\bVs\.': 'Versus', r'\bet al\.': 'et alia',
            r'\betc\.': 'etcetera', r'\bi\.e\.': 'that is', r'\be\.g\.': 'for example',
            r'\bNo\.': 'Number', r'\bno\.': 'number', r'\bVol\.': 'Volume',
            r'\bvol\.': 'volume', r'\bFig\.': 'Figure', r'\bfig\.': 'figure',
            r'\bpp\.': 'pages', r'\bp\.': 'page',
        }
        for pattern, replacement in word_abbrev.items():
            text = re.sub(pattern, replacement, text)

    # === Years: 1962 -> nineteen sixty-two ===
    # Must come before general number handling.
    #
    # Years ARE spelled for EVERY engine, including modern ones — reversed
    # 2026-07-14 after an A/B, judged by ear (#26).
    #
    # History worth keeping: this was previously skipped for modern engines
    # because spelling "1976" made them PAUSE before the final digit ("1976"
    # heard as "1970...6", incident 2026-07-08). That diagnosis was WRONG. The
    # pause came from the COMMA num2words inserts into spelled numbers
    # ("three thousand, four hundred") — engines read a comma as a pause. Once the
    # comma was stripped, Dave A/B'd raw "1997" vs "nineteen ninety-seven" on
    # chatterbox and judged the SPELLED form better. So the original defect was
    # the comma, not the spelling, and the ban was collateral damage.
    #
    # Modern engines still keep raw currency/percent/large ints (untested by ear —
    # do NOT extend this without an A/B; see #26).
    # === Decades: 1990s, 1800s, and the apostrophe form 1980's ===
    # MUST run before the year rule below, not after. "1980's" puts a non-word
    # character after the digits, so the year regex matched it and produced
    # "nineteen eighty's" — a possessive, which is not what the text said. And
    # the naive plural gave "nineteen eightys" for "1980s" on every book that
    # mentioned a decade.
    #
    # The APOSTROPHE form is fixed for every engine, because it is not decade
    # spelling — it is repairing damage the YEAR rule does, and modern engines
    # run the year rule. Left alone, modern output says "nineteen eighty's".
    #
    # The BARE form stays legacy-only. Spelling "1990s" for modern would be a
    # plain-number transform, which the MODERN-ENGINE CONTRACT forbids without
    # an ear test — and a regression guard enforces exactly that. I changed it
    # on inference and the guard caught me; it was right and I was wrong.
    text = re.sub(r"\b(\d{4})'s\b", lambda m: _decade_to_words(m.group(1)), text)
    if not modern:
        text = re.sub(r'\b(\d{4})s\b', lambda m: _decade_to_words(m.group(1)), text)

    # === "50k" -> "fifty thousand" (Dave, 2026-07-27) ===
    # Unhandled on every engine, so it was read as "fifty kay".
    #
    # Guarded against the two things that look identical and are not numbers:
    # screen resolutions (4K, 8K) and distances (10km). Requiring the value to
    # be >= 10 excludes the resolutions without needing to enumerate them, and
    # the negative lookahead for "m" keeps kilometres intact.
    def _k_suffix(m):
        num = m.group(1)
        try:
            val = float(num)
        except ValueError:
            return m.group(0)
        if val < 10:
            return m.group(0)
        return f"{_decimal_to_words(num)} thousand"

    text = re.sub(r'(?<![\w.])(\d+(?:\.\d+)?)[kK]\b(?!m)', _k_suffix, text)

    # A year RANGE is read "to", not as two years jammed together. This has to
    # happen while they are still digits, before the line below turns them into
    # words. Found while adding the hyphenated-compound rule: "1914-1918" was
    # becoming "nineteen fourteen-nineteen eighteen", i.e. a hyphen the engine
    # pauses at and no "to" anywhere — so the range read as two bare years.
    # Deliberately narrow: four-digit year to four-digit year only, so phone
    # numbers, scores and part numbers are untouched.
    text = re.sub(r'\b(1[0-9]{3}|20[0-9]{2})\s*[-–—]\s*(1[0-9]{3}|20[0-9]{2})\b',
                  r'\1 to \2', text)

    text = re.sub(r'\b(1[0-9]{3}|20[0-9]{2})\b', lambda m: _year_to_words(m.group(0)), text)

    # === Currency (before general number handling) ===
    def replace_currency(m):
        symbol = m.group(1)
        amount_str = m.group(2).replace(',', '')
        scale = (m.group(3) or '').strip()
        try:
            whole_text, dot, fraction_text = amount_str.partition('.')
            whole = int(whole_text)
        except ValueError:
            return m.group(0)

        units = {
            '$': ('dollar', 'dollars', 'cent', 'cents'),
            '£': ('pound', 'pounds', 'penny', 'pence'),
            '€': ('euro', 'euros', 'cent', 'cents'),
        }
        major_one, major_many, minor_one, minor_many = units[symbol]

        # "$33 billion" must become "thirty-three billion dollars",
        # not "thirty-three dollars billion"
        if scale:
            words = _decimal_to_words(amount_str) if dot else _number_to_words(whole)
            return f"{words} {scale} {major_many}"

        # Ordinary two-decimal prices are spoken as major + minor currency,
        # not as a bare decimal followed by a unit: "$33.50" becomes
        # "thirty-three dollars and fifty cents". A one-digit fraction is a
        # conventional price shorthand ("$33.5" == "$33.50"). Longer
        # fractions are measurements rather than normal prices and retain
        # explicit point-by-point speech.
        if dot and 1 <= len(fraction_text) <= 2:
            minor = int(fraction_text.ljust(2, '0'))
            parts = []
            if whole or not minor:
                major_unit = major_one if whole == 1 else major_many
                parts.append(f"{_number_to_words(whole)} {major_unit}")
            if minor:
                minor_unit = minor_one if minor == 1 else minor_many
                parts.append(f"{_number_to_words(minor)} {minor_unit}")
            return ' and '.join(parts)

        words = _decimal_to_words(amount_str) if dot else _number_to_words(whole)
        major_unit = major_one if not dot and whole == 1 else major_many
        return f"{words} {major_unit}"

    # Modern engines read "$50" / "£33 billion" natively; skip (MODERN CONTRACT).
    if not modern:
        text = re.sub(r'([$£€])(\d[\d,]*\.?\d*)(\s+(?:thousand|million|billion|trillion)\b)?',
                      replace_currency, text)

    # === Percentages ===
    def replace_percent(m):
        num_str = m.group(1).replace(',', '')
        try:
            n = float(num_str)
            if n == int(n):
                return f"{_number_to_words(int(n))} percent"
            # Decimals were left as digits ("12.5 percent"), so the engine got a
            # bare numeral in the middle of otherwise-spelled text.
            return f"{_decimal_to_words(num_str)} percent"
        except ValueError:
            return m.group(0)

    if not modern:  # modern reads "50%" natively (MODERN CONTRACT)
        text = re.sub(r'(\d[\d,]*\.?\d*)%', replace_percent, text)

    # === Ordinals: 1st, 2nd, 3rd, 4th, 21st, etc. ===
    def replace_ordinal(m):
        n = int(m.group(1))
        if n > 1000000:
            return m.group(0)  # Don't convert huge ordinals
        return _ordinal_to_words(n)

    if not modern:  # modern reads "1st"/"21st" natively (MODERN CONTRACT)
        text = re.sub(r'\b(\d+)(?:st|nd|rd|th)\b', replace_ordinal, text)


    # === Chapter/Part/Volume headings ===
    def replace_heading_number(m):
        label = m.group(1)
        n = int(m.group(2))
        if n > 200:
            return m.group(0)
        return f"{label} {_number_to_words(n).title()}"

    if not modern:  # modern reads "Chapter 3" natively (MODERN CONTRACT)
        text = re.sub(
            r'\b(Chapter|CHAPTER|Part|PART|Book|BOOK|Volume|VOLUME|Section|SECTION|Act|ACT|Scene|SCENE)\s+(\d+)\b',
            replace_heading_number, text)

    # === Large numbers with commas: 1,000,000 -> one million ===
    # Must come after currency/percent handling
    def replace_comma_number(m):
        num_str = m.group(0).replace(',', '')
        try:
            n = int(num_str)
            if n > 999999999999:  # Don't convert absurdly large numbers
                return m.group(0)
            return _number_to_words(n)
        except ValueError:
            return m.group(0)

    # Numbers with comma separators (at least one comma).
    # Modern engines read "2,905" natively; spelling it "two thousand, nine
    # hundred and five" adds comma-pauses that sound wrong. Skip for modern.
    if not modern:
        text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', replace_comma_number, text)

    # === Standalone large numbers without commas (4+ digits) ===
    def replace_large_number(m):
        try:
            n = int(m.group(0))
            # Don't convert years (1000-2099) here as they are handled above
            if 1000 <= n <= 2099:
                return m.group(0)
            if n > 999999999999:
                return m.group(0)
            return _number_to_words(n)
        except ValueError:
            return m.group(0)

    if not modern:
        text = re.sub(r'\b\d{4,}\b', replace_large_number, text)

    # === Ellipsis normalization ===
    # Multiple dots that aren't proper ellipsis
    text = re.sub(r'\.{4,}', '...', text)


    # === Pacing and Punctuation (Enhance Flow) ===
    # Keep em/en dashes AS dashes. Modern voice-clone models (TADA, Chatterbox)
    # render "—" as a natural clause break; the old "convert every dash to a
    # comma" hack (for dumb engines) produced constant unnatural pauses on
    # dash-heavy prose like Apple in China (incident 2026-07-08). Normalize the
    # spacing only.
    text = re.sub(r'\s*[—–]\s*', ' — ', text)
    text = re.sub(r'\s*--\s*', ' — ', text)

    # === Hyphenated compounds: join the word, don't pause inside it ===
    # Dave, on a TADA render of the rabbit-hole paragraph (2026-07-27):
    # *"'daisychain' was 'daisy.....chain'"*. The engine reads an intra-word
    # hyphen as a clause break, so a single compound word comes out as two words
    # with a gap between them.
    #
    # NOT a measurement, and an earlier commit message wrongly implied one. The
    # hyphen-free Nano render came out ~15 KB smaller at a constant bitrate,
    # which looked like a second of removed dead air — but the TADA pair went
    # the other way, and both engines are autoregressive and non-deterministic,
    # so two generations of two different strings cannot be compared by size.
    # The evidence here is Dave's ear plus the finding below. Nothing more.
    #
    # This is the SAME failure this file already documents one screen above —
    # "feeding them a human pronunciation guide like Coo-per-TEE-no makes them
    # read the hyphens as pauses". That finding was only ever acted on for
    # lexicon respellings; the identical hyphen arriving in the SOURCE TEXT was
    # never guarded, and ordinary English prose is full of them (daisy-chain,
    # half-hearted, ill-tempered — Alice alone has dozens).
    #
    # Modern engines only, and deliberately so: the non-modern lexicon path
    # *uses* hyphens as syllable separators ("Coo-per-TEE-no"), and this rule
    # runs after that substitution, so applying it universally would flatten
    # every respelling the dumb-engine path depends on. MODERN-ENGINE CONTRACT.
    #
    # Letter-to-letter only. A digit hyphen ("1914-1918", "COVID-19") is a range
    # or an identifier, not a compound, and "1914 1918" would lose the "to" that
    # makes it mean anything.
    if modern:
        text = re.sub(r'(?<=[A-Za-z])-(?=[A-Za-z])', ' ', text)

    # === Thousands separators, for modern engines ===
    # Modern engines keep raw numbers by contract, but a THOUSANDS COMMA is not
    # a number — it is a comma, and this file already establishes that engines
    # read a comma as a pause. That is the exact defect behind the 2026-07-08
    # "stilted and weird" incident; it was fixed for the comma num2words emits
    # and never for the comma the source text already contained, so "3,400"
    # still reads as "three thousand… four hundred" on the engines that render
    # every book.
    #
    # Removing the separator is the minimal fix: "3400" is read correctly and
    # keeps the MODERN-ENGINE CONTRACT (no spelling-out, which remains unjudged
    # by ear). Requires a digit on both sides, so dates and lists are untouched.
    if modern:
        for _ in range(3):          # 1,250,000 needs more than one pass
            text = re.sub(r'(?<=\d),(?=\d{3}\b)', '', text)

    # Standardize ellipses (real pause) without forcing spaces mid-word.
    text = re.sub(r'\.{2,}', '… ', text)

    return text



def preprocess_epub(epub_path: str | Path, output_path: str | Path | None = None, lexicon: dict = None, modern: bool = False) -> tuple[Path, int]:
    """Preprocess an EPUB file: normalize text for better TTS pronunciation.

    Modifies HTML content inside the EPUB. If output_path is None,
    creates a preprocessed copy alongside the original with _tts suffix.

    Returns (path to the preprocessed EPUB, number of HTML files changed).
    """
    epub_path = Path(epub_path)
    if output_path is None:
        output_path = epub_path.parent / f"{epub_path.stem}_tts{epub_path.suffix}"
    output_path = Path(output_path)

    # Work on a temp copy to avoid corrupting the original
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    shutil.copy2(epub_path, tmp_path)

    html_extensions = {'.xhtml', '.html', '.htm', '.xml'}
    changes_made = 0

    try:
        with zipfile.ZipFile(tmp_path, 'r') as zin:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    suffix = Path(item.filename).suffix.lower()

                    if suffix in html_extensions:
                        try:
                            text = data.decode('utf-8')

                            # Layer 1: structural sanitization (footnote/endnote
                            # markers and bodies) — must run before text-level
                            # rules because markers live in their own tags.
                            if HAS_BS4:
                                try:
                                    text = sanitize_html(text)
                                except Exception as e:
                                    logging.warning(
                                        f"sanitize_html failed for {item.filename}: {e}")

                            # Layer 2: normalize text content, not HTML tags/attributes
                            # Simple approach: normalize text between > and <
                            def normalize_segment(m):
                                return normalize_text_for_tts(m.group(0), lexicon=lexicon, modern=modern)

                            normalized = re.sub(
                                r'(?<=>)[^<]+(?=<)',
                                normalize_segment,
                                text
                            )
                            if normalized != data.decode('utf-8'):
                                changes_made += 1
                            data = normalized.encode('utf-8')
                        except Exception:
                            pass

                    zout.writestr(item, data)

    finally:
        tmp_path.unlink(missing_ok=True)

    return output_path, changes_made


if __name__ == '__main__':
    # Quick test
    test_cases = [
        ("The company earned $1,000,000 in revenue.", "The company earned one million dollars in revenue."),
        ("Chapter 3: The Beginning", "Chapter Three: The Beginning"),
        ("He was the 1st to arrive.", "He was the first to arrive."),
        ("Dr. Smith and Mr. Jones met on the 23rd.", "Doctor Smith and Mister Jones met on the twenty-third."),
        ("About 50% of the 2,500 people agreed.", "About fifty percent of the two thousand, five hundred people agreed."),
        ("The population reached 1000000.", "The population reached one million."),
        ("It was 1962.", "It was nineteen sixty-two."),
    ]

    print("Text normalization tests:")
    for input_text, expected in test_cases:
        result = normalize_text_for_tts(input_text)
        status = "PASS" if result == expected else "DIFF"
        print(f"  [{status}] {input_text}")
        if status == "DIFF":
            print(f"         Got:    {result}")
            print(f"         Expect: {expected}")
