# PLAN v3: Full Pipeline Audit & Fixes (2026-02-12)

## Context

A full read-only audit of the system was performed on 2026-02-12. This plan documents every issue found and the fix for each. The system has three machines involved:

| System | IP | Role | Status |
|--------|------|------|--------|
| **Zorin** | 192.168.1.88 | **Active production** — epub-to-audiobook stack (UI + worker + Kokoro + Piper + TTS proxy) | ✅ Running, 6 days uptime |
| **docker-vm** | 192.168.1.113 | Audiobookshelf, LazyLibrarian, Calibre-web, wanted_monitor script | ✅ Running |
| **khpi5** | 192.168.1.143 | **Stale duplicate** epub-to-audiobook stack — empty data dirs, broken library mount, non-functional | ⚠️ Running but useless |

The intended end-to-end pipeline:
1. User adds book to LazyLibrarian wanted list
2. wanted_monitor (cron on docker-vm) checks hourly, searches OpenBooks, downloads EPUB
3. User (or future automation) opens webapp, clicks Convert
4. Conversion produces MP3s via Kokoro TTS
5. MP3s are rsynced to Audiobookshelf on docker-vm
6. User listens on Audiobookshelf
7. Telegram/WhatsApp notification when a wanted book is found

---

## Status (Updated 2026-02-12)

### Completed This Session
- ✅ **Kokoro memory limit** — `mem_limit: 10g` + `memswap_limit: 10g` in docker-compose.yml. Docker OOM-kills and restarts Kokoro predictably.
- ✅ **Watchdog chapter-level recovery** — `handle_job_failure()` now detects partial output and calls `recover_partial_conversion()` instead of full job restart.
- ✅ **Race condition fix** — Removed inline `retry_missing_chapters()` from `convert_book()`. Missing chapters now hand off to `recover_partial_conversion()` (same single path the watchdog uses). No more duplicate recovery threads or Telegram spam.
- ✅ **Recovery mutex** — `_recovery_in_progress` dict + `'recovering'` job status prevent duplicate recovery threads from watchdog + convert_book + orphan cleanup.
- ✅ **Inside Apple** — All 14 chapters converted, renamed, synced to ABS, job marked completed.
- ✅ **ABS library rescan API** — `copy_to_audiobookshelf()` now triggers `POST /api/libraries/:id/scan` after rsync.
- ✅ **ABS API token** — Stored in `.secrets/abs_api_token`, loaded via `ABS_API_TOKEN` env var.
- ✅ **The Everything Store** — Conversion re-queued and running (job c7dfc813).

---

## Issues Found (Priority Order)

### P0 — ~~Broken: Books Appear Incomplete in Audiobookshelf~~ ✅ FIXED

**Fix applied:** `copy_to_audiobookshelf()` now triggers ABS library rescan via API after rsync. ABS API token configured. Inside Apple verified with all 14 chapters in ABS.

---

### P1 — Missing Chapters: The Everything Store Ch 1 & Ch 3

**Symptom:** Tracks 06 (Chapter 1 "The House of Quants") and 09 (Chapter 3 "Fever Dreams") were never produced by the converter. The EPUB contains both chapters fully (26,796 and 74,407 chars respectively).

**Root cause:** The upstream `ghcr.io/p0n1/epub_to_audiobook` converter skipped these chapters. The EPUB uses `part0006.html` and `part0008.html` for Ch 1 and Ch 3 — the converter's chapter detection may have issues with the navigation spine ordering in this particular EPUB.

**Fix:**
- [ ] **Step 1:** Re-convert The Everything Store from the source EPUB (still at `/data/uploads/646fee19_...epub` on Zorin) with the `--remove_endnotes` flag and `--speed 0.9` to also address the speed issue
- [ ] **Step 2:** After conversion, verify all 11 chapters + prologue are present as substantial MP3 files
- [ ] **Step 3:** If chapters are still missing, investigate `--title_mode tag_text` vs `first_few` to see if a different parsing mode handles this EPUB better
- [ ] **Step 4:** Delete the old incomplete audiobook from ABS and sync the new one

**Validation:** All 11 chapters present as multi-MB MP3 files, no gaps in track numbering.

---

### P2 — Photo Captions & Endnotes Noise (Everything Store)

**Symptom:** 26 MP3 tracks (tracks 20-45) are TTS readings of image alt-text/captions like "Jeff Bezos childhood portrait..." (75-225 KB each, <10 seconds). Additionally, tracks 48-67 are a duplicate notes/endnotes section with tiny chapter summaries.

**Root cause:** The converter processes every HTML file in the EPUB, including image-only pages and endnotes sections. No filtering is applied.

**Fix:**
- [ ] **Step 1:** Use `--remove_endnotes` flag (already supported by the converter) — this should eliminate tracks 48-67
- [ ] **Step 2:** Add a post-conversion cleanup step in `app.py` that removes MP3 files smaller than a configurable threshold (e.g., 500 KB) — this catches photo captions, part dividers, and other noise
- [ ] **Step 3:** Make the threshold configurable via env var `MIN_CHAPTER_SIZE_KB` (default: 500)
- [ ] **Step 4:** Consider adding `--remove_endnotes` as a default flag in the conversion command, with an opt-out in the UI

**Validation:** Re-converted Everything Store has no photo caption tracks and no duplicate endnotes.

---

### P3 — TTS Speed Too Fast / Pronunciation Issues

**Symptom:** TTS narration is ~2.2x faster than human narration. Words like "next" are mispronounced as "N-EX-to-T". Intonation feels rushed and robotic.

**Evidence:**
- Inside Apple: 2h 57m TTS vs 6h 42m commercial (44%)
- Everything Store: 5h 25m TTS vs 13h commercial (42%)
- Kokoro TTS confirmed to support `--speed` parameter (tested: `speed=0.85` works)

**Fix:**
- [ ] **Step 1:** Add `--speed` parameter to the conversion command in `app.py` (line ~1642). Default to `0.9` (10% slower than current).
- [ ] **Step 2:** Make speed configurable in the webapp UI (dropdown or slider: 0.7-1.0, default 0.9)
- [ ] **Step 3:** Store the speed setting per job in the jobs table
- [ ] **Step 4:** Re-convert Inside Apple and The Everything Store with `--speed 0.9`

**Note on pronunciation:** Some mispronunciations are inherent to the TTS model and not fixable via speed alone. The converter supports `--search_and_replace_file` for text substitutions (e.g., replacing "next" with phonetic hints). Consider creating a common substitutions file for known problem words.

**Validation:** Re-converted books are ~3.5-4h (Inside Apple) and ~6.5-7h (Everything Store). Listen to a chapter and verify improved pacing.

---

### P4 — Wanted Monitor Cron Missing

**Symptom:** The wanted_monitor script on docker-vm has NO crontab entry. Last log entry is 2026-02-09 20:00. The script is not running.

**Root cause:** The crontab was lost — possibly wiped by a system update or user error. `crontab -l` returns empty.

**Fix:**
- [ ] **Step 1:** Restore the crontab on docker-vm:
  ```
  # Wanted monitor: process queue + check wanted list (hourly)
  0 * * * * /usr/bin/flock -n /tmp/wanted_monitor.lock /home/dave/scripts/run_wanted_monitor.sh >> /home/dave/scripts/wanted_monitor.log 2>&1
  ```
- [ ] **Step 2:** Run the monitor manually once to verify it works: `bash /home/dave/scripts/run_wanted_monitor.sh`
- [ ] **Step 3:** Verify the log shows activity after the next hourly run
- [ ] **Step 4:** Add a healthcheck/monitoring alert (via Uptime Kuma or similar) that warns if the log file hasn't been updated in 2+ hours

**Validation:** `crontab -l` shows the entry, log file updates hourly.

---

### P5 — Stale khpi5 Instance

**Symptom:** khpi5 (192.168.1.143) runs an epub-to-audiobook stack (UI + Kokoro + Piper) but:
- Data directories are empty (no jobs.db, no uploads, no audiobooks)
- `/mnt/openbooks` is not mounted
- No `.env` file configured
- API returns 404 on `/api/library` (different code version?)
- It's consuming resources (RAM/CPU) for nothing

**Fix:**
- [ ] **Step 1:** Stop and remove the epub-to-audiobook containers on khpi5:
  ```
  docker stop epub-to-audiobook-ui kokoro-tts piper-tts
  docker rm epub-to-audiobook-ui kokoro-tts piper-tts
  ```
- [ ] **Step 2:** Remove the stack directory if not needed: `rm -rf /home/dave/ai/lab/stacks/epub-to-audiobook` on khpi5
- [ ] **Step 3:** Document Zorin (192.168.1.88) as the single production host in README.md or a deployment doc

**Validation:** `docker ps` on khpi5 shows no epub-to-audiobook containers. Only Zorin runs the stack.

---

### P6 — Webapp Has Only 2 Voices

**Symptom:** `GET /api/voices` returns only 2 voices. Kokoro supports 22+ voices.

**Root cause:** The voice list is likely hardcoded or the voice discovery from Kokoro is failing. Need to check how voices are populated.

**Fix:**
- [ ] **Step 1:** Check the `/api/voices` endpoint code and the Kokoro `/v1/audio/voices` response
- [ ] **Step 2:** If voices are hardcoded, update to dynamically fetch from Kokoro
- [ ] **Step 3:** Verify Piper voices are also listed when the Piper profile is active

**Validation:** `/api/voices` returns 20+ voices.

---

### P7 — SSH Config Permissions in Container

**Symptom:** The webapp container's SSH config at `/root/.ssh/config` has bad permissions (`Bad owner or permissions`). The sync code works around this with `-F /dev/null` but it's fragile.

**Root cause:** The SSH config is bind-mounted from `ssh-keys/config` on the host. The file permissions or ownership don't match what SSH expects (must be 600 and owned by the running user).

**Fix:**
- [ ] **Step 1:** In the Dockerfile or entrypoint, copy the SSH config and fix permissions:
  ```
  cp /root/.ssh/config.mount /root/.ssh/config && chmod 600 /root/.ssh/config
  ```
  Or mount as read-only and use `-F /root/.ssh/config` explicitly in the rsync command.
- [ ] **Step 2:** Remove the `-F /dev/null` workaround from `copy_to_audiobookshelf()` once permissions are fixed

**Validation:** `ssh docker-vm echo ok` works from inside the container without permission errors.

---

### P8 — No Auto-Convert After Download

**Symptom:** The pipeline currently requires manual intervention to convert a book after it's downloaded. The user wants: book downloaded → auto-convert → auto-sync to ABS → notification.

**Current state:** The wanted_monitor finds books and notifies, but conversion requires opening the webapp and clicking Convert.

**Fix (two options):**

**Option A — Webhook trigger (recommended):**
- [ ] Add a `POST /api/convert` endpoint to the webapp that accepts a library path
- [ ] In wanted_monitor, after a book is downloaded, POST to the webapp's convert API
- [ ] The webapp queues the job automatically
- [ ] Conversion → sync → notification all happen automatically

**Option B — File watcher:**
- [ ] Add a filesystem watcher on `/mnt/openbooks` that triggers conversion when new EPUBs appear
- [ ] More complex, harder to deduplicate, but doesn't require wanted_monitor changes

**Validation:** Add a book to LazyLibrarian wanted list → it automatically appears as an audiobook in ABS within a few hours (depending on OpenBooks availability + conversion time).

---

## Execution Order

| Step | Issue | Effort | Dependency |
|------|-------|--------|------------|
| 1 | P4 — Restore wanted_monitor cron | 5 min | None |
| 2 | P5 — Decommission khpi5 instance | 10 min | None |
| 3 | P0 — Fix ABS metadata (rescan) | 10 min | None |
| 4 | P3 — Add `--speed` to conversion | 30 min | None |
| 5 | P2 — Add `--remove_endnotes` + small file cleanup | 30 min | None |
| 6 | P7 — Fix SSH permissions | 15 min | None |
| 7 | P1 — Re-convert Everything Store | 2-3h (mostly wait) | Steps 4, 5 |
| 8 | P1 — Re-convert Inside Apple | 1-2h (mostly wait) | Steps 4, 5 |
| 9 | P6 — Fix voice discovery | 20 min | None |
| 10 | P8 — Auto-convert via webhook | 1-2h | Steps 4, 5, 6 |

---

## Kokoro Reliability (Updated 2026-02-12)

**Problem:** Kokoro leaks ~1GB RAM per chapter. On a 15.5GB NUC, crashes after ~12 chapters.

**Mitigations now deployed:**
1. `mem_limit: 10g` — Docker OOM-kills at 10GB, `restart: unless-stopped` brings it back at ~1GB
2. Single recovery path — `recover_partial_conversion()` restarts Kokoro, waits for health, retries only missing chapters
3. Converter's built-in HTTP retry (exponential backoff) can survive brief Kokoro restarts mid-chunk

**Result:** Kokoro keeps its top-tier audio quality. Crashes are handled gracefully.

---

## Alternative Approaches Considered

### Alternative TTS Engines (Quality-First Analysis)

**Non-negotiable: audio quality must match or exceed Kokoro.**

| Engine | Quality | Speed | GPU? | Memory | Local? | Notes |
|--------|---------|-------|------|--------|--------|-------|
| **Kokoro** (current) | ⭐⭐⭐⭐⭐ | Slow | CPU-only avail | Leaks ~1GB/ch | ✅ | Best open-source quality, memory leak mitigated |
| **Kokoro GPU** | ⭐⭐⭐⭐⭐ | Fast | Yes (CUDA) | Same leak? | ✅ | Same quality, 5-10x faster, needs GPU hardware |
| **F5-TTS** | ⭐⭐⭐⭐½ | Medium | Yes | ~4GB | ✅ | Very natural, supports voice cloning, needs GPU |
| **Chatterbox** | ⭐⭐⭐⭐ | Medium | Yes | ~6GB | ✅ | Voice cloning + emotion control, newer |
| **Edge TTS** | ⭐⭐⭐ | Fast | No | Minimal | ❌ Cloud | Good but noticeably synthetic, free, no GPU |
| **Piper** (in stack) | ⭐⭐½ | Very fast | No | ~200MB | ✅ | Lightweight but robotic, good for drafts |
| **OpenAI TTS** | ⭐⭐⭐⭐⭐ | Fast | No | N/A | ❌ Cloud | Best quality but $15/million chars (~$2-5/book) |

### Your options without a GPU:

1. **Stay with Kokoro CPU** (recommended) — Memory leak is now mitigated. Quality is the best you'll get without a GPU or cloud API. The recovery system handles crashes automatically.

2. **Add a GPU** — Even a used GTX 1060 6GB (~$80) would let you run Kokoro GPU (5-10x faster) or F5-TTS. A used RTX 3060 12GB (~$180) opens up everything including Chatterbox voice cloning.

3. **Run Kokoro GPU on Hetzner** — You have `hetzner-arm` (37.27.243.187). Hetzner offers GPU servers (~€0.50/hr). Could spin up on-demand for batch conversions, then shut down.

4. **Hybrid: Kokoro main + Edge TTS fallback** — Use Kokoro for the main pass, fall back to Edge TTS only for chapters that fail all Kokoro retries. Slight quality dip on ~5% of chapters vs losing them entirely. But you said no compromise, so this is last resort.

5. **OpenAI TTS API** — The converter already supports `--tts openai`. $2-5 per book, best quality, zero local resources. Could be worth it for important books.

### Alternative EPUB Parsers
- The upstream `p0n1/epub_to_audiobook` has known issues with certain EPUB structures. Consider:
  - Pre-processing the EPUB with Calibre's `ebook-convert` to normalize chapter structure before sending to the converter
  - Using `--title_mode first_few` instead of `auto` to avoid chapter detection bugs
  - Extracting text separately (e.g., with `ebooklib` Python library) and feeding plain text to TTS

### Audiobookshelf Integration
- Instead of rsync + hope ABS scans, use the **ABS API** directly:
  - `POST /api/libraries/:id/scan` to trigger rescan after sync
  - `POST /api/items/:id/scan` to rescan a specific book
  - This requires an ABS API token (generated in ABS settings)

### Monitoring & Alerting
- Add the wanted_monitor health to Uptime Kuma (check log freshness)
- Add conversion job failure alerts to Telegram/WhatsApp
- Add ABS library item count monitoring (detect if books go missing)

---

## Files Modified by This Plan

| File | Changes |
|------|---------|
| `webapp/app.py` | Add `--speed`, `--remove_endnotes` to conversion cmd; add small-file cleanup; add ABS rescan trigger; fix SSH; add auto-convert endpoint |
| `docker-compose.yml` | Add `ABS_API_TOKEN` env var; fix SSH config mount permissions |
| `scripts/wanted/wanted_monitor.py` | Add auto-convert webhook call after download |
| `webapp/templates/index.html` | Add speed control to UI |
| docker-vm crontab | Restore wanted_monitor schedule |
| khpi5 | Decommission containers |
