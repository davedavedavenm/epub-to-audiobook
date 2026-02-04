# PLAN v2: Ingestion + UI Modernization

Status: Draft (2026-02-04)

## Goals

1. Build a reliable ebook ingestion flow from search/request/download into the app library.
2. Modernize the UI with a maintainable design system and clear conversion UX.
3. Keep live conversion reliability and queue behavior stable during rollout.

## Workstreams

### A) Ingestion Pipeline (LazyLibrarian/OpenBooks -> Library -> Convert)

1. Discovery and mapping
   - Inventory existing scripts on `khpy5` and `docker-vm`.
   - Document real source/destination paths and trigger points.
   - Confirm where the app reads library files (`LIBRARY_DIR`).
2. Pipeline contract
   - Define states: `requested`, `searching`, `downloading`, `syncing`, `ready`, `failed`.
   - Add durable logs and retry behavior per step.
3. Integration
   - Trigger requests from LazyLibrarian/OpenBooks automatically.
   - Sync final EPUB/PDF into the app library path.
   - Ensure the app library tab reflects new files without manual restarts.
4. Validation
   - Test at least 3 title flows end-to-end.
   - Verify failure recovery and idempotency.

### B) UI/UX System Upgrade

1. Design tokens + theming
   - Implement semantic tokens for both themes.
   - Remove hardcoded color drift and duplicated dark/light rules.
2. Component system
   - Standardize: button, input, select, card, tabs, progress, toast, modal, table row, empty state.
3. Information architecture
   - Primary flow emphasis: Upload -> Voice -> Start -> Progress.
   - Reduce visual noise and competing calls to action.
4. Status UX redesign
   - Clear phases, retry info, ETA confidence, failures, and next actions.
5. Advanced UI features (incremental)
   - Conversion timeline panel.
   - Queue operations bar.
   - Diagnostics drawer ("why slow").
   - Voice lab scaffold.
   - Recovery center scaffold.

### C) Deployment and Safety

1. One canonical stack path and reproducible deploy flow.
2. Version fingerprint endpoint and smoke checks.
3. No hardcoded secrets in compose.
4. Guard rails for stale container conflicts and restart recovery.

## Delivery Phases

### Phase 1 (done/in-progress reliability)
- Health endpoint resilience.
- Version fingerprint endpoint.
- Stale container cleanup on job start.
- Retry error surfaced in UI.
- Restart behavior fixes for queued jobs.

### Phase 2 (ingestion foundation)
- Host script discovery + path map.
- Ingestion state model + queue integration.
- Sync pipeline with retries and operator visibility.

### Phase 3 (UI system)
- Token system + component baseline.
- Convert/Queue screens refactor.
- Status card redesign.

### Phase 4 (advanced UX)
- Timeline, queue ops, diagnostics, voice lab/recovery center first iteration.

## Acceptance Criteria

1. A requested title appears in library and is convertible without manual file operations.
2. Retry/failure states are explicit in UI (no silent failures).
3. Dark/light themes share one token-driven style layer.
4. Deploy metadata (`/api/version`) always matches running build.

