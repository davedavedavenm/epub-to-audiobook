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
    text = re.sub(r'\b(1[0-9]{3}|20[0-9]{2})\b', lambda m: _year_to_words(m.group(0)), text)

    # === Currency (before general number handling) ===
    def replace_currency(m):
        symbol = m.group(1)
        amount_str = m.group(2).replace(',', '')
        try:
            amount = float(amount_str)
            if amount == int(amount):
                amount = int(amount)
            words = _number_to_words(amount) if isinstance(amount, int) else str(amount)
        except ValueError:
            return m.group(0)

        currencies = {'$': 'dollars', '£': 'pounds', '€': 'euros'}
        unit = currencies.get(symbol, symbol)
        # "$33 billion" must become "thirty-three billion dollars",
        # not "thirty-three dollars billion"
        scale = (m.group(3) or '').strip()
        if scale:
            return f"{words} {scale} {unit}"
        return f"{words} {unit}"

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
            return f"{num_str} percent"
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

    # === Decades: 1990s, 1800s ===
    # Plain date number -> skip for modern (see MODERN-ENGINE CONTRACT).
    def replace_decade(m):
        year_str = m.group(1)
        year = int(year_str)
        if 1000 <= year <= 2099:
            # Handle 1860s as "eighteen sixties"
            prefix = int(year_str[:2])
            suffix = int(year_str[2:])
            if suffix == 0:
                return f"{_number_to_words(prefix)} hundreds"
            return f"{_number_to_words(prefix)} {_number_to_words(suffix)}s"
        if HAS_NUM2WORDS:
            return _number_to_words(year) + 's'
        return m.group(0)

    if not modern:
        text = re.sub(r'\b(\d{4})s\b', replace_decade, text)

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
                        except (UnicodeDecodeError, Exception):
                            pass  # Skip files that can't be decoded

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
