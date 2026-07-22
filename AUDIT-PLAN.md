# Audit Remediation Plan — 2026-07-22

Created from a full read-only audit (code, Docker, docs, tests, frontend, security).
Every item below is a concrete, verifiable change. Order is by risk-reduction per hour.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

---

## Phase 1 — Critical fixes (this session)

### 1.1 Runtime bugs in `webapp/app.py`
- [ ] Fix undefined `stderr` variable on conversion failure path (~line 3781)
- [ ] Remove duplicate `verify_chapter_integrity` definition (~lines 1171, 1190)
- [ ] Fix `_extract_epub_cover` called but never defined (~line 2940)
- [ ] Remove duplicate `MIN_CHAPTER_SIZE_KB` definition (lines 70, 108)
- [ ] Remove duplicate log message (lines 2004-2007, printed 3x)

### 1.2 Security: path traversal in `tts_proxy/proxy.py`
- [ ] Validate/sanitize `job_id` before using it as a filesystem path component
- [ ] Reject any `job_id` containing `/`, `\`, `..`, or non-alphanumeric chars

### 1.3 Security: GitHub Actions injection in `.github/workflows/convert.yml`
- [ ] Move all `${{ inputs.* }}` expressions to `env:` variables
- [ ] Quote all variable references in the `run:` block

### 1.4 Docker: create `.dockerignore`
- [ ] Exclude `.env`, `.secrets/`, `ssh-keys/`, `.git/`, `data/`, `__pycache__/`,
      `jobs.db`, `*.wav`, `.pytest_cache/`, `.gemini/`, `.claude/`, `archive/`,
      `.playwright-cli/`, `audio_verify/`, `*.epub`, `*.mp3`

### 1.5 Docker: fix duplicate `LIBRARY_DIR` env var
- [ ] Remove the dead first `LIBRARY_DIR` line (140/228) in `docker-compose.yml`
      — keep only the `${LIBRARY_DIR:-/mnt/openbooks}` that matches the volume mount

### 1.6 Docker: add healthchecks to webapp and worker
- [ ] Add curl-based healthcheck to `webapp` service (`/api/health` or similar)
- [ ] Add healthcheck to `worker` service
- [ ] Change `depends_on` for kokoro from `service_started` to `service_healthy`
- [ ] Reduce kokoro healthcheck interval from 300s to 60s

### 1.7 Docker: add memory limits to webapp and worker
- [ ] Add `mem_limit` to webapp (2g) and worker (4g) services

---

## Phase 2 — Doc fixes (this session)

### 2.1 Stale deployment path
- [ ] Fix `README.md` — `/opt/epub-to-audiobook` → `$STACK_PATH` or the real path
- [ ] Fix `GPU-PLAYBOOK.md` lines 108, 208 — same stale path
- [ ] Fix `scripts/deploy.sh` default `STACK_PATH`

### 2.2 Stale hardware references (post i5-12400 upgrade)
- [ ] Update `OPERATIONS.md` "Capacity truths (NUC, 15 GB RAM)" section
- [ ] Update `ENGINES.md` hardware table (line 112)
- [ ] Update `PLAN.md` NUC 32 GB SODIMM discussion (already happened)
- [ ] Fix `STATUS.md` internal contradiction (lines 106-107 vs 8-16)

### 2.3 Doc consistency
- [ ] Fix `GETTING-STARTED.md` line 140 — settings are in DB, not `.env`
- [ ] Add `ENGINES.md` to `AGENTS.md` doc map table
- [ ] Fix `AGENTS.md` reference to empty `archive/` directory
- [ ] Fix `AGENTS.md` stage count ("5 stages" → "6 stages; 1–4 implemented")
- [ ] Update `PLAN.md` §6 — mark completed items as done
- [ ] Fix version mismatch: `.env.example` says 1.3.0, README says 2.0.x

### 2.4 `.env.example` completeness
- [ ] Add missing vars: `KOKORO_URL`, `CHATTERBOX_URL`, `TADA_URL`, `PIPER_URL`,
      `TTS_PROXY_URL`, `GPU_RENDER_ENABLED`, `AUTOSCALE_*`, `AUDIO_ASR_VERIFY_ENABLED`,
      `TELEGRAM_*`, `AWS_*`, `KAGGLE_*`, `VASTAI_*`, `MAX_CONCURRENT_JOBS`

---

## Phase 3 — Code quality (next sessions)

### 3.1 `app.py` thread safety
- [ ] Add threading locks around `running_processes`, `running_containers`,
      `_recovery_in_progress`, `_watchdog_last_progress`

### 3.2 File handle leaks in `kaggle_render.py`
- [ ] Replace all bare `open()` calls with `with` context managers (5+ instances)

### 3.3 DRY: consolidate duplicate `epub_generator.py`
- [ ] Determine which version (root vs webapp) is canonical
- [ ] Remove the other; update any imports

### 3.4 DRY: engine URL selection logic
- [ ] Extract the `if tts_engine == 'piper': ... elif ...` pattern into a shared
      helper used by both `convert_book()` and `build_retry_cmd_from_job()`

### 3.5 Error handling cleanup
- [ ] Replace bare `except: pass` / `except: continue` with specific exception
      types and logging in: `app.py`, `epub_generator.py` (both), `llm_metadata.py`
- [ ] Fix `except (UnicodeDecodeError, Exception): pass` in `tts_preprocess.py:527`

### 3.6 Logging
- [ ] Replace `print()` calls with proper logging in `epub_generator.py` (both),
      `tts_proxy/proxy.py`
- [ ] Remove `import signal` (unused) from `app.py`
- [ ] Normalize `import time as _time` / `as time_module` / `as t` aliases

### 3.7 GPU manager supply chain
- [ ] Add SHA-256 checksum verification for the downloaded `vast.py` in
      `gpu_manager.py`, or vendor the CLI

---

## Phase 4 — Docker hardening (next sessions)

### 4.1 Docker socket proxy
- [ ] Add Tecnativa/docker-socket-proxy as a compose service
- [ ] Whitelist only needed endpoints (containers/create, start, stop, logs, etc.)
- [ ] Point webapp + worker at the proxy instead of raw `/var/run/docker.sock`

### 4.2 Non-root containers
- [ ] Add `USER` directive to all 5 Dockerfiles
- [ ] Fix file ownership for any paths the app writes to

### 4.3 Network segmentation
- [ ] Define custom Docker networks (frontend, backend, engines)
- [ ] Remove unnecessary port exposure (tts-proxy 8882 → internal only)

### 4.4 Image hygiene
- [ ] Pin `kokoro-fastapi-cpu` to a specific version tag (not `:latest`)
- [ ] Add multi-stage builds to webapp and tts-proxy Dockerfiles
- [ ] Replace `curl | sh` Docker CLI install with pinned apt package
- [ ] Add logging rotation config to all services

### 4.5 Dependency pinning
- [ ] Pin all Python deps in `webapp/requirements.txt` (pip freeze)
- [ ] Pin `chatterbox-tts` and `hume-tada` to specific versions
- [ ] Add a `requirements.lock` or use `pip-compile`

---

## Phase 5 — Testing (next sessions)

### 5.1 API smoke tests
- [ ] Add pytest fixture that starts the Flask test client
- [ ] Test: library listing, book upload, conversion submit, job status, settings CRUD
- [ ] Test: voice preview endpoint, sample endpoint

### 5.2 Worker/queue tests
- [ ] Test: job lifecycle (queued → converting → completed)
- [ ] Test: recovery from failure (missing chapters re-run)
- [ ] Test: cancelled jobs stay cancelled (regression for #14)

### 5.3 Engine integration tests (mocked)
- [ ] Test: engine URL selection for each engine type
- [ ] Test: modern vs legacy preprocessing path selection
- [ ] Test: failover chain behavior

### 5.4 CI pipeline
- [ ] Add GitHub Actions workflow: lint + pytest on PR
- [ ] Add webapp image build + push to CI

---

## Phase 6 — Frontend (later)

### 6.1 Quick fixes
- [ ] Fix `btoa()` crash on non-ASCII book filenames
- [ ] Remove dead legacy "Narration Press" CSS (lines 9-128)
- [ ] Remove unused Google Fonts `<link>` (Fraunces, Hanken Grotesk)
- [ ] Fix `font-family: 'Lora'` references (load it or remove)
- [ ] Add error handling to `loadLibrary()` and `loadHistory()`

### 6.2 Accessibility
- [ ] Add ARIA roles to tab interface
- [ ] Associate labels with inputs
- [ ] Add `aria-label` to icon buttons

### 6.3 Performance
- [ ] Gate polling intervals behind active tab check
- [ ] Debounce API calls where appropriate

### 6.4 Mobile responsiveness (PLAN.md §5 scope)
- [ ] Collapsible sidebar with hamburger menu
- [ ] Responsive grid for library cards

---

## Phase 7 — Repo hygiene (quick wins)

- [ ] Remove root `epub_generator.py` and `convert.sh` if superseded
- [ ] Remove duplicate `.gitignore` entries (ssh-keys/, __pycache__/)
- [ ] Add `.gemini/` to `.gitignore`
- [ ] Add `.gitattributes` with `*.wav binary`
- [ ] Evaluate git-lfs for the 28 WAV voice reference files
- [ ] Add `CONTRIBUTING.md`

---

## Not in scope (tracked elsewhere)

- `app.py` decomposition into modules — too large for a remediation pass;
  should be its own project with a design doc
- TADA engine fix (#23) — separate issue
- QA Layer 2 UI wiring (#7, #10) — PLAN.md §1
- M4B output — robustness backlog
- Vast GPU one-click — PLAN.md §3
