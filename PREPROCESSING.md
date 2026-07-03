# Text Preprocessing Pipeline

**Status: mandatory.** Whatever voice engine a job uses, its text goes through
this pipeline first. Direction set 2026-07 after the Abundance test proved the
worst listening problems were text defects, not voice defects.

## Why this exists

A listening test on *Abundance* (Klein/Thompson) traced the main quality
complaints to text handling, not the TTS engine:

1. **Endnote markers read aloud.** Publishers attach endnote numbers inside
   `<sup><a>33</a></sup>` tags. Flattened to text they become
   `...inflation.33 But...` and the narrator says "thirty-three".
2. **Upstream `--remove_endnotes` corrupts real numbers.** The p0n1 converter's
   endnote regex strips any digits after a letter or period: `$2.58` becomes
   `$2.`, `B12` becomes `B`, while *missing* markers after curly quotes
   (`consultant.”35`). We no longer pass that flag anywhere.
3. **Unicode junk.** Hair spaces, soft hyphens, and zero-width characters
   confuse TTS chunking and pronunciation.

## Pipeline stages

All stages run in `webapp/tts_preprocess.py` (called from `convert_book` in
`webapp/app.py`), producing a `<book>_tts.epub` copy. The original file is
never modified. If preprocessing fails, conversion falls back to the original
file and logs a warning. The crash-recovery / chapter-retry paths use the same
`_tts.epub`, so recovered chapters get identical text.

### Stage 1 — Structural sanitization (implemented)

Operates on the EPUB's HTML with BeautifulSoup, so it is immune to quote
styles and publisher typography:

- Remove note **reference markers**: `epub:type="noteref"` /
  `role="doc-noteref"` anchors, `<sup>` elements whose text is a bare number,
  and links whose visible text is a bare/bracketed number.
- Remove note **bodies**: `epub:type` footnote/endnote/rearnote asides and
  sections (`role="doc-footnote"` etc.).
- Conservative by design: `<sup>note</sup>` (words) and normal links survive.

### Stage 2 — Deterministic text normalization (implemented)

Regex/num2words rules applied to text segments:

- Unicode cleanup (exotic spaces → space; soft hyphens/zero-widths removed).
- Leftover flattened endnote digits after sentence punctuation — using
  fixed-width lookbehinds that provably cannot touch decimals or
  alphanumerics (see `tests/test_tts_preprocess.py`).
- Numbers: `1,000,000` → "one million"; years (`1987` → "nineteen
  eighty-seven"); decades; ordinals; percentages.
- Currency incl. scale words: `$33 billion` → "thirty-three billion dollars".
- Abbreviations (`Dr.`, `Sen.`, `i.e.`, `U.S.` …).
- Pacing: em-dashes → commas, ellipsis normalization.

### Stage 3 — Pronunciation rules (implemented)

- LLM-generated lexicon per book (`llm_metadata.generate_lexicon`) applied as
  whole-word replacements during Stage 2.
- `data/uploads/global_pronunciations.conf` + per-job custom regex are passed
  to the converter via `--search_and_replace_file`.

### Stage 4 — Per-book narration profile (planned, next)

The "knows what to do per book" layer. One LLM pass over sampled excerpts
(metadata, TOC, and the highest-difficulty passages by digit/acronym density)
produces a stored, user-reviewable JSON profile:

- **Domain** (e.g. US politics nonfiction vs tech/business) selecting
  normalization style.
- **Entity lexicon** with per-entity decisions: `BART` → word, `WSP` →
  letters, `Vartabedian` → phonetic spelling. Extends the existing lexicon
  generator; compiled into Stage 3 rules so it costs nothing at chunk time
  and is consistent across all chapters.
- **Structural fingerprint**: the endnote marker style detected for *this*
  book, epigraphs, tables — steering Stage 1.
- **Number/unit style** decisions.

### Stage 5 — LLM chunk normalization (planned)

For what rules can't anticipate: each ~4k-char chunk through a flash-class
LLM (same `LLM_API_*` settings; Z AI flash tier is free, Gemini Flash free
tier as fallback — 150–200 requests per book) with the narration profile in
the system prompt. Guardrails: output must be within ±15% length and lose no
sentences, otherwise the original chunk is used. Runs as a queue stage before
TTS, so rate-limit throttling doesn't matter. Feedback loop: ASR fidelity
check failures append to the book's profile; affected chunks re-render.

## Testing

`tests/test_tts_preprocess.py` covers the sanitizer and the normalization
rules, including the regressions that motivated this pipeline (decimals,
alphanumerics, curly-quote endnotes). Run: `python -m pytest tests/`.

## Invariants

- The pipeline must never make text *worse*: every destructive rule needs a
  proof it cannot fire on legitimate content (fixed-width lookbehinds,
  structural selectors) or a fallback to the original text.
- `--remove_endnotes` must never be reintroduced (see defect list above).
- The original upload is never modified; `_tts.epub` is regenerable.
