import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "webapp"))

from build_listening_excerpt import build_excerpt  # noqa: E402
from chapters import _title_for, list_renderable_chapters  # noqa: E402


def _source(path: Path, count: int = 400) -> None:
    words = " ".join(f"word{number}" for number in range(count))
    chapter = f"<html><body><h1>One</h1><p>{words}</p></body></html>"
    opf = """<package><manifest><item id="c1" href="c1.xhtml"/></manifest>
    <spine><itemref idref="c1"/></spine></package>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.opf", opf)
        archive.writestr("c1.xhtml", chapter)


def _paragraph_source(path: Path) -> None:
    first = " ".join(f"alpha{number}" for number in range(130))
    second = " ".join(f"beta{number}" for number in range(130))
    chapter = f"<html><body><h1>One</h1><p>{first}</p><p>{second}</p></body></html>"
    opf = """<package><manifest><item id="c1" href="c1.xhtml"/></manifest>
    <spine><itemref idref="c1"/></spine></package>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.opf", opf)
        archive.writestr("c1.xhtml", chapter)


def test_builds_exact_hashed_renderable_excerpt(tmp_path):
    source = tmp_path / "source.epub"
    output = tmp_path / "excerpt.epub"
    _source(source)

    manifest = build_excerpt(source, output, words=250, chapter=1)

    assert manifest["excerpt_words"] == 250
    assert manifest["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert manifest["epub_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert list_renderable_chapters(output)[0]["words"] == 250
    assert json.loads(output.with_suffix(".manifest.json").read_text()) == manifest


def test_rejects_excerpt_longer_than_chapter(tmp_path):
    source = tmp_path / "source.epub"
    _source(source, count=150)

    try:
        build_excerpt(source, tmp_path / "excerpt.epub", words=151, chapter=1)
    except ValueError as exc:
        assert "only 150 words" in str(exc)
    else:
        raise AssertionError("expected a short chapter to be rejected")


def test_excerpt_preserves_source_paragraph_boundary(tmp_path):
    source = tmp_path / "source.epub"
    output = tmp_path / "excerpt.epub"
    _paragraph_source(source)

    manifest = build_excerpt(source, output, words=200, chapter=1)

    with zipfile.ZipFile(output) as archive:
        chapter = archive.read("OEBPS/chapter1.xhtml").decode("utf-8")
    assert manifest["excerpt_words"] == 200
    assert "</p>\n    <p>beta0" in chapter


def test_title_selection_ignores_project_gutenberg_wrapper_heading():
    html = '''<html><body>
    <div id="pg-header"><h1>The Project Gutenberg eBook of A Story</h1></div>
    <h1>A Story</h1><p>The real book begins here.</p>
    </body></html>'''
    assert _title_for(html, "fallback") == "A Story"
