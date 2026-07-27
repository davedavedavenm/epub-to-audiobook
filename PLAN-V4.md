# PLAN V4 — Correctness sprint (2026-07-25)

> ## Status 2026-07-27 — the sprint is essentially done
>
> **Closed on evidence from job `f83170d2`** (Alice, Nano, v1.5.0+):
> **#32** M4B carries real epub metadata (`artist="Lewis Carroll"`, widened to
> year/publisher/language/series) · **#34** `ORANGE MARMALADE` → `Orange
> marmalade` in the text actually voiced · **#35** ABS reconnected, 7 orphans
> purged, 401s now loud · **#37** startup self-check for a read-only settings
> DB · **#38** M4B published atomically, epub no longer synced (401 MB → 242 MB
> per book).
>
> **#33 is closed.** Transcript capture now works on every engine — it was
> previously impossible for Chatterbox and TADA, so no book had ever been
> verifiable — and the ASR pass that compares *audio* to that text is **on by
> default**. It was briefly opt-in on my claim that "Whisper roughly doubles
> render time"; that was never measured and was wrong. Measured: **20×
> realtime, about 6% of a render**. #39, which existed only to make it cheaper,
> is closed as unnecessary — and was technically wrong too, since
> faster-whisper cannot use OpenVINO.
>
> **Three bugs were introduced and caught during this sprint**, all by running
> the system rather than reading it: `--job-id` reaching only the watchdog path,
> `TRANSCRIPTS_DIR` being set to an empty string so the fallback never applied,
> and reading `jobs.db` from the host — which created WAL sidecars under the
> wrong uid and silently broke every Settings write. That last one is #37 and
> was self-inflicted. The lesson is recorded in OPERATIONS.md.
>
> **Shipped beyond this plan:** voice cloning by WAV upload (v1.6.0) and URL →
> audio (v1.7.0, #36).

Successor to PLAN-V3, which is essentially complete. Where V3 was about
**capability** (engines, UI, output formats), V4 is about **truth**: several
subsystems report success while doing nothing, and today's first end-to-end
book audit found them.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

---

## Why this plan exists

The Alice render (job `32c63813`) was the first time a whole book had been put
through the pipeline and then *inspected* rather than assumed. It confirmed the
good news — RTF 0.83 synthesis, exact M4B chapter boundaries, correct ID3 — and
turned up four defects in a single run. Every one of them is the same shape:

> **A component reports success without evidence, and the reporting looks
> identical to the working case.**

- ASR verification wrote a clean gate having inspected nothing (#33).
- The ABS sync badge is green because the half that works is the half being
  measured — the API half has been dead for an unknown period (#35).
- The M4B path re-derives metadata it could have inherited, and silently loses
  the author (#32).
- `ORANGE MARMALADE` renders as confident, fluent, wrong audio (#34) — which is
  precisely what #33 exists to catch, and couldn't.

The theme for V4 is therefore: **make silence loud, and give each fact one
owner.**

---

## 1. Make skipped verification impossible to mistake for a pass (#33)

Cheapest, highest value, do first. Does not fix coverage — fixes the lie.

- [ ] 1.1 `_presync_gate.json` gains an explicit `verified` field. A run that
      inspected nothing writes `{"verified": false, "reason": "no transcript
      chunks (engine does not route via tts-proxy)"}` — never a bare
      `held: false`.
- [ ] 1.2 Job record carries the same state; the Queue/History card shows
      **"unverified"** distinctly from "verified clean".
- [ ] 1.3 `append_job_log` for a skipped verification logs at warning level, not
      alongside routine progress.
- [ ] 1.4 Test: a job whose chunks are absent must not produce a clean gate.

## 2. Capture transcript chunks at the converter, not the proxy (#33)

The real fix. `chunks.jsonl` is currently written by `tts_proxy/proxy.py`, so
verification only exists for engines routed through it. `get_engine_url()`
returns **direct** URLs for `chatterbox_nano`, `chatterbox` and `tada` — the
quality engines — so no Chatterbox book has ever been ASR-verified, and Nano is
the default voice.

- [ ] 2.1 Move chunk capture into `scripts/convert_book.py`, which already
      chunks the text (`chunks = chunk(text, chunk_chars)`) and knows the
      chapter index. Append to the same `chunks.jsonl` path and format.
- [ ] 2.2 Make the proxy's writer a no-op when the converter already wrote, so
      proxy-routed engines don't double-log.
- [ ] 2.3 Confirm capture on one chapter for **every** engine, direct and
      proxied.
- [ ] 2.4 Move the cleanup step (`Cleaned up transcript chunks`) to *after* the
      verifier runs — currently it appears immediately after the skip.

> **Bonus:** this removes one of the last real reasons the proxy must sit in the
> render path, which is a prerequisite argument in PLAN-V3 #9.

## 3. Actually run ASR verification on a Chatterbox book (#33)

- [ ] 3.1 With 1 and 2 done, re-run Alice and let the layer work.
- [ ] 3.2 `faster-whisper` is already a dependency — run it in-process rather
      than via the Docker CLI (PLAN-V3 #9.2 wanted this anyway; same job).
- [ ] 3.3 Record what it flags. **Expect `ORANGE MARMALADE` to be caught** — if
      it isn't, the verifier's thresholds are the next thing to examine.

## 4. One owner for book metadata (#32)

`convert_book.py._book_meta()` reads `dc:title`/`dc:creator` from the OPF and is
correct. `_maybe_build_m4b()` in `app.py` instead uses the job's filename-derived
`book_name` and digs `author` out of the LLM `narration_profile` — which
describes narration *style* and has no author key, so it resolves to empty.

- [ ] 4.1 Lift `_book_meta()` into a shared helper (`webapp/book_meta.py`). It
      is a dozen lines of stdlib `zipfile` + `re` with no converter state.
- [ ] 4.2 Both the MP3 tagger and `_maybe_build_m4b()` call it.
- [ ] 4.3 Keep the filename stem as the documented fallback when the OPF has no
      `dc:title`/`dc:creator` — existing behaviour when metadata is genuinely
      absent.
- [ ] 4.4 Decide whether MP3s should carry embedded cover art. Today only the
      M4B does; `cover.jpg` sits alongside and ABS copes.
- [ ] 4.5 Test asserting M4B and MP3 tags agree.

> Same shape as the bug `chapters.py` was created to kill: two paths deriving
> one fact independently, and the second drifting.

## 5. Normalise all-caps before synthesis (#34)

- [ ] 5.1 Two or more consecutive all-caps words → sentence case
      (`ORANGE MARMALADE` → `Orange marmalade`). Cannot hit `CEO`/`NASA`, which
      appear as single tokens in normal-case surroundings.
- [ ] 5.2 Single all-caps token, ≥5 letters, a normal English word → lower case
      (`LIMITED`, `WARRANTY`).
- [ ] 5.3 Leave everything else — preserves real acronyms and the existing
      dotted-acronym dictionary.
- [ ] 5.4 Regression test: `ORANGE MARMALADE` → `Orange marmalade` while `CEO`
      still becomes `C E O`.
- [ ] 5.5 **Settle by ear**, per the standing rule. Re-render the rabbit-hole
      paragraph before and after.

## 6. Repair the Audiobookshelf integration (#35)

- [ ] 6.1 Regenerate the ABS API token and save it via **Settings** so it lands
      in `app_settings` (survives restarts) rather than in `.env`.
- [ ] 6.2 Surface a 401 loudly — job card and Settings → Test Connection. Today
      a dead token is invisible because the file copy is `rsync` over SSH and
      keeps working.
- [ ] 6.3 Close the deletion path: removing a render should
      `DELETE /api/items/{id}` or trigger a scan. Otherwise every
      `e2e_proof.sh` run leaves a ghost — there are currently **7 orphaned
      "The Raven" entries** from exactly this.
- [ ] 6.4 One-off: purge those 7 via the ABS UI. Do **not** edit
      `absdatabase.sqlite` under a running server.

---

## Execution order

1. **#33 step 1** — half a day, stops the system claiming assurance it lacks.
2. **#35 token + loud failure** — small, and it unblocks knowing whether ABS
   features work at all.
3. **#34 all-caps** — contained, audible, testable.
4. **#32 shared metadata** — contained refactor with a test.
5. **#33 step 2** — the real work: engine-independent chunk capture.
6. **#33 step 3** — run the verifier and see what a real book looks like.

Items 1–4 are each an evening. 5 is a proper piece of work and touches
PLAN-V3 #9.

## Standing rules this plan inherits

- **Settle audio questions by ear, not argument.** This project has been burned
  three times by reasoning about TTS output instead of listening to it.
- **Give the LLM jobs whose mistakes are visible and cheap** (structure,
  metadata), never jobs whose mistakes are invisible until you hear them
  (pronunciation).
- **A component that cannot do its job must say so.** V4 exists because four of
  them didn't.
