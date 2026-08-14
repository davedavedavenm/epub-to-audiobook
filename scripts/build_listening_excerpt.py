#!/usr/bin/env python3
"""Build a repeatable, single-chapter EPUB for long-form listening tests.

The source is a real renderable chapter selected by the same chapter parser as
the production converter.  The output manifest records the source file hash,
chapter number, exact excerpt word count, and excerpt hash so two engines can
be compared against identical text without committing the book or generated
audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webapp"))

from article import article_to_epub  # noqa: E402
from chapters import _plain_text, list_renderable_chapters  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _truncate_words_preserving_paragraphs(text: str, limit: int) -> str:
    """Take exactly *limit* words without flattening source paragraph breaks."""
    remaining = limit
    kept: list[str] = []
    for paragraph in text.split("\n\n"):
        words = paragraph.split()
        if not words:
            continue
        take = words[:remaining]
        if take:
            kept.append(" ".join(take))
            remaining -= len(take)
        if remaining == 0:
            break
    return "\n\n".join(kept)


def build_excerpt(source: Path, output: Path, words: int, chapter: int) -> dict:
    chapters = list_renderable_chapters(source)
    selected = next((item for item in chapters if item["index"] == chapter), None)
    if selected is None:
        available = ", ".join(str(item["index"]) for item in chapters) or "none"
        raise ValueError(f"chapter {chapter} is not renderable; available: {available}")

    with zipfile.ZipFile(source) as archive:
        text = _plain_text(archive.read(selected["href"]).decode("utf-8", "ignore"))
    excerpt = _truncate_words_preserving_paragraphs(text, words)
    excerpt_words = excerpt.split()
    if len(excerpt_words) < words:
        raise ValueError(
            f"chapter {chapter} has only {len(excerpt_words)} words; requested {words}"
        )
    excerpt_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()

    title = f"Listening Gate — {source.stem} — Chapter {chapter} — {words} words"
    article_to_epub(
        {
            "title": title,
            "author": "Evaluation copy",
            "site": "epub-to-audiobook listening gate",
            "url": f"sha256:{sha256(source)}",
            "text": excerpt,
        },
        output,
    )
    manifest = {
        "source_filename": source.name,
        "source_sha256": sha256(source),
        "source_chapter": chapter,
        "source_chapter_title": selected["title"],
        "requested_words": words,
        "excerpt_words": len(excerpt_words),
        "excerpt_sha256": excerpt_hash,
        "epub_filename": output.name,
        "epub_sha256": sha256(output),
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--words", type=int, default=2800)
    parser.add_argument("--chapter", type=int, default=1)
    args = parser.parse_args()
    if args.words < 120:
        parser.error("--words must be at least 120 so the excerpt is renderable")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_excerpt(args.source, args.output, args.words, args.chapter)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
