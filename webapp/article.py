"""Turn a web page into something the audiobook pipeline can already render.

The insight that keeps this small: the expensive machinery — preprocessing,
six engines, cloned voices, ID3/M4B packaging, the queue, Audiobookshelf
delivery — is all downstream of "clean text plus a title and an author". An
epub is one way to produce that. A URL is another.

So this module does exactly two things:

    fetch_article(url)          -> {title, author, site, date, text, ...}
    article_to_epub(meta, path) -> a minimal, valid epub

and everything after that is the existing pipeline, unchanged. Rendering an
article is therefore not a second code path — it is the same path with a
different front door (#36).

Deliberately no new dependency: bs4 and lxml are already in the image. A
purpose-built readability library would extract marginally better on hostile
pages, but every dependency in the render path is a thing that can break a
book, and there is a human preview step here to catch bad extractions.
"""

from __future__ import annotations

import html
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Identify honestly. Some sites serve different markup to unknown agents, and
# pretending to be Chrome to scrape harder is not a fight worth picking.
USER_AGENT = ('Mozilla/5.0 (compatible; epub-to-audiobook/1.0; '
              '+https://github.com/davedavedavenm/epub-to-audiobook)')

# Structural furniture that is never the article.
_STRIP_TAGS = ('script', 'style', 'noscript', 'nav', 'header', 'footer',
               'aside', 'form', 'iframe', 'svg', 'button', 'figure')

# Class/id fragments that reliably mark non-article regions.
_NOISE = re.compile(
    r'(nav|menu|sidebar|footer|header|comment|share|social|promo|advert|'
    r'newsletter|subscribe|related|recirc|cookie|banner|paywall|byline-)',
    re.I)

MIN_ARTICLE_WORDS = 100


class ExtractionError(Exception):
    """Raised when a page yields nothing worth narrating."""


def _meta(soup, *names) -> str:
    """First matching <meta> content, checking property= and name=."""
    for n in names:
        for attr in ('property', 'name', 'itemprop'):
            el = soup.find('meta', attrs={attr: n})
            if el and el.get('content'):
                return el['content'].strip()
    return ''


def _json_ld(soup) -> dict:
    """Article metadata from JSON-LD, which is often better than og: tags."""
    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(tag.string or '{}')
        except Exception:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict):
                continue
            if node.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                return node
    return {}


def _author_from(node: dict) -> str:
    a = node.get('author')
    if isinstance(a, dict):
        return (a.get('name') or '').strip()
    if isinstance(a, list) and a:
        first = a[0]
        return (first.get('name') if isinstance(first, dict) else str(first)).strip()
    return (a or '').strip() if isinstance(a, str) else ''


def _score(el) -> float:
    """Crude readability: paragraph text wins, link-heavy blocks lose.

    Navigation and related-article rails are mostly anchor text, so the ratio
    of linked to unlinked characters separates them from prose better than
    raw length does.
    """
    paras = el.find_all('p')
    if not paras:
        return 0.0
    text_len = sum(len(p.get_text(strip=True)) for p in paras)
    if text_len < 200:
        return 0.0
    link_len = sum(len(a.get_text(strip=True)) for a in el.find_all('a'))
    link_ratio = link_len / max(text_len, 1)
    ident = ' '.join(filter(None, [el.get('id', ''), ' '.join(el.get('class', []) or [])]))
    penalty = 0.35 if _NOISE.search(ident) else 1.0
    return text_len * (1 - min(link_ratio, 0.9)) * penalty


def _strip_noise(soup) -> None:
    """Remove furniture, without ever removing the article with it.

    The naive version of this deleted whole pages. Wikipedia puts
    `vector-feature-language-in-header-enabled` on the <html> element — which
    contains "header", so the noise pattern matched the ROOT and decompose()
    took the entire document with it. Extraction returned zero words on one of
    the most ordinary pages on the web.

    Two guards, both of which express the same idea: furniture does not contain
    the article.
      1. Never touch html/body/head, whatever classes they carry.
      2. Never remove an element holding a large share of the page's
         paragraphs — that is a wrapper, not a sidebar.
    """
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    total_paras = len(soup.find_all('p')) or 1
    for attr in ('class', 'id'):
        for el in soup.find_all(attrs={attr: _NOISE}):
            if el.name in ('html', 'body', 'head'):
                continue
            if not el.parent:                       # already detached
                continue
            if len(el.find_all('p')) > total_paras * 0.4:
                continue
            el.decompose()


def _extract_body(soup) -> str:
    """Best-scoring container's paragraphs, as plain text."""
    _strip_noise(soup)

    candidates = soup.find_all(['article', 'main', 'div', 'section'])
    best, best_score = None, 0.0
    for el in candidates:
        s = _score(el)
        if s > best_score:
            best, best_score = el, s
    root = best or soup.body or soup

    parts = []
    for p in root.find_all(['p', 'h2', 'h3', 'blockquote', 'li']):
        t = ' '.join(p.get_text(' ', strip=True).split())
        if not t:
            continue
        # Length-filter prose only. Subheadings are legitimately short — an
        # early version dropped "A subheading" for being under 25 characters,
        # which quietly removed the article's structure.
        if p.name not in ('h2', 'h3') and len(t) < 25:
            continue
        if p.name in ('h2', 'h3'):
            parts.append('')                # a beat before a subheading
        parts.append(t)
    return '\n\n'.join(x for x in parts if x is not None).strip()


def fetch_article(url: str, timeout: int = 25) -> dict:
    """Fetch a URL and return its readable content plus metadata.

    Raises ExtractionError with something a human can act on — extraction
    failure is the normal case for paywalls and JS-rendered pages, not an
    exceptional one, so the message matters.
    """
    if not re.match(r'^https?://', url, re.I):
        raise ExtractionError('URL must start with http:// or https://')

    try:
        r = requests.get(url, timeout=timeout,
                         headers={'User-Agent': USER_AGENT,
                                  'Accept': 'text/html,application/xhtml+xml'})
        r.raise_for_status()
    except requests.HTTPError as e:
        raise ExtractionError(f'The site returned {e.response.status_code}. '
                              f'It may require a login or block automated access.')
    except Exception as e:
        raise ExtractionError(f'Could not fetch that URL: {e}')

    ctype = r.headers.get('Content-Type', '')
    if 'html' not in ctype.lower():
        raise ExtractionError(f'That URL is {ctype or "not HTML"}, not a web page. '
                              f'For a PDF, upload it on the Library tab instead.')

    # Pass BYTES, not r.text. requests falls back to ISO-8859-1 for text/*
    # when the response header carries no charset, which mangles UTF-8 into
    # mojibake — and curly quotes and em dashes are exactly what a narrator
    # then reads aloud as gibberish. lxml honours the document's own meta
    # charset, which is what the page actually declared.
    soup = BeautifulSoup(r.content, 'lxml')
    ld = _json_ld(soup)

    title = (ld.get('headline') or _meta(soup, 'og:title', 'twitter:title')
             or (soup.title.get_text(strip=True) if soup.title else '') or 'Untitled')
    author = (_author_from(ld) or _meta(soup, 'article:author', 'author', 'byl')
              or '')
    site = (_meta(soup, 'og:site_name')
            or re.sub(r'^www\.', '', requests.utils.urlparse(url).netloc))
    date = (ld.get('datePublished')
            or _meta(soup, 'article:published_time', 'date', 'pubdate') or '')
    image = _meta(soup, 'og:image', 'twitter:image')

    text = _extract_body(soup)
    words = len(text.split())
    if words < MIN_ARTICLE_WORDS:
        raise ExtractionError(
            f'Only {words} words of readable text were found. The page is '
            f'probably paywalled, or builds its content with JavaScript — '
            f'neither of which this can read. Try the printer-friendly or '
            f'reader-mode URL if there is one.')

    # An author is often absent on blogs; the site is a reasonable stand-in and
    # makes for a far better library entry than a blank.
    if not author:
        author = site

    return {
        'url': url,
        'title': html.unescape(title).strip(),
        'author': html.unescape(author).strip(),
        'site': site,
        'date': (date or '')[:10],
        'image': image,
        'text': text,
        'word_count': words,
        # ~155 wpm is a typical narration pace; good enough to set expectations.
        'estimated_minutes': max(1, round(words / 155)),
    }


def _xml_escape(s: str) -> str:
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def article_to_epub(meta: dict, out_path: str | Path) -> Path:
    """Write a minimal, valid epub containing the article.

    Going through an epub rather than injecting text straight into the
    converter is deliberate: every downstream stage — chapter detection,
    preprocessing, ID3 tagging, M4B, ABS sync — already knows how to handle
    one. An article becomes a one-chapter book and needs no special case
    anywhere else.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    title = _xml_escape(meta.get('title') or 'Untitled')
    author = _xml_escape(meta.get('author') or '')
    uid = f'urn:uuid:{uuid.uuid4()}'
    date = meta.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d')

    paras = '\n'.join(f'    <p>{_xml_escape(p)}</p>'
                      for p in meta.get('text', '').split('\n\n') if p.strip())

    chapter = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body>
    <h1>{title}</h1>
{paras}
  </body>
</html>'''

    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{uid}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:date>{_xml_escape(date)}</dc:date>
    <dc:source>{_xml_escape(meta.get('url', ''))}</dc:source>
    <dc:publisher>{_xml_escape(meta.get('site', ''))}</dc:publisher>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>'''

    nav = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Contents</title></head>
  <body><nav epub:type="toc"><ol><li><a href="chapter1.xhtml">{title}</a></li></ol></nav></body>
</html>'''

    container = '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        # mimetype must be first and STORED, per the epub spec.
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip',
                   compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container)
        z.writestr('OEBPS/content.opf', opf)
        z.writestr('OEBPS/nav.xhtml', nav)
        z.writestr('OEBPS/chapter1.xhtml', chapter)

    return out_path
