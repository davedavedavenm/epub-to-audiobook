"""
as_prep.py — Canonical text preparation for the Armed Struggle Cillian render
(locked recipe, see CILLIAN-RECIPE.md). Single source of truth; unit-tested.

Pipeline: lexicon -> dates (with/without year) -> year ranges -> standalone
years (1000-2099 spoken correctly) -> currency -> numbers -> orphan merge ->
abbrev-safe sentence split with quote detection.
"""

import json
import re
from pathlib import Path

_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_ORD_BASE = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth", 9: "ninth",
             12: "twelfth"}
_ROOT = Path(__file__).resolve().parents[1]


def under100(n):
    if n < 20:
        return _ONES[n]
    if n % 10 == 0:
        return _TENS[n // 10]
    return f"{_TENS[n // 10]}-{_ONES[n % 10]}"


def under1000(n):
    if n < 100:
        return under100(n)
    h = f"{_ONES[n // 100]} hundred"
    r = n % 100
    return h if r == 0 else f"{h} and {under100(r)}"


def num_words(n):
    if n == 0:
        return "zero"
    if n >= 1_000_000:
        m, r = divmod(n, 1_000_000)
        return f"{num_words(m)} million" + (f" {num_words(r)}" if r else "")
    if n >= 1000:
        t, r = divmod(n, 1000)
        return f"{under1000(t)} thousand" + (f" {num_words(r)}" if r else "")
    return under1000(n)


def ordinal_words(n):
    if n % 100 in (11, 12, 13):
        base = {11: "eleventh", 12: "twelfth", 13: "thirteenth"}[n % 100]
        if n < 100:
            return base
        return f"{under1000(n - n % 100)} {base}"
    if n < 20:
        return _ORD_BASE.get(n, under100(n) + "th")
    d = n % 10
    if d == 0:
        t = _TENS[n // 10]
        return {_TENS.index(tt): tt[:-1] + "ieth" for tt in ("twenty", "thirty", "forty",
                "fifty", "sixty", "seventy", "eighty", "ninety")}[n // 10]
    return _TENS[n // 10] + "-" + _ORD_BASE.get(d, _ONES[d] + "th")


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


def short_year_words(two_digit: str) -> str:
    n = int(two_digit)
    if n == 0:
        return "hundred"
    if n < 10:
        return f"oh {_ONES[n]}"
    return under100(n)


ABBR = ["Mr", "Mrs", "Ms", "Dr", "Prof", "St", "Sr", "Jr", "Col", "Gen", "Lt", "Cpt",
        "Capt", "Sgt", "Rev", "Hon", "Sinn", "Vol", "No"]
PLACEHOLDER = "\ue000"


def prep(raw: str, lexicon: dict) -> list[dict]:
    for key in sorted((k for k in lexicon if not k.startswith("_")), key=len, reverse=True):
        raw = raw.replace(key, lexicon[key])

    # decades: 1920s / late-1920s / early-1930s -> "nineteen twenties" etc.
    def decade_repl(m):
        y = int(m.group(1))
        cent = year_words(y - y % 100 + 100)[: -len(under100(100) + "")] if False else None
        if 1000 <= y <= 1099:
            cent = "ten"
        elif y // 100 == 11:
            cent = "eleven"
        elif y // 100 == 12:
            cent = "twelve"
        elif y // 100 == 13:
            cent = "thirteen"
        elif y // 100 == 14:
            cent = "fourteen"
        elif y // 100 == 15:
            cent = "fifteen"
        elif y // 100 == 16:
            cent = "sixteen"
        elif y // 100 == 17:
            cent = "seventeen"
        elif y // 100 == 18:
            cent = "eighteen"
        elif y // 100 == 19:
            cent = "nineteen"
        elif y // 100 == 20:
            cent = "twenty"
        else:
            cent = under1000(y // 100)
        d = y % 100
        plural = "hundreds" if d == 0 else under100(d)[:-1] + "ies"
        return f"{cent} {plural}"

    raw = re.sub(r"\b((?:1[0-9]|20)\d{2})s\b", decade_repl, raw)

    def date_full(m):
        day, mon, yr = int(m.group(1)), m.group(2), int(m.group(3))
        return f"the {ordinal_words(day)} of {mon} {year_words(yr)}"

    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\s+((?:19|20)\d{2})\b",
                 date_full, raw)
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(" + "|".join(_MONTHS) + r")\b",
                 lambda m: f"the {ordinal_words(int(m.group(1)))} of {m.group(2)}", raw)
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b",
                 lambda m: f"the {ordinal_words(int(m.group(1)))} of {m.group(2)}", raw)
    # month-first: "January 30, 1972" / "January 30"
    raw = re.sub(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{2})\b",
                 lambda m: f"the {ordinal_words(int(m.group(2)))} of {m.group(1)} {year_words(int(m.group(3)))}", raw)
    raw = re.sub(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b",
                 lambda m: f"the {ordinal_words(int(m.group(2)))} of {m.group(1)}", raw)
    # year ranges: any 4-digit year to short or full second year
    raw = re.sub(r"\b(\d{4})\s*[-–—]\s*(\d{2}|\d{4})\b",
                 lambda m: f"{year_words(int(m.group(1)))} to {year_words(int(m.group(2))) if len(m.group(2)) == 4 else short_year_words(m.group(2))}",
                 raw)
    raw = re.sub(r"\b(\d{4})\b", lambda m: year_words(int(m.group(1))), raw)
    # short-form quote years: ’98 / '45 (Irish-historic context)
    raw = re.sub(r"[‘’'](\d{2})\b", lambda m: short_year_words(m.group(1)), raw)
    raw = re.sub(r"£(\d{1,3}(?:,\d{3})+|\d+)\s*million",
                 lambda m: f"{num_words(int(m.group(1).replace(',', '')))} million pounds", raw)
    raw = re.sub(r"£(\d{1,3}(?:,\d{3})+|\d+)",
                 lambda m: f"{num_words(int(m.group(1).replace(',', '')))} pounds", raw)
    # mixed decade ranges: "forties–80s" -> "forties to eighties"
    def dec_plural(dd):
        return "hundreds" if dd == 0 else under100(dd)[:-1] + "ies"

    raw = re.sub(r"[–—-](\d0)s\b", lambda m: f" to {dec_plural(int(m.group(1)))}", raw)
    # weights: "250lb" -> words + pound
    raw = re.sub(r"\b(\d{1,3})lb\b", lambda m: f"{num_words(int(m.group(1)))} pound", raw)
    # times: "8.45 p.m." / bare "10.30"
    raw = re.sub(r"\b(\d{1,2})\.(\d{2})\s*([ap])\.m\.",
                 lambda m: f"{under100(int(m.group(1)))} {short_year_words(m.group(2))} {m.group(3)}.m.", raw)
    raw = re.sub(r"\b(\d{1,2})\.(\d{2})\b",
                 lambda m: f"{under100(int(m.group(1)))} {short_year_words(m.group(2))}", raw)
    # calibers: ".45 revolver"
    raw = re.sub(r"\s\.(\d{2})\b", lambda m: f" {short_year_words(m.group(1))}", raw)
    # bare ordinals: "the 8th", "the 28th"
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", lambda m: ordinal_words(int(m.group(1))), raw)
    raw = re.sub(r"\b(\d{1,3}(?:,\d{3})+|\d{3,})\b",
                 lambda m: num_words(int(m.group(1).replace(",", ""))), raw)
    raw = re.sub(r"\b(\d{2})\b", lambda m: under100(int(m.group(1))), raw)
    # bare ordinals: "the 8th", "the 28th"
    raw = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)\b", lambda m: ordinal_words(int(m.group(1))), raw)
    # any remaining bare small integers (world war 1 etc)
    raw = re.sub(r"\b(\d)\b", lambda m: _ONES[int(m.group(1))], raw)

    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()
             and not re.fullmatch(r"\d{1,3}", p.strip())]

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


def load_lexicon():
    return json.loads((_ROOT / "fixtures" / "irish_pronunciation_lexicon.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    # hard unit tests
    assert ordinal_words(1) == "first" and ordinal_words(2) == "second" and ordinal_words(3) == "third"
    assert ordinal_words(9) == "ninth" and ordinal_words(11) == "eleventh" and ordinal_words(12) == "twelfth"
    assert ordinal_words(13) == "thirteenth" and ordinal_words(20) == "twentieth" and ordinal_words(21) == "twenty-first"
    assert ordinal_words(23) == "twenty-third" and ordinal_words(31) == "thirty-first" and ordinal_words(10) == "tenth"
    assert year_words(1014) == "ten fourteen"
    assert year_words(1798) == "seventeen ninety-eight"
    assert year_words(1801) == "eighteen oh one"
    assert year_words(1848) == "eighteen forty-eight"
    assert year_words(1867) == "eighteen sixty-seven"
    assert year_words(1900) == "nineteen hundred"
    assert year_words(1916) == "nineteen sixteen"
    assert year_words(1923) == "nineteen twenty-three"
    assert year_words(1969) == "nineteen sixty-nine"
    assert year_words(1981) == "nineteen eighty-one"
    assert year_words(2002) == "two thousand and two"
    assert num_words(4500) == "four thousand five hundred"
    assert num_words(55000) == "fifty-five thousand"
    assert num_words(15) == "fifteen"
    assert short_year_words("98") == "ninety-eight" and short_year_words("45") == "forty-five"
    out = prep("On 12 July 1921, by 1848 the ’98 spirit rose again; 4,500 attended, cost £15 million. On 9 October nothing moved. World War 1 began in 1914. In the early 1920s and late-1930s, 82 men and 12 rounds of .45 ammunition were counted. At 8.45 p.m. and around 10.30, the Catch 22 held on the 28th. It spanned 1919-21 and 1763–98, from January 30, 1972.", load_lexicon())
    joined = " ".join(s["text"] for s in out)
    for probe in ["twelfth of July nineteen twenty-one", "eighteen forty-eight",
                  "ninety-eight spirit", "four thousand five hundred",
                  "fifteen million pounds", "ninth of October", "World War one",
                  "nineteen fourteen", "nineteen twenties", "thirties",
                  "eighty-two men", "twelve rounds", "forty-five ammunition",
                  "eight forty-five p.m.", "ten thirty", "twenty-two",
                  "twenty-eighth", "nineteen nineteen to twenty-one",
                  "seventeen sixty-three to ninety-eight",
                  "the thirtieth of January nineteen seventy-two"]:
        assert probe in joined, f"MISSING: {probe}"
    assert not re.search(r"\d", joined), f"digits remain: {re.findall(r'.{0,25}\\d.{0,25}', joined)}"
    print("ALL PREP TESTS PASS")
