# Text Preprocessing Pipeline

**Status: mandatory.** Whatever voice engine a job uses, its text goes through
this pipeline first. Direction set 2026-07 after the Abundance test proved the
worst listening problems were text defects, not voice defects.

---

## ✅ SETTLED BY EAR 2026-07-27 — modern engines get RAW text

> **Edge exception found by ear, 2026-07-28:** the accent was *"not bad"*, but
> all Chinese firms' names were pronounced badly in the Edge audition. Edge uses
> the legacy path and therefore received the current seed respellings, so their
> presence does not prove pronunciation is fixed. Because auditions and books
> share preprocessing, this is a real output-path defect for Chinese-business
> nonfiction. Capture the exact payload and run raw-vs-current Edge A/B before
> changing either the lexicon or engine classification.

The single most-litigated question in this pipeline is closed. Three clips, one
sentence, identical voice and engine, the respelling the only variable:

```
A  The Xiaomi factory in Shenzhen produces components for Huawei.
B  The SHOW-mee factory in SHEN-jen produces components for HWAH-way.
C  The shaow-mee factory in shun-jen produces components for hwah-way.
```

**Verdict: "A better by far."** Raw wins decisively. Both respelling styles are
worse.

So the modern-engine lexicon filter in `normalize_text_for_tts` is **correct and
must stay**:

```python
active = lexicon if not modern else {
    k: v for k, v in lexicon.items() if _is_letter_spacing(k, v)}
```

**Do not reopen this without a new ear test.** The issue that prompted the test
(#27) argued the *format* was to blame — shouty caps and hyphens — by analogy
with the comma bug below, where a similar-looking ban turned out to be a
misdiagnosis. That analogy did not hold. A natural lowercase respelling lost
too. Chatterbox does not want pronunciation help; it wants the text.

**What follows from it:** the LLM per-book lexicon and the QA loop's
pronunciation suggestions earn nothing on Chatterbox — their output is
correctly discarded. The QA layer's value on modern engines is catching
**dropped, truncated or garbled** audio, not fixing pronunciation.

---

## ⚠️ Read this first: two hard-won lessons (2026-07-14)

### 1. A comma is a pause. This one bug caused two wrong conclusions.

`num2words` returns `3,400` → **"three thousand, four hundred"**. Every TTS engine
reads that **comma as a pause**, so large numbers came out broken-up and stilted.
Dave heard it and said *"stilted and weird — not wrong, stilted."*

That single defect is now believed to be the true cause of an earlier finding that
got **year-spelling banned for modern engines** (the model appeared to "pause
mid-number": `1976` heard as `1970…6`). It wasn't the spelling. **It was the comma
inside the spelling.**

- Commas are now stripped from all spelled numbers (regression-tested).
- Years are now spelled for **every** engine, modern included — A/B'd by ear
  (**#26**): Dave judged the spelled form better.

**Lesson: when a transform "hurts" an engine, suspect the *formatting* of the
output before you ban the *idea*.**

### 2. Help the weak engines hard. Leave the strong one alone. (**#27**)

The asymmetry is the *point*, not a defect. A good voice-clone model reads real
words and numbers natively; a weak one cannot. So:

- **Weak engines (kokoro / piper / edge / polly) get EVERYTHING** — numbers spelled,
  proper nouns respelled, abbreviations expanded, the full seed + LLM + QA lexicon.
  This is what makes them usable at all, and it is why kokoro leapt in quality once
  the sample finally applied it.
- **Modern engines (chatterbox / tada) get almost nothing** — deliberately. Only
  years and acronym letter-spacing. Phonetic respellings are dropped because
  `Beijing` → `Bay-JING` was heard as "bay…zhing".

Verified end-to-end, same source sentence:

```
SOURCE     : In 1997 Xiaomi and Huawei shipped 3,400 units, 52% of $1.2 billion,
             said Dr. Nguyen in Shenzhen.

KOKORO     : In nineteen ninety-seven SHOW-mee and HWAH-way shipped three thousand
             four hundred units, fifty-two percent of 1.2 billion dollars,
             said Doctor Nwin in SHUN-jen.

CHATTERBOX : In nineteen ninety-seven Xiaomi and Huawei shipped 3,400 units,
             52% of $1.2 billion, said Dr. Nguyen in Shenzhen.
```

**The open question (#27) is NOT "why is the filter there".** It is: *does
chatterbox actually pronounce `Xiaomi` / `Nguyen` / `Shenzhen` correctly on its
own?* If yes, the filter is exactly right. If it mangles them, the rules it needs
are being filtered out — and the fix would be **natural-format** respellings, since
the shouty `SHOW-mee` / `Bay-JING` style is the prime suspect, not the concept
(cf. lesson #1). **Untested. Do not touch the filter without an ear-test.**

---

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
- Currency incl. scale words and decimal prices: `$1.2 billion` → "one point
  two billion dollars"; `$33.50` → "thirty-three dollars and fifty cents";
  `£57.25` → "fifty-seven pounds and twenty-five pence".
- Abbreviations (`Dr.`, `Sen.`, `i.e.`, `U.S.` …).
- Pacing: em-dashes → commas, ellipsis normalization.

### Stage 3 — Pronunciation rules (implemented)

- LLM-generated lexicon per book (`llm_metadata.generate_lexicon`) applied as
  whole-word replacements during Stage 2.
- `data/uploads/global_pronunciations.conf` + per-job custom regex are passed
  to the converter via `--search_and_replace_file`.

### Stage 4 — Per-book narration profile (implemented)

The "knows what to do per book" layer (`webapp/llm_metadata.py:
generate_narration_profile`). It classifies the book **form** (fiction vs
non-fiction) — steering what to hunt for (fiction → character/place/invented
names + dialogue flow; non-fiction → acronyms, companies, ambiguous figures) —
and returns a lexicon merged into Stage 3. Degrades to a seed dict if no LLM is
configured. One LLM pass over sampled excerpts
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

### Stage 6 — ASR verification (QA Layer 2, implemented core)

The self-correcting / "learning" layer (`webapp/qa_asr.py`). After a chapter
renders, a LOCAL Whisper (faster-whisper, CPU — `pip install faster-whisper`)
transcribes the audio; `diff_report()` aligns it to the source text and scores
divergence (WER + per-span drops/subs/extras). Reliably catches dropped
words/sentences, gross misreads, and numbers that lost a piece ("1976" heard as
"nineteen seventy"); it does **not** judge fine prosody/pronunciation (ASR
normalises those). High-confidence 1:1 misreads become lexicon *suggestions*
(`suggest_lexicon`); everything is written to `qa_report.json` in the book's
output dir. Opt-in today via `convert_book.py --qa`; the roadmap is auto-adding
high-confidence fixes to the profile and re-rendering only the flagged spans
(closing the loop so bugs are caught by the system, not by ear).

## Testing

`tests/test_tts_preprocess.py` covers the sanitizer and the normalization
rules, including the regressions that motivated this pipeline (decimals,
alphanumerics, curly-quote endnotes). Run: `python -m pytest tests/`.

For listening tests, always use the **canonical test passage** (the
*Abundance* solar-energy section — see LOW-COST-TTS.md "Canonical test
passage" for why it was chosen and how to regenerate it with
`scripts/extract_test_passage.py`). Verified 2026-07-04: the pipeline strips
all five of its endnote markers structurally while leaving "2.6 percent",
"140 years", and the quoted material intact.

## Invariants

- The pipeline must never make text *worse*: every destructive rule needs a
  proof it cannot fire on legitimate content (fixed-width lookbehinds,
  structural selectors) or a fallback to the original text.
- `--remove_endnotes` must never be reintroduced (see defect list above).
- The original upload is never modified; `_tts.epub` is regenerable.

---

## What each engine ACTUALLY receives (2026-07-14)

The pipeline is deliberately **asymmetric**. `normalize_text_for_tts(text, lexicon,
modern=…)` is the single function that decides this, and it is called by **both**
`scripts/convert_book.py` (real renders) and `webapp/voice_sample.py` (voice
auditions) — so **what you audition is what the book gets**. That is the whole
point; do not let them drift.

The isolated Pocket/NeuTTS/Kitten evaluation scripts violated that principle
on 2026-08-13: they imported raw `SAMPLE_TEXT` directly and their cached files
were later served in the app. They did not exercise this pipeline. The
2026-08-14 pinned raw-versus-normalized A/B corrected the evidence: Dave chose
the normalized arm for all four voices. Any future Pocket/NeuTTS/Kitten
integration must therefore use explicit number/currency normalization. The
normalized arm fails closed unless the app-pinned `num2words==0.5.14`
dependency is present. Jo's residual insertion and Jasper's scratchy opening
are separate synthesis artifacts, not reasons to undo the normalization.

| Transform | modern (chatterbox / tada) | legacy (kokoro / piper / edge / polly) |
| --- | --- | --- |
| Structural clean (endnotes, unicode) | ✅ | ✅ |
| **Years** (`1997` → "nineteen ninety-seven") | ✅ *(reversed 2026-07-14, #26)* | ✅ |
| **Acronym letter-spacing** (`CEO` → `C E O`) | ✅ | ✅ |
| Numbers / large ints (`3,400`) | ❌ raw | ✅ spelled, **no comma** |
| Currency (`$1.2 billion`) | ❌ raw | ✅ spelled |
| Percent (`52%`) | ❌ raw | ✅ spelled |
| Ordinals (`21st`) | ❌ raw | ✅ spelled |
| **Phonetic respellings** (`Xiaomi` → `SHOW-mee`) | ❌ **dropped — see #27** | ✅ |
| Word abbreviations (`Dr.` → `Doctor`) | ❌ raw | ✅ |

**Untested by ear (do not change without an A/B):** currency, percent, large ints
and ordinals for modern engines. Those are the numbers that dominate real
non-fiction, so they are the obvious next A/B after #27.

## The rule this project keeps re-learning

> **Never conclude anything about TTS output by reasoning. Render it and listen.**

Two documented bans (year-spelling; and probably respellings) came from
misdiagnosing a *formatting* artefact as a *conceptual* failure. Both cost months.
The A/B harness exists precisely so this is cheap:
`scripts/kaggle/render_voice_samples.py` renders comparison clips on a free GPU in
minutes, and `/api/sample/<name>` serves them for judgement.

## Voice auditions must not flatter (or libel) the engine

The voice sample runs through the **same preprocessing and the same seed lexicon**
as a real render (`webapp/voice_sample.py` + `webapp/lexicon.py`, both shared with
the converter).

This was broken once and it matters: the sample used to send proper nouns **raw**
while a real book respelled them, so kokoro sounded **worse in the audition than in
the actual book**. An audition you can't trust is worse than no audition.
