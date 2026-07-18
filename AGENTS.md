# AGENTS.md — EPUB to Audiobook

Self-hosted ebook-to-audiobook conversion app with Docker services, TTS engines, queue processing, Audiobookshelf sync, and optional Telegram/WhatsApp notifications.

## Current Direction & Doc Map (2026-07)

Read these before changing anything TTS- or text-related:

| Doc | What it holds |
|-----|---------------|
| [GETTING-STARTED.md](GETTING-STARTED.md) | New-user walkthrough: install, convert, connect an LLM, voices, ABS. |
| [OPERATIONS.md](OPERATIONS.md) | Runbook + incident log: job states, failure responses, capacity truths. |
| [STATUS.md](STATUS.md) | **Current state & remaining tasks — read first.** What's verified vs unverified vs not-done. |
| [PREPROCESSING.md](PREPROCESSING.md) | **Mandatory** text pipeline (5 stages; 1–3 implemented in `webapp/tts_preprocess.py`, 4–5 designed). Why upstream `--remove_endnotes` must never return. |
| [LOW-COST-TTS.md](LOW-COST-TTS.md) | Engine bake-off, listening verdicts, cost model, UK reference voices. |
| [PLAN.md](PLAN.md) | **Forward plan**: adaptive QA system, TADA/GPU completion, UI. |
| [GPU-SAFETY.md](GPU-SAFETY.md) | **READ FIRST for any GPU work.** Default-local rules; how to not drain the Vast balance. |
| [GPU-PLAYBOOK.md](GPU-PLAYBOOK.md) | Vast.ai RTX 3060 batch pattern + operational steps. |
| `archive/` | Historical plans, infra notes, roadmap — superseded, do not follow. |

## Verification Discipline (2026-07-15 — every rule here was paid for)

These are not style preferences. Each rule exists because its violation shipped a
broken result that the **user** had to find. An agent that follows the diagnosis
playbook but skips these is a net negative.

1. **"Fixed" means measured or listened-to, never deployed.** A deploy that
   compiles and restarts proves nothing. Before claiming a render works: check the
   output files exist, are full-length (duration/size vs source words), and — for
   anything audible — that a human has heard it or an ASR pass matches the source.
   *Violation: "being rendered correctly right now" claimed while only 1 of 3
   chapters existed on disk.*
2. **When you fix a bug in one code path, audit every parallel path for the same
   class before announcing the fix.** This repo has duplicate paths by design
   (Kaggle vs local render; webapp vs recovery vs finalize). A fix to one is a
   *claim about all of them* the moment you describe it as "the app now does X".
   *Violation: chapter numbering unified for Kaggle only; the local p0n1 path kept
   its own numbering and rendered publisher junk instead of the book (#28).*
3. **When you change an input, re-check every limit sized to the old input.**
   Longer sample text broke a 180s timeout sized for shorter text; every chatterbox
   sample was synthesised, timed out, and discarded — and it looked like slowness,
   not failure.
4. **When you invalidate state, stop describing its former condition.** After
   wiping a cache, "cached and instant" is false until re-verified — say
   "regenerating, N/M done" instead.
5. **Background work shares the host with the product.** Throttle it (load-aware,
   skip-done, off-switch) and check UI latency + engine healthchecks while it runs.
   *Violation: unthrottled sample generation drove load to 8+, starved the UI, and
   made healthy engines report "offline".*
6. **Repeat the user's nouns, not your own.** If the user says kokoro, the work is
   about kokoro. Restate their complaint in their words before diagnosing; do not
   substitute the component you were already thinking about.
7. **TTS conclusions come from rendering and listening, never reasoning.** Two
   documented bans (year-spelling; suspect: respellings) came from misdiagnosing a
   formatting artefact as a conceptual failure. The A/B harness
   (`scripts/kaggle/render_voice_samples.py` + `/api/sample/<name>`) makes this
   cheap. See PREPROCESSING.md "read this first".
8. **Status must distinguish claim-levels.** STATUS.md separates *verified* /
   *unverified* / *open* — GitHub issues carry measured evidence. Never move an
   item up a level without the measurement in hand.

Key facts an agent must know:
- Conversion runs the upstream container `ghcr.io/p0n1/epub_to_audiobook` (a *different* project with a confusingly similar name); our webapp orchestrates it and preprocesses a `_tts.epub` copy first.
- The deployed stack is currently a Git checkout on Zorin at `/home/dave/ai/lab/stacks/epub-to-audiobook` (the older `/opt/epub-to-audiobook` documentation was stale). Deploy **from git only**; never patch application source live. The default deploy enables Piper only. Chatterbox and TADA require the explicit `ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1` opt-ins and must remain off on the 15 GiB NUC until capacity is re-proven.
- Two custom engines are BUILT and containerised: `chatterbox/` (Turbo) and `tada/` (TADA), both OpenAI-compatible, UK human-cloned voices baked in. Adding an engine = VOICES entries + a branch at the three `tts_engine ==` sites in app.py.

## Scope

- App code, scripts, tests, Docker Compose, and deployment docs for this repo.
- Target stack paths and host-specific deployment details are documented in `README.md`, `GPU-PLAYBOOK.md`, and `archive/INFRASTRUCTURE.md`.
- Do not expose or commit `.env`, `.secrets/`, SSH keys, generated audio, job databases, or local screenshots unless explicitly requested and reviewed.

## MCPProxy / Tool Surfaces

- Use the MCPProxy instance local to where the agent is running. Windows normally uses `http://127.0.0.1:8080/mcp`; `khpi5` uses `http://127.0.0.1:9092` for work started on that host.
- Discover tools before calling them and use exact `server:tool` names.
- Use `win-filesystem` / local shell for repo edits and local checks.
- Use SSH for deployment host checks when the task targets a remote stack.
- Nango surfaces are not primary for this repo. If notifications or external service proofs are needed, pick the project-appropriate email/calendar/Telegram/WhatsApp surface explicitly and avoid Callout/Clean Bean Stripe or Cloudflare surfaces unless the task names them.
- Appwrite is not part of this repo.

## Core Rules

1. Build and test locally before changing deployment state.
2. Preserve Docker Compose service boundaries; do not remove worker/queue services without proving queue behavior.
3. Treat TTS model assets and generated audiobooks as large runtime artifacts, not source.
4. Stage only intentional files; never `git add -A`.
5. **GPU/Vast.ai costs real money — default is LOCAL. Never spin up a Vast
   instance or enable `GPU_RENDER_ENABLED` without an explicit user request
   for the current task, and always destroy instances you create in the same
   session. Read [GPU-SAFETY.md](GPU-SAFETY.md) before ANY GPU action.**

## Verification

Prefer targeted checks:
- unit or smoke scripts in `tests/` / `scripts/`
- `docker compose config`
- app smoke check against the configured local or remote URL

