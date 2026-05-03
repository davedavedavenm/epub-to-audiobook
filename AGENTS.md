# AGENTS.md — EPUB to Audiobook

Self-hosted ebook-to-audiobook conversion app with Docker services, TTS engines, queue processing, Audiobookshelf sync, and optional Telegram/WhatsApp notifications.

## Scope

- App code, scripts, tests, Docker Compose, and deployment docs for this repo.
- Target stack paths and host-specific deployment details are documented in `README.md`, `INFRASTRUCTURE.md`, `GPU-PLAYBOOK.md`, and related plan files.
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

## Verification

Prefer targeted checks:
- unit or smoke scripts in `tests/` / `scripts/`
- `docker compose config`
- app smoke check against the configured local or remote URL

