# Contributing

## Setup

```bash
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook
cp .env.example .env
docker compose up -d
```

## Development

- App code lives in `webapp/` (Flask). TTS engine servers in `chatterbox/` and `tada/`.
- `docker compose config` validates the compose file after changes.
- Run tests: `python -m pytest tests/ -x -q` (set `PYTHONPATH=webapp`).
- CI runs automatically on push/PR (pytest + compose validation).

## Rules

- Deploy from git only; never patch application source live on the server.
- Stage only intentional files; never `git add -A`.
- Do not commit `.env`, `.secrets/`, SSH keys, generated audio, or `jobs.db`.
- TTS conclusions come from rendering and listening, never reasoning alone.
- Read `AGENTS.md` and `PREPROCESSING.md` before changing text/TTS code.
- Read `GPU-SAFETY.md` before any GPU/Vast.ai action.

## Architecture

| Service | Role |
|---------|------|
| `webapp` | Flask UI + API (port 8881) |
| `worker` | Queue runner, spawns conversion containers |
| `kokoro-tts` | Default TTS engine (port 8880) |
| `chatterbox-tts` | Voice-cloning engine, profile `chatterbox` (port 8004) |
| `tada-tts` | Voice-cloning engine, profile `tada` (port 8005) |
| `piper-tts` | Lightweight fallback, profile `piper` (port 5000) |
| `tts-proxy` | Transcript capture + Edge/Polly/Inworld routing |
| `docker-socket-proxy` | Restricted Docker API proxy for webapp/worker |
