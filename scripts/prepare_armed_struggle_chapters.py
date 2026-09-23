"""
prepare_armed_struggle_chapters.py — Book-wide prep for the full Cillian render.

Extracts Preface + Chapters ONE..EIGHT + Conclusion from the calibre EPUB, applies
the LOCKED recipe text prep (lexicon incl. corrected Tánaiste, dates->words,
year ranges/standalone years, numbers/currency, orphan merge, quote detection),
and writes one payload JSON per chapter to scratch/as_book/ for the production
kernel builder.
"""

import html as htmlmod
import json
import re
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
epub = Path(r"C:\Users\Dave\AppData\Local\Temp\opencode\armed_struggle.epub")
out_dir = root / "scratch" / "as_book"
out_dir.mkdir(parents=True, exist_ok=True)

CHAPTERS = [
    ("preface", "Preface", "index_split_013.html"),
    ("ch1", "ONE: The Irish Revolution 1916-23", "index_split_016.html"),
    ("ch2", "TWO: New States 1923-63", "index_split_017.html"),
    ("ch3", "THREE: The Birth of the Provisional IRA 1963-72", "index_split_020.html"),
    ("ch4", "FOUR: The Politics of Violence 1972-6", "index_split_021.html"),
    ("ch5", "FIVE: The Prison War 1976-81", "index_split_024.html"),
    ("ch6", "SIX: Politicization and the Cycle of Violence 1981-8", "index_split_025.html"),
    ("ch7", "SEVEN: Talking and Killing 1988-94", "index_split_028.html"),
    ("ch8", "EIGHT: Cessations of Violence 1994-2002", "index_split_029.html"),
    ("conclusion", "Conclusion", "index_split_030.html"),
]

lex = json.loads((root / "fixtures" / "irish_pronunciation_lexicon.json").read_text(encoding="utf-8"))

_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


def under100(n):
    return _ONES[n] if n < 20 else f"{_TENS[n // 10]}-{_ONES[n % 10]}"


def under1000(n):
    if n < 100:
        return under100(n)
    h = f"{_ONES[n // 100]} hundred"
    r = n % 100
    return h if r == 0 else f"{h} and {under100(r)}"


def year_words(y):
    if 1000 <= y <= 1099:
        rest = y - 1000
        if rest == 0:
            return "ten hundred"
        if rest < 10:
            return f"ten oh {_ONES[rest]}"
        return f"ten {under100(rest)}"
    if 1100 <= y <= 1899:
        cent = {11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
                15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen"}[y // 100]
        rest = y % 100
        if rest == 0:
            return f"{cent} hundred"
        if rest < 10:
            return f"{cent} oh {_ONES[rest]}"
        return f"{cent} {under100(rest)}"
    if 1900 <= y <= 1999:
        rest = y - 1900
        if rest == 0:
            return "nineteen hundred"
        if rest < 10:
            return f"nineteen oh {_ONES[rest]}"
        return f"nineteen {under100(rest)}"
    if 2000 <= y <= 2099:
        rest = y - 2000
        if rest == 0:
            return "two thousand"
        if rest < 10:
            return f"two thousand and {_ONES[rest]}"
        return f"two thousand and {under100(rest)}"
    return num_words(y)

def num_words(n):
    if n >= 1_000_000:
        m, r = divmod(n, 1_000_000)
        return f"{num_words(m)} million" + (f" {num_words(r)}" if r else "")
    if n >= 1000:
        t, r = divmod(n, 1000)
        return f"{under1000(t)} thousand" + (f" {num_words(r)}" if r else "")
    return under1000(n)


_ORD_SPECIAL = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth",
                9: "ninth", 12: "twelfth"}


def ordinal_words(n):
    if n in _ORD_SPECIAL:
        return _ORD_SPECIAL[n]
    if n % 100 in (11, 12, 13):
        return under100(n) + "th"
    return under100(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def prep_text(raw: str) -> list[dict]:
    for key in sorted((k for k in lex if not k.startswith("_")), key=len, reverse=True):
        raw = raw.replace(key, lex[key])

    def date_repl(m):
        day, mon, yr = int(m.group(1)), m.group(2), int(m.group(3))
        return f"the {ordinal_words(day)} of {mon} {year_words(yr)}"

    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\s+((?:19|20)\d{2})\b",
                 date_repl, raw)
    # year-less dates: "9 October", "12th of July"
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b",
                 lambda m: f"the {ordinal_words(int(m.group(1)))} of {m.group(2)}", raw)
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(" + "|".join(_MONTHS) + r")\b",
                 lambda m: f"the {ordinal_words(int(m.group(1)))} of {m.group(2)}", raw)
    raw = re.sub(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2}|\d{2})\b",
                 lambda m: f"{year_words(int(m.group(1)))} to {year_words(int(m.group(2))) if len(m.group(2)) == 4 else under100(int(m.group(2)))}",
                 raw)
    raw = re.sub(r"\b((?:19|20)\d{2})\b", lambda m: year_words(int(m.group(1))), raw)
    raw = re.sub(r"£(\d+) million", lambda m: f"{num_words(int(m.group(1)))} million pounds", raw)
    raw = re.sub(r"£(\d+)", lambda m: f"{num_words(int(m.group(1)))} pounds", raw)
    raw = re.sub(r"\b(\d{1,3}(?:,\d{3})+|\d{3,})\b",
                 lambda m: num_words(int(m.group(1).replace(",", ""))), raw)

    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()
             and not re.fullmatch(r"\d{1,3}", p.strip())]
    PLACEHOLDER = "\ue000"
    ABBR = ["Mr", "Mrs", "Ms", "Dr", "Prof", "St", "Sr", "Jr", "Col", "Gen", "Lt", "Cpt",
            "Capt", "Sgt", "Rev", "Hon", "Sinn", "Vol", "No"]

    def protect(text):
        for a in ABBR:
            text = text.replace(a + ".", a + PLACEHOLDER)
        text = re.sub(r"\b([A-Z])\.(?=\s+[A-Z])", r"\1" + PLACEHOLDER, text)
        return text

    flat = []
    for pid, para in enumerate(paras):
        pieces = re.split(r"(?<=[.!?])\s+", protect(para))
        pieces = [p.replace(PLACEHOLDER, ".").strip() for p in pieces]
        pieces = [p for p in pieces if p]
        merged = []
        buf = ""
        for p in pieces:
            buf = (buf + " " + p).strip() if buf else p
            if re.search(r"[.!?][”’\"']?$", buf) and len(buf.split()) >= 3:
                merged.append(buf)
                buf = ""
            else:
                buf = buf
        if buf:
            if merged:
                merged[-1] = merged[-1] + " " + buf
            else:
                merged.append(buf)
        for s in merged:
            in_quote = ("‘" in s) or bool(re.search(r"(?<![A-Za-z])’", s))
            flat.append({"text": s, "para": pid, "quote": in_quote})
    return flat


z = zipfile.ZipFile(epub)
summary = []
for slug, title, html_name in CHAPTERS:
    raw = z.read(html_name).decode("utf-8", errors="replace")
    raw = re.sub(r'<span[^>]*class="[^"]*dropcap[^"]*"[^>]*>([A-Za-z])</span>', r"\1", raw)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    raw = htmlmod.unescape(raw)
    sents = prep_text(raw)
    payload = {"slug": slug, "title": title, "sents": sents}
    out = out_dir / f"{slug}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    words = sum(len(s["text"].split()) for s in sents)
    quotes = sum(1 for s in sents if s["quote"])
    digit_years = len(re.findall(r"\b(?:19|20)\d{2}\b", " ".join(s["text"] for s in sents)))
    summary.append((slug, title[:45], len(sents), words, quotes, digit_years))
    print(f"{slug:10} {title[:45]:47} {len(sents):5} sents {words:6} words {quotes:4} quote-sents digitYears={digit_years}")

print("\nTOTAL:", sum(s[3] for s in summary), "words | est audio @150wpm:",
      round(sum(s[3] for s in summary) / 150 / 60, 1), "h")
