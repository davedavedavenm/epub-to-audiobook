# Contributing

## Setup

```bash
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook
cp .env.example .env
./scripts/bootstrap.sh
```

## Development

- App code lives in `webapp/` (Flask). TTS engines have separate service directories. See [README.md](README.md#tts-engines).
- `docker compose config` validates the compose file after changes.
- Run tests: `python -m pytest tests/ -x -q` (set `PYTHONPATH=webapp`).
- Run `scripts/ci_local.sh` from the intended commit before pushing. It runs lint and tests in a clean checkout.
- GitHub CI runs the workflow in `.github/workflows/ci.yml` on pushes and pull requests.

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
| `chatterbox-nano` | **Default TTS engine** with Beatrice (Nano), profile `chatterbox-nano` |
| `kokoro-tts` | Compatibility/debug TTS engine (port 8880); its tested voices are retired from normal quality selection, so it is not the default |
| `chatterbox-tts` | Voice-cloning engine, profile `chatterbox` (port 8004) |
| `tada-tts` | Voice-cloning engine, profile `tada` (port 8005) |
| `tontaube`, `zonos3`, `reverb` | Optional stock CPU book narrators, each in its own profile |
| `tts-proxy` | Transcript capture + Edge/Polly/Inworld routing |
| `docker-socket-proxy` | Restricted Docker API proxy for webapp/worker |
