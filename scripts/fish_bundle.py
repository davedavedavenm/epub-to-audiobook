"""fish_bundle.py — build the as_bundle.zip a Fish lane render consumes.

Canonical text prep lives in ``as_prep.py`` (locked recipe, CILLIAN-RECIPE.md);
this module turns ANY EPUB into the bundle the runner (fish_colab_runner.py)
expects on a lane:

    payloads/<slug>.json    per-chapter sentence payloads {slug,title,sents}
                            (sents carry {text, para, quote} — quote sentences
                            get the expressive reference automatically)
    transcripts/<slug>.txt  source text for the ASR completeness gate
    refs/                   cillian_irish.wav (tracked in the repo),
                            crop_expressive_tail.wav (byte-exact tail of the
                            same clip — verified 2026-09-24), refs.json texts
    manifest.json           book/voice tags, slug -> chapter-index map, the
                            runner's ORDER, recipe parameters, digit-run scan

Chapter numbering comes from webapp/chapters.list_renderable_chapters — the
SAME list the converter and verify_book_complete use, so a lane-rendered book
cannot disagree with the app about how many chapters it has or what they are.

Digit rule (recipe hard rule): any digit run surviving prep will be read
wrongly by TTS. Acronym-style exceptions (MI6, M60) are expected; bare digit
tokens are reported in ``manifest['digit_runs']`` and surfaced in the job log.

CLI:
    python scripts/fish_bundle.py <book.epub> [-o out.zip] [--start N] [--end N]
"""
import html as htmlmod
import json
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(ROOT / "webapp")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from as_prep import load_lexicon, prep  # noqa: E402
import book_preflight  # noqa: E402
import higgs_prep  # noqa: E402

DEFAULT_NARRATION_REF = ROOT / "chatterbox" / "voices" / "cillian_irish.wav"
REF_TEXTS = ROOT / "fixtures" / "fish_ref_texts.json"
# The quote ref is the exact byte tail of the narration clip so a fresh
# checkout reproduces the locked recipe without scratch/ artifacts: the
# deployed crop_expressive_tail.wav is byte-identical to the last 342720
# frames (685440 bytes = 14.28 s) of the tracked 24 kHz mono clip — verified
# by byte comparison, 2026-09-24.
QUOTE_REF_TAIL_FRAMES = 342720
QUOTE_REF_BYTES = QUOTE_REF_TAIL_FRAMES * 2  # mono, 16-bit (24 kHz)

RECIPE = {
    "engine": "fish-s2-pro",
    "temperature": 0.85,
    "seeds": [42, 43, 44],
    "top_p": 0.9,
    "top_k": 30,
    "chunk_length": 300,
    "gap_sentence": 0.18,
    "gap_paragraph": 0.50,
    "mastering": "equalizer=f=220:width_type=o:width=1.2:g=1.0,"
                 "highshelf=f=7500:gain=-2.0:width=1.0,loudnorm=I=-20:TP=-2:LRA=11",
}

RECIPE_HIGGS = {
    "engine": "higgs-tts-3",
    "model": "bosonai/higgs-audio-v3-tts-4b",
    "runtime": "vllm==0.30.0 vllm-omni==0.30.0 (py3.12 venv), bf16, TRITON_ATTN",
    "seeds": [42, 43, 44, 45, 46],
    "chunk_max_words": higgs_prep.MAX_WORDS,
    "gap_chunk": 0.3,
    "gap_paragraph": 0.5,
    "gates": "health, clipping, duration sanity, abrupt end (<=0.25) with seed re-roll",
    "mastering": "gain-only to ~-20 LUFS, sample peak <= -2 dBFS; no EQ, no dynamic loudnorm",
    "allowed_emotions": sorted(higgs_prep.ALLOWED_EMOTIONS),
}

_HEAD = re.compile(r"<head\b.*?</head>", re.I | re.S)
_CHAPTER_NUMBER = re.compile(
    r'<(p|div|span|h[1-6])[^>]*class="[^"]*chapter[_-]?(?:number|num|no)\b[^"]*"[^>]*>\s*(\d{1,3})\s*</\1>',
    re.I | re.S)
_DROP_CAP = re.compile(r'<span[^>]*class="[^"]*dropcap[^"]*"[^>]*>([A-Za-z])</span>')
_TAGS = re.compile(r"<[^>]+>")
# Footnote references (<a href><sup>2</sup></a>, <sup><a>2</a></sup>, bare <sup>2</sup>) are not
# narrated. Inline tags join text instead of breaking it: when every tag became a newline, an empty
# page anchor or a footnote link left a blank line = a paragraph break in the middle of a sentence
# (Armed Struggle Preface: "rigorous fashion, | and the pre-Provisional IRA", each half spoken as a
# finished sentence with a 0.45 s pause - heard by Dave 2026-10-07).
_NOTEREF = re.compile(
    r"<a\b[^>]*>\s*<sup\b[^>]*>\s*[\d*†‡§]{1,4}\s*</sup>\s*</a>"
    r"|<sup\b[^>]*>\s*<a\b[^>]*>\s*[\d*†‡§]{1,4}\s*</a>\s*</sup>"
    r"|<sup\b[^>]*>\s*[\d*†‡§]{1,4}\s*</sup>"
    r"|<a\b[^>]*>\s*\[?[\d*†‡§]{1,4}\]?\s*</a>", re.I)   # a link that is only a number = note/page ref
_INLINE_TAG = re.compile(
    r"</?(?:a|abbr|b|bdi|bdo|big|cite|code|del|dfn|em|font|i|img|ins|kbd|mark|q|s|samp|small|"
    r"span|strike|strong|sub|sup|time|tt|u|var|wbr)\b[^>]*>", re.I)
# Digits attached to uppercase letters are acronym readings the lexicon or
# listener expects verbatim (MI6, M60, B52); a BARE digit run is the defect.
_BARE_DIGITS = re.compile(r"(?<![A-Za-z0-9])\d+(?![A-Za-z])")


def chapter_text(html: str) -> str:
    """Strip a spine doc to plain text exactly like regenerate_as_book.py did
    for the Armed Struggle payloads (dropcaps unwrapped, tags -> newlines)."""
    html = _DROP_CAP.sub(r"\1", html)
    # <head>/<title> is never narrated: Say Nothing's chapter files carry <title>Say-8</title>
    # and the first chunk of the rendered chapter was "Say-eight. An Abduction." (heard by Dave
    # 2026-10-06). The same leak put "Armed Struggle" at the top of every AS chapter.
    html = _HEAD.sub("", html)
    # Publisher chapter-number elements (<p class="chapter_number">1</p>) become "Chapter 1";
    # otherwise the standalone-digit-line filter in as_prep (footnote markers) would delete them.
    html = _CHAPTER_NUMBER.sub(lambda m: f"<p>Chapter {m.group(2)}</p>", html)
    html = _NOTEREF.sub("", html)
    # An inline tag joins its neighbours ("f<span>u</span>n" -> "fun", Why Q Needs U) unless the join
    # would glue a word to a number or a capital ("exhibition<span>8 PM", "Fox</span><span>Local"):
    # those are styled lines, so they keep a space.
    # A 1-3 digit number that is the whole content of an inline tag is a note/page marker
    # ("loathes<span>6</span>", "<span>125</span>an"); the old every-tag-is-a-line text put it on
    # its own line and as_prep dropped it, so drop it here too.
    html = _INLINE_TAG.sub("\x00", html)
    html = re.sub(r"\x00+[ \t]*\d{1,3}[ \t]*\x00+", "\x00", html)
    html = re.sub(r"(?<=[a-z])\x00+(?=[A-Z0-9])|(?<=[A-Z])\x00+(?=[A-Z][a-z])|(?<=[A-Za-z])\x00+(?=\d)",
                  " ", html)
    html = html.replace("\x00", "")
    html = _TAGS.sub("\n", html)
    return re.sub(r"[ \t]{2,}", " ", htmlmod.unescape(html))   # "See <a>7</a> below" -> "See below"


# Front/back matter is never narrated. Found on Say Nothing (2026-10-06): the chapter
# detector listed Copyright, Contents, Acknowledgements, Notes (23k words), an untitled
# 26k-word duplicate, Bibliography and Index as chapters = ~7 h of wasted GPU audio.
_SKIP_TITLE = re.compile(
    r"^(copyright(\s+page)?|contents|table of contents|title page|half[- ]?title|cover|"
    r"list of (abbreviations|illustrations|plates|maps|figures|tables)|abbreviations|"
    r"dedication|also by .*|by the same author|about the authors?|praise for .*|"
    r"acknowledge?ments?|notes?( and references)?|references|endnotes?|(a )?notes? on (the )?(sources?|text)|"
    r"(select(ed)? )?bibliography|further reading|sources|index|permissions|credits|"
    r"(photo(graph)? )?credits|(list of )?illustrations|maps?|glossary|colophon)$",
    re.I)
# Once one of these appears after real chapters, nothing that follows is narrative.
_CUT_TITLE = re.compile(
    r"^(acknowledge?ments?|notes?( and references)?|references|endnotes?|(a )?notes? on (the )?(sources?|text)|"
    r"(select(ed)? )?bibliography|further reading|sources|index|about the authors?)$",
    re.I)


def spine_chapters(epub_path) -> list:
    """Chapter list built straight from the EPUB spine, for books where the app's chapter detector
    finds nothing (5 of 187 library books, e.g. The War of Art, Interpreter of Maladies). Each
    reading-order document with >= 100 words becomes a chapter; the title is its first heading."""
    import posixpath
    import xml.etree.ElementTree as ET
    from urllib.parse import unquote
    out = []
    with zipfile.ZipFile(epub_path) as z:
        names = set(z.namelist())
        try:
            root = ET.fromstring(z.read("META-INF/container.xml"))
            opf_path = next(e.get("full-path") for e in root.iter() if e.tag.endswith("rootfile"))
            opf = ET.fromstring(z.read(opf_path))
        except Exception:
            return []
        base = posixpath.dirname(opf_path)
        items, mtypes = {}, {}
        for e in opf.iter():
            if e.tag.endswith("}item") or e.tag == "item":
                items[e.get("id")] = e.get("href")
                mtypes[e.get("id")] = (e.get("media-type") or "").lower()
        order = [e.get("idref") for e in opf.iter() if e.tag.endswith("itemref") and e.get("linear") != "no"]
        for idref in order:
            href = items.get(idref)
            if not href:
                continue
            path = posixpath.normpath(posixpath.join(base, unquote(href)))
            # trust the declared media type, not the extension (books ship content as .xml or .html_split_000)
            if path not in names or mtypes.get(idref) not in ("application/xhtml+xml", "text/html"):
                continue
            raw = z.read(path).decode("utf-8", errors="replace")
            text = chapter_text(raw)
            words = len(text.split())
            if words < 100:
                continue
            m = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", raw, re.I | re.S)
            title = re.sub(r"<[^>]+>", " ", m.group(1)) if m else ""
            title = re.sub(r"\s+", " ", htmlmod.unescape(title)).strip() or f"Chapter {len(out) + 1}"
            out.append({"index": len(out) + 1, "title": title[:120], "words": words, "href": path,
                        "snippet": " ".join(text.split()[:60]), "back_matter": False})
    return out


_IMPRINT_LINE = re.compile(
    r"first published|this (electronic |paperback )?edition published|all rights reserved|ISBN|"
    r"©|printed (in|by)|cataloguing[- ]in[- ]publication|www[.][a-z0-9-]+[.]|"
    r"copyright\s*(©|[(]c[)]|[0-9]|by\b)|moral right|library of congress|british library", re.I)


_IMPRINT_STRONG = re.compile(r"all rights reserved|moral right|ISBN|reproduced|publication data|www[.]", re.I)


def strip_imprint(payloads: dict, slugs: list, first_n: int = 3, scan: int = 60) -> int:
    """Remove copyright/imprint SENTENCES from the first chapters (short lines only), in place.
    8 of 187 library books kept their copyright page as a chapter; stripping the lines is safer than
    refusing the book. Returns how many sentences were removed."""
    removed = 0
    for slug in slugs[:first_n]:
        sents = payloads[slug]["sents"]
        keep = []
        for i, s in enumerate(sents):
            n_words = len(s["text"].split())
            if i < scan and _IMPRINT_LINE.search(s["text"]) and (
                    n_words < 45 or (n_words < 130 and _IMPRINT_STRONG.search(s["text"]))):
                removed += 1
                continue
            keep.append(s)
        payloads[slug]["sents"] = keep
    return removed


# Copyright / imprint pages are recognised by their TEXT, not only their title: a webapp job's file
# name ("81b98898_Armed Struggle - Richard English.epub") defeats title matching, and the first
# Armed Struggle web run would have narrated "www.panmacmillan.com" and the ISBN (2026-10-06).
_FRONT_SNIPPET = re.compile(
    r"first published|this (electronic |paperback )?edition published|all rights reserved|\bISBN\b|"
    r"©|printed (in|by)|cataloguing[- ]in[- ]publication|www\.[a-z0-9-]+\.(com|co\.uk|org)",
    re.I)
NARRATIVE_WORDS_BEFORE_CUT = 8000   # back matter is only recognised after this much real text
MIN_KEPT_FRACTION = 0.5             # refuse to drop more than half of a book


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def filter_matter(chapter_list: list, keep_matter: bool = False,
                  book_title: str | None = None) -> tuple[list, list]:
    """(narrative chapters, skipped [{title, why}]). A chapter list is in spine order.

    Titles decide what is front/back matter; word counts (``c['words']``) decide WHEN the
    back matter starts. The first version counted entries ("3 chapters seen") instead of
    words, so on Armed Struggle the title page, copyright page and list of abbreviations
    counted as chapters, "Acknowledgments" then triggered the cut, and EVERY real chapter was
    dropped (1,767 words left). Hence: a cut needs >= NARRATIVE_WORDS_BEFORE_CUT words of
    narrative first, and the whole filter raises rather than discard more than half the book.
    """
    if keep_matter:
        return list(chapter_list), []
    title_key = _norm_title(book_title or "")
    # A title shared by 3+ chapters ("index", "index", "index"...) is a FILE NAME leaking through
    # (Bonfire of the Vanities: 8 body files called index_split_00x), not matter.
    from collections import Counter
    repeated = {t for t, n in Counter(_norm_title(c.get("title")) for c in chapter_list).items()
                if t and n >= 3}
    kept, skipped, narrative_words = [], [], 0
    total = sum(int(c.get("words") or 0) for c in chapter_list) or 1
    for pos, c in enumerate(chapter_list):
        title = re.sub(r"\s+", " ", str(c.get("title") or "")).strip()
        words = int(c.get("words") or 0)
        is_repeated = _norm_title(title) in repeated
        if (narrative_words >= NARRATIVE_WORDS_BEFORE_CUT and not is_repeated
                and (_CUT_TITLE.match(title) or c.get("back_matter"))):
            skipped.extend({"title": str(x.get("title") or ""), "why": "back matter (cut)"}
                           for x in chapter_list[pos:])
            break
        if _SKIP_TITLE.match(title) and not is_repeated:
            skipped.append({"title": title, "why": "front/back matter"})
            continue
        if (narrative_words < NARRATIVE_WORDS_BEFORE_CUT and words < 3000
                and _FRONT_SNIPPET.search(str(c.get("snippet") or ""))):
            skipped.append({"title": title, "why": "imprint/copyright page"})
            continue
        # Title/half-title/copyright pages carry the BOOK'S title before any real text.
        if (narrative_words < NARRATIVE_WORDS_BEFORE_CUT and words < 3000 and title_key
                and _norm_title(title) and title_key.startswith(_norm_title(title))):
            skipped.append({"title": title, "why": "title page"})
            continue
        kept.append(c)
        narrative_words += words
    kept_words = sum(int(c.get("words") or 0) for c in kept)
    if kept_words < MIN_KEPT_FRACTION * total:
        raise ValueError(
            f"front/back-matter filter would keep only {kept_words}/{total} words "
            f"({100 * kept_words // total}%) - refusing; inspect the chapter list "
            f"or pass keep_matter=True")
    return kept, skipped


def _tagify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "book").lower()).strip("_")
    return s[:48] or "book"


def read_refs(narration_ref: Path | None = None) -> tuple[bytes, bytes, dict]:
    """(narration wav bytes, quote wav bytes, ref texts dict).

    The quote ref is the exact tail of the narration clip's PCM frames, so a
    fresh checkout reproduces the locked recipe without scratch/ artifacts.
    (Raw byte tails are wrong: the clip carries a trailer chunk after the data
    chunk — frames must be read through the wave module. Verified 2026-09-24.)
    Override either path with FISH_NARRATION_REF / FISH_QUOTE_REF.
    """
    import io
    import wave

    narr = Path(narration_ref or os_env("FISH_NARRATION_REF") or DEFAULT_NARRATION_REF)
    quote_override = os_env("FISH_QUOTE_REF")
    if not narr.is_file():
        raise FileNotFoundError(f"narration reference not found: {narr}")
    data = narr.read_bytes()
    if quote_override:
        quote = Path(quote_override).read_bytes()
    else:
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError(f"{narr.name}: expected mono 16-bit PCM to derive "
                                 f"the quote crop (set FISH_QUOTE_REF instead)")
            frames = w.readframes(w.getnframes())
        if len(frames) < QUOTE_REF_BYTES:
            raise ValueError(f"{narr.name} is shorter than the quote-crop tail "
                             f"({len(frames)} < {QUOTE_REF_BYTES} bytes of frames)")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(24000)
            out.writeframes(frames[-QUOTE_REF_BYTES:])
        quote = buf.getvalue()
    texts = json.loads(REF_TEXTS.read_text(encoding="utf-8")) if REF_TEXTS.exists() else {}
    return data, quote, texts


def os_env(key: str) -> str:
    import os
    return (os.environ.get(key) or "").strip()


def scan_digit_runs(payloads: dict) -> list:
    """Bare digit runs left in prepped text — the recipe's hard rule is zero
    (exceptions are alphabetic-anchored acronyms, which this regex spares)."""
    found = []
    for slug, payload in payloads.items():
        for i, s in enumerate(payload["sents"], 1):
            for m in _BARE_DIGITS.finditer(s["text"]):
                found.append({"slug": slug, "sent": i, "text": s["text"][:80],
                              "digit": m.group(0)})
    return found


def build_bundle(epub_path, out_zip, title: str | None = None,
                 start: int | None = None, end: int | None = None,
                 narration_ref: Path | None = None, engine: str = "fish",
                 tagger=None, keep_matter: bool = False, chunk_max_words: int | None = None) -> dict:
    """Build the bundle zip at *out_zip* and return the manifest dict.

    *start*/*end* are 1-based renderable-chapter indexes (the same numbering
    the job picker shows); None means the whole book.

    *engine* ``"fish"`` (locked Cillian recipe) or ``"higgs"``. For Higgs each payload also
    carries ``chunks`` (scripts/higgs_prep.build_chunks) and the manifest's per-chapter
    ``sents`` is the CHUNK count, because the runner banks and reports progress per chunk.
    *tagger* (optional, Higgs only) is ``callable(sents) -> {sentence_index: emotion}``;
    only emotions in higgs_prep.ALLOWED_EMOTIONS ever reach the audio.
    """
    if engine not in ("fish", "higgs"):
        raise ValueError(f"unknown engine {engine!r}")
    import chapters as _chapters  # webapp/chapters.py (on sys.path)

    epub_path = Path(epub_path)
    out_zip = Path(out_zip)
    lex = load_lexicon()
    chapter_list = _chapters.list_renderable_chapters(str(epub_path))
    if not chapter_list:                       # the app's detector found nothing: read the spine
        chapter_list = spine_chapters(epub_path)
    chapter_list, skipped_matter = filter_matter(chapter_list, keep_matter,
                                                 book_title=re.sub(r"^[0-9a-f]{8}_", "", title or epub_path.stem))

    payloads: dict = {}
    manifest_chapters = []
    with zipfile.ZipFile(epub_path) as z:
        for c in chapter_list:
            idx = int(c["index"])
            if start and idx < start:
                continue
            if end and idx > end:
                continue
            href = c.get("href")
            if not href or href not in z.namelist():
                continue
            raw = chapter_text(z.read(href).decode("utf-8", errors="replace"))
            sents = prep(raw, lex)
            if not sents:
                continue
            slug = f"ch{idx:02d}"
            payloads[slug] = {"slug": slug, "title": c.get("title") or f"Chapter {idx}",
                              "sents": sents}
            n_units = len(sents)
            if engine == "higgs":
                chunks = higgs_prep.build_chunks(sents, max_words=chunk_max_words or higgs_prep.MAX_WORDS)
                tags = tagger(sents) if tagger else None
                for ch in chunks:
                    tagged = higgs_prep.apply_tags(sents, ch, tags)
                    if tagged != ch["text"]:
                        ch["tagged"] = tagged
                payloads[slug]["chunks"] = chunks
                n_units = len(chunks)
            manifest_chapters.append({
                "slug": slug, "index": idx,
                "title": payloads[slug]["title"],
                "sents": n_units,
                "sentences": len(sents),
                "words": sum(len(s["text"].split()) for s in sents),
            })

    if not payloads:
        raise ValueError(f"no renderable chapters found in {epub_path.name} "
                         f"(range start={start} end={end})")

    stripped = strip_imprint(payloads, [c["slug"] for c in manifest_chapters])
    for c in manifest_chapters:
        c["words"] = sum(len(t["text"].split()) for t in payloads[c["slug"]]["sents"])
    digits = scan_digit_runs(payloads)
    manifest = {
        "book": title or _tagify(epub_path.stem),
        "book_tag": _tagify(title or epub_path.stem),
        "engine": engine,
        "voice": "cillian",
        "voice_tag": "cillian_higgs" if engine == "higgs" else "cillian",
        "source": epub_path.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recipe": ({**RECIPE_HIGGS, "chunk_max_words": chunk_max_words or higgs_prep.MAX_WORDS}
                   if engine == "higgs" else RECIPE),
        "chapters": manifest_chapters,
        "skipped": skipped_matter,
        "imprint_sentences_stripped": stripped,
        "digit_runs": digits,
    }

    # Automatic audit BEFORE anything is rendered; the lane refuses the job on errors.
    manifest["preflight"] = book_preflight.audit(manifest, payloads)

    narr, quote, texts = read_refs(narration_ref)

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for slug, payload in payloads.items():
            zf.writestr(f"payloads/{slug}.json",
                        json.dumps(payload, ensure_ascii=False))
            text = " ".join(s["text"] for s in payload["sents"])
            zf.writestr(f"transcripts/{slug}.txt", text)
        zf.writestr("refs/cillian_irish.wav", narr)
        zf.writestr("refs/crop_expressive_tail.wav", quote)
        zf.writestr("refs/refs.json", json.dumps(texts, ensure_ascii=False, indent=1))

    manifest["bundle"] = str(out_zip)
    manifest["bytes"] = out_zip.stat().st_size
    return manifest


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Build a Fish lane render bundle")
    ap.add_argument("epub")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--engine", choices=("fish", "higgs"), default="fish")
    ap.add_argument("--chunk-words", type=int, default=None, help="Higgs chunk ceiling (default higgs_prep.MAX_WORDS)")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else Path(a.epub).with_suffix(".as_bundle.zip")
    m = build_bundle(a.epub, out, title=a.title, start=a.start, end=a.end, engine=a.engine,
                     chunk_max_words=a.chunk_words)
    print(f"bundle: {m['bundle']} ({m['bytes']} bytes)")
    for c in m["chapters"]:
        print(f"  {c['slug']}  {c['sents']:5} sents  {c['words']:6} words  {c['title'][:60]}")
    print(book_preflight.format_report(m["preflight"]))
    if not m["preflight"]["ok"]:
        return 3
    if m["digit_runs"]:
        print(f"WARNING: {len(m['digit_runs'])} bare digit run(s) survive prep:")
        for d in m["digit_runs"][:10]:
            print(f"  {d['slug']}#{d['sent']}: {d['digit']} — {d['text']}")
        return 2
    print("digit scan: clean (no bare digit runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
