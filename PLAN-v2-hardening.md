# Plan: Reliability & Ops Hardening (v2)

Date: 2026-02-05
Owner: Codex
Status: In progress

## Goals
- Make queue processing resilient to webapp restarts and crashes.
- Make Audiobookshelf sync verifiable and auditable.
- Reduce container-related failure modes (stale names, orphaned containers).
- Improve observability: per-job logs and deterministic job state transitions.

## Non‑Goals (for this plan)
- New UI redesign beyond Ops/diagnostics
- Ingestion pipeline automation (LazyLibrarian/OpenBooks) unless needed for testing

---

## Phase 1 — Hardening within current architecture (fast, safe)

### 1. Sync verification & metadata
**Why:** “synced” is currently a boolean without proof; users can’t tell where it went.

**Changes:**
- Add job fields:
  - `sync_target_host`, `sync_target_path`, `sync_timestamp`, `sync_file_count`, `sync_status`
- Update `copy_to_audiobookshelf()` to:
  - Verify SSH target path exists before rsync
  - Capture rsync stdout/stderr
  - Count files post‑sync and record
  - Mark sync failure with details
- Expose sync fields in `/api/jobs/<id>` and Ops diagnostics

**Files:**
- `webapp/app.py` (DB migration + sync logic + API)

### 2. Per‑job log capture
**Why:** troubleshooting is guesswork without a persistent per‑job log.

**Changes:**
- Write `data/logs/<job_id>.log` for key lifecycle events:
  - job start, conversion engine, container name, chapter progress, failure reason
  - rsync results for ABS
- Add `/api/jobs/<id>/logs` to return tail (already exists; wire to file)

**Files:**
- `webapp/app.py`

### 3. Container hygiene + deterministic cleanup
**Why:** stale container names are a major failure source.

**Changes:**
- On job start: `docker rm -f <container_name>` if exists (already partially done; standardize)
- On job completion: remove conversion container
- On failure: remove conversion container after log capture

**Files:**
- `webapp/app.py`

### 4. Queue resilience check
**Why:** avoid silent stalls.

**Changes:**
- If no converting jobs and queued > 0, auto‑start next job (already exists; ensure no race)
- Add health/diagnostics to show queue runner state

**Files:**
- `webapp/app.py`, `webapp/templates/index.html`

---

## Phase 2 — Architecture split (resilient by design)

### 5. Split queue worker from webapp
**Why:** isolates conversion lifecycle from UI deploys.

**Changes:**
- Add `worker` service in `docker-compose.yml` using same image
- Worker runs a new `python -m worker` entrypoint that:
  - monitors queue
  - starts conversions
  - owns watchdog
- Webapp becomes UI/API only

**Files:**
- `webapp/app.py` (extract queue/worker logic)
- `webapp/worker.py` (new)
- `webapp/Dockerfile`
- `docker-compose.yml`

### 6. Regression tests / smoke checks
**Why:** prevent re‑introducing queue stalls.

**Changes:**
- Extend `scripts/smoke-check.sh` to:
  - call queue status
  - verify `/api/version`
  - verify job log endpoint

**Files:**
- `scripts/smoke-check.sh`

---

## Milestones
- M1: Phase 1 complete, deployed to Zorin, logs verified
- M2: Worker split complete, queue survives webapp restart
- M3: Smoke tests updated and documented

---

## Validation Checklist
- ABS sync verified with file count and target path
- Job log endpoint returns recent log lines
- Stale container conflicts no longer occur
- Queue continues after webapp restart

