"""Safe aggregation for chapter-level structural QA reports.

Every render session may cover only a subset of a book.  A new report must
therefore be merged by chapter number; replacing the file makes an incomplete
recovery session look like whole-book verification.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def merge_qa_reports(current: dict | None, incoming: dict | None) -> dict:
    current = current or {}
    incoming = incoming or {}
    chapters: dict[int, dict] = {}
    for report in (current, incoming):
        for chapter in report.get("chapters") or []:
            if chapter.get("chapter") is not None:
                chapters[int(chapter["chapter"])] = chapter

    merged_chapters = [chapters[number] for number in sorted(chapters)]
    suggestions = {}
    suggestions.update(current.get("lexicon_suggestions") or {})
    suggestions.update(incoming.get("lexicon_suggestions") or {})

    merged = dict(current or incoming)
    merged.update(incoming)
    merged.update({
        "chapters": merged_chapters,
        "flagged_chapters": [
            chapter["chapter"] for chapter in merged_chapters
            if chapter.get("flagged")
        ],
        "lexicon_suggestions": suggestions,
    })
    return merged


def read_qa_report(path: str | Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def write_qa_report_atomic(path: str | Path, report: dict) -> None:
    destination = Path(path)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary.replace(destination)


def merge_qa_report_files(incoming_path: str | Path,
                          destination_path: str | Path) -> dict:
    incoming = read_qa_report(incoming_path)
    current = read_qa_report(destination_path)
    merged = merge_qa_reports(current, incoming)
    write_qa_report_atomic(destination_path, merged)
    return merged
