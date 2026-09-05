#!/usr/bin/env python3
"""Extract 2 pages of Chapter 1 from Breakneck and normalize with explicit profile."""
import sys
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

# Import preprocessing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from tts_preprocess import normalize_text_for_tts

def main():
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        epub_path = Path(sys.argv[1])
    else:
        for p in [Path("breakneck.epub"), Path("/home/dave/booklib/Breakneck - Dan Wang.epub")]:
            if p.exists():
                epub_path = p
                break

    print(f"Reading from {epub_path}")
    with zipfile.ZipFile(epub_path) as z:
        raw_ch1 = z.read('OEBPS/text/08_Chapter01.xhtml').decode('utf-8')
        soup = BeautifulSoup(raw_ch1, 'html.parser')
        stop_tag = soup.find(id='page_3')
        paras = []
        for h in soup.find_all(['h1', 'h2']):
            h_text = h.get_text().strip()
            if h_text:
                paras.append(h_text)

        for p in soup.find_all('p'):
            if stop_tag and stop_tag in p.find_all():
                break
            text = p.get_text().strip()
            if text:
                paras.append(text)

        raw_text = '\n\n'.join(paras)
        norm_text = normalize_text_for_tts(raw_text, modern=True, expand_numbers=True)

        fixtures_dir = Path(__file__).resolve().parents[1] / 'fixtures'
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        out_raw = fixtures_dir / 'breakneck_ch1_2pages_raw.txt'
        out_norm = fixtures_dir / 'breakneck_ch1_2pages_norm.txt'
        out_raw.write_text(raw_text, encoding='utf-8')
        out_norm.write_text(norm_text, encoding='utf-8')

        print(f"Extracted raw: {len(raw_text)} chars, {len(raw_text.split())} words")
        print(f"Extracted norm: {len(norm_text)} chars, {len(norm_text.split())} words")
        print(f"Saved to {out_raw} and {out_norm}")

if __name__ == '__main__':
    main()
