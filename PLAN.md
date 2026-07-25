# PLAN V2 — Path to a Flawless, Self-Checking, Complete System

> ## ⚠️ SUPERSEDED — historical record only (marked 2026-07-25)
>
> This file called itself "the authoritative execution plan" for three weeks
> after it stopped being one. The live plan is **PLAN-V4.md**; **PLAN-V3.md**
> is the immediately preceding sprint and still holds two open items (#8 module
> split, #9 sidecar). Kept because the reasoning behind the local-OR-GPU
> architecture and the self-checking goal originates here — but do not pick
> work from this file.

**Created 2026-07-06.** ~~The authoritative execution plan.~~ Goal: an
end-to-end system that works **local OR via Vast GPU**, includes **both Turbo
and TADA**, **catches book-specific issues automatically** (not hardcoded),
and has a **polished UI**. STATUS.md tracks what's done; this is what's next.

---

## 1. Adaptive Quality Assurance — "catch the bugs, per book, automatically"

**The problem:** hardcoded preprocessing (regex/num2words) will always miss
book-specific quirks. The "2000 → twenty hundred" bug, "US → us", odd names —
these vary per book and can't all be pre-coded. We need a system that adapts
to each book and self-checks.

**The solution: three layers. None hardcoded.**

### Layer 1 — LLM pre-flight review (PREVENT)  [uses existing LLM settings]
Before converting, sample the book (metadata + TOC + high-difficulty
excerpts) and run one LLM pass that emits a per-book **narration profile**:
- Flags every risky token: numbers that normalize awkwardly, acronyms
  (US/NASA/IPO — letters vs word), unusual proper nouns and names, foreign
  words, units, dates.
- Emits **pronunciation rules** (`search==replace`) written into that book's
  regex config automatically — the adaptive, non-hardcoded layer.
- Stored on the job, shown in the UI for optional review/edit before convert.
- Builds on the EXISTING `llm_metadata.generate_lexicon`; extend it to sample
  more widely and output the full profile.

### Layer 2 — ASR post-flight verification (DETECT)  [extends existing audio_verify/]
After each chapter (or sampled), transcribe the generated audio with Whisper
(the `audio_verify/` feature already does this) and compare to the source
text. Flag:
- Dropped/skipped words, mangled numbers, inserted content, wrong homophones.
- Score each chapter; anything over a mismatch threshold is flagged.
- **This is what would have caught the year bug**: audio said "twenty
  hundred", source said "2000" → mismatch flagged.
Currently `AUDIO_ASR_VERIFY_ENABLED` defaults off and only samples a few
files. Make it: on by default for new engines, per-chapter, with a clear
UI report of flagged chapters.

### Layer 3 — Feedback loop (FIX)
- Flagged mismatches → propose new pronunciation rules → append to the book
  profile → re-render only the affected chunks.
- Confirmed rules graduate into reusable **domain presets** (e.g. "US
  politics nonfiction", "tech/business") so later books start smarter.

**Deliverables:** (a) profile generator module, (b) ASR verify hardening +
per-chapter report, (c) UI panel showing profile + flagged chapters + one-
click re-render, (d) feedback/preset store.

---

## 2. TADA — full integration (local + Vast GPU)

Bring TADA to parity with Turbo as a selectable engine.
- **`tada/` container**: OpenAI-compatible FastAPI server wrapping TADA-1B
  (recipe proven — see PLAN.md Phase B: tokenizer redirect to
  ungated mirror, float32/bf16, soundfile, transcript-cached refs). CPU
  default; CUDA when present. Port 8005. UK voices baked in.
- **Production first-word fix**: prepend a lead-in that is TRIMMED from the
  audio (not spoken) — generate lead-in + real text, cut the lead-in's
  duration off the front. No more spoken "Well".
- **app.py**: VOICES entries (engine `tada`), branches at all three sites,
  `TADA_URL`.
- **compose**: `tada-tts` service, `tada` profile, model-cache volume.
- **Deliver both**: local CPU path + Vast GPU path (see §3).

## 3. Vast GPU — usable end-to-end (not just manual)

Make "render on GPU" a real, safe, one-click path for Turbo AND TADA.
- Generalize `gpu_manager.py` beyond Kokoro: per-engine template/URL config.
- A GPU render, when `GPU_RENDER_ENABLED` is on, provisions a Vast instance
  running the chosen engine's container, routes the job to it, and destroys
  it when the queue drains — all gated by the safety toggle + cost cap.
- Vast templates for the chatterbox and tada server images (mirror the Kokoro
  onstart-watchdog template; document hashes in GPU-PLAYBOOK.md).
- Everything stays OFF by default (GPU-SAFETY.md).


## 3a. GPU economics — BATCH, and MEASURE (added 2026-07-06)

Honest correction: prior "~20 min/book on GPU" figures were ESTIMATES, never
measured. TADA/Turbo speed on a Vast RTX 3060/3090 must be benchmarked before
any number is trusted.

Because a Vast instance bills per hour AND has ~15 min one-time setup +
model-download overhead, the unit of work is a **batch, not a chapter**:
- Spin up once → convert an entire book (all chapters), or several books in a
  queue → destroy. Setup cost amortizes to near-zero per book.
- Never spin up a GPU for a single chapter.
- Local option for free/no-rush: run on the fastest LOCAL machine (Dave's
  Windows box is ~2x the NUC), overnight. The NUC alone is too slow for full
  books (~13h/chapter measured 2026-07-06).

Benchmark task (do first): one Vast session, Turbo + TADA, convert a real
multi-chapter book, record actual chars/sec and $/book into LOW-COST-TTS.md.


## TADA long-term plan (zorin-first — owner decision 2026-07-08)

Constraint: the Windows box is OUT of the architecture (owner decision);
zorin does as much as possible. TADA cannot run on the NUC as-is (15 GB RAM,
model load OOMs — incident-verified). Therefore:

1. **Default engine on zorin stays Chatterbox** — free, app-managed,
   auto-resuming, proven on full books.
2. **TADA = GPU on demand, driven FROM zorin**: `scripts/vast-gpu.sh up tada`
   (runs on zorin), set the printed `TADA_URL` in `.env`, restart worker —
   the UI's TADA voices light up automatically (health-gated), books queue
   through the normal app with all its recovery machinery. ~GBP0.5 and ~4 h
   per book. `down` when finished.
3. **RAM upgrade done (2026-07-20)**: zorin now has 31 GB (i5-12400).
   TADA would fit in memory but stays off because it is broken (#23).
   Once #23 is fixed, TADA can run as a normal compose service.
4. Full one-click integration (GPU_RENDER_ENABLED auto-provisioning TADA via
   the generalized gpu_manager) remains §3 of this plan — the manual runbook
   is the validated interim.

Auto-resume truths (asked 2026-07-08): app-managed jobs on zorin survive
restarts (orphan recovery + cross-process lock — incident-tested). Anything
run as an ad-hoc script on a workstation does NOT — which is why script-based
conversion off-zorin is now out of scope.

## 4. Full-length reliability

- Run a real full book on Turbo (and TADA) end-to-end; watch NUC memory,
  watchdog, ABS sync over hours. Fix what surfaces.
- Pre-warm engine models on container start (kill first-chapter stall).
- Duplicate-book guard before ABS sync.
- M4B output option + chapter metadata for clean ABS playback.

## 5. Web UI revamp ("it feels vibe-coded")

Full visual + UX overhaul of `webapp/templates/index.html`:
- Coherent design system (spacing scale, type, components) — not ad-hoc
  inline styles. Extract CSS; consider a proper component structure.
- Clear per-book conversion flow: engine → voice (with live preview) →
  narration profile review → range → convert, as a guided path.
- Real queue/ops dashboard: progress, logs, flagged-chapters QA, ABS status.
- Settings organized (engines, cloud/GPU, integrations, pronunciation).
- Keep it a single self-hosted app; no framework bloat unless it earns its
  place.

## 6. Repo hygiene (keep public)

- ~~Delete dead `archive/root-scripts/`~~ (done — archive/ is now empty).
- ~~Parameterize the private IP / stack paths~~ (done — `STACK_PATH` env var
  with generic defaults in docker-compose.yml and .env.example).
- Keep functional docs; ensure `.env.example` documents every engine + GPU
  toggle for friends.
- See [AUDIT-PLAN.md](AUDIT-PLAN.md) for the full remediation backlog
  (Docker hardening, code quality, testing, frontend).

---

## Execution order (fastest path to "all usable")

1. **Repo hygiene** (quick, safe) — §6.
2. **TADA container + engine wiring** — §2 (parity with Turbo).
3. **QA Layer 1 (LLM profile) + Layer 2 (ASR per-chapter)** — §1, the
   bug-catching system.
4. **Full-length test** on Turbo + TADA — §4.
5. **Vast GPU one-click** for both engines — §3.
6. **UI revamp** — §5 (largest; can proceed in parallel once engines settle).

Each step ships independently and is logged in STATUS.md as it lands.
