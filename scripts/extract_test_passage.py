"""Extract the canonical TTS test passage from an EPUB and preprocess it.

The canonical passage (chosen by Dave, 2026-07-04) is the solar-energy section
of *Abundance* (Klein/Thompson) quoting Hannah Ritchie — dense with the things
that trip TTS: endnote markers, percentages, decades, "$" figures, names
(Hannah Ritchie, Jenny Chase, BloombergNEF), nested quotes, and an academic
paper title. Use it for every engine/voice comparison so results stay
comparable across sessions.

The passage text itself is NOT committed to the repo (copyrighted excerpt);
this script regenerates it from the EPUB in the library.

Usage:
    python scripts/extract_test_passage.py <book.epub> <out.txt>

Requires the webapp package deps (bs4, num2words) importable — run from repo
root. Applies the full tts_preprocess pipeline so the output is exactly what
a TTS engine would receive.
"""
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from tts_preprocess import preprocess_epub  # noqa: E402

ANCHOR_START = 'Environmental action is often framed'
ANCHOR_END = 'about half the price of coal.'


def html_to_paras(html: str) -> list[str]:
    # crude but adequate: paragraphs by <p>, tags stripped
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.S)
    out = []
    for p in paras:
        text = re.sub(r'<[^>]+>', '', p)
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            out.append(text)
    return out


def main(epub_path: str, out_path: str) -> None:
    clean_epub = Path(out_path).with_suffix('.epub')
    preprocess_epub(epub_path, clean_epub)

    z = zipfile.ZipFile(clean_epub)
    passage = None
    for name in z.namelist():
        if not re.search(r'\.x?html?$', name):
            continue
        paras = html_to_paras(z.read(name).decode('utf-8', 'ignore'))
        idx_start = idx_end = None
        for i, p in enumerate(paras):
            if ANCHOR_START.split()[0] in p and 'framed' in p and idx_start is None:
                idx_start = i
            if idx_start is not None and 'price of coal' in p:
                idx_end = i
                break
        if idx_start is not None and idx_end is not None:
            passage = '\n\n'.join(paras[idx_start:idx_end + 1])
            print(f'found in {name}: paras {idx_start}-{idx_end}')
            break

    z.close()
    if not passage:
        raise SystemExit('anchor text not found in EPUB')

    Path(out_path).write_text(passage, encoding='utf-8')
    clean_epub.unlink(missing_ok=True)
    print(f'{len(passage)} chars -> {out_path}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
