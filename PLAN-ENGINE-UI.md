# PLAN: Next-Gen Engine + Web UI Upgrade

**Status: planned, awaiting Dave's engine decision (see LOW-COST-TTS.md
bake-off). Live plan — when superseded, move to `archive/plans/`.**

What is already DONE and needs no UI work: the mandatory preprocessing
pipeline (PREPROCESSING.md stages 1–3) runs invisibly for every job on every
engine. The upgrades below add the chosen next-gen engine to the app and
surface preprocessing in the UI.

## Phase A — Chatterbox Turbo as a first-class engine

Applies if Turbo (with LibriVox UK voices) wins. Est. one working session.

1. **Compose service** (`docker-compose.yml`):
   - New service `chatterbox-tts` from devnen/Chatterbox-TTS-Server
     (build from their repo; no published image), CPU by default.
   - Mount `data/voice_refs/` into the server's `voices/` dir so
     `uk_male_minter` / `uk_female_golding` are predefined voices.
   - `config.yaml`: `model.repo_id: chatterbox-turbo`, port 8004.
   - New env `CHATTERBOX_URL` (default `http://chatterbox-tts:8004/v1`),
     overridable to a Vast SSH tunnel exactly like `KOKORO_URL` GPU mode.
2. **webapp/app.py plumbing** — add `tts_engine == 'chatterbox'` to ALL
   THREE command-builder/branch sites (search for `tts_engine ==`):
   `convert_book`, `build_retry_cmd_from_job`, and the voice-preview
   endpoint. Base URL = `CHATTERBOX_URL` (via tts-proxy `/j/{job}/v1` when
   `TTS_PROXY_URL` set, for transcript capture); model name `tts-1`;
   voice name = predefined voice file stem.
3. **UI** (`webapp/templates/index.html`):
   - Engine dropdown: add "Chatterbox Turbo (UK voices)".
   - Voice list: `uk_male_minter` → "Arthur (UK male)", `uk_female_golding`
     → "Ruth (UK female)" (display names TBD by Dave). Preview buttons work
     through the existing preview endpoint once step 2 is done.
4. **ETA/watchdog**: add a chars-per-minute entry for chatterbox to
   `estimate_eta_minutes` (measure once; CPU ~2.5x slower than realtime,
   RTX 3060 ~3x faster).
5. **GPU-PLAYBOOK addendum**: Vast template for the chatterbox server image
   (mirror the Kokoro template: onstart watchdog, port, ≤$0.06/hr 3060
   filter), tunnel port 8891 to avoid clashing with Kokoro's 8890.
6. **Smoke checks**: extend `scripts/smoke-check.sh` with a
   `/v1/audio/voices` probe on the chatterbox service.

## Phase B — TADA as an engine (only if TADA wins)

Bigger lift; do not start without a GPU benchmark (LOW-COST-TTS.md).

1. Build a minimal FastAPI wrapper exposing OpenAI-compatible
   `/v1/audio/speech` around HumeAI/tada (no server exists upstream).
   Reference audio per voice name, ~880-char passes, stitch, return MP3.
2. Then follow Phase A steps 2–6 identically (`tts_engine == 'tada'`).

## Phase C — Preprocessing in the UI (independent of engine choice)

1. **"Preprocessed" badge per job**: `convert_book` already logs sanitizer/
   normalizer activity; store `preprocess_changes` count on the job row and
   show a badge + tooltip in the queue/history tabs.
2. **Narration profile panel (PREPROCESSING.md Stage 4)**: job detail view
   gets a "Narration profile" card — LLM-generated JSON (domain, entity
   lexicon, number style) shown before conversion starts, editable, with
   approve-or-ignore semantics. Feeds `--search_and_replace_file` and the
   Stage 5 system prompt.
3. **Voice audition helper (nice-to-have)**: paste a LibriVox archive.org
   URL + offset, server cuts an 18s reference clip into `data/voice_refs/`
   and registers it as a new voice.

## Non-goals

- No UI redesign; the tab structure stays.
- No removal of existing engines (EdgeTTS/Kokoro/Piper remain).
