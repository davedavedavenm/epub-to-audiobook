# Audit Remediation Plan — 2026-07-22

> **Historical audit checklist.** It records what was remediated in July; it is
> not current configuration guidance. `DECISIONS.md`, `STATUS.md` and
> `GPU-SAFETY.md` govern. In particular, the `AUTOSCALE_*` configuration noted
> below was retired on 2026-08-13 and queue-driven paid provisioning is banned.

Created from a full read-only audit (code, Docker, docs, tests, frontend, security).
Every item below is a concrete, verifiable change. Order is by risk-reduction per hour.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

---

## Phase 1 — Critical fixes (this session)

### 1.1 Runtime bugs in `webapp/app.py`
- [x] Fix undefined `stderr` variable on conversion failure path (~line 3781)
- [x] Remove duplicate `verify_chapter_integrity` definition (~lines 1171, 1190)
- [x] ~~Fix `_extract_epub_cover` called but never defined~~ — NOT A BUG: defined at line 5311
- [x] Remove duplicate `MIN_CHAPTER_SIZE_KB` definition (lines 70, 108)
- [x] Remove duplicate log message (lines 2004-2007, printed 3x)

### 1.2 Security: path traversal in `tts_proxy/proxy.py`
- [x] Validate/sanitize `job_id` before using it as a filesystem path component
- [x] Reject any `job_id` containing `/`, `\`, `..`, or non-alphanumeric chars

### 1.3 Security: GitHub Actions injection in `.github/workflows/convert.yml`
- [x] Move all `${{ inputs.* }}` expressions to `env:` variables
- [x] Quote all variable references in the `run:` block

### 1.4 Docker: create `.dockerignore`
- [x] Exclude `.env`, `.secrets/`, `ssh-keys/`, `.git/`, `data/`, `__pycache__/`,
      `jobs.db`, `*.wav`, `.pytest_cache/`, `.gemini/`, `.claude/`, `archive/`,
      `.playwright-cli/`, `audio_verify/`, `*.epub`, `*.mp3`

### 1.5 Docker: fix duplicate `LIBRARY_DIR` env var
- [x] Remove the dead first `LIBRARY_DIR` line (140/228) in `docker-compose.yml`
      — keep only the `${LIBRARY_DIR:-/mnt/openbooks}` that matches the volume mount

### 1.6 Docker: add healthchecks to webapp and worker
- [x] Add curl-based healthcheck to `webapp` service (`/api/health`)
- [x] Add healthcheck to `worker` service (pgrep-based)
- [x] Change `depends_on` for kokoro from `service_started` to `service_healthy`
- [x] Reduce kokoro healthcheck interval from 300s to 60s

### 1.7 Docker: add memory limits to webapp and worker
- [x] Add `mem_limit` to webapp (2g) and worker (4g) services

---

## Phase 2 — Doc fixes (this session)

### 2.1 Stale deployment path
- [x] Fix `README.md` — `/opt/epub-to-audiobook` → `$STACK_PATH` or the real path
- [x] Fix `GPU-PLAYBOOK.md` lines 108, 208 — same stale path
- [x] Fix `scripts/deploy.sh` default `STACK_PATH`

### 2.2 Stale hardware references (post i5-12400 upgrade)
- [x] Update `OPERATIONS.md` "Capacity truths (NUC, 15 GB RAM)" section
- [x] Update `ENGINES.md` hardware table (line 112)
- [x] Update `PLAN.md` NUC 32 GB SODIMM discussion (already happened)
- [x] Fix `STATUS.md` internal contradiction (lines 106-107 vs 8-16)

### 2.3 Doc consistency
- [x] Fix `GETTING-STARTED.md` line 140 — settings are in DB, not `.env`
- [x] Add `ENGINES.md` + `TTS-LANDSCAPE-2026-07.md` to `AGENTS.md` doc map table
- [x] Fix `AGENTS.md` reference to empty `archive/` directory
- [x] Fix `AGENTS.md` stage count ("5 stages" → "6 stages; 1–4 implemented")
- [x] Update `PLAN.md` §6 — mark completed items as done
- [x] Fix version mismatch: `.env.example` says 2.0.0, README says 2.0.x

### 2.4 `.env.example` completeness
- [x] Add missing vars: `KOKORO_URL`, `CHATTERBOX_URL`, `TADA_URL`, historical
      `PIPER_URL` (removed when Piper was retired on 2026-08-15),
      `TTS_PROXY_URL`, `GPU_RENDER_ENABLED`, `AUTOSCALE_*`, `AUDIO_ASR_VERIFY_ENABLED`,
      `TELEGRAM_*`, `AWS_*`, `KAGGLE_*`, `MAX_CONCURRENT_JOBS`, `VOICE_CACHE_*`

---

## Phase 3 — Code quality (next sessions)

### 3.1 `app.py` thread safety
- [x] Add `_state_lock` for `running_processes`, `running_containers`,
      `_recovery_in_progress`, `_proxy_progress_state`

### 3.2 File handle leaks in `kaggle_render.py`
- [x] Replace all bare `open()` calls with `with` context managers (7 instances)

### 3.3 DRY: consolidate duplicate `epub_generator.py`
- [x] Determine which version (root vs webapp) is canonical — webapp/ is canonical
- [x] Remove root epub_generator.py (dead code, never imported, never containerised)

### 3.4 DRY: engine URL selection logic
- [x] Extract `get_engine_url()` helper, replaced both if/elif blocks in app.py

### 3.5 Error handling cleanup
- [x] Extract `_strip_markdown_fences()` in llm_metadata.py (was 3x duplicated)
- [x] Fix `except (UnicodeDecodeError, Exception): pass` in `tts_preprocess.py`
- [ ] Replace remaining bare `except: pass` / `except: continue` in `app.py`

### 3.6 Logging
- [x] Replace `print()` calls with proper logging in `tts_proxy/proxy.py`
- [x] Remove `import signal` (unused) from `app.py`
- [ ] Replace `print()` in `webapp/epub_generator.py`
- [ ] Normalize `import time as _time` / `as time_module` / `as t` aliases

### 3.7 GPU manager supply chain
- [x] Add SHA-256 checksum verification for `vast.py` in `gpu_manager.py`
      (set `VAST_CLI_SHA256` to pin; None = accept any for now)

---

## Phase 4 — Docker hardening

### 4.1 Docker socket proxy
- [x] Add Tecnativa/docker-socket-proxy as a compose service
- [x] Whitelist only needed endpoints (CONTAINERS, IMAGES, GET, POST, NETWORKS, VOLUMES)
- [x] webapp + worker use `DOCKER_HOST=tcp://docker-socket-proxy:2375` on
      internal `dockersock` network; raw `/var/run/docker.sock` mount removed

### 4.2 Non-root containers
- [x] Add `USER` directive to tts_proxy, chatterbox, tada, audio_verify
- [x] Fix file ownership (`chown` at build time for /app, /data)
- [ ] webapp/worker still root — SSH keys under /root/.ssh + Docker CLI
      need further refactoring to move mount targets

### 4.3 Network segmentation
- [x] Add `dockersock` internal network for socket proxy isolation
- [x] Remove tts-proxy host port exposure (8882 → `expose` internal only)

### 4.4 Image hygiene
- [x] Pin `kokoro-fastapi-cpu` to `v0.2.2` (was `:latest`)
- [x] Add logging rotation (json-file, 10m max, 3 files) to all services
- [x] Replace `curl | sh` Docker CLI install with `apt docker.io`
- [ ] Multi-stage builds deferred (calibre makes slim final stage complex)

### 4.5 Dependency pinning
- [x] Pin all Python deps in `webapp/requirements.txt` to exact versions
- [x] Pin `chatterbox-tts==0.2.0`, `hume-tada==0.3.0`, fastapi, uvicorn, etc.

---

## Phase 5 — Testing

### 5.1 API smoke tests
- [x] 10 tests: health, version, voices, jobs, queue, settings, library,
      gpu, convert validation, 404 handling

### 5.2 Worker/queue tests
- [x] Job lifecycle (queued → converting → completed)
- [x] Cancelled jobs stay cancelled (regression for #14)
- [x] Queue counting with mixed states

### 5.3 Engine integration tests (mocked)
- [x] `get_engine_url()` for all 5 engine types
- [x] Modern vs legacy preprocessing contract
- [x] Year-spelling reversal (2026-07-14) verified in both modes

### 5.4 CI pipeline
- [x] GitHub Actions: pytest + compose config validation on push/PR
- [ ] Webapp image build + push to CI (deferred)

---

## Phase 6 — Frontend

### 6.1 Quick fixes
- [x] Fix `btoa()` crash → `encodeURIComponent`
- [x] Remove dead legacy CSS + unused Google Fonts
- [x] Fix `font-family: 'Lora'` → `var(--serif)`
- [x] Error handling on `loadLibrary()` / `loadHistory()`

### 6.2 Accessibility
- [x] ARIA tablist/tab/tabpanel roles on tab interface
- [x] `aria-label` on icon buttons (theme, close, preview)
- [x] `for`/`id` associations on 22 label-input pairs

### 6.3 Performance
- [ ] Gate polling intervals behind active tab check
- [ ] Debounce API calls where appropriate

### 6.4 Mobile responsiveness
- [x] Hamburger menu + sliding sidebar drawer at ≤768px
- [x] Single-column library grid on mobile
- [x] Semi-transparent overlay behind open sidebar

---

## Phase 7 — Repo hygiene

- [x] Remove root `epub_generator.py` (dead code)
- [x] Remove `convert.sh` (superseded by `scripts/convert_book.py`)
- [x] Remove duplicate `.gitignore` entries
- [x] Add `.gemini/` to `.gitignore`
- [x] Add `.gitattributes` with binary file markers
- [x] Add `CONTRIBUTING.md`
- [ ] Evaluate git-lfs for the 28 WAV voice reference files

---

## CosyVoice 3 audition — FAILED (2026-07-22)

- HF spaces all broken (silence / internal errors / quota)
- Kaggle kernels pushed (v4 has correct deps) but output pull blocked by
  KGAT_ token scope (`kernels.get` denied). Kernel may have succeeded on
  Kaggle — check the web UI manually.
- Kernel script kept at `scripts/kaggle/run_cosyvoice3.py` for retry.
- **Blocker**: need `kaggle.json` (username+key from kaggle.com/settings →
  Create New Token) instead of KGAT_ access_token for read permissions.

---

## Not in scope (tracked elsewhere)

- `app.py` decomposition into modules — too large for a remediation pass;
  should be its own project with a design doc
- TADA engine fix (#23) — separate issue
- QA Layer 2 UI wiring (#7, #10) — PLAN.md §1
- M4B output — robustness backlog
- Vast GPU one-click — PLAN.md §3
