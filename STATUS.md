# Project Status & Remaining Tasks

**Last updated: 2026-07-14.** Honest single source of truth. "Verified" = it
was actually run; "unverified" = the code exists but hasn't been proven
end-to-end by ear/measurement. Open work is tracked as **GitHub issues** —
this file is the narrative index, the issues are the live backlog.

## Aims vs reality — the owner's scorecard (2026-07-15)

The aims below are Dave's, stated verbatim or near-verbatim during development.
This table is the project's honest report card; agents should treat a ❌/⚠️ here
as the priority order.

| Aim (as stated) | State | Evidence |
|---|---|---|
| "I go to the web UI, choose narrate, and it'll **just work**, all automatic" | ✅ **Kaggle path** / ❌ **local path** | Kaggle proven end-to-end twice (Breakneck 8ch, Summer Moon 22ch: chapters→GPU→progress→verify→cover→ABS, no manual steps). Local render uses a different renderer with different chapter numbering and shipped marketing pages instead of the book (#28). |
| Everything **checked automatically** — no blind trust | ⚠️ porous | Verification + pre-sync gate + QA exist and each caught something, but a book with NO content passed all of them at "completed, 100%" (#30). QA/lexicon loop inert on chatterbox by design (#27). |
| Accurate progress/ETA, no fake numbers | ✅ | Real per-chapter progress (ntfy call-home); honest "chapter X/N"; no ETA before evidence. Was elapsed-guesswork before. |
| Chapter selection = the actual book, by title | ✅ picker / ❌ local render | Picker shows titles, flags back-matter, defaults to body (LLM guard + heuristic). The local renderer ignores that numbering (#28), so it's only end-to-end true on Kaggle. |
| Covers + metadata land in ABS, chapters navigable | ✅ | ID3 title/album/artist/track on every convert_book render; auto cover-sync; ABS shows named ordered chapters. p0n1 path still untagged (#31). |
| **All voices cached**, instant, judged on hard text | ✅ | 69/69 usable voices, ~30ms serve, ~135-word sample with years/currency/acronyms/names, production-accurate preprocessing per engine. 20 voices are dead engines, documented not hidden (#23/#24). |
| Clear visually which voice is speaking | ✅ | Speaking card: accent glow, equaliser, stop toggle, single-voice rule. |
| LLM guard: check/sort/act, local or free | ⚠️ partial | Chapter classifier live (Groq free, <1.5s, fail-open); gate phrasing on shared khpi5 Ollama. But the gate's porosity (#30) is the gap between "exists" and "guards". |
| Anyone can clone + deploy and get all this | ⚠️ | Compose/env/docs carry every feature, but a fresh deployer using local render hits #28. |
| "I shouldn't have to find every bug" | ❌ | Nine defects were found by the owner, not the system: wrong cover, false ready-badge, fake progress, false FAILED, wrong chapter range, stilted numbers, raw Xiaomi, uncached sample, bookless "book". This is the metric to move. |

**Bottom line: cloud render ~90% of the aim; local render ~40%; automated
trust ~60%. Fix order: #28/#29 (local path), #30 (content gate), then #24/#23.**

## OPEN — local-render is broken (2026-07-15, needs work)

A real conversion ("In the Nick of Time", `render_target: local`, kokoro) rendered
**two publisher marketing pages and NOT the story**. Root cause: **the local path
uses a different renderer with different chapter numbering than the picker.** The
Kaggle path was unified on `chapters.py`; the local path was not — it still shells
out to the legacy p0n1 container. This is not a one-off; any local render can pick
the wrong chapters. Tracked, grounded, for other agents:

- **#28** (CRITICAL) — local renders produce the WRONG chapters: picker numbering
  (`chapters.py`) ≠ p0n1 numbering. The fix is to route local renders through
  `scripts/convert_book.py` (one renderer, one numbering).
- **#29** — `convert_book.py` crashes on kokoro's streaming WAV (blocks #28). A fix
  is committed (`89ff1a5`) but **UNVERIFIED** — a kokoro book has not rendered
  end-to-end.
- **#30** — nothing catches a "completed" book that contains no real content
  (rendered-words vs source-words sanity check missing).
- **#31** — p0n1 ignores the min-words filter and writes no ID3 tags.

**Do not trust a `completed` local render until #28/#29 are fixed and verified by
listening/measurement.**

## Recent fixes (2026-07-14)

- **Numbers were STILTED, not mispronounced.** `num2words` returns
  "three thousand**,** four hundred" and every TTS engine reads that comma as a
  **pause** — so large numbers came out broken-up. Dave heard it as "stilted and
  weird". Commas are now stripped; numbers read as one flowing phrase.
  Regression-tested. This hit **every large number in every book**.
  *Suspected knock-on:* this comma is very likely the true cause of the old
  "year-spelling hurts modern engines" finding (the model "pausing" mid-number) —
  see **#26**, to be settled by an ear-test A/B, not by argument.
- **Voice samples are now GPU-rendered, one-off.** Chatterbox on CPU is ~3.5
  min/sample; 23 voices saturated the NUC (load 8+, swap full) and starved the UI
  — engines even failed their own healthchecks and reported "offline" while merely
  too busy to answer. Samples are a fixed set, so
  `scripts/kaggle/render_voice_samples.py` renders them all on a free T4 in
  minutes and they're cached permanently. Local caching is now **throttled**
  (load-aware, skip-cached, off-switch) so it can never starve the host again.
- **The sample is production-accurate.** `webapp/voice_sample.py` holds ONE
  sample text, shared by the web app and the GPU renderer, and it runs through the
  **same `normalize_text_for_tts` a real render uses** (per-engine modern/legacy
  contract). What you audition is what the book gets.
- **Preview timeout was shorter than the synthesis** (180s cap vs ~208s of CPU
  work), so every chatterbox sample was generated, timed out, and discarded — the
  cache could never fill and merely looked "slow". Raised to 600s.
- **MP3s now carry ID3 tags** (title/album/artist/track), so Audiobookshelf can
  group a book and order/name its chapters — chapter navigation was broken without
  them.
- **Voices that cannot work are documented, not silently broken:** TADA (engine
  fails to load, **#23**), Inworld (no API key) and Polly (no AWS creds) — **#24**.

## Recent fixes (2026-07-13)

- **Chapter picker now matches the renderer.** The UI numbered chapters by raw
  spine position (Cover=1, Contents=4, Introduction=5) while the converter
  numbered only substantial chapters (Introduction=1) — so "chapters 5–13" of a
  10-chapter book rendered Chapter 4 → back-matter and looked broken. New
  `webapp/chapters.py` is the single source of truth for chapter numbering,
  imported by **both** the web UI and `scripts/convert_book.py`. The picker shows
  real chapter **titles**, flags back-matter (Acknowledgments/Notes/Index), and
  defaults the range to the book body.
- **Range verification no longer false-fails.** A range that reaches the end of
  the book compared file count to `end-start+1` (the raw span) and marked a
  finished render FAILED (so it never synced). It now checks the renderer's true
  renderable-chapter count.
- **Kaggle epub-attach race fixed.** The kernel could be pushed before the epub
  dataset finished Kaggle's async ingestion, dying with "no .epub under
  /kaggle/input". The orchestration now waits for `datasets status = ready`.
- **Auto cover-sync to Audiobookshelf** on every render; **honest Kaggle
  progress** (chapter X/N, no fake ETA before a chapter completes); library
  "Audiobook ready" badge now verifies the audio actually exists.

## TL;DR (2026-07-10)

The engines, pipeline, and web UI all work end to end. Focus has shifted from
"does it convert" to **product**: a clean UI, free cloud-GPU rendering anyone
can drive, and self-service configuration.

- **Chosen engine (by ear, 2026-07-10)**: Chatterbox Turbo (Arthur) graded
  "really really good" on Apple in China and is the working full-book engine on
  Dave's hardware — recorded neutrally in ENGINES.md (NOT a general ranking;
  TADA's ceiling is higher, GPU/fiction may flip it).
- **Render anywhere, from the UI**: per-book **Render on → This machine /
  Kaggle GPU / Vast** selector. Kaggle GPU is free (~30 GPU-hrs/wk) and fully
  wired: the worker uploads the epub as a Kaggle dataset, pushes the GPU kernel,
  polls, pulls the MP3s back into the library, and syncs to ABS — appears in the
  Queue with (elapsed-estimate) progress. `webapp/kaggle_render.py` + the CLI
  kernels in `scripts/kaggle/`.
- **Self-service config**: Settings has guided, secure, persistent setup for
  Kaggle + LLM + ABS + others — secrets stored in the app_settings DB on the
  `/data` volume (survive restarts, masked on read), with Test-Connection
  buttons. No `.env` editing needed.
- **Studio Console UI** (2026-07-10 redesign): cool ink + one signal-coral
  accent, mono for data, on-air motif, **real epub book covers**, library sorted
  most-recent-first, light + dark.
- **Preprocessing** is robust and layered: structural sanitize → minimal
  deterministic normalization (MODERN-ENGINE CONTRACT: modern engines keep raw
  numbers/years; acronym letter-spacing kept — "CEO"→"C E O") → per-book LLM
  narration profile (fiction/non-fiction aware) → seed-rule floor.
- **GPU images** pinned to the full cu126/cu124 stack (torch+vision+audio) after
  repeated silent-CPU drift; regression-guarded. `cuda_available` gate refuses
  CPU runs.
- **Fixed 2026-07-10**: ABS sync host (#15, AUDIOBOOKSHELF_HOST now the real IP).
- **Remaining product gaps**: Kaggle progress is an elapsed estimate (Kaggle
  exposes no per-chapter signal without a call-home tunnel); a webapp restart
  strands an in-flight Kaggle job (render still completes on Kaggle's side).

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

- **Post-fix audio quality** — clean-concat + `--denoise` (afftdn) is built;
  a free-Kaggle render (kernel v3, TF-conflict fixed) is validating it (#12).
  Not yet heard on a completed render (Vast attempt OOM-died #9; earlier Kaggle
  runs hit env conflicts, now fixed).
- **Background hiss** — TADA vocoder artifact. `--denoise` now attacks it but
  the TADA-vs-Chatterbox A/B and default policy are open (#8).
- **Engine A/B — verified by ear 2026-07-10**: on `Apple in China` (non-fiction,
  CPU-only local), **Chatterbox Turbo (Arthur) graded "really really good" and
  is the working choice for full-book runs here.** TADA v8 was better than
  earlier cuts but still drifted on pacing/proper-nouns. This is one book on one
  (GPU-less) box — NOT a general ranking; TADA's ceiling is higher and may win
  on GPU / shorter chapters / dialogue. Recorded neutrally in ENGINES.md; TADA
  refinement path in #21.

## Open work → GitHub issues

Milestone: **Audio quality + closed-loop QA**.

| Issue | What |
|---|---|
| [#7](../../issues/7) | QA Layer 2: auto-apply high-confidence fixes + auto re-render flagged spans |
| [#8](../../issues/8) | Eliminate TADA background hiss (denoise default policy + engine A/B) |
| [#9](../../issues/9) | bug: Vast engine has no memory cap — OOM mid-render |
| [#10](../../issues/10) | Wire QA Layer 2 into the web UI (auto-run + report surface) |
| [#11](../../issues/11) | Engine failover toggle in the UI |
| [#12](../../issues/12) | Validation: clean-audio A/B on free Kaggle |
| [#13](../../issues/13) | Finish Inside Apple audiobook (CPU vs GPU re-render) |
| [#14](../../issues/14) | bug: startup recovery resurrects cancelled jobs, blocks queue |
| [#15](../../issues/15) | bug: ABS sync broken (docker-vm unresolvable + token) — partially fixed |

Not yet an issue but the biggest lever: **GPU auto-provision for TADA/Chatterbox
from the UI** so quality engines don't run on CPU (the "one-click" goal).

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
