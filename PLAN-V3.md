# PLAN V3 — Product + Quality Sprint (2026-07-23)

Successor to PLAN.md. Every item below was accepted by Dave on 2026-07-23.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

> ## Where this plan actually stands (audited 2026-07-25)
>
> The per-item checkboxes below went stale — work shipped without them being
> ticked. Verified against the code, not the boxes:
>
> **Done and verified in the codebase:**
> #1 Nano engine · #4 guided convert flow · #5 chapter progress · #6 voice
> compare · #7 dark default · #10 SQLite WAL · #12 ruff in CI · #13 CosyVoice
> evaluated · #14 CosyVoice server + Kaggle render path · #16 LLM assist
>
> **#3 (git scrub) appears moot:** no `archive/` directory exists anywhere in
> history, `-S` searches for the named keys hit only this plan's own text, and
> no key-shaped strings remain in tracked files. Close it unless you know of a
> specific secret still to rotate.
>
> **Closed since this audit (2026-07-25):**
> - **#15 M4B — DONE.** `webapp/m4b.py`; verified chapter index, tags and cover
>   on real audio. Opt-in per job via an "Output" selector.
> - **#11 integration test — DONE.** `tests/test_integration_pipeline.py` runs
>   the real converter against a real epub with a mock TTS server. 99 tests pass.
> - **#9 — premise was wrong; mostly closed the cheap way.** The plan assumed
>   conversions shell out to Docker and proposed a sidecar to mediate that. They
>   don't — conversions run in-process. Only TWO docker calls existed; Edge
>   previews now use the `edge-tts` package directly, leaving ONE (the
>   ASR-verify image). Removing that natively is a far smaller job than building
>   a sidecar, and it is what actually unlocks 9.3/9.4 (drop the CLI and the
>   socket proxy).
>
> **Still outstanding:**
> - **#2 Turbo-vs-Nano A/B** — blocked on Dave's ears; both renders prepared
> - **#9 last mile** — run ASR-verify in-process (faster-whisper is already a
>   dependency), then delete the docker CLI and docker-socket-proxy
> - **#8 app.py module split** — parked by decision (see note at #8)

---

## 1. Chatterbox Nano — new engine option (NOT default yet)

> **DONE + verified 2026-07-24.** Prior state was "wired but broken": voices +
> routing existed, but `requirements.txt` pinned `chatterbox-tts>=0.1.7` (no
> `nano=` param), a single container can only load Turbo XOR Nano, and it was
> never rebuilt/deployed. Fixed: git-pinned dep (`5de7a54`), a dedicated
> `chatterbox-nano` container (profile `chatterbox-nano`, port 8006,
> `CHATTERBOX_NANO_URL`), `NUMBA_CACHE_DIR` + HF-cache-volume chown.
> **Measured RTF 0.83 on Zorin CPU**, ASR-verified. 1.5 samples came from the
> HF Space; 1.6/1.7 now done on real hardware. Ear-level Turbo-vs-Nano A/B (#2)
> still owed.

Add Nano as a selectable engine alongside Turbo, with full preview voices.

- [ ] 1.1 Install chatterbox from git-master in the `chatterbox/` container
      (PyPI 0.1.7 doesn't include Nano; merged Jul 21)
- [ ] 1.2 Update `chatterbox/server.py` to support `nano=True` model loading
      (env `CHATTERBOX_NANO=1` or per-request model param)
- [ ] 1.3 Add Nano voices to `VOICES` in `app.py` (same UK refs: Minter,
      Golding, Yearsley, Samuel — suffixed `_nano`)
- [ ] 1.4 Add engine branches at the three `tts_engine ==` sites in app.py
- [ ] 1.5 Generate preview samples for all 4 Nano voices (cache in data/previews/)
- [ ] 1.6 Rebuild chatterbox Docker image, test on zorin
- [ ] 1.7 Run `scripts/bench_nano.py` on zorin — record measured RTF in
      LOW-COST-TTS.md and TTS-LANDSCAPE-2026-07.md

## 2. Settle #27 — proper noun A/B with Nano

- [ ] 2.1 Render canonical passage + one non-fiction chapter with:
      (a) Nano raw, (b) Nano + natural respellings, (c) Turbo raw, (d) Turbo + SHOW-mee
- [ ] 2.2 Dave listens, verdict recorded in #27
- [ ] 2.3 If natural respellings win: reverse the filter for natural-format
      rules in `normalize_text_for_tts`, update PREPROCESSING.md

## 3. Scrub git history (#18)

- [ ] 3.1 Rotate exposed keys (LazyLibrarian, NZBFinder, SABnzbd) if still active
- [ ] 3.2 `git filter-repo --path archive/ --invert-paths`
- [ ] 3.3 Force-push, re-clone on zorin
- [ ] 3.4 Verify no other secrets in history: `git log -p --all -S 'API_KEY\|api_key\|password\|secret'`
- [ ] 3.5 Close #18

## 4. UI: Guided conversion flow (#25)

- [ ] 4.1 Restructure convert panel as 3-step wizard:
      Step 1: Voice picker + preview (primary)
      Step 2: Chapter range (auto-selected by guard, editable)
      Step 3: Render target + Convert button
- [ ] 4.2 Advanced controls (speed, regex, fallback, blend) behind
      "More options" collapse
- [ ] 4.3 Visual hierarchy: group what (book/chapters/voice) vs where/how
      (render target/fallback), tighten spacing

## 5. UI: Real-time chapter progress

- [ ] 5.1 Add `/api/jobs/<id>/progress` endpoint that parses the conversion
      log for "Chapter X/N" lines
- [ ] 5.2 Queue tab shows per-chapter progress bar (not just %)
- [ ] 5.3 Kaggle renders already have ntfy per-chapter — surface the same
      data in the same UI component

## 6. UI: Voice comparison player

- [ ] 6.1 Voices tab: "Compare" mode — pick 2 voices, render same paragraph
- [ ] 6.2 Back-to-back playback with A/B toggle
- [ ] 6.3 Use the canonical sample text (voice_sample.py) for consistency

## 7. UI: Dark mode default

- [ ] 7.1 Default theme to dark, respect `prefers-color-scheme`
- [ ] 7.2 Keep manual toggle, persist preference in localStorage

> **Status 2026-07-24: parked, not started.** A prior agent created only
> `webapp/db.py` + `webapp/sync.py` (2 of the ~6 modules) and wired them into
> nothing — `app.py` still imports neither, so they were orphaned dead code.
> They've been removed from the working tree (repo stays unified) and preserved
> outside it pending a decision. This is a large mechanical refactor of a
> ~5k-line file gated on "8.7 all tests still pass", so it needs its own focused
> pass — not a loose end to finish piecemeal. Resume the whole item or drop it.

## 8. Architecture: Extract app.py into modules

- [ ] 8.1 `webapp/db.py` — get_db, save_job, update_job, get_job, app_settings
- [ ] 8.2 `webapp/queue_runner.py` — worker loop, recovery, watchdog,
      maybe_start_next_queued_job
- [ ] 8.3 `webapp/conversion.py` — convert_book, build_retry_cmd, get_engine_url
- [ ] 8.4 `webapp/sync.py` — copy_to_audiobookshelf, Telegram, WhatsApp
- [ ] 8.5 `webapp/routes/` — Flask blueprints for API endpoints
- [ ] 8.6 Each module under 500 lines; app.py becomes a thin wiring layer
- [ ] 8.7 All 96 tests still pass after refactor

## 9. Architecture: Docker sidecar for container orchestration

- [ ] 9.1 Design a minimal sidecar API: "run conversion", "run ASR verify"
- [ ] 9.2 Webapp/worker call the sidecar HTTP API instead of Docker CLI
- [ ] 9.3 Remove Docker CLI from webapp Dockerfile
- [ ] 9.4 Remove docker-socket-proxy (sidecar replaces it)

## 10. Architecture: SQLite WAL mode

- [ ] 10.1 Set `PRAGMA journal_mode=WAL` in get_db()
- [ ] 10.2 Test concurrent webapp + worker access under load

## 11. Testing: Integration test for conversion pipeline

- [ ] 11.1 Mock TTS engine (tiny FastAPI returning sine wave MP3)
- [ ] 11.2 Run convert_book() end-to-end in CI
- [ ] 11.3 Verify: output files exist, ID3 tags correct, chapter count matches

## 12. CI: Add ruff linting

- [ ] 12.1 Add `ruff` to CI workflow (lint on PR)
- [ ] 12.2 Fix existing violations or add per-file ignores
- [ ] 12.3 Add `ruff.toml` config

> **#13 DONE 2026-07-24; #14 revised.** CosyVoice 3 auditioned and verified:
> a full 30-min chapter (mean ASR similarity 0.966) + a hard-normalization test.
> Dave: "surprisingly good, listenable." **Architecture revised:** #14 assumed a
> local `cosyvoice/` Docker service, but CPU is not viable (Kaggle Xeon: ~10–50×
> realtime AND malformed audio), and Zorin has no GPU — so CosyVoice is a
> **Kaggle-GPU render engine**, not a local service. `cosyvoice/server.py`
> (OpenAI-compatible, GPU-only) is built as the engine backend the Kaggle kernel
> drives. Remaining: `scripts/kaggle/run_cosyvoice.py` (production kernel: py3.10
> venv + CosyVoice repo + `convert_book.py`) and webapp `_ENGINE_KERNEL` +
> engine-gate + `TTS_ENGINES` wiring, then a verify-render. The standalone
> `build_chapter_kernel.py` renders whole chapters today. See TTS-LANDSCAPE §Verified.

## 13. TTS: Evaluate CosyVoice 3

- [ ] 13.1 Create kaggle.json (username+key) for CLI read access
- [ ] 13.2 Pull kernel v4 output, listen to samples
- [ ] 13.3 If promising: render canonical passage + one chapter
- [ ] 13.4 Record verdict in TTS-LANDSCAPE-2026-07.md

## 14. TTS: CosyVoice 3 server (if listen test passes)

- [ ] 14.1 `cosyvoice/` directory: server.py, Dockerfile, voices/
- [ ] 14.2 OpenAI-compatible `/v1/audio/speech` endpoint
- [ ] 14.3 Pronunciation inpainting integration (CMU phoneme hotfixes)
- [ ] 14.4 Compose service + profile

## 15. M4B output

- [ ] 15.1 After conversion, concat MP3s → single M4B with ffmpeg
- [ ] 15.2 Embed chapter markers + cover art + ID3 metadata
- [ ] 15.3 Option in convert panel: "Output: MP3 chapters / M4B single file"
- [ ] 15.4 ABS sync handles M4B (it already supports it natively)

> **EXECUTED 2026-07-25. Outcome: scope deliberately CUT on evidence.**
> - **16.1 done.** Ollama installed on zorin; measured **5.97 tok/s vs khpi5's
>   1.83 — 3.3x**. Bound to `0.0.0.0` via a systemd drop-in (it defaults to
>   localhost, so containers silently got nothing). `OLLAMA_URL` now points at
>   zorin.
> - **The profile call was unaffordable and always failed.** A 24,000-char
>   prompt with an unbounded reply timed out at 120s (221s across retries) — so
>   every book silently fell back to the seed floor. Cut to 8,000 chars +
>   800-token cap: now **19-80s and actually returning**.
> - **16.2/16.3 → pronunciation generation turned OFF by default.** With it
>   finally running, qwen2.5:7b proposed `'National Front' -> 'nay-ti-oh-shun
>   fohnnt'` and classified the literary novel *The Names* as "epic fantasy".
>   Meanwhile a chapter rendered with the LLM **fully disabled** was judged good
>   ("pretty good, not perfect but fine"). No engine needs it: CosyVoice
>   normalises numbers/dates/acronyms natively, and the only real misses are
>   exotic surnames — where a curated list beats a guessing model. The
>   hand-curated floor stays; `LLM_PRONUNCIATION_RULES=1` re-enables guessing.
>   A guard also drops any rule whose key is entirely common English words.
> - **16.4 done — the one clear win is chapter structure.** On a real book the
>   LLM correctly started the body at **chapter 2, skipping a copyright page**
>   the heuristic would have narrated. But it ran the END 3 chapters into the
>   back matter (28 vs 25). So the code now takes the **LLM's start** and
>   **clamps the end to `body_end_index`** — each used only where it wins.
> - **Robustness (the reason this bit).** Enabling the LLM put a slow blocking
>   call in the conversion path; the watchdog treated "no container yet" as
>   "container died" and looped renders forever. Fixed with
>   `PREPARE_GRACE_MINUTES` + a bounded `LLM_TIMEOUT_SECONDS`.
>
> **Rule of thumb learned:** give the LLM jobs whose mistakes are *visible and
> cheap* (structure, metadata). Keep it away from jobs whose mistakes are
> *invisible until you hear them* (pronunciation).

## 16. LLM assist — make it real (accepted 2026-07-24)

Context: `OLLAMA_URL` had been configured for weeks but **no code path ever read
it** — `_llm_chat()` and `llm_metadata._get_llm_settings()` both required
`LLM_API_KEY` and silently skipped without it, despite a docstring claiming
"local Ollama primary / cloud fallback". Fixed in `c30fc8b`; every LLM feature
had been dormant until then. These items follow from that.

### 16.1 Move Ollama off the Pi (highest, only guaranteed payoff)
- [x] 16.1.1 Install Ollama on zorin (i5-12400 / 31 GB); pull `qwen2.5:7b`
- [x] 16.1.2 Benchmark BOTH hosts on the same prompt, record tok/s here.
      Baseline measured 2026-07-24: **khpi5 (Raspberry Pi 5) = ~1.9 tok/s**
      (84 tokens in 45 s). Expect 3-5x on zorin — LLM inference is
      memory-bandwidth-bound and the Pi has roughly a third of zorin's.
- [x] 16.1.3 Point `OLLAMA_URL` at the winner; keep the other as fallback
- [x] 16.1.4 Confirm no contention with a live TTS render (LLM work is bursty —
      once per book at job start — so overlap should be rare, but verify)

### 16.2 Right model for the right job
- [x] 16.2.1 Keep `qwen2.5:7b` for chapter classification + metadata (easy,
      short-context; a 3B would likely do — try it if speed matters)
- [x] 16.2.2 Do NOT trust a local 7B for pronunciation: it's world-knowledge and
      small models confidently invent answers. **A wrong lexicon entry is worse
      than no entry** — it corrupts audio that would otherwise be merely imperfect.

### 16.3 Pronunciation lexicon strategy
- [x] 16.3.1 Keep the hand-curated deterministic floor (`llm_metadata.py`) as the
      trusted layer
- [ ] 16.3.2 Optionally use cloud (`gpt-4o-mini`, well under a cent per book on a
      30k-char sample) ONLY for the lexicon, where world knowledge actually pays
- [x] 16.3.3 Treat all generated entries as **suggestions to review**, never truth
- [x] 16.3.4 Apply per engine: CosyVoice 3 takes CMU phonemes (pronunciation
      inpainting); Chatterbox needs respellings. Same lexicon, different rendering.

### 16.4 Prove it helps before relying on it
- [x] 16.4.1 Run 2-3 books; compare LLM-chosen chapter ranges vs the deterministic
      heuristic (`chapters.body_end_index`)
- [x] 16.4.2 Record the win/loss here. If it doesn't beat the heuristic it is just
      latency — turn it off for that job.
- [x] 16.4.3 Keep the guard non-load-bearing (returns None on any problem, caller
      falls back). This is existing design; do not regress it.

### 16.5 Hold the line on scope
- [x] 16.5.1 No new LLM surface (chapter summaries, blurbs, tag generation) until
      16.4 shows the three existing jobs are actually earning their keep

**Engine-dependency note (measured 2026-07-24) — what needs what:**

| Job | Engine-dependent? | Notes |
|-----|-------------------|-------|
| Chapter front/body/back selection | **No** | Picks *which text* is read. Every engine needs it equally. |
| Metadata / narration profile | No | — |
| Proper-noun pronunciation | Partly | *No engine escapes it* — CosyVoice mangled Featherstonehaugh/Cholmondeley; Turbo has "occasional pronunciation trips". Only the **fix format** differs per engine. |
| Number / date / symbol normalization | **Yes** | But this is the **deterministic** pipeline, not the LLM. CosyVoice 3's built-in normalization handled `23.7%`, `07/24/2026`→"24 July", `NASA`, `km/h`, `£89.50` unaided; Kokoro/Piper lean harder on preprocessing. |

---

## Execution order

1. **#3 git scrub** — security, do first, blocks nothing
2. **#1 Nano engine** — highest product value
3. **#2 #27 A/B** — needs Nano, settles a long-standing question
4. **#7 dark default** — quick win
5. **#4 guided flow** — biggest UI improvement
6. **#5 progress** + **#6 comparison** — UI polish
7. **#10 WAL** + **#12 ruff** — quick infra wins
8. **#8 app.py split** — large but mechanical
9. **#11 integration test** — depends on #8
10. **#13-14 CosyVoice** — when Kaggle auth is fixed
11. **#9 sidecar** — replaces socket proxy, depends on #8
12. **#15 M4B** — polish, any time

**Revised order 2026-07-24** (after the CosyVoice/Nano/LLM session):
1. **#16.1 move Ollama to zorin** — contained, only guaranteed payoff (Pi is ~1.9 tok/s)
2. **#16.4 prove the LLM helps** — it has been dormant since day one; nothing is validated
3. **#2 Turbo-vs-Nano A/B** — Nano now works and is faster than realtime on CPU; only the ear-test is missing
4. **#16.3 lexicon strategy** — the direct fix for the proper-noun weakness measured in CosyVoice
5. **#13-14 remainder** — CosyVoice full-book render is wired; needs a clean end-to-end pass
6. everything else as originally ordered
