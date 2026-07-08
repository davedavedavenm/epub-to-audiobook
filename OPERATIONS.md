# Operations Runbook & Incident Log

How the system behaves under failure, what the states mean, how to respond,
and the honest record of incidents found during hardening. **This file is the
documented plan — if it isn't written here or in PLAN.md, it doesn't count.**

## Job states and what they actually mean

| State | Meaning | Action needed |
|-------|---------|---------------|
| `queued` | waiting for a worker slot (MAX_CONCURRENT_JOBS, default 1) | none |
| `converting` | converter container running | none — watch progress |
| `recovering` | **designed behavior, not a new failure**: the converter died mid-book with partial output; the system is re-converting only the missing chapters, one at a time | none unless it loops (see incidents) |
| `failed` | retries exhausted or timed out | read the Log on the job card; Resume re-runs only missing chapters |
| `completed` | all chapters done; ABS sync attempted | check sync badge |

## Capacity truths (NUC, 15 GB RAM)

- Kokoro (idle ~1-2 GB) + Chatterbox (2-6 GB generating) + webapp/worker fit.
- **TADA does NOT fit** alongside them (model load needs ~6.5 GB peak). The
  tada-tts service is intentionally not run on the NUC; the UI health
  lockdown marks TADA offline there. TADA runs: Windows box (free, slow),
  GitHub Actions (free, very slow), or Vast GPU (fast, ~GBP0.5/book).
- A full Chatterbox book on the NUC is ~12-16 h. The job timeout is floored
  accordingly (see incident 3).

## Common failures → responses

- **Engine offline** (UI shows OFFLINE, queueing returns 409): start it —
  `docker compose --profile chatterbox|tada up -d`.
- **Job failed with some chapters done**: press *Resume from failure* — only
  missing chapters are re-run.
- **Chatterbox/TADA server unresponsive or restarted**: it now has a hard
  mem_limit; Docker restarts it cleanly and in-flight chapter retries recover.
  If it thrash-restarts, reduce concurrent jobs to 1 and check `free -h`.
- **Vast GPU**: only via `scripts/vast-gpu.sh` (see GPU-SAFETY.md). Always
  `down` after. Health must show `cuda_available:true` or you're paying GPU
  price for CPU speed.

## Incident log

### 2026-07-07a — Full-book job failed 3x instantly (job d67c50ac)
- **Symptom**: "Container died unexpectedly", 0% each retry.
- **Root cause**: UI chapter count off-by-one (end 19 vs converter's 18) made
  the converter exit at startup; self-healing capped the range but every
  retry aborted on a stale `container_name` tripping the duplicate-start
  guard. Second bug: the webapp ran conversions despite QUEUE_RUNNER=0.
- **Fixes**: retries clear container_name + force-remove stale container;
  job spawns gated by QUEUE_RUNNER_ENABLED. Verified: same job re-run
  self-healed and converted.

### 2026-07-07b — Chatterbox server OOM death-spiral mid-book (job ebe7c78d)
- **Symptom**: book died at ch6; each chapter retry ground ~45 min then
  failed; kernel log: `Out of memory: Killed process (uvicorn) rss:10.8GB`.
- **Root cause**: the engine server ran generations **concurrently** (FastAPI
  sync threadpool). When a long chapter made the converter's client time out
  and retry, the server kept generating the abandoned request AND the new
  one → memory ballooned → kernel OOM-killed the server → every retry hit a
  dead/thrashing engine. Compounding: job timeout (375 min) was far below a
  realistic full-book time because partial-range jobs had polluted the
  chars/sec metrics (whole-book char_count recorded for 1-chapter jobs).
- **Fixes**: (1) generation serialized behind a lock + inference_mode + gc in
  BOTH engine servers; (2) mem_limit on engine containers so overruns restart
  cleanly; (3) timeout floored at char_count/4 chars-per-sec for
  chatterbox/tada; (4) metrics recorded only from full-book conversions.
- **Status**: fixes committed; engine images rebuild in CI; the job resumes
  (chapters 1-5 already done) after the fixed image is pulled.


### 2026-07-08b — "endnote numbers read aloud" was actually year-spelling (Apple in China)
- **Symptom (Dave)**: "from its founding in 1970......6", "returned in 1990...7"
  — sounded like endnote citation numbers being spoken.
- **Diagnosis**: NOT endnotes (this book's refs are empty `<span id="ennoteN"/>`
  anchors, correctly stripped). The years 1976 and 1997 were spelled out as
  "nineteen seventy-SIX" / "nineteen ninety-SEVEN"; TADA pauses before the
  final digit, so "six"/"seven" sounded detached — heard as "1970...6".
- **Fix**: number/year/large-number spelling is now SKIPPED for modern
  voice-clone engines (chatterbox/tada) via `normalize_text_for_tts(...,
  modern=True)`, plumbed through preprocess_epub + app + convert_book. Modern
  models read "1976" natively and correctly. Legacy engines (Kokoro/Piper)
  unchanged. Regression-guarded.
- Lesson: several normalization "helpers" tuned for dumb engines actively
  HURT modern models (this + the em-dash→comma fix). Modern path should be
  minimal-normalization.

### 2026-07-08 — Duplicate recovery threads across processes (job ebe7c78d)
- **Symptom**: resume + worker startup each launched a chapter-recovery pass
  4 s apart (both logged "Retrying 9 missing").
- **Root cause**: the duplicate-recovery guard was an in-memory dict; the
  resume API runs in the webapp process and orphan cleanup in the worker —
  separate processes, so the guard could not see the other thread.
- **Fix**: cross-process recovery lock in the DB (app_settings key
  `recovery_lock_<job>`, 3 h staleness takeover). Regression-guarded.
- **Correction (same morning)**: NOT benign — the racing threads killed each
  other's retry containers, producing spurious 16-second "Chapter FAILED
  after 3 retries" verdicts while the real generation was still running.
  Lock deployed 2026-07-08 06:05 and verified live ("another process holds
  the recovery lock, skipping").
- **Also fixed**: the UI froze at the pre-crash percentage during recovery
  (looked stuck all night while 4 chapters actually completed — file
  timestamps 21:06/23:49/03:03/06:09). Recovery now updates
  progress_percent/current_chapter as chapters land.

**Speed reality for this class of book**: Inside Apple's chapters are 45-80
MINUTES of audio each; the NUC generates ~one chapter per ~3 h. A ~13 h
audiobook = roughly a day and a half of NUC compute. That is the honest price
of the free path; the GPU runbook does the same book in ~4 h for ~GBP0.5.

### 2026-07-06/07 — GPU images silently ran on CPU
- CPU-only torch + missing NVIDIA envs; no sshd in slim images; GHCR pulls
  stall on slow Vast hosts. All fixed; validated with measured RTFs (TADA
  0.34, Chatterbox ~0.85 on RTX 3090). See LOW-COST-TTS.md.

## Standing rules for claims

A path may be called "working" in STATUS.md only with evidence: a completed
real conversion (job id / artifact / measurement) recorded alongside it.
