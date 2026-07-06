# PLAN V2 — Path to a Flawless, Self-Checking, Complete System

**Created 2026-07-06.** The authoritative execution plan. Goal: an
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
  (recipe proven — see PLAN-ENGINE-UI.md Phase B: tokenizer redirect to
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

- Delete dead `archive/root-scripts/` (one-off scripts leaking homelab paths).
- Parameterize the private IP / stack paths in `docker-compose.yml`,
  `webapp/app.py`, `.env.example` via env with generic defaults.
- Keep functional docs; ensure `.env.example` documents every engine + GPU
  toggle for friends.

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
