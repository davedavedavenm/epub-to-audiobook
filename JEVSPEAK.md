# JEVSPEAK — TypeSafe/Jev decision layer for TTS preparation

Optional, **off by default**. Two focused uses of TypeSafe's Jev model
(`jev-latest`) in the text-preparation stage. Both follow the
[TypeSafe "select instead of generate" pattern](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook):
regex finds candidates, Jev makes one batched `choice` judgment per candidate,
and ordinary code applies the result.

- Code: `webapp/jevspeak.py`
- Tests: `tests/test_jevspeak.py`
- Measurement script: `scripts/measure_jevspeak.py`
- API: `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`

With both flags off, the pipeline is **byte-identical** to before this module
existed: `normalize_text_for_tts_jev` delegates straight to
`normalize_text_for_tts`, and `refine_boundaries` returns its input unchanged.
`tests/test_jevspeak.py::test_off_matches_normalizer_exactly` and
`::test_chapters_off_path_is_unchanged` pin that.

## What it does

### 1. TTS text normalization (`JEV_TTS_NORMALIZATION_ENABLED`)

Wired into `scripts/convert_book.py::chapter_text`, which is the stage that turns
book HTML into narration text for the engine. Ambiguous spans are found by
regex, then **one batched request per chapter** asks how each should be read in
its own sentence; the chosen spoken form is substituted before the deterministic
normalizer runs.

| Candidate | Question | Choices |
|---|---|---|
| `1/2`, `3/4` | fraction / date / ratio? | fraction, date (British), ratio, leave |
| `£4.50` | money / literal decimal? | money, literal, leave |
| `Dr.` | doctor / drive? | doctor, drive, leave |
| `St.` | saint / street? | saint, street, leave |
| `No. 4` | number / no? | number, no, leave |
| `IV` | roman numeral / letters? | numeral, letters, leave |
| `3.5mm`, `5kg`, `5m` | measurement / letters? | measurement, letters, leave |
| `10-12` | range / sequence? | range, sequence, leave |
| `J. R. R.` | dotted initials | letters, leave |

Deliberately **not** sent to Jev: years, decades (`1990s`), ordinals (`4th`),
large integers, percentages and the currency/abbrev classes the deterministic
normalizer already handles correctly. Those are unambiguous and already solved
in code; sending them would only cost tokens. `1914-1918` is skipped because the
existing year-range rule owns it.

### 2. Chapter/section boundary ranking (`JEV_CHAPTER_BOUNDARY_ENABLED`)

Wired into `webapp/chapters.py::list_renderable_chapters` (the shared numbering
source of truth for the UI picker). A section is sent to Jev **only when the
existing heuristic is ambiguous**:

- it sits just below the word floor (`JEV_CANDIDATE_MIN_WORDS`, default 40) —
  candidates for rescue, or
- its title matched the back-matter regex (possible false positive), or
- its word count is within 1.5× the floor (possible front/back matter).

Everything else — a normal-length chapter with a normal title — makes no API
call at all. Ambiguous sections get one batched `choice`: `body` /
`front_matter` / `back_matter`. Confident `front_matter`/`back_matter` answers
drop the section; a confident `body` keeps it and clears a false-positive
`back_matter` flag. Survivors are renumbered 1..N so the picker and the
converter keep the same numbering invariant.

## Configuration

All read at call time from the environment; both master flags default off.

| Variable | Default | Meaning |
|---|---|---|
| `JEV_TTS_NORMALIZATION_ENABLED` | `0` | Enable feature 1 |
| `JEV_CHAPTER_BOUNDARY_ENABLED` | `0` | Enable feature 2 |
| `TYPESAFE_API_KEY` | — | API key (preferred) |
| `TYPESAFE_API_KEY_PATH` | — | Path to a key file |
| `TYPESAFE_MODEL` | `jev-latest` | Model alias |
| `TYPESAFE_API_URL` | `https://api.typesafe.ai/v1/systemone` | Endpoint |
| `JEV_MIN_CONFIDENCE` | `0.55` | Below this Choice confidence, keep the old behaviour |
| `JEV_MAX_CANDIDATES` | `60` | Cap on spans per chapter text |
| `JEV_MAX_CHAPTER_CANDIDATES` | `40` | Cap on sections per book listing |
| `JEV_CANDIDATE_MIN_WORDS` | `40` | Below-floor scan limit for feature 2 |
| `JEV_BATCH_SIZE` | `40` | Questions per HTTP request |
| `JEV_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `JEV_MAX_ATTEMPTS` | `2` | Attempts on transient 429/5xx (bounded backoff) |
| `JEV_STATE_MAX_CHARS` | `8000` | Cap on shared `state` sent to Jev |

If no key is configured the features log a warning and do nothing (they do not
raise), so an install without a TypeSafe key is unaffected.

## Evidence for the threshold

`scripts/measure_jevspeak.py` runs 15 tricky, realistic spans in **one** request.
Measured 2026-09-23, `model: jev-1.13.0`, usage `2519` input + `571` output tokens:

| span | context | choice | conf |
|---|---|---|---|
| `1/2` | She added 1/2 a cup of sugar | fraction | 1.00 |
| `3/4` | He scored 3/4 in the test | fraction | 0.85 |
| `9/11` | The 9/11 attacks | date | 0.92 |
| `Dr.` | Dr. Smith examined the patient | doctor | 1.00 |
| `Dr.` | He turned onto Elm Dr. | drive | 0.98 |
| `St.` | St. Patrick drove the snakes | saint | 1.00 |
| `St.` | The office is on High St. | street | 0.99 |
| `No.` | See No. 4 in the list | number | 0.99 |
| `IV` | Chapter IV begins the tale | numeral | 0.91 |
| `IV` | The nurse started an IV drip | letters | 0.89 |
| `3.5mm` | The cable is 3.5mm thick | measurement | 0.99 |
| `5m` | He ran 5m to the open door | measurement | 0.97 |
| `10-12` | Pages 10-12 cover the war | range | 1.00 |
| `£4.50` | It cost £4.50 at the market | money | 0.99 |
| `J. R. R.` | J. R. R. Tolkien wrote the book | letters | 0.97 |

Every answer was the intended reading, including the context-dependent pairs
(`Dr.` doctor vs drive, `St.` saint vs street, `IV` numeral vs letters). The
**lowest confidence is 0.85**, so the default `JEV_MIN_CONFIDENCE=0.55` sits
well below the observed distribution: a genuine answer is acted on, while a
genuinely split one falls back. Re-measure before lowering it.

## Cost and volume

TypeSafe bills per token (see the TypeSafe console for current pricing). Measured
marginal cost is roughly **170 input + 38 output tokens per candidate**, plus a
small fixed overhead per request. Volume is bounded in code:

- Feature 1: at most `JEV_MAX_CANDIDATES` (60) spans per chapter text, batched at
  `JEV_BATCH_SIZE` (40) per request. A typical prose chapter has a handful; a
  technical chapter with many measurements is capped.
- Feature 2: at most `JEV_MAX_CHAPTER_CANDIDATES` (40) sections per book, and
  only ambiguous ones.

Example ceiling for a 30-chapter book at the caps: ~30 feature-1 requests of up
to 60 candidates. In practice most chapters are far below the cap. Turning the
flags off makes the marginal cost exactly zero.

## Failure behaviour (fail-safe)

`ask_jev` never raises. The following all fall back to the existing
deterministic result:

- no API key / no key file
- timeout, DNS/connection error, non-2xx status
- `429`/`5xx`: one bounded retry with exponential backoff, then fall back
- malformed or empty response body
- a `choice` outside the offered criteria
- `confidence < JEV_MIN_CONFIDENCE`

In feature 1 a fallback means the span is left exactly as it was and the normal
deterministic rules apply. In feature 2 a fallback means below-floor sections
stay dropped and everything else keeps its heuristic classification.

## Rollback

1. Unset `JEV_TTS_NORMALIZATION_ENABLED` and `JEV_CHAPTER_BOUNDARY_ENABLED`
   (or set both to `0`) and restart. That alone restores the previous behaviour
   exactly — the wiring is a pass-through when the flags are off.
2. To remove the feature entirely: revert the commits touching
   `webapp/jevspeak.py`, `webapp/chapters.py`, `scripts/convert_book.py`,
   `tests/test_jevspeak.py`, `scripts/measure_jevspeak.py` and this file.

## Deliberately not changed

- No default path, engine, voice, threshold or output was altered. The two
  integration points are pass-throughs while the flags are off.
- The deterministic normalization rules in `webapp/tts_preprocess.py` are
  untouched; Jev only supplies readings for spans the rules cannot disambiguate.
- The standalone converter's own chapter loop
  (`scripts/convert_book.py`, around the `renderable_wordcount` calls) is **not**
  wired for feature 2. It numbers chapters independently of
  `chapters.list_renderable_chapters`, and unifying them is a larger refactor
  than this change. Feature 2 therefore currently affects the shared listing
  (UI picker, excerpt builder) only; `jevspeak.refine_boundaries` is the hook for
  a future converter wiring.
- No `git add -A`; only the specific files above were touched.
