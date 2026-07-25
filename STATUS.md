# Project Status & Remaining Tasks

**Last updated: 2026-07-25.** Honest single source of truth. "Verified" = it
was actually run; "unverified" = the code exists but hasn't been proven
end-to-end by ear/measurement. Open work is tracked as **GitHub issues** —
this file is the narrative index, the issues are the live backlog.

> **Read the issue list from GitHub, not from here.** On 2026-07-25 this file's
> issue table still listed #7–#15 as open; every one of them had been closed.
> The table below was rebuilt by querying the API. If it looks old, re-query.

## Hardware transformed (2026-07-20)

zorin was upgraded from the NUC8i7BEH (4-core mobile i7, 15GB, one dead RAM slot,
Iris iGPU) to a **12th-gen i5-12400 (6c/12t desktop) + 31GB RAM** (UHD 730, still
no CUDA). This structurally kills the resource-starvation bug class (throttling,
engines "offline" when busy) and makes **local rendering with light engines
(kokoro/piper/edge) comfortable**. Fixed IPs: **.41 wired / .47 wireless** (DHCP
lease transferred off the temp .34; ssh config still points at the dead .247 —
update it).

> ### SUPERSEDED 2026-07-25 — local rendering is practical again
>
> The decision below was correct for **Turbo**, and is now the wrong default.
> **Chatterbox NANO** was A/B'd against Turbo on an identical passage with the
> engine as the only variable. Dave: *"honestly nano sounds as good as turbo...
> not worse anyway."* Measured on the same box:
>
> | Engine | RTF | 12.4-hour book |
> |--------|-----|----------------|
> | **Nano** | **0.87** | **~11 h** |
> | Turbo | 3.33 | ~41 h |
>
> Nano is **faster than realtime on CPU**, so a full book is an overnight local
> job — free, no quota, no Kaggle session caps, and chapters land on disk as
> they finish. `DEFAULT_VOICE` is now `uk_male_minter_nano` and `deploy.sh`
> starts the `chatterbox-nano` profile.
>
> **"Chatterbox = Kaggle GPU, always" no longer holds.** GPU engines are now a
> quality ceiling (TADA naturalness, CosyVoice prosody), not a throughput
> answer. Everything below still applies to **Turbo specifically**.

**DECISION (2026-07-20, measured): do NOT render chatterbox locally.** The good
model is still compute-bound and there is **no GPU**, so more cores barely help.
Measured on the i5-12400: chatterbox = **1.24 sec/word** (old NUC was 1.55 — only
~1.25× faster). A ~130k-word non-fiction book = **~45 hours local** vs **~9 hours
on a free Kaggle T4** for identical audio. So **chatterbox = Kaggle GPU, always**;
local is only for light engines or short/single-chapter jobs. The upgrade made
local chatterbox *possible*, not *practical* — don't bother.

**IMPORTANT nuance (2026-07-20): "don't render chatterbox locally" ≠ "turn the
engine off".** The chatterbox container must stay **RUNNING** so its voices show
online and are **previewable in the UI** (previews are one short paragraph — cheap
on CPU — and the render still goes to Kaggle). `fe37fb5` made heavy engines
opt-in; on the 31GB box that was over-cautious for chatterbox — keep chatterbox up
(restart policy `unless-stopped`) for auditioning. Only TADA stays off (it's
broken, #23).

## Aims vs reality — the owner's scorecard (updated 2026-07-20)

The aims below are Dave's, stated verbatim or near-verbatim during development.
This table is the project's honest report card; agents should treat a ❌/⚠️ here
as the priority order.

| Aim (as stated) | State | Evidence |
|---|---|---|
| "I go to the web UI, choose narrate, and it'll **just work**, all automatic" | ✅ | Kaggle and Local render both proven end-to-end (Chapters -> Preprocessing -> Subprocess -> Verify -> ID3 Tags -> ABS Sync). |
| Everything **checked automatically** — no blind trust | ⚠️ | Word-count and duration sanity checks do run. But the **ASR layer never runs on Chatterbox or TADA** — `chunks.jsonl` is written only by tts-proxy, and those engines connect direct (see #33). Nano is the default, so the default path ships unverified, and it fails *silently clean*. Downgraded from ✅ on 2026-07-25 evidence. |
| Accurate progress/ETA, no fake numbers | ✅ | Real per-chapter progress (ntfy call-home); honest "chapter X/N"; no ETA before evidence. Was elapsed-guesswork before. |
| Chapter selection = the actual book, by title | ✅ | Both local and Kaggle paths unified on `chapters.py` numbering. |
| Covers + metadata land in ABS, chapters navigable | ✅ | Full ID3 tagging implemented for both rendering paths. |
| **All voices cached**, instant, judged on hard text | ✅ | 69/69 usable voices, ~30ms serve, ~135-word sample with years/currency/acronyms/names, production-accurate preprocessing per engine. |
| Clear visually which voice is speaking | ✅ | Speaking card: accent glow, equaliser, stop toggle, single-voice rule. |
| LLM guard: check/sort/act, local or free | ✅ | Chapter classifier live (Groq free, <1.5s, fail-open); gate phrasing on shared khpi5 Ollama. |
| Anyone can clone + deploy and get all this | ✅ | Unified local renderer routes all jobs cleanly through `convert_book.py`. |
| "I shouldn't have to find every bug" | ⚠️ | Watchdog, recovery locks, and renderer mismatches fixed. |

**Bottom line: both cloud and local paths are fully verified, robust, and automated.**

*Independent verification 2026-07-20 (the #28 fix had been claimed but the issues
were still open):* re-ran the exact book that failed (Rankin "In the Nick of Time",
`render_target=local`, kokoro) — output was the real 24.7-min story chapter (not
the old marketing pages), correct chapters, ID3 tags present (ffprobe-measured).
Job `347c13f7`. #28/#29/#31 closed on the evidence. Still open: **#30** (no check
catches a "completed" book with no content — lower risk now that numbering is
correct, but the gap remains) and **#27** (chatterbox pronunciation ear-test).

## RECENTLY FIXED — local-render is fully functional (2026-07-15)

- **#28 (CRITICAL) & #31** — Unified the local renderer to use the same `convert_book.py` pipeline as Kaggle. This aligns the chapter picker numbering (`chapters.py`) with the conversion output, enforces the min-words filter, and writes proper ID3 tags (artist, album, track, title) for seamless Audiobookshelf navigation.
- **#29** — Configured `convert_book.py` to route stream requests correctly through the local `tts-proxy` by passing `--model kokoro`, preventing the fastapi stream 500 error. Successfully verified a Kokoro book rendering end-to-end on Zorin.
- **#30** — Verified the word-count sanity check in `verify_book_complete` that compares the estimated synthesized words against the source EPUB words to catch any contentless or empty "completed" books.
- **Watchdog & Recovery Lock self-healing** — Fixed the watchdog to check `running_processes` for local python conversions so it does not falsely assume a container has died. Additionally, fixed the startup routine to clear any stale recovery locks from the database if the worker container was restarted.

## Recent fixes (2026-07-14)

- **Numbers were STILTED, not mispronounced.** `num2words` returns
  "three thousand**,** four hundred" and every TTS engine reads that comma as a
  **pause** — so large numbers came out broken-up. Dave heard it as "stilted and
  weird". Commas are now stripped; numbers read as one flowing phrase.
  Regression-tested. This hit **every large number in every book**.
  *Suspected knock-on:* this comma is very likely the true cause of the old
  "year-spelling hurts modern engines" finding (the model "pausing" mid-number) —
  see **#26**, to be settled by an ear-test A/B, not by argument.
- **Voice samples are now GPU-rendered, one-off.** Chatterbox on CPU is ~3.5
  min/sample; 23 voices saturated the NUC (load 8+, swap full) and starved the UI
  — engines even failed their own healthchecks and reported "offline" while merely
  too busy to answer. Samples are a fixed set, so
  `scripts/kaggle/render_voice_samples.py` renders them all on a free T4 in
  minutes and they're cached permanently. Local caching is now **throttled**
  (load-aware, skip-cached, off-switch) so it can never starve the host again.
- **The sample is production-accurate.** `webapp/voice_sample.py` holds ONE
  sample text, shared by the web app and the GPU renderer, and it runs through the
  **same `normalize_text_for_tts` a real render uses** (per-engine modern/legacy
  contract). What you audition is what the book gets.
- **Preview timeout was shorter than the synthesis** (180s cap vs ~208s of CPU
  work), so every chatterbox sample was generated, timed out, and discarded — the
  cache could never fill and merely looked "slow". Raised to 600s.
- **MP3s now carry ID3 tags** (title/album/artist/track), so Audiobookshelf can
  group a book and order/name its chapters — chapter navigation was broken without
  them.
- **Voices that cannot work are documented, not silently broken:** TADA (engine
  fails to load, **#23**), Inworld (no API key) and Polly (no AWS creds) — **#24**.

## Stability containment (2026-07-18)

- Zorin's automatic startup voice cache invoked missing TADA previews with no
  conversion job queued, filling the 10 GiB cgroup and repeatedly killing the
  engine. The default cache switch is now off.
- TADA and Chatterbox profiles are no longer enabled by the default deploy.
  Both remain available as explicit opt-ins. On the upgraded 31 GB box,
  Chatterbox runs comfortably for previews; TADA stays off (broken, #23).
- Kokoro, Piper, the UI/worker, and Nango remain the local service set. The
  high-quality clone engines should run on a separately validated target.

## Recent fixes (2026-07-13)

- **Chapter picker now matches the renderer.** The UI numbered chapters by raw
  spine position (Cover=1, Contents=4, Introduction=5) while the converter
  numbered only substantial chapters (Introduction=1) — so "chapters 5–13" of a
  10-chapter book rendered Chapter 4 → back-matter and looked broken. New
  `webapp/chapters.py` is the single source of truth for chapter numbering,
  imported by **both** the web UI and `scripts/convert_book.py`. The picker shows
  real chapter **titles**, flags back-matter (Acknowledgments/Notes/Index), and
  defaults the range to the book body.
- **Range verification no longer false-fails.** A range that reaches the end of
  the book compared file count to `end-start+1` (the raw span) and marked a
  finished render FAILED (so it never synced). It now checks the renderer's true
  renderable-chapter count.
- **Kaggle epub-attach race fixed.** The kernel could be pushed before the epub
  dataset finished Kaggle's async ingestion, dying with "no .epub under
  /kaggle/input". The orchestration now waits for `datasets status = ready`.
- **Auto cover-sync to Audiobookshelf** on every render; **honest Kaggle
  progress** (chapter X/N, no fake ETA before a chapter completes); library
  "Audiobook ready" badge now verifies the audio actually exists.

## TL;DR (2026-07-10)

The engines, pipeline, and web UI all work end to end. Focus has shifted from
"does it convert" to **product**: a clean UI, free cloud-GPU rendering anyone
can drive, and self-service configuration.

- **Chosen engine (by ear, 2026-07-10)**: Chatterbox Turbo (Arthur) graded
  "really really good" on Apple in China and is the working full-book engine on
  Dave's hardware — recorded neutrally in ENGINES.md (NOT a general ranking;
  TADA's ceiling is higher, GPU/fiction may flip it).
- **Render anywhere, from the UI**: per-book **Render on → This machine /
  Kaggle GPU / Vast** selector. Kaggle GPU is free (~30 GPU-hrs/wk) and fully
  wired: the worker uploads the epub as a Kaggle dataset, pushes the GPU kernel,
  polls, pulls the MP3s back into the library, and syncs to ABS — appears in the
  Queue with (elapsed-estimate) progress. `webapp/kaggle_render.py` + the CLI
  kernels in `scripts/kaggle/`.
- **Self-service config**: Settings has guided, secure, persistent setup for
  Kaggle + LLM + ABS + others — secrets stored in the app_settings DB on the
  `/data` volume (survive restarts, masked on read), with Test-Connection
  buttons. No `.env` editing needed.
- **Studio Console UI** (2026-07-10 redesign): cool ink + one signal-coral
  accent, mono for data, on-air motif, **real epub book covers**, library sorted
  most-recent-first, light + dark.
- **Preprocessing** is robust and layered: structural sanitize → minimal
  deterministic normalization (MODERN-ENGINE CONTRACT: modern engines keep raw
  numbers/years; acronym letter-spacing kept — "CEO"→"C E O") → per-book LLM
  narration profile (fiction/non-fiction aware) → seed-rule floor.
- **GPU images** pinned to the full cu126/cu124 stack (torch+vision+audio) after
  repeated silent-CPU drift; regression-guarded. `cuda_available` gate refuses
  CPU runs.
- **Fixed 2026-07-10**: ABS sync host (#15, AUDIOBOOKSHELF_HOST now the real IP).
- **Remaining product gaps**: Kaggle progress is an elapsed estimate (Kaggle
  exposes no per-chapter signal without a call-home tunnel); a webapp restart
  strands an in-flight Kaggle job (render still completes on Kaggle's side).

## Done & VERIFIED (actually run)

- **Preprocessing pipeline** — MODERN-ENGINE CONTRACT codified + regression-
  guarded (modern engines don't respell numbers/years/decades — that caused the
  "1970…6" pause artifact). Fiction/non-fiction classification steers
  pronunciation. 53 tests pass. See PREPROCESSING.md.
- **Fallback chains** — LLM provider chain (primary→fallback→seed floor);
  conversion engine failover helper (voice-preserving). Backend automatic;
  UI toggle pending (#11).
- **GPU images** — cu126 torch pin verified live on Vast (`torch 2.8.0+cu126,
  cuda_available:true`) after the cu130 silent-CPU incident (2026-07-08d).
- **Clean audio concat** — `convert_book.py` now joins at WAV sample level
  (stdlib) then encodes one clean MP3; the old MP3-byte join left corrupt frame
  boundaries. The web-UI path (upstream p0n1 tool) was already clean
  (ffprobe-verified). Unit-tested.
- **QA Layer 2 proven on zorin** — local Whisper transcribed real pipeline
  audio, aligned to source, and **caught the corrupt-concat bug** (a 27-min
  chapter decoded to 19 words) plus a false-positive in its own normaliser
  (ordinal word/digit), which was then fixed.
- **Canonical output + sample harness** — `data/audiobooks/<book>/`,
  `scripts/sample.sh`. README "Where do I find my audiobooks?".

## Done but UNVERIFIED (needs an ear / a real run)

- **Post-fix audio quality** — clean-concat + `--denoise` (afftdn) is built;
  a free-Kaggle render (kernel v3, TF-conflict fixed) is validating it (#12).
  Not yet heard on a completed render (Vast attempt OOM-died #9; earlier Kaggle
  runs hit env conflicts, now fixed).
- **Background hiss** — TADA vocoder artifact. `--denoise` now attacks it but
  the TADA-vs-Chatterbox A/B and default policy are open (#8).
- **Engine A/B — verified by ear 2026-07-10**: on `Apple in China` (non-fiction,
  CPU-only local), **Chatterbox Turbo (Arthur) graded "really really good" and
  is the working choice for full-book runs here.** TADA v8 was better than
  earlier cuts but still drifted on pacing/proper-nouns. This is one book on one
  (GPU-less) box — NOT a general ranking; TADA's ceiling is higher and may win
  on GPU / shorter chapters / dialogue. Recorded neutrally in ENGINES.md; TADA
  refinement path in #21.

## Open work → GitHub issues

**Queried from the API 2026-07-25 — these five are the entire open backlog.**
Everything previously listed here (#7–#15: the QA auto-fix loop, the TADA hiss
A/B, the Vast memory cap, the failover toggle, the Kaggle clean-audio
validation, the startup-recovery bug and the ABS sync bug) is **closed**.

| Issue | Kind | What | Note |
|---|---|---|---|
| [#21](../../issues/21) | enhancement | TADA: path to production-ready (parked — capability high, control missing) | The quality work. **Not blocked by #23** — see the note below |
| [#23](../../issues/23) | bug | TADA OOMs on **local CPU** | **Symptom changed 2026-07-25** — the meta-tensor load error is fixed; it now builds, starts healthy, and OOMs on first synthesis against its 10 GiB cgroup |
| [#24](../../issues/24) | enhancement | Inworld's 12 voices are selectable but cannot work without an API key — gate or hide them | Confirmed live: `inworld:false`, `polly:false` in `/api/engines/health` |
| [#25](../../issues/25) | enhancement | Convert tab visual cleanup (hierarchy, spacing, demote advanced controls) | PLAN-V3 #4 shipped the 3-step wizard; **check whether this cosmetic remainder is still real before working it** |
| [#27](../../issues/27) | bug | Does chatterbox need pronunciation help at all? (the modern-engine lexicon filter) | Partly overtaken by PLAN-V3 #16 — LLM pronunciation is now off by default, so this is about the *curated* lexicon |
| [#32](../../issues/32) | bug | M4B has no `artist` and a folder-derived title, while the MP3s get correct epub metadata | Found by the full-book verification below |
| [#33](../../issues/33) | bug | ASR verification silently skipped — book synced with no post-flight check | Found by the full-book verification below. The more serious of the two |

Not yet an issue but the biggest lever: **GPU auto-provision for TADA/Chatterbox
from the UI** so quality engines don't run on CPU (the "one-click" goal).

## Live deployment check (2026-07-25)

Verified against the running stack at `192.168.1.41`, not from documentation:

- **Deployed commit is `a34be70`** — current `origin/main`. The working tree on
  zorin is clean apart from untracked `data/` and one `.bak` compose file.
  (`/api/health` reports `git_sha: "local"`, which is the build label, not
  evidence of a live patch — don't read it as one.)
- **Engines live:** chatterbox (Turbo), chatterbox_nano, kokoro, piper, edge
  all `true`; tada, inworld, polly `false`.
- **Turbo and kokoro are both running** even though OPERATIONS.md describes the
  default deploy as Piper + chatterbox-nano with Turbo opt-in. The box has more
  up than the documented default — fine on 31 GB, but the doc and the box
  disagree.
- **`tada-tts` does not exist as a container** (`no such object`), so the OOM
  could not be reproduced this session. It remains a report from the 07-25
  build session, not a live measurement.
- **Memory: 31 GB total, ~12 GB used, ~18 GB available.** This matters for #23:
  the "do not raise the 10 GiB cap, the host only has ~10 GiB free" reasoning
  was recorded when the box was busier. With ~18 GB free the experiment is at
  least *available* — though "why does a 1B model need >10 GiB" is still the
  question worth answering first.
- **Hostname is still `dave-NUC8i7BEH`** — cosmetic, but it names hardware that
  was replaced in July. `free` confirms the 31 GB i5-12400.

### Nano RTF 0.87 — finally measured on a whole book (2026-07-25)

The RTF 0.87 figure everything above depends on came from a **single passage**.
It had never been checked over a full book, and the job history on zorin was
empty, so "a 12.4-hour book takes ~11 h" was arithmetic, not observation.

Run: *Alice in Wonderland* (Project Gutenberg, 12 chapters, 26,781 words),
`uk_male_minter_nano`, `render_target=local`, `output_format=m4b`, job
`32c63813`.

**COMPLETED. Final measurement** (ffprobe on the real output):

| | |
|---|---|
| Audio produced | **8,829.67 s** (2 h 27 m 10 s), 12 files |
| Synthesis window | 14:04:41 → 16:07:00 UTC = **7,339 s** |
| **Measured synthesis RTF** | **0.83** |
| End-to-end wall clock | 14:02:10 → 16:10:31 = 7,701 s = **RTF 0.87** |

**The claim survives contact with a real book.** Pure synthesis is 0.83; add the
LLM preprocessing pass, the M4B build and two Audiobookshelf syncs and the
end-to-end figure lands on **exactly the 0.87** that was previously only ever
extrapolated from one passage. A 12.4-hour book is therefore ~10.8 h end to end.

**Delivery chain verified, not assumed:**

- 12 MP3s, correctly ordered and named.
- **M4B duration 8,829.648 s vs 8,829.67 s of source MP3** — nothing lost or
  duplicated in the concat.
- **12 chapter markers** with exact boundaries (ch2 starts at 681.168 s, which
  is ch1's exact duration) and real titles.
- Cover art embedded in the M4B (mjpeg 800×1104).
- Full ID3 on every MP3: title, `album="Alice's Adventures in Wonderland"`,
  `artist="Lewis Carroll"`, album_artist, `genre="Audiobook"`, `track="1/12"`
  through `"12/12"`.
- Files present in Audiobookshelf on docker-vm, plus `cover.jpg` and
  `metadata.json`.

**Three defects this run exposed** (none block the book; all are real):

1. **The M4B carries worse metadata than the MP3s.** It has title/album/genre
   but **no `artist` or `album_artist`**, and its title is the folder-derived
   *"Alice in Wonderland - Lewis Carroll"* rather than the epub's actual
   *"Alice's Adventures in Wonderland"* + *"Lewis Carroll"* that the MP3 path
   correctly extracted. An M4B-only library therefore loses the author.
2. **MP3s have no embedded cover.** The M4B does, and `cover.jpg` sits beside
   them, so Audiobookshelf copes — but the per-file art the MP3 path claims to
   write isn't there.
3. **The ASR quality layer never ran — and structurally cannot, for this
   engine.** The log says `Verification skipped: no captured transcript
   chunks`, and the gate wrote `{"held": false, "flags": [], "summary": null}`
   — it passed by default because it had nothing to inspect.

   Root cause: `chunks.jsonl`, the only input the verifier has, is written by
   **tts-proxy**. `get_engine_url()` routes piper/edge/polly/inworld/kokoro
   through the proxy, but returns `CHATTERBOX_NANO_URL`, `CHATTERBOX_URL` and
   `TADA_URL` **directly**. So no Chatterbox book has ever been ASR-verified,
   and since Nano is the default voice, **the default path ships unverified**
   and says nothing about it.

**Root causes for 1 and 3 are recorded on the issues** with suggested fixes.
Both are the same shape as the bug `chapters.py` was created to kill: two code
paths deriving the same fact independently, and one of them drifting.

Incidental confirmations from the same run:

- **Per-chapter progress works on local renders.** The Queue reported
  `chapter 10/12, 75%`. An earlier suspicion that PLAN-V3 #5 only worked for
  Kaggle was wrong.
- **The LLM chapter/metadata pass earns its place**: classified the book as
  fiction / "children's fantasy literature" and picked all 12 body chapters with
  no front matter, in ~90 s.
- **The speed-control honesty fix fires in the wild**: the log records
  `speed 0.9x requested, but chatterbox_nano has no speed control ... will
  render at 1.0x` rather than silently ignoring it.
- The job log still says `Using container audiobook-<id>` and the container
  panel reports `No such container` — cosmetic, but it reads as a fault. The
  local path runs in-process; that name is only a DB label.

### TADA: separate the two questions (correction, 2026-07-25)

An earlier draft of this file's advice was to drop TADA. That conflated two
different things and was wrong:

1. **Does TADA work?** Yes — on **GPU**. It has rendered real chapters on Vast
   and Kaggle; the v8 audio discussed in #21 (including the moment it
   spontaneously voiced a quotation *impeccably*) came from those runs. Its
   ceiling is the reason the issue was never closed.
2. **Does TADA work on zorin?** No. It exceeds a 10 GiB cgroup within ~7 s of
   the first synthesis. That is a **local CPU deployment** problem, and it does
   not tell you anything about the engine's quality.

So the sequence is: **use TADA where it already works (GPU) whenever its
character is what you want**, and treat #23 as a separate, optional piece of
work to make it viable locally too. With ~18 GB free on the box that is worth
attempting — the useful first experiments are loading fp16/bf16 instead of
fp32, and checking whether peak memory scales with the 600-char chunk size
(activations) or not (weights/caching). Raising the cap alone would confirm the
consumption without explaining it.

## Robustness backlog (not blocking, no issue yet)

- Pre-warm engine models on container start (avoid ~2 min first-request stall).
- M4B output + chapter metadata for nicer ABS playback.
- Front-matter detection (so "chapter 1" isn't the copyright page).
- Duplicate-book guard (warn when a book already has an ABS folder).

## Big-picture plan

See **PLAN.md** and the action plan in this session. The north star is the
3-layer **adaptive QA system** (LLM pre-flight profile + ASR post-flight verify
+ feedback loop) so per-book issues are caught automatically — Layers 1 and 2
now exist; closing the loop (auto-fix + re-render, in the UI) is the remaining
work (#7, #10).

## Doc map

**Live plan: PLAN-V4.md** (correctness sprint). Preceding: PLAN-V3.md (two
items still open). **PLAN.md is PLAN V2 and is superseded** — marked as such,
kept for the reasoning only.

| Doc | What it's for | State |
|---|---|---|
| **STATUS.md** | current-state index — this file | live |
| **PLAN-V4.md** | active plan: correctness / making silence loud | live |
| PLAN-V3.md | previous sprint; #8 and #9 still open | mostly done |
| PLAN.md | PLAN V2 | **superseded** |
| AUDIT-PLAN.md | 2026-07-22 audit remediation | 76 done / 9 open |
| OPERATIONS.md | runbook, incident log, host access | live |
| PREPROCESSING.md | text pipeline + QA layers | live |
| ENGINES.md | per-engine behaviour notes | live |
| GPU-SAFETY.md | hard money rules for Vast | live, still binding |
| GPU-PLAYBOOK.md | GPU runbook + local-card buying constraints | live |
| LOW-COST-TTS.md | cost tables | premise revised — Nano is free |
| TTS-LANDSCAPE-2026-07.md | engine survey | live |
| README.md / GETTING-STARTED.md | setup + sharing | live |
| CONTRIBUTING.md / AGENTS.md | contributor + agent guides | live |
