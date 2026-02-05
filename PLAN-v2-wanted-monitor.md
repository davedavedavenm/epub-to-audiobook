# PLAN v2: Wanted Books Monitor + Library Feed (Legal-First)

Date: 2026-02-05
Status: In progress

## Goal
Maintain a list of wanted books, check for availability a few times per day without spamming, and when a wanted book becomes available in the local library folder (`/mnt/openbooks`), notify via Telegram/WhatsApp. Do not auto-convert to audiobooks.

## Constraints / Policy
- I will not help automate acquisition of copyrighted books from unauthorized sources.
- The automation will be provider-agnostic: it can detect when a file appears in the library and notify. Optional “search/request” hooks are supported only for legitimate sources you control.

## Current State (Verified)
- Webapp library reads `LIBRARY_DIR=/mnt/openbooks` and the library endpoint is working.
- docker-vm runs `wanted_monitor.py` via cron hourly with `flock` to avoid overlaps.
- `wanted_monitor.py` reads LazyLibrarian DB for `Status='Wanted'`, checks the webapp library via `--library-api`, and maintains per-title state in `wanted_state.db`.
- `Abundance | Ezra Klein` exists in LazyLibrarian as `Wanted` but is not currently present in the webapp library.

## Plan

### Phase 0: Make the pipeline observable
1. Add a local state DB (or JSON) to track per-title `last_checked`, `next_check`, `attempt_count`, `found`.
2. Add structured logging so we can answer “did it run, what did it check, what happened?”

### Phase 1: Make checks fair + non-spammy
1. Round-robin / priority scheduling so the same first 5 titles are not checked repeatedly.
2. Cap checks per run (e.g. 5) with a configurable per-title backoff.
3. Default schedule: 3 times per day (configurable).

### Phase 2: Detect “found” reliably
1. Define “found” as: matching EPUB/PDF file exists in the OpenBooks library folder.
2. Matching logic:
   - Normalize title/author strings.
   - Prefer exact-ish matches; fall back to fuzzy match with a conservative threshold.
3. When found:
   - Mark wanted item as found in state DB.
   - Send a notification (Telegram first; WhatsApp optional).

### Phase 3: Optional legitimate “request/search” hooks
1. If you have a legitimate provider/API, add a plugin interface:
   - `request_book(title, author)`
2. Keep hooks disabled by default.
3. If enabled, enforce strict rate limits:
   - default `--max-requests-per-run 1`
   - per-title `--request-cooldown-s` (default 12h)

### Phase 4: Validation
1. Add a known test wanted item that is already in `/mnt/openbooks` and confirm notification.
2. Add a new wanted item and verify it rotates through checks over time.
3. Confirm no auto-conversion occurs.
4. Confirm notification anti-spam behavior:
   - default `--notification-mode summary`
   - default `--max-notifications 1` per run (hard cap across channels)

## Deliverables
- Versioned script in repo (so configuration is reproducible).
- Deployment steps for docker-vm cron.
- Documentation for adding wanted items in LazyLibrarian and for notification config.

