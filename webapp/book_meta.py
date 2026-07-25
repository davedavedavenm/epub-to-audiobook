"""Book metadata, read from the epub, in ONE place.

Why this module exists
----------------------
There were two independent readers of "what is this book called and who wrote
it". `scripts/convert_book.py` read `dc:title` / `dc:creator` out of the OPF and
tagged the MP3s correctly. `webapp/app.py`'s M4B builder did something else
entirely — it used the job's filename-derived name for the title and dug the
author out of the LLM *narration profile*, which describes narration style and
has no author field. So it always resolved to empty.

The result, measured on a real render (#32): MP3s tagged
`album="Alice's Adventures in Wonderland" artist="Lewis Carroll"`, while the
M4B built from those same files in the same job said
`title="Alice in Wonderland - Lewis Carroll"` with no artist at all. An
M4B-only library lost the author.

This is the same failure `chapters.py` was created to kill: two code paths
deriving one fact independently, and the second drifting. So: one reader, one
fallback policy, both callers use it.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

# Dublin Core elements worth having. ABS reads title/author/series/published
# year and description; the rest are cheap to carry and useful downstream.
_DC_FIELDS = {
    'title': 'title',
    'creator': 'author',
    'publisher': 'publisher',
    'description': 'description',
    'language': 'language',
    'date': 'date',
    'identifier': 'identifier',
    'subject': 'subject',
}


def _first(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return ''
    # Collapse whitespace: OPF fields are frequently wrapped across lines.
    return ' '.join(m.group(1).split()).strip()


def _strip_tags(s: str) -> str:
    return ' '.join(re.sub(r'<[^>]+>', ' ', s).split())


def read_book_meta(epub_path: str | Path) -> dict:
    """Return a metadata dict for an epub. Never raises.

    Keys always present: title, author. Others appear only when the OPF has
    them, so callers can use plain truthiness.

    `title` falls back to the file stem when the OPF has no `dc:title` — that
    was the prior behaviour of both callers and stays the documented default,
    so a book with bare metadata is no worse off than before.
    """
    epub_path = Path(epub_path)
    meta: dict[str, str] = {}
    try:
        with zipfile.ZipFile(epub_path) as z:
            opfs = [n for n in z.namelist() if n.lower().endswith('.opf')]
            if not opfs:
                raise ValueError('no OPF in epub')
            raw = z.read(opfs[0]).decode('utf-8', 'ignore')

        for dc, key in _DC_FIELDS.items():
            val = _first(rf'<dc:{dc}[^>]*>(.*?)</dc:{dc}>', raw)
            if val:
                meta[key] = _strip_tags(val)

        # Series lives in a <meta> element, and the two competing conventions
        # (epub2 calibre-style and epub3 belongs-to-collection) are both common.
        series = (_first(r'<meta[^>]+name=["\']calibre:series["\'][^>]+content=["\']([^"\']+)', raw)
                  or _first(r'<meta[^>]+property=["\']belongs-to-collection["\'][^>]*>(.*?)</meta>', raw))
        if series:
            meta['series'] = _strip_tags(series)
        seq = _first(r'<meta[^>]+name=["\']calibre:series_index["\'][^>]+content=["\']([^"\']+)', raw)
        if seq:
            meta['series_index'] = seq

    except Exception:
        # Corrupt or exotic epub: fall through to the filename fallback rather
        # than failing a render over metadata.
        pass

    if not meta.get('title'):
        meta['title'] = epub_path.stem
    meta.setdefault('author', '')

    # A four-digit year is what taggers and ABS actually want out of dc:date.
    if meta.get('date') and not meta.get('year'):
        y = re.search(r'(\d{4})', meta['date'])
        if y:
            meta['year'] = y.group(1)

    return meta


def title_author(epub_path: str | Path) -> tuple[str, str]:
    """Convenience for the common case. Mirrors the old `_book_meta()`."""
    m = read_book_meta(epub_path)
    return m.get('title', ''), m.get('author', '')
