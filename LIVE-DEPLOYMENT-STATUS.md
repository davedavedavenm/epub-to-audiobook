# Live Deployment Status (Historical Snapshot)

Snapshot date: 2026-02-04  
Snapshot host: `192.168.1.88` (Zorin)

> This document is a point-in-time audit and may be outdated after later hotfixes/deploys.
> Use live checks (`/api/version`, `/api/health`, `docker compose ps`) for current state.

## Executive Summary

- Live stack is reachable and serving traffic on `8881` (webapp), `8880` (Kokoro), and `5000` (Piper).
- GitHub/local repo is **ahead** of live by 1 commit.
- Live runtime is split across mixed compose state and one legacy repo path.
- Health endpoint is noisy (`503`) due to a strict 5s Kokoro timeout, even when Kokoro is actually reachable.

## GitHub vs Live Version

- Local/GitHub `master` HEAD: `29589008c9e5869a34a579a14865f9182c0b3fc7` (`v1.3.0` tag exists).
- Live repo (`/home/dave/stacks/epub-to-audiobook.OLD-DEPRECATED`) HEAD: `1bd6bafa1ab1db77bec04cc29e9ad66f1d27200b`.
- After `git fetch` on host: ahead/behind `HEAD...origin/master = 0 1` (live is 1 commit behind).

## Runtime Cross-Reference

Running containers on live host:

- `epub-to-audiobook-ui` (`epub-to-audiobook-webapp`, up)
- `kokoro-tts` (`ghcr.io/remsky/kokoro-fastapi-cpu:latest`, healthy)
- `piper-tts` (`ghcr.io/matatonic/openedai-speech-min:latest`, up)
- conversion workers: `audiobook-1ad2b701`, `audiobook-499f7338`

Notable drift:

- `epub-to-audiobook-ui` compose labels point to `/home/dave/ai/lab/stacks/epub-to-audiobook/docker-compose.yml`, but that path currently contains only `data/` and `ssh-keys/` (no compose file/repo).
- `kokoro-tts` compose labels point to `/home/dave/stacks/epub-to-audiobook/docker-compose.yml` (path missing now).
- `piper-tts` is on image `openedai-speech-min:latest` and does not show normal compose labels, suggesting it was started outside current compose state.

## Code Parity Checks

- Live webapp code hash matches legacy host repo commit `1bd6...`:
  - `/app/templates/index.html` hash matches `1bd6...`
  - `/app/app.py` hash matches `1bd6...`
- Local/GitHub `master` (`2958900...`) has newer `webapp/app.py` and `docker-compose.yml` changes not present on live.

## Operational Findings

- `/api/health` often returns:
  - `503 {"database":"ok","kokoro":"...Read timed out (read timeout=5)","webapp":"ok"}`
- Direct Kokoro endpoint still responds (`/v1/audio/voices` returns `200`), indicating timeout sensitivity rather than full outage.
- Jobs API currently shows:
  - `converting` job with `retry_count=3`
  - `failed` job due to container-name conflict (`audiobook-499f7338` already exists)
  - one queued job waiting

## Conclusion

GitHub is **not behind** live; live is currently behind GitHub by one commit and running with deployment drift (mixed compose metadata/paths).
