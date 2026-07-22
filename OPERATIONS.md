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

## Capacity truths (zorin: i5-12400, 31 GB RAM, no GPU — upgraded 2026-07-20)

- Kokoro + Piper + Chatterbox + webapp/worker fit comfortably on 31 GB.
- **Chatterbox stays RUNNING** for voice previews and UI auditioning (previews
  are one short paragraph — cheap on CPU). Full-book renders go to Kaggle GPU.
- **TADA stays OFF** — it is broken (#23) and its 10 GiB cgroup was OOM-killed
  repeatedly on the old 15 GB NUC. Re-validate on the 31 GB box only after #23
  is fixed.
- `scripts/deploy.sh` enables Piper only by default. Chatterbox and TADA
  require `ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1`.
- Startup voice-preview generation defaults off. Set `VOICE_CACHE_ON_START=1`
  only for a controlled cache-fill window after confirming the enabled engines
  and host capacity.
- A full Chatterbox book on the i5-12400 is ~45 h (1.24 s/word measured).
  Use Kaggle GPU (~9 h, free) for full books.

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

### 2026-07-18 — Startup preview cache caused repeated TADA OOM bursts
- **Symptom:** repeated freezes/reboots after Docker and the web app started.
- **Trigger:** there were no queued TADA jobs. Five seconds after web-app start,
  `_cache_all_voices_background()` attempted missing TADA previews directly.
  Model load filled TADA's 10 GiB cgroup; the kernel killed uvicorn and Docker
  restarted it. Four preview attempts produced three kills per startup.
- **Wider finding:** retained journals also contain Chatterbox 6 GiB cgroup
  kills and TADA host-wide OOM events, so the history is a multi-engine memory
  problem rather than one infinite TADA retry loop.
- **Containment:** stop TADA and Chatterbox on the NUC; keep Kokoro/Piper/UI
  available. Preview caching and both heavy deploy profiles now default off.
- **Do not:** raise TADA to 12 GiB on this host; that removes the remaining
  headroom and risks converting a contained cgroup kill into host-wide OOM.

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
- **Codified 2026-07-08 (stop finding these one at a time)**: the
  MODERN-ENGINE CONTRACT is now documented at the top of
  `webapp/tts_preprocess.py` and enforced by
  `test_modern_contract_skips_all_plain_number_spelling`. Rule: for
  `modern=True`, SKIP every transform that respells a plain number / year /
  decade / large integer (engine reads them right); KEEP symbol/abbrev
  expansion ($, %, U.S., 1st); anything genuinely ambiguous for one book is
  caught adaptively by the per-book LLM narration profile, NOT by adding
  another regex. Decades (`1990s`) were brought under the guard at the same
  time. Any new numeric transform must go under the single `if not modern:`
  block by default.

### 2026-07-08c — Preprocessing now classifies fiction vs non-fiction
- The narration profile (`generate_narration_profile`) returns
  `form`/`is_fiction` and steers what it hunts for: fiction → character/place/
  invented names and dialogue flow (dashes, quotes); non-fiction → acronyms,
  company/brand names, ambiguous figures. Surfaced in the job log and the
  standalone converter, persisted in `narration_profile`.
- Honest limit: with a single-voice engine this does NOT do per-character
  voices. It biases pronunciation-rule search and pacing handling only.

### 2026-07-08d — TADA image silently ran on CPU (unpinned torch → cu130)
- **Symptom**: fresh Vast TADA instance came up healthy but `/health` showed
  `device:cpu, cuda_available:false` with `torch 2.12.1+cu130`.
- **Root cause**: `tada/Dockerfile` installed `torch --index-url cu124`
  UNPINNED, then `pip install -r requirements.txt`. hume-tada requires
  torch>=2.7 (cu124's max is 2.6.0) and pulls torchaudio/torchvision unpinned,
  so the requirements step re-resolved the whole stack from PyPI to the default
  cu130 build (torch 2.12). cu130 needs an R580+ driver; most GPU hosts have
  older drivers, so torch fell back to CPU. Chatterbox was unaffected because
  chatterbox-tts pins torch==2.6.0, matching its preinstalled cu124 build.
- **Fix**: pin the FULL cu126 stack (`torch==2.8.0 torchvision==0.23.0
  torchaudio==2.8.0 --index-url .../cu126`) BEFORE the requirements install so
  hume-tada finds everything satisfied and touches nothing. cu126 needs only
  R560+ (broad host coverage) and satisfies torch>=2.7. Regression-guarded
  (`test_tada_torch_stack_pinned`). `scripts/vast-gpu.sh` offer filter now
  requires `cuda_max_good>=12.6`.
- **What caught it**: the `/health` cuda_available gate — the standing rule to
  refuse CPU runs. Interim workaround for the run: used a CUDA-13 host so the
  still-deployed cu130 image worked; the cu126 image rebuilds via CI.
- Lesson: an unpinned `pip install torch` is a landmine — a transitive dep with
  a torch floor silently re-pulls the default (newest-CUDA) build. Pin the
  whole torch stack, always.

### 2026-07-08 — Kaggle free-GPU path blocked on phone verification
- Kaggle kernels get NO internet ("Temporary failure in name resolution",
  pip/git/HF all fail) until the account is **phone-verified**
  (kaggle.com/settings), regardless of `enable_internet:true` in
  kernel-metadata.json. One-time, needs Dave's phone.
- The kernel + epub dataset are pushed and ready
  (`davedavedavedavenm/apple-china-tada-ch1-2`); re-run free once verified.
  Alternative if verification isn't possible: attach the ~5GB TADA models +
  hume-tada wheel as offline Kaggle datasets so the kernel needs no internet.

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

### 2026-07-08e — real-worker-path deploy surfaced a cluster of latent bugs
Running conversions only through hand-driven scripts hid several bugs; deploying
the day's code to the live worker and submitting a real webapp job exposed them.
The lesson (now a standing rule): **prove fixes through the real worker path.**
- **MP3 concat corruption** (`convert_book.py`): joined per-chunk MP3 *bytes*,
  leaving corrupt frame headers at each boundary. Players tolerate it; strict
  decoders (ffmpeg/PyAV, audiobook-player seek/duration) hit "Header missing"
  and stop after chunk 1 (a 27-min chapter ASR-decoded to 19 words). Fixed:
  concat at WAV sample level via stdlib `wave`, then one clean MP3 encode.
  The web-UI path (upstream p0n1 tool) re-encodes and was already clean.
- **Preprocessing use-before-assign** (webapp `convert_book`): the preprocess
  block referenced the local `tts_engine` ~25 lines before it was assigned, so
  on EVERY real conversion it threw and silently fell back to raw text — none
  of the modern-contract/pronunciation/endnote work applied. Invisible until
  the worker (running 14-hour-old code) was redeployed. Fixed: read the engine
  from the job. Regression-guarded.
- **Recovery resurrects cancelled jobs** (#14): startup orphan-recovery flipped
  a cancelled job back to `converting`, jamming the single MAX_CONCURRENT slot.
  Recovery must exclude terminal states. Open.
- **ABS sync silently broken** (#15): worker's `AUDIOBOOKSHELF_HOST=docker-vm`
  doesn't resolve (ABS must be reached by its LAN IP, not the `docker-vm` alias) and the API token had expired
  2026-06-07 — so conversions weren't reaching AudioBookShelf (jobs showed
  `synced_to_abs=0` with no alert). Token + ABS_API_URL restored in settings;
  host env + rsync SSH key + a restart still needed. Open.
- **Free Kaggle TADA broke on a Kaggle-image clash**: `transformers` (via
  hume-tada) eagerly imported Kaggle's preinstalled TensorFlow, whose protobuf
  was mismatched. Fixed: `USE_TF=0` + uninstall tensorflow in the kernel.
- **LLM configured 2026-07-08**: initially there was no LLM key on zorin so
  `generate_narration_profile` fell back to seed rules. Now Groq
  (`llama-3.3-70b-versatile`, OpenAI-compatible at api.groq.com/openai/v1) is
  stored in app_settings and verified live — production conversions get full
  adaptive pronunciation + fiction/non-fiction. The seed floor remains the
  offline fallback.

## Standing rules for claims

A path may be called "working" in STATUS.md only with evidence: a completed
real conversion (job id / artifact / measurement) recorded alongside it.

**Official docs are the baseline.** Engine behavior claims come from the
engine's official documentation (collected in ENGINES.md), not from
experiment-derived guesses. The TADA reference-transcript requirement and
Chatterbox's cfg_weight/exaggeration pacing controls were both in the docs
all along while we debugged blind (2026-07-09).

**Prove fixes through the REAL worker path, not scripts.** Standalone scripts
and hand-driven GPU rigs hid a cluster of bugs (2026-07-08e). A fix isn't
proven until it has run through the webapp/worker the user actually uses — and
that requires the change to be DEPLOYED (the worker runs the built image, not
the working tree; `git pull` alone does nothing until the worker is rebuilt).

**Canonical output location** (so "where do I look?" is never re-litigated):
finished audio ALWAYS lands in `data/audiobooks/<book>/` on the machine that
ran the conversion — webapp jobs, standalone `convert_book.py`, and the
`scripts/sample.sh` harness (samples go to `data/audiobooks/_samples/`).
AudioBookShelf is the unified listening library the webapp syncs to. Do NOT
add new ad-hoc output dirs.
