"""Single source of truth for splitting a book into renderable chapters.

BOTH the converter (scripts/convert_book.py) and the web UI's chapter picker
import from here, so the chapter NUMBER a user picks in the UI is always the
chapter that actually renders.

History: the picker used raw spine position (Cover=1, Title=2, Contents=4,
Introduction=5, ...) while the converter numbered only substantial chapters
(Introduction=1, Chapter 1=2, ...). So "chapter 5" meant two different things —
a user asking for "5-13" got Chapter 4 through the back-matter. This module
removes that mismatch: one function decides what's renderable and how it's
numbered, and everyone calls it.
"""
import re
import zipfile
from html.parser import HTMLParser

from tts_preprocess import sanitize_html, normalize_text_for_tts

# Sections shorter than this are front/back matter (Cover, Title, Dedication,
# Contents, ...) and are skipped — matching the converter's --min-words default.
MIN_WORDS = 120

# Renderable, but usually not "the book" — Acknowledgments, Notes/citations,
# Index, etc. Flagged so the UI can default "convert the whole book" to the body
# and not tack on a citations dump the listener didn't ask for.
BACK_MATTER_RE = re.compile(
    r'\b(acknowledge?ments?|notes?|bibliograph|references?|index|'
    r'copyright|about the author|glossary|appendix|footnotes?|endnotes?|'
    r'credits|permissions|further reading|colophon|also by)\b', re.I)


class _PBody(HTMLParser):
    """Collect text inside <p> tags only — identical to the converter's parser so
    the two produce the same word counts."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.inp = False

    def handle_starttag(self, t, a):
        if t == 'p':
            self.inp = True
            self.parts.append('\n\n')

    def handle_endtag(self, t):
        if t == 'p':
            self.inp = False

    def handle_data(self, d):
        if self.inp:
            self.parts.append(d)


def spine_docs(z):
    """Reading-order (x)html documents from the OPF spine. Identical logic to the
    converter so both walk the book the same way."""
    opf = [n for n in z.namelist() if n.endswith('.opf')][0]
    t = z.read(opf).decode('utf-8', 'ignore')
    base = opf.rsplit('/', 1)[0] + '/' if '/' in opf else ''
    items = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', t))
    items.update({b: a for a, b in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', t)})
    spine = re.findall(r'<itemref[^>]*idref="([^"]+)"', t)
    docs = [base + items[i] for i in spine if i in items and re.search(r'\.x?html?$', items.get(i, ''))]
    return [d for d in docs if d in z.namelist()]


def _plain_text(html):
    """Body text used ONLY for the renderable word-count decision. Deliberately
    lexicon-free and pinned to modern=True so the count is deterministic and
    engine/voice-independent — the picker and converter must agree regardless of
    which voice is chosen."""
    p = _PBody()
    p.feed(sanitize_html(html))
    text = re.sub(r'[ \t]+', ' ', ''.join(p.parts)).strip()
    return normalize_text_for_tts(text, modern=True)


def renderable_wordcount(z, name):
    """Word count that decides whether a spine doc is a renderable chapter.
    Deterministic so the UI and converter classify chapters identically."""
    return len(_plain_text(z.read(name).decode('utf-8', 'ignore')).split())


def _title_for(html, fallback):
    """Human title for a chapter: first heading, else <title>, else fallback."""
    for m in re.finditer(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.I | re.S):
        t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).strip()
        if t:
            return t[:80]
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    if m:
        t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', m.group(1))).strip()
        if t and t.lower() not in ('untitled', 'chapter', ''):
            return t[:80]
    return fallback


def list_renderable_chapters(epub_path, min_words=MIN_WORDS):
    """The chapters that will actually render, numbered exactly as the converter
    numbers them (1-based, after dropping sub-min_words front/back matter).

    Each item: {index, title, words, back_matter}.
    """
    out = []
    with zipfile.ZipFile(epub_path) as z:
        idx = 0
        for name in spine_docs(z):
            html = z.read(name).decode('utf-8', 'ignore')
            words = len(_plain_text(html).split())
            if words < min_words:
                continue
            idx += 1
            title = _title_for(html, f"Chapter {idx}")
            out.append({
                'index': idx,
                'title': title,
                'words': words,
                'href': name,
                'back_matter': bool(BACK_MATTER_RE.search(title)),
            })
    return out
