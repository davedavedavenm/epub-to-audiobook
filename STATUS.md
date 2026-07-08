# Project Status & Remaining Tasks

**Last updated: 2026-07-08.** Honest single source of truth. "Verified" = it
was actually run; "unverified" = the code exists but hasn't been proven
end-to-end by ear/measurement. Open work is tracked as **GitHub issues** —
this file is the narrative index, the issues are the live backlog.

## TL;DR (2026-07-08)

The engines and pipeline work; the current frontier is **audio quality** and
making the **self-correcting loop automatic in the UI**.

- **Preprocessing** is robust and layered: structural sanitize → minimal
  deterministic normalization (MODERN-ENGINE CONTRACT: modern engines keep raw
  numbers/years) → per-book LLM narration profile (fiction/non-fiction aware) →
  seed-rule floor. Provider fallback chain; never collapses to nothing.
- **Engines**: Kokoro, Chatterbox Turbo, Hume TADA-1B, Piper — OpenAI-compatible.
  TADA/Chatterbox GPU images pull a pinned **cu126** torch stack (fixes the
  silent-CPU drift; `cuda_available:true` verified on Vast RTX 3090).
- **GPU strategy**: Kaggle-first (free, ~30 GPU-hrs/wk, now phone-verified) +
  Vast burst (~$1/book). Runbooks: `scripts/kaggle/`, `scripts/vast-gpu.sh`.
- **QA Layer 2 (ASR self-check)** exists and is **proven locally on zorin**:
  it caught a real audio bug (see below). Not yet automatic in the UI.
- **Output**: one canonical location `data/audiobooks/<book>/`; AudioBookShelf
  is the unified library. `scripts/sample.sh` for fast local few-page tests.

## Done & VERIFIED (actually run)

- **Preprocessing pipeline** — MODERN-ENGINE CONTRACT codified + regression-
  guarded (modern engines don't respell numbers/years/decades — that caused the
  "1970…6" pause artifact). Fiction/non-fiction classification steers
  pronunciation. 53 tests pass. See PREPROCESSING.md.
- **Fallback chains** — LLM provider chain (primary→fallback→seed floor);
  conversion engine failover helper (voice-preserving). Backend automatic;
  UI toggle pending (#11).
- **GPU images** — cu126 torch pin verified live on Vast (`torch 2.8.0+cu126,
  cuda_available:true`) after the cu130 silent-CPU incident (2026-07-08d).
- **Clean audio concat** — `convert_book.py` now joins at WAV sample level
  (stdlib) then encodes one clean MP3; the old MP3-byte join left corrupt frame
  boundaries. The web-UI path (upstream p0n1 tool) was already clean
  (ffprobe-verified). Unit-tested.
- **QA Layer 2 proven on zorin** — local Whisper transcribed real pipeline
  audio, aligned to source, and **caught the corrupt-concat bug** (a 27-min
  chapter decoded to 19 words) plus a false-positive in its own normaliser
  (ordinal word/digit), which was then fixed.
- **Canonical output + sample harness** — `data/audiobooks/<book>/`,
  `scripts/sample.sh`. README "Where do I find my audiobooks?".

## Done but UNVERIFIED (needs an ear / a real run)

- **Post-fix audio quality** — the clean-concat + LLM-profile + (planned)
  denoise combination has not yet been heard on a completed render (the Vast
  attempt OOM-died, #9). Validation planned on free Kaggle (#12).
- **Background hiss** — TADA vocoder artifact, NOT addressed by any fix yet
  (#8: denoise step + TADA/Chatterbox A/B).

## Open work → GitHub issues

| Issue | What |
|---|---|
| [#7](../../issues/7) | QA Layer 2: auto-apply high-confidence fixes + auto re-render flagged spans |
| [#8](../../issues/8) | Eliminate TADA background hiss (denoise + engine A/B) |
| [#9](../../issues/9) | bug: Vast engine has no memory cap — OOM mid-render |
| [#10](../../issues/10) | Wire QA Layer 2 into the web UI (auto-run + report surface) |
| [#11](../../issues/11) | Engine failover toggle in the UI |
| [#12](../../issues/12) | Validation: clean-audio A/B on free Kaggle |
| [#13](../../issues/13) | Finish Inside Apple audiobook (CPU vs GPU re-render) |

## Robustness backlog (not blocking, no issue yet)

- Pre-warm engine models on container start (avoid ~2 min first-request stall).
- M4B output + chapter metadata for nicer ABS playback.
- Front-matter detection (so "chapter 1" isn't the copyright page).
- Duplicate-book guard (warn when a book already has an ABS folder).

## Big-picture plan

See **PLAN.md** and the action plan in this session. The north star is the
3-layer **adaptive QA system** (LLM pre-flight profile + ASR post-flight verify
+ feedback loop) so per-book issues are caught automatically — Layers 1 and 2
now exist; closing the loop (auto-fix + re-render, in the UI) is the remaining
work (#7, #10).

## Doc map

README.md (setup/sharing) · PREPROCESSING.md (text pipeline + QA layers) ·
LOW-COST-TTS.md (engine bake-off + GPU strategy) · PLAN.md (build plan) ·
GPU-SAFETY.md / GPU-PLAYBOOK.md (GPU rules + runbook) · OPERATIONS.md
(incident log + standing rules) · AGENTS.md (agent guide). This file is the
current-state index.
