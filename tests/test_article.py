"""URL ingest: extraction quality and the epub handoff (#36).

The design bet is that an article becomes a one-chapter epub and then needs no
special case anywhere downstream. These tests guard both halves of that: that
extraction actually finds the article rather than the furniture, and that the
epub it produces round-trips through the same metadata reader books use.
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import pytest  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from article import (_extract_body, article_to_epub, fetch_article,  # noqa: E402
                     ExtractionError)
from book_meta import read_book_meta  # noqa: E402

PROSE = "The harbour road was quiet at that hour, though not entirely still. "


def _page(body_html: str) -> BeautifulSoup:
    return BeautifulSoup(f'<html><head><title>T</title></head><body>{body_html}</body></html>', 'lxml')


class TestExtraction:
    def test_finds_the_article_not_the_furniture(self):
        soup = _page(f"""
            <nav><a href=/>Home</a><a href=/n>News</a><a href=/s>Sport</a></nav>
            <div class="sidebar"><p>Related stories you might possibly enjoy reading next</p></div>
            <article><p>{PROSE * 6}</p></article>
            <footer><p>Copyright, cookie notice, all rights reserved forever</p></footer>""")
        body = _extract_body(soup)
        assert 'harbour road' in body
        assert 'Sport' not in body
        assert 'Related stories' not in body
        assert 'Copyright' not in body

    def test_subheadings_survive_the_length_filter(self):
        """Short headings are structure, not noise — an early cut dropped them."""
        soup = _page(f'<article><p>{PROSE*6}</p><h2>A subheading</h2><p>{PROSE*6}</p></article>')
        assert 'A subheading' in _extract_body(soup)

    def test_noise_pattern_never_eats_the_whole_document(self):
        """The bug that returned zero words on Wikipedia.

        Wikipedia puts `vector-feature-language-in-header-enabled` on <html>.
        That contains "header", so the noise pattern matched the ROOT element
        and decompose() deleted the entire page. Guarding html/body is the
        fix; this test is the reason it must stay.
        """
        soup = BeautifulSoup(
            '<html class="vector-feature-language-in-header-enabled">'
            f'<body class="page-header-thing"><article><p>{PROSE*6}</p></article></body></html>',
            'lxml')
        assert 'harbour road' in _extract_body(soup)

    def test_a_wrapper_holding_the_article_is_not_stripped(self):
        """Furniture does not contain the article. A div named like furniture
        but holding most of the paragraphs is a wrapper, and must survive."""
        soup = _page(f'<div class="page-header"><p>{PROSE*6}</p><p>{PROSE*6}</p></div>')
        assert 'harbour road' in _extract_body(soup)

    def test_genuine_furniture_is_still_stripped(self):
        """The guard must not have disarmed the whole mechanism."""
        soup = _page(f"""
            <div class="sidebar"><p>Related stories you might enjoy reading later on</p></div>
            <article><p>{PROSE*6}</p><p>{PROSE*6}</p><p>{PROSE*6}</p></article>""")
        body = _extract_body(soup)
        assert 'harbour road' in body
        assert 'Related stories' not in body

    def test_link_heavy_blocks_lose_to_prose(self):
        soup = _page(f"""
            <div><p><a href=/1>One</a> <a href=/2>Two</a> <a href=/3>Three</a>
                 <a href=/4>Four</a> <a href=/5>Five</a> <a href=/6>Six link text here</a></p></div>
            <div><p>{PROSE * 6}</p></div>""")
        assert 'harbour road' in _extract_body(soup)

    def test_short_pages_are_refused_with_a_useful_message(self, monkeypatch):
        class R:
            status_code, headers = 200, {'Content-Type': 'text/html'}
            # bytes, not text: fetch_article parses r.content so that lxml can
            # honour the document's own charset instead of requests guessing.
            content = b'<html><body><p>Too short.</p></body></html>'
            def raise_for_status(self): pass
        monkeypatch.setattr('article.requests.get', lambda *a, **k: R())
        monkeypatch.setattr('article.socket.getaddrinfo',
                            lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 443))])
        with pytest.raises(ExtractionError) as e:
            fetch_article('https://example.com/x')
        msg = str(e.value).lower()
        assert 'paywall' in msg or 'javascript' in msg

    def test_non_html_is_refused(self, monkeypatch):
        class R:
            status_code, headers = 200, {'Content-Type': 'application/pdf'}
            content = b''
            def raise_for_status(self): pass
        monkeypatch.setattr('article.requests.get', lambda *a, **k: R())
        monkeypatch.setattr('article.socket.getaddrinfo',
                            lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 443))])
        with pytest.raises(ExtractionError) as e:
            fetch_article('https://example.com/x.pdf')
        assert 'pdf' in str(e.value).lower()

    def test_scheme_is_validated(self):
        with pytest.raises(ExtractionError):
            fetch_article('ftp://example.com/x')

    def test_private_network_destination_is_refused_before_fetch(self, monkeypatch):
        called = False

        def should_not_fetch(*_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError('private destination reached requests')

        monkeypatch.setattr('article.requests.get', should_not_fetch)
        with pytest.raises(ExtractionError, match='local network'):
            fetch_article('http://127.0.0.1:8881/api/settings')
        assert called is False

    def test_redirect_to_private_network_is_refused(self, monkeypatch):
        class Redirect:
            status_code = 302
            headers = {'Location': 'http://192.168.1.41:8881/api/settings'}

            def close(self):
                pass

        def resolve(host, port, **_kwargs):
            ip = '93.184.216.34' if host == 'example.com' else '192.168.1.41'
            return [(2, 1, 6, '', (ip, port))]

        monkeypatch.setattr('article.socket.getaddrinfo', resolve)
        monkeypatch.setattr('article.requests.get', lambda *a, **k: Redirect())
        with pytest.raises(ExtractionError, match='local network'):
            fetch_article('https://example.com/redirect')


class TestTitle:
    """The title becomes the book title, the filename and the ID3 tag."""

    def test_site_suffix_is_dropped(self):
        from article import _strip_site_suffix
        assert _strip_site_suffix('Audiobook - Wikipedia', 'en.wikipedia.org') == 'Audiobook'
        assert _strip_site_suffix('My Post | Site', 'site.com') == 'My Post'

    def test_subdomains_and_cctlds_resolve(self):
        """split('.')[0] gave "en" for en.wikipedia.org, so the suffix stayed."""
        from article import _strip_site_suffix
        assert _strip_site_suffix('Lewis Carroll - Wikipedia', 'en.wikipedia.org') == 'Lewis Carroll'
        assert _strip_site_suffix('Some story | BBC', 'www.bbc.co.uk') == 'Some story'

    def test_a_real_dash_in_a_title_survives(self):
        from article import _strip_site_suffix
        t = 'A piece about dashes - and more'
        assert _strip_site_suffix(t, 'theguardian.com') == t

    def test_partial_site_match_is_not_stripped(self):
        from article import _strip_site_suffix
        t = 'Some story - BBC News'          # tail is "BBC News", not "bbc"
        assert _strip_site_suffix(t, 'www.bbc.co.uk') == t


class TestEpubHandoff:
    """The point of generating an epub is that nothing downstream changes."""

    def _build(self, tmp_path, **over):
        meta = {'title': 'Alice & the <Rabbit>', 'author': 'Lewis Carroll',
                'text': 'One paragraph here.\n\nAnd a second one.',
                'url': 'https://example.com/a?b=1&c=2', 'site': 'Example',
                'date': '2026-07-27'}
        meta.update(over)
        p = tmp_path / 'a.epub'
        article_to_epub(meta, p)
        return p

    def test_produces_a_valid_epub(self, tmp_path):
        p = self._build(tmp_path)
        z = zipfile.ZipFile(p)
        assert z.testzip() is None
        # The spec requires mimetype first and uncompressed.
        assert z.namelist()[0] == 'mimetype'
        assert z.getinfo('mimetype').compress_type == zipfile.ZIP_STORED

    def test_metadata_round_trips_through_the_shared_reader(self, tmp_path):
        m = read_book_meta(self._build(tmp_path))
        assert m['title'] == 'Alice & the <Rabbit>'      # not &amp; / &lt;
        assert m['author'] == 'Lewis Carroll'
        assert m['publisher'] == 'Example'
        assert m['year'] == '2026'

    def test_xml_special_chars_do_not_corrupt_the_package(self, tmp_path):
        p = self._build(tmp_path, title='A & B < C > D "quoted"',
                        text='Text with & and < inside.')
        assert read_book_meta(p)['title'] == 'A & B < C > D "quoted"'

    def test_missing_author_still_yields_a_readable_book(self, tmp_path):
        m = read_book_meta(self._build(tmp_path, author=''))
        assert m['title']
        assert 'author' in m


class TestPodcastRSS:
    def test_generate_podcast_rss_valid_xml(self):
        from article import generate_podcast_rss
        items = [{
            'title': 'Test Article',
            'author': 'Test Author',
            'site': 'Ars Technica',
            'url': 'https://arstechnica.com/test',
            'audio_url': '/data/audiobooks/test.mp3',
            'file_size': 1234567,
            'date_str': '2026-08-09',
            'guid': 'job123'
        }]
        xml = generate_podcast_rss('Ars Technica', items, 'https://myhost.com')
        assert '<rss version="2.0"' in xml
        assert '<title>Ars Technica</title>' in xml
        assert '<title>Test Article</title>' in xml
        assert 'url="https://myhost.com/data/audiobooks/test.mp3"' in xml
        assert 'length="1234567"' in xml
        assert '<pubDate>Sun, 09 Aug 2026 00:00:00 GMT</pubDate>' in xml
