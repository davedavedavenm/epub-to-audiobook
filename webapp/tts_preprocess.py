"""Text preprocessing for TTS conversion.

Normalizes text in EPUB files to improve TTS pronunciation:
- Numbers with commas: 1,000,000 -> one million
- Currency: $50 -> fifty dollars, £100 -> one hundred pounds
- Ordinals: 1st, 2nd, 3rd -> first, second, third
- Chapter/part headings: Chapter 1 -> Chapter One
- Common abbreviations: Dr. -> Doctor, Mr. -> Mister, etc.
- Percentages: 50% -> fifty percent
- Decades: 1990s -> nineteen nineties

This runs on EPUB HTML content before the converter sends it to TTS.
"""
import re
import zipfile
import shutil
import tempfile
from pathlib import Path

# num2words is optional — gracefully degrade if not installed
try:
    from num2words import num2words
    HAS_NUM2WORDS = True
except ImportError:
    HAS_NUM2WORDS = False


def _number_to_words(n: int, lang: str = 'en') -> str:
    """Convert integer to words, with fallback if num2words unavailable."""
    if HAS_NUM2WORDS:
        return num2words(n, lang=lang)
    return str(n)


def _ordinal_to_words(n: int, lang: str = 'en') -> str:
    """Convert ordinal number to words."""
    if HAS_NUM2WORDS:
        return num2words(n, to='ordinal', lang=lang)
    # Fallback for common ordinals
    suffixes = {1: 'first', 2: 'second', 3: 'third'}
    if n in suffixes:
        return suffixes[n]
    return f"{n}th"


def normalize_text_for_tts(text: str) -> str:
    """Apply all TTS normalization rules to a text string."""

    # === Abbreviations (must come before period-related rules) ===
    abbreviations = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Ms',
        r'\bProf\.': 'Professor',
        r'\bSt\.': 'Saint',
        r'\bGen\.': 'General',
        r'\bSgt\.': 'Sergeant',
        r'\bCpl\.': 'Corporal',
        r'\bLt\.': 'Lieutenant',
        r'\bCol\.': 'Colonel',
        r'\bCapt\.': 'Captain',
        r'\bGov\.': 'Governor',
        r'\bSen\.': 'Senator',
        r'\bRep\.': 'Representative',
        r'\bvs\.': 'versus',
        r'\bVs\.': 'Versus',
        r'\bet al\.': 'et alia',
        r'\betc\.': 'etcetera',
        r'\bi\.e\.': 'that is',
        r'\be\.g\.': 'for example',
        r'\bU\.S\.A\.': 'U S A',
        r'\bU\.S\.': 'U S',
        r'\bU\.K\.': 'U K',
        r'\bU\.N\.': 'U N',
        r'\bE\.U\.': 'E U',
        r'\bD\.C\.': 'D C',
        r'\bB\.C\.': 'B C',
        r'\bA\.D\.': 'A D',
        r'\bNo\.': 'Number',
        r'\bno\.': 'number',
        r'\bVol\.': 'Volume',
        r'\bvol\.': 'volume',
        r'\bFig\.': 'Figure',
        r'\bfig\.': 'figure',
        r'\bpp\.': 'pages',
        r'\bp\.': 'page',
    }
    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text)

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
        return f"{words} {unit}"

    text = re.sub(r'([$£€])(\d[\d,]*\.?\d*)', replace_currency, text)

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

    text = re.sub(r'(\d[\d,]*\.?\d*)%', replace_percent, text)

    # === Ordinals: 1st, 2nd, 3rd, 4th, 21st, etc. ===
    def replace_ordinal(m):
        n = int(m.group(1))
        if n > 1000000:
            return m.group(0)  # Don't convert huge ordinals
        return _ordinal_to_words(n)

    text = re.sub(r'\b(\d+)(?:st|nd|rd|th)\b', replace_ordinal, text)

    # === Decades: 1990s, 1800s ===
    def replace_decade(m):
        year = int(m.group(1))
        if HAS_NUM2WORDS:
            return _number_to_words(year) + 's'
        return m.group(0)

    text = re.sub(r'\b(\d{4})s\b', replace_decade, text)

    # === Chapter/Part/Volume headings ===
    def replace_heading_number(m):
        label = m.group(1)
        n = int(m.group(2))
        if n > 200:
            return m.group(0)
        return f"{label} {_number_to_words(n).title()}"

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

    # Numbers with comma separators (at least one comma)
    text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', replace_comma_number, text)

    # === Standalone large numbers without commas (4+ digits) ===
    def replace_large_number(m):
        try:
            n = int(m.group(0))
            # Don't convert years (1800-2099) that appear to be years
            if 1800 <= n <= 2099:
                return m.group(0)  # Leave years as-is for TTS to handle
            if n > 999999999999:
                return m.group(0)
            return _number_to_words(n)
        except ValueError:
            return m.group(0)

    text = re.sub(r'\b\d{4,}\b', replace_large_number, text)

    # === Ellipsis normalization ===
    # Multiple dots that aren't proper ellipsis
    text = re.sub(r'\.{4,}', '...', text)


    # === Pacing and Punctuation (Enhance Flow) ===
    # Convert em-dashes and en-dashes to commas for better breath pauses
    text = re.sub(r'\\s*[—–]\\s*', ', ', text)
    text = re.sub(r'\\s*--\\s*', ', ', text)
    
    # Standardize ellipses and add space for a breath
    text = re.sub(r'\\.{2,}', '... ', text)
    
    # Inject breath pauses into overly long sentences (heuristic: >150 chars without punctuation)
    def inject_breaths(m):
        sentence = m.group(0)
        if len(sentence) > 150 and ',' not in sentence:
            return re.sub(r'(.{80,}?) (and|but|or|because) ', r'\\1, \\2 ', sentence, count=1)
        return sentence
        
    text = re.sub(r'[^.!?]+[.!?]', inject_breaths, text)

    return text



def preprocess_epub(epub_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Preprocess an EPUB file: normalize text for better TTS pronunciation.

    Modifies HTML content inside the EPUB. If output_path is None,
    creates a preprocessed copy alongside the original with _tts suffix.

    Returns the path to the preprocessed EPUB.
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
                            # Only normalize text content, not HTML tags/attributes
                            # Simple approach: normalize text between > and <
                            def normalize_segment(m):
                                return normalize_text_for_tts(m.group(0))

                            normalized = re.sub(
                                r'(?<=>)[^<]+(?=<)',
                                normalize_segment,
                                text
                            )
                            if normalized != text:
                                changes_made += 1
                            data = normalized.encode('utf-8')
                        except (UnicodeDecodeError, Exception):
                            pass  # Skip files that can't be decoded

                    zout.writestr(item, data)

    finally:
        tmp_path.unlink(missing_ok=True)

    return output_path


if __name__ == '__main__':
    # Quick test
    test_cases = [
        ("The company earned $1,000,000 in revenue.", "The company earned one million dollars in revenue."),
        ("Chapter 3: The Beginning", "Chapter Three: The Beginning"),
        ("He was the 1st to arrive.", "He was the first to arrive."),
        ("Dr. Smith and Mr. Jones met on the 23rd.", "Doctor Smith and Mister Jones met on the twenty-third."),
        ("About 50% of the 2,500 people agreed.", "About fifty percent of the two thousand, five hundred people agreed."),
        ("The population reached 1000000.", "The population reached one million."),
    ]

    print("Text normalization tests:")
    for input_text, expected in test_cases:
        result = normalize_text_for_tts(input_text)
        status = "PASS" if result == expected else "DIFF"
        print(f"  [{status}] {input_text}")
        if status == "DIFF":
            print(f"         Got:    {result}")
            print(f"         Expect: {expected}")
