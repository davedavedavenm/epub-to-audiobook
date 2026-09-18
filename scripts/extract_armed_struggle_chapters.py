import re
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
epub_path = root / "fixtures" / "armed_struggle.epub"

book = epub.read_epub(str(epub_path))
items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

# Target splits: 13 (Preface), 16 (Ch 1), 17 (Ch 2), 20 (Ch 3), 21 (Ch 4), 24 (Ch 5), 25 (Ch 6), 28 (Ch 7), 29 (Ch 8), 30 (Conclusion), 31 (Afterword)
target_splits = [
    (13, "08 - Preface"),
    (16, "09 - One The Irish Revolution Nineteen Sixteen 23"),
    (17, "10 - Two New States Nineteen Twenty Three 63"),
    (20, "11 - Three The Birth Of The Provisional Ira Nineteen Sixty Three 72"),
    (21, "12 - Four The Politics Of Violence Nineteen Seventy Two 6"),
    (24, "13 - Five The Prison War Nineteen Seventy Six 81"),
    (25, "14 - Six Politicization And The Cycle Of Violence Nineteen Eighty One 8"),
    (28, "15 - Seven Talking And Killing Nineteen Eighty Eight 94"),
    (29, "16 - Eight Cessations Of Violence Nineteen Ninety Four To Two Thousand Two"),
    (30, "17 - Conclusion"),
    (31, "18 - Afterword")
]

out_dir = root / "fixtures" / "armed_struggle_chapters"
out_dir.mkdir(parents=True, exist_ok=True)

for split_idx, title in target_splits:
    item = items[split_idx]
    soup = BeautifulSoup(item.get_content(), "html.parser")
    
    # Clean up superscripts, endnotes, footnote anchors
    for tag in soup.find_all(["sup", "sub", "a"]):
        # Remove footnote link numbers e.g. <a href="...">[1]</a> or <sup>1</sup>
        t = tag.get_text().strip()
        if re.match(r"^\[?\d+\]?$", t):
            tag.decompose()
            
    # Extract clean paragraphs
    paragraphs = []
    for p in soup.find_all(["p", "h1", "h2", "h3", "h4"]):
        text = p.get_text().strip()
        if text and len(text) > 1:
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text)
            paragraphs.append(text)
            
    full_text = "\n\n".join(paragraphs)
    words = len(full_text.split())
    out_file = out_dir / f"{title}.txt"
    out_file.write_text(full_text, encoding="utf-8")
    print(f"Extracted {title} ({words:,} words) -> {out_file.name}")
