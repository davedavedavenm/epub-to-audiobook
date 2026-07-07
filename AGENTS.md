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

Key facts an agent must know:
- Conversion runs the upstream container `ghcr.io/p0n1/epub_to_audiobook` (a *different* project with a confusingly similar name); our webapp orchestrates it and preprocesses a `_tts.epub` copy first.
- The deployed stack lives on zorin at `/opt/epub-to-audiobook`, deploys **from git only** (never patch live files). Deploy with `--profile piper --profile chatterbox --profile tada`.
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

