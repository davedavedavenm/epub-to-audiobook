# Project Status & Remaining Tasks

**Last updated: 2026-07-06.** Honest single source of truth. If it says
"verified" it was actually run; "unverified" means the code exists but hasn't
been proven end-to-end.

## TL;DR

Turbo (Chatterbox) is a working, containerised, local-default engine with UK
voices, and a real conversion has been proven end-to-end including ABS sync.
The system is usable for full-book testing on Turbo **now**. It is not yet
"flawless" — full-length reliability, TADA integration, and several polish
items remain (below).

## Done & VERIFIED (actually run)

- **Mandatory preprocessing pipeline** (structural sanitizer + normalization
  + pronunciation). Fixes endnotes, unicode, numbers/years/currency. Live in
  prod. Tests in `tests/test_tts_preprocess.py` (21 pass). See PREPROCESSING.md.
  - Recent fix: years 2000–2009 now read "two thousand [n]" (was "twenty
    hundred" / "twenty oh one").
- **Chatterbox Turbo engine** — `chatterbox/` container (CPU, OpenAI-compatible
  server, UK voices baked in). Builds and runs on zorin.
  - **End-to-end conversion VERIFIED**: a real 1-chapter job (engine
    `chatterbox`, voice Arthur) completed 100% and produced a valid MP3.
- **ABS sync VERIFIED**: completed jobs rsync to Audiobookshelf on `docker-vm`
  at `/opt/stacks/audiobookshelf/audiobooks/<book>_<jobid>/`.
  - **Does NOT overwrite existing audiobooks** — each conversion goes to a
    unique `_<jobid>` folder, and rsync runs without `--delete`. Converting
    the same book twice creates two ABS folders (duplicate, not replacement).
- **Web UI updated** for: Upload voice picker, library voice-blend + per-book
  pronunciation regex, queue pause/cancel/retry-all/log viewer, preprocessing
  PRE badge, global pronunciation dictionary, Render Location toggle, honest
  Polly/Inworld labels, Arthur/Harriet voices. (Confirmed present in deployed
  UI.)
- **GPU safety**: `GPU_RENDER_ENABLED` defaults off, `/api/gpu/scale-up` 403s
  by default, `AUTOSCALE_ENABLED` compose default flipped to false. See
  GPU-SAFETY.md.

## Done but UNVERIFIED end-to-end (works in theory / at unit level)

- **Full-length novel on Turbo** — only 1 chapter tested. Multi-hour runs,
  NUC memory footprint (Chatterbox + Kokoro + worker in RAM), watchdog over
  long jobs: not yet proven. **This is what your full-book test will surface.**
- **Chatterbox voice preview in the UI** — first click triggers a ~2 min model
  load; the request may appear to hang / the preview UX is untested.
- **Chatterbox crash-recovery / chapter-retry path** — code branch added but
  not exercised by an actual mid-job failure.

## NOT done (remaining tasks)

Priority order:

1. **Pre-warm the Chatterbox model on container start** — avoid the ~2 min
   first-request stall (load model in a startup hook, not lazily).
2. **Deploy flag fix** — the deploy uses `--profile piper`; Chatterbox needs
   `--profile piper --profile chatterbox` or it won't restart after a
   redeploy. Update `scripts/deploy.sh` and docs.
3. **Public-repo hygiene** — repo is PUBLIC and contains the homelab private
   IP (192.168.1.113), internal paths (`/home/dave/ai/lab/...`), git email.
   Decide: scrub these (parameterize) or make the repo private.
4. **TADA as an app engine (Phase B)** — currently standalone scripts only.
   Needs the OpenAI-compatible wrapper container + engine wiring, and a
   production-ready first-word fix (the "lead-in" trick currently *speaks* the
   filler word — must trim it). Recipe in PLAN-ENGINE-UI.md Phase B.
5. **Pronunciation seed rules** — e.g. "US" reads as the word "us". The UI
   supports per-book + global regex, but no default dictionary is shipped.
6. **Render toggle scope** — the Local/Cloud-GPU toggle currently only gates
   the Kokoro autoscaler. It does not yet move Chatterbox/TADA compute to a
   GPU (those have no GPU-integration path in-app yet). Wire this when Phase
   B/C land.
7. **ETA/watchdog tuning for Chatterbox** — default rate (~10 chars/s)
   happens to match Chatterbox CPU and errs safe, but a measured entry would
   be cleaner (and correct on GPU).

## Robustness improvements worth making (not blocking)

- **Duplicate-book guard**: warn/skip when a book already has an ABS folder,
  to avoid accidental duplicates.
- **Health gating**: the webapp could refuse to queue a Chatterbox job if
  `chatterbox-tts` isn't healthy, with a clear message (currently the job
  would start and stall).
- **`.env.example` coverage**: ensure every new env (`CHATTERBOX_URL`,
  `GPU_RENDER_ENABLED`, `AUTOSCALE_ENABLED`) is documented there for friends.
- **M4B output + chapter metadata** for nicer ABS playback (currently per-
  chapter MP3s).
- **Front-matter detection**: auto-skip copyright/title pages so "chapter 1"
  isn't the copyright page.

## Doc map

README.md (setup/sharing) · PREPROCESSING.md (text pipeline) ·
LOW-COST-TTS.md (engine bake-off + costs) · PLAN-ENGINE-UI.md (build plan) ·
GPU-SAFETY.md (GPU rules) · ROADMAP.md (feature status) · AGENTS.md (agent
guide). This file (STATUS.md) is the current-state index.
