"""book_preflight.py - automatic pre-render audit of a lane bundle (no GPU, no LLM).

Every defect found by hand during the first two books (Say Nothing, Armed Struggle) is a rule
here, so the NEXT book fails fast and loudly BEFORE any GPU time is spent instead of being
discovered by listening:

  ERRORS (job is refused, nothing is spent)
    no-chapters       the filter left nothing
    leaked-filename   a chunk starts with a file name / title leak ("Say-8", "index_split_013")
    duplicate         two chapters carry the same text (an untitled duplicate file)
    matter-in-body    a kept chapter is named like Notes/Index/Bibliography/Contents/Copyright
    junk-heavy        > 1 % of sentences are URLs, e-mails, ISBNs, photo credits or symbol soup
    tiny-book         < 300 words in total (almost certainly a bad extraction)
  WARNINGS (job runs; they are written to the job log and the QA report)
    giant-chapter     a chapter > 4x the median (a notes/index section that slipped through)
    tiny-chapter      a chapter < 150 words that is not a prologue/preface/epigraph
    digits            bare digit runs survive prep (the recipe's hard rule is zero)
    junk-sentences    a few URL/credit/symbol sentences (listed)
    long-chunks       chunks at the model's ceiling (listed count)
  INFO
    estimated audio hours, GPU hours and Colab compute units; names the lexicon does not know.

``audit(manifest, payloads)`` is pure; ``format_report`` renders it for logs.
"""
from __future__ import annotations

import hashlib
import re
import statistics

HOURS_PER_AUDIO_HOUR = {"higgs": 1.4, "fish": 2.7}     # measured RTFs (L4)
UNITS_PER_GPU_HOUR = 1.54                               # Colab L4, measured
WORDS_PER_AUDIO_HOUR = 150 * 60

_LEAK = re.compile(r"^(?:[A-Za-z]+-\d+\b|index[_ -]?split|part\d+|chapter\d+\.x?html|[\w-]+\.x?html?\b)", re.I)
_MATTER_TITLE = re.compile(
    r"^(notes?( and references)?|endnotes?|references|(select(ed)? )?bibliography|index|contents|"
    r"table of contents|copyright|acknowledge?ments?|list of .*)$", re.I)
_JUNK = {
    "url": re.compile(r"https?://|www\.[a-z0-9-]+\.", re.I),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "isbn": re.compile(r"\bISBN\b|\b97[89][- ]?\d{1,5}[- ]?\d+", re.I),
    "credit": re.compile(r"\((?:[^()]*[/,] ?)?(?:AP|PA|Getty|Alamy|Reuters|Corbis|Shutterstock|REX|Mirrorpix)\b[^()]*\)\s*$", re.I),
    "symbols": re.compile(r"[<>{}|\\_~^*#@]{2,}|[<>{}|]"),
}
_BARE_DIGITS = re.compile(r"(?<![A-Za-z0-9])\d+(?![A-Za-z])")
_OK_SHORT = re.compile(r"(prologue|preface|foreword|introduction|epigraph|afterword|epilogue|conclusion|dedication)", re.I)


def _sentences(payload: dict) -> list[str]:
    return [s["text"] for s in payload.get("sents", [])]


def audit(manifest: dict, payloads: dict) -> dict:
    errors, warnings, info = [], [], {}
    chapters = manifest.get("chapters", [])
    engine = manifest.get("engine", "fish")

    if not chapters:
        errors.append({"rule": "no-chapters", "msg": "nothing left to render after the matter filter"})
        return {"ok": False, "errors": errors, "warnings": warnings, "info": info}

    words = [int(c.get("words") or 0) for c in chapters]
    total_words = sum(words)
    # Only a near-empty extraction is refused: a deliberate single-chapter render (~1,000 words) is legitimate.
    if total_words < 300:
        errors.append({"rule": "tiny-book", "msg": f"only {total_words} words in total"})

    # duplicates (same text under two spine entries)
    seen: dict[str, str] = {}
    for c in chapters:
        txt = re.sub(r"\W+", " ", " ".join(_sentences(payloads[c["slug"]]))).lower().strip()
        if len(txt) < 200:
            continue
        h = hashlib.sha1(txt.encode("utf-8")).hexdigest()
        if h in seen:
            errors.append({"rule": "duplicate", "msg": f"{c['slug']} '{c['title']}' has the same text as {seen[h]}"})
        seen[h] = c["slug"]

    junk_total, sent_total, junk_examples = 0, 0, []
    digits = []
    long_chunks = 0
    for c in chapters:
        p = payloads[c["slug"]]
        sents = _sentences(p)
        sent_total += len(sents)
        first = (p.get("chunks") or [{"text": sents[0] if sents else ""}])[0]["text"]
        if _LEAK.match(first.strip()):
            errors.append({"rule": "leaked-filename",
                           "msg": f"{c['slug']} starts with a file-name style leak: {first[:60]!r}"})
        if _MATTER_TITLE.match(str(c.get("title") or "").strip()):
            errors.append({"rule": "matter-in-body", "msg": f"{c['slug']} is titled {c['title']!r}"})
        for i, t in enumerate(sents):
            for kind, rx in _JUNK.items():
                if rx.search(t):
                    junk_total += 1
                    if len(junk_examples) < 8:
                        junk_examples.append(f"{c['slug']}#{i + 1} [{kind}] {t[:70]}")
                    break
            for m in _BARE_DIGITS.finditer(t):
                digits.append(f"{c['slug']}#{i + 1}: {m.group(0)}")
        long_chunks += sum(1 for ch in p.get("chunks", []) if ch.get("words", 0) >= 70)

    # An ISBN / URL / imprint line in the first chapters is a copyright page about to be read aloud.
    imprint = re.compile(r"\bISBN\b|www\.[a-z0-9-]+\.|first published|all rights reserved|©", re.I)
    for c in chapters[:3]:
        hits = [t for t in _sentences(payloads[c["slug"]])[:40] if imprint.search(t)]
        if hits:
            errors.append({"rule": "front-matter-leak",
                           "msg": f"{c['slug']} '{c['title'][:30]}' contains an imprint/ISBN/URL line "
                                  f"(a copyright page would be narrated): {hits[0][:60]!r}"})
    if sent_total and junk_total / sent_total > 0.01:
        errors.append({"rule": "junk-heavy",
                       "msg": f"{junk_total}/{sent_total} sentences look like URLs/credits/symbols",
                       "examples": junk_examples})
    elif junk_total:
        warnings.append({"rule": "junk-sentences", "msg": f"{junk_total} URL/credit/symbol-like sentence(s)",
                         "examples": junk_examples})
    if digits:
        warnings.append({"rule": "digits", "msg": f"{len(digits)} bare digit run(s) survive prep",
                         "examples": digits[:8]})

    med = statistics.median(words)
    for c, w in zip(chapters, words):
        if med and w > 4 * med and len(chapters) >= 5:
            warnings.append({"rule": "giant-chapter",
                             "msg": f"{c['slug']} '{c['title'][:40]}' is {w} words (median {int(med)})"})
        if w < 150 and not _OK_SHORT.search(str(c.get("title") or "")):
            warnings.append({"rule": "tiny-chapter", "msg": f"{c['slug']} '{c['title'][:40]}' is only {w} words"})
    if long_chunks:
        info["chunks_at_ceiling"] = long_chunks

    audio_h = total_words / WORDS_PER_AUDIO_HOUR
    gpu_h = audio_h * HOURS_PER_AUDIO_HOUR.get(engine, 2.7)
    info.update({"words": total_words, "chapters": len(chapters), "audio_hours": round(audio_h, 1),
                 "gpu_hours": round(gpu_h, 1), "colab_units": round(gpu_h * UNITS_PER_GPU_HOUR + 0.5, 1)})
    return {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}


def format_report(rep: dict) -> str:
    i = rep["info"]
    lines = []
    if i.get("words"):
        lines.append(f"preflight: {i['chapters']} chapters, {i['words']} words, ~{i['audio_hours']} h audio, "
                     f"~{i['gpu_hours']} GPU-h (~{i['colab_units']} Colab units)")
    for e in rep["errors"]:
        lines.append(f"  ERROR   {e['rule']}: {e['msg']}")
        lines.extend(f"            {x}" for x in e.get("examples", [])[:4])
    for w in rep["warnings"]:
        lines.append(f"  warning {w['rule']}: {w['msg']}")
        lines.extend(f"            {x}" for x in w.get("examples", [])[:3])
    lines.append("preflight: " + ("PASS" if rep["ok"] else "REFUSED - nothing was rendered or spent"))
    return "\n".join(lines)
