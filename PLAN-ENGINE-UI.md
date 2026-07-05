# PLAN: UI Parity + Next-Gen Engines

**Status: live plan, execution-grade. Audited against the code 2026-07-04.**
Written so a less-experienced agent can execute phase by phase. Read
[AGENTS.md](AGENTS.md) rules first (no `git add -A`; deploy via git only).

Engines are ADDITIVE — this is not either-or. The app already runs five
engines side by side; Turbo and TADA join the list, one becomes the default
narrator. Phase 0 is valuable regardless of any engine decision.

## Verified architecture facts (do not re-derive; checked 2026-07-04)

- **Voice → engine mapping**: `VOICES` dict, `webapp/app.py:391` — each voice
  id maps to `{name, accent, gender, engine}`. Engine for a job is derived
  `VOICES[voice].get('engine', 'kokoro')` in `start_conversion` (~line 3818)
  and `convert_from_library` (~line 4548). **Adding an engine = add VOICES
  entries + a `tts_engine == '<engine>'` branch at the three sites below.**
- **The three engine-branch sites** (search `tts_engine ==` in app.py):
  1. `convert_book` (~line 3005) — main conversion, sets `tts_base_url`/`tts_model`.
  2. `build_retry_cmd_from_job` (~line 2316) — crash-recovery command rebuild.
  3. `generate_voice_preview` (~line 2000) — per-engine preview branches.
- **Job DB schema** (`init_db`, ~line 490): already has `voice2`,
  `newline_mode`, `title_mode`, `custom_regex`, `queue_rank`, sync columns.
  Schema migrations elsewhere in init_db use `ALTER TABLE ... ADD COLUMN`
  guarded by try/except — follow that pattern for new columns.
- **Endpoints that exist but have NO UI** (verified live, all in app.py):
  `/api/queue/pause` (POST `{paused}` or toggle), `/api/queue/reorder`
  (POST `{ordered_ids: [...]}`), `/api/queue/retry-failed`,
  `/api/jobs/<id>/cancel`, `/api/jobs/<id>/retry`, `/api/jobs/<id>/logs`,
  `/api/jobs/<id>/timeline`, `/api/jobs/<id>/sync`,
  `/api/library/estimate_cost` (POST `{path, voice}`), `/api/diagnostics`.
- **Upload form** (`/api/convert`) accepts `voice, voice2, start_chapter,
  end_chapter, tts_speed, newline_mode, title_mode, custom_regex,
  notify_*` — but the UI (`startProduction()` in
  `webapp/templates/index.html`) sends only the file and a **hardcoded**
  `voice='en-GB-RyanNeural'`.
- **Library convert** (`/api/library/convert`) accepts only
  `path, voice, start_chapter, end_chapter, tts_speed` — it silently drops
  voice2/custom_regex/newline_mode/title_mode, and contains leftover
  `print(f"DEBUG RAW: ...")` statements.
- **GPU autoscaler** (`webapp/gpu_manager.py`): full Vast.ai lifecycle
  (search → create from template → tunnel container on port 8890 → verify →
  adopt-on-restart → cost cap env `AUTOSCALE_COST_CAP`). **Hardwired to
  Kokoro** (template hash/id, `GPU_KOKORO_URL`, health check). UI shows only
  a status dot; scale-up/down endpoints exist.
- **Preprocessing** (PREPROCESSING.md stages 1–3) runs inside `convert_book`
  (~line 2934): writes `<name>_tts.epub`, logs to job log, but stores
  nothing on the job row → invisible to the UI.
- Frontend is a single file, `webapp/templates/index.html` (718 lines,
  vanilla JS, `voices` injected via Jinja) + `webapp/static/llm_ui.js`
  (LLM provider dropdown logic).

## Phase 0 — UI parity & hygiene (unblocked, engine-independent)

**STATUS: DONE 2026-07-04** (commit `9c59912`, deployed to zorin, verified:
UI renders, pronunciations endpoint round-trips, queue status live; PRE
badge appears on the next converted book). Tasks kept below as the record
of what was built.

Each task: change → acceptance criteria (AC).

**0.1 Upload tab voice picker.** In index.html, add Narrator select (reuse
the `voiceOptions` optgroup builder from `renderLibrary()` — extract it to a
shared function), speed input, and optional chapter range to the Upload card;
`startProduction()` sends them via FormData instead of the hardcoded voice.
AC: uploading with a Kokoro voice selected creates a job whose queue card
shows that voice/engine; no hardcoded `en-GB-RyanNeural` remains in index.html.

**0.2 Library convert parity.** Backend: `convert_from_library` reads
`voice2`, `custom_regex`, `newline_mode`, `title_mode` from the JSON body
(mirror `start_conversion`'s handling incl. validation `voice2 in VOICES`)
and passes them into `save_job`; delete the `DEBUG RAW`/`DEBUG PARSED`
prints. Frontend: workspace panel gains "Blend voice (optional, Kokoro
only)" select and a collapsible "Pronunciation fixes (regex)" textarea; sent
in the POST. AC: a library job created with voice2 + custom regex shows both
on the job row (`sqlite3 data/jobs.db "SELECT voice2,custom_regex FROM jobs
ORDER BY created_at DESC LIMIT 1"`), and the converter receives
`--search_and_replace_file`.

**0.3 Queue controls.** Queue tab header gets: Pause/Resume toggle (reflects
`/api/queue/status`), Retry-all-failed button. Every active job card gets
Cancel (`/api/jobs/<id>/cancel`); failed cards keep existing Resume/Delete.
Add a collapsible "Log" section per card fetching `/api/jobs/<id>/logs?tail=40`
on expand. AC: pausing prevents the next queued job from starting (verify
with two queued jobs); cancel stops the container (`docker ps` shows
`audiobook-<id>` gone); log expander shows the same lines as
`data/logs/<job>.log`.

**0.4 Preprocessing visibility.** Backend: add job column
`preprocess_summary TEXT` (ALTER TABLE pattern); in `convert_book`, after
`preprocess_epub` succeeds, store e.g. `"sanitized+normalized, N files
changed, lexicon M terms"` (preprocess_epub already counts `changes_made` —
return/expose it; lexicon size known at call site). UI: badge "PRE ✓" with
tooltip = summary on queue + history cards; tooltip says "failed, original
text used" when preprocessing errored. AC: convert any epub → badge appears;
`preprocess_summary` populated in DB; unit tests still pass
(`python -m pytest tests/`).

**0.5 Global pronunciation editor.** New endpoints GET/POST
`/api/settings/pronunciations` reading/writing
`UPLOAD_DIR/global_pronunciations.conf` (plain text, `search==replace` per
line — format documented in a placeholder in the textarea). Settings tab
gains a "Pronunciation dictionary (all books)" card with textarea + save.
AC: saved lines appear in the next job's generated `search_<job>.conf`.

**0.6 Settings honesty.** Polly card: add warning line "Legacy — proven too
expensive for full audiobooks (see LOW-COST-TTS.md); kept for compatibility."
Inworld card: add "~GBP2–5/novel — over the GBP3 budget rule for full books."
AC: text visible; no functional change.

**0.7 Docs drift.** README + ROADMAP "UI Features" sections currently claim
Convert/Queue/Library/Ops/History tabs, 4 themes, design modes. Reality:
Library/Upload/Queue/Voices/History/Settings, light/dark. Fix both; screenshot
optional. AC: docs match the rendered UI.

Verification for the whole phase: `python -m pytest tests/`,
`docker compose config -q`, deploy to zorin via git, run
`scripts/smoke-check.sh http://localhost:8881`, convert one short epub end
to end.

## Phase A — Chatterbox Turbo engine (after Phase 0; ~one session)

1. **Compose service** `chatterbox-tts`: build from
   https://github.com/devnen/Chatterbox-TTS-Server (no published image;
   `build:` a vendored `docker/chatterbox/Dockerfile` cloning a pinned
   commit). CPU by default, port 8004, `config.yaml` with
   `model.repo_id: chatterbox-turbo`. Mount `./data/voice_refs:/app/voices:ro`
   so `uk_male_minter.wav` / `uk_female_golding.wav` are predefined voices
   (server uses file stem as voice name). Healthcheck: GET
   `/v1/audio/voices`. Env: `CHATTERBOX_URL` default
   `http://chatterbox-tts:8004/v1`.
2. **VOICES entries** (app.py:391 dict):
   `'uk_male_minter': {'name': 'Arthur (UK Human)', 'accent': 'British',
   'gender': 'Male', 'engine': 'chatterbox'}` and
   `'uk_female_golding': {'name': 'Harriet (UK Human)', ...}` (display names
   = Dave's call; voice id MUST equal the wav file stem).
3. **Engine branches** at the three verified sites: base URL
   `CHATTERBOX_URL` (route via `TTS_PROXY_URL/j/{job}/v1` when set, like
   Kokoro), `tts_model = 'tts-1'`. Preview branch: POST OpenAI speech shape
   to `CHATTERBOX_URL`.
4. **ETA model**: add `'chatterbox'` to `estimate_eta_minutes`'s rates.
   Measured: CPU ≈ 2.5x slower than realtime; RTX 3060 ≈ 3x faster
   (LOW-COST-TTS.md). Watchdog multipliers follow from ETA automatically.
5. **Reference-clip hygiene**: chunking is handled by the devnen server
   (default chunk 120 chars, configurable) — do NOT send >300-char
   generations anywhere else (known ending-degradation, LOW-COST-TTS.md).
6. **Smoke**: extend `scripts/smoke-check.sh` with chatterbox voices probe.
AC: voice preview plays for both UK voices from the Voices tab; a 2-chapter
test book converts end to end on CPU with engine badge CHATTERBOX; pytest
green.

## Phase B — TADA engine (gated: run GPU benchmark FIRST)

Gate: rent one RTX 3060 on Vast, run TADA-1B on ~10 min of canonical-passage
text, record RTF into LOW-COST-TTS.md. Proceed only if RTF < 1 (faster than
realtime).
1. Build `tada-server/` FastAPI wrapper: OpenAI-compatible
   `POST /v1/audio/speech {model, input, voice, response_format}` →
   sentence-split input to ~880-char passes (pacing drifts on longer passes —
   verified by ear 2026-07-03), reference wav per voice name from
   `voice_refs/`, concat, return MP3. `GET /v1/audio/voices` lists wav stems.
2. Then repeat Phase A steps 2–6 with `engine: 'tada'`, `TADA_URL`, port 8005.
Note TADA traits for the voice cards: most natural prosody; emergent
character voices on quoted dialogue (Dave likes this); Llama 3.2 license.

## Phase C — GPU autoscale for new engines

`gpu_manager.py` is Kokoro-specific. Generalize minimally: extract per-engine
config dict `{engine: {template_hash, template_id, tunnel_port, gpu_url,
cpu_url, health_path}}`; scale decisions unchanged. Requires creating a Vast
template for the chatterbox server image first (mirror the Kokoro template:
onstart watchdog loop, direct ports; document its hash in GPU-PLAYBOOK.md).
Tunnel port 8891 (Kokoro keeps 8890). AC: with `AUTOSCALE_ENABLED=true` and
3+ chatterbox jobs queued, a GPU instance spins up, jobs route to it, and it
destroys itself when the queue drains (cost cap respected).

## Phase D — Narration profile panel (PREPROCESSING.md Stage 4)

Backend first: profile generation module (extend `llm_metadata.py`
`generate_lexicon` to also sample high-difficulty excerpts and emit the full
profile JSON), stored on the job row (`narration_profile TEXT`). UI: job
detail card shows the profile pre-conversion with Edit/Approve; approved
lexicon compiles into the existing `search_<job>.conf` path. Spec details in
PREPROCESSING.md Stage 4. Do not start before Phases 0+A are deployed.

## Execution rules for the implementing agent

- One phase per PR/commit series; run `python -m pytest tests/` and
  `docker compose config -q` before every commit; never commit `.env`,
  `jobs.db`, audio, or `voice_refs` content.
- app.py is fragile (long history of indentation breakage): after every edit
  run `python -m py_compile webapp/app.py`.
- Deploy = push to master, then on zorin
  `cd /home/dave/ai/lab/stacks/epub-to-audiobook && git pull && docker
  compose --profile piper up -d --build`, then
  `bash scripts/smoke-check.sh http://localhost:8881`.
- The canonical listening test for any voice/engine change:
  `scripts/extract_test_passage.py` passage + `data/voice_refs/` clips
  (LOW-COST-TTS.md "Canonical test passage").
