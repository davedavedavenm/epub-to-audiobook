"""Regenerate all Armed Struggle chapter payloads with the canonical as_prep module,
then hard-scan: zero digit runs, zero broken ordinals anywhere."""

import glob
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from as_prep import load_lexicon, prep  # noqa: E402

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

lex = load_lexicon()
z = zipfile.ZipFile(epub)
broken_ordinal_pat = re.compile(r"onest\b|twond\b|threerd\b|twelveth\b|oneth\b|twentyth\b|thirtyth\b|fortieth\b")
total_words = 0
for slug, title, hf in CHAPTERS:
    raw = z.read(hf).decode("utf-8", errors="replace")
    raw = re.sub(r'<span[^>]*class="[^"]*dropcap[^"]*"[^>]*>([A-Za-z])</span>', r"\1", raw)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    import html as htmlmod

    raw = htmlmod.unescape(raw)
    sents = prep(raw, lex)
    (out_dir / f"{slug}.json").write_text(json.dumps({"slug": slug, "title": title, "sents": sents},
                                                     ensure_ascii=False), encoding="utf-8")
    text = " ".join(s["text"] for s in sents)
    digits = re.findall(r"\d+", text)
    brok = broken_ordinal_pat.findall(text)
    words = len(text.split())
    total_words += words
    status = "OK" if not digits and not brok else f"DIGITS {digits[:6]} BROKEN {brok[:4]}"
    print(f"{slug:10} {len(sents):5} sents {words:6} words {status}")
print("TOTAL words:", total_words)
