# Plan (2026-02-06): Reliability, Wanted Pipeline, End-to-End Tests

This plan is written to keep the stack reliable without requiring you to “discover bugs” manually.

## 1) Reliability (conversion + queue)

### Done
- Fixed Audiobookshelf sync failures caused by apostrophes/quoting by syncing to `output_dir.name` and POSIX-safe quoting for SSH commands.
- Improved restart behavior:
  - On webapp restart, in-flight jobs are no longer blindly failed.
  - If outputs exist, jobs are finalized as `completed`.
  - Otherwise, jobs are re-queued (bounded by `MAX_RETRY_COUNT`) so queued work isn’t lost.

### Next
- Add a small “post-deploy smoke” that runs on the host and asserts:
  - `GET /api/health`
  - `GET /api/library`
  - `GET /api/jobs`
  - `tts-proxy` healthz

## 2) Wanted List -> Library (non-spam, safe)

Goal: maintain a list of wanted titles in LazyLibrarian; periodically check; when a wanted book is actually downloaded into the Library, notify (Telegram/WhatsApp). Do not auto-convert.

Current behavior (live; docker-vm hourly cron):
- Each run does 2 phases:
  - Process queued OpenBooks requests (max 2 sends per run).
  - Check LazyLibrarian Wanted, enqueue up to 2 new OpenBooks requests, and check for downloads via the webapp Library API.
- OpenBooks requests are queued in sqlite (so we never spam OpenBooks).
- Notifications are per-title (not summary), and should be low-noise.

What “good” looks like (requirements)
- A title marked Wanted in LazyLibrarian stays tracked automatically (no manual file editing).
- If you delete an unwanted title in LazyLibrarian, it is purged from local state and will not be requested again.
- Telegram/WhatsApp messages:
  - Per-title only.
  - Only when the title is downloaded successfully into the library (not “already have it”).
  - De-duped so concurrent runs do not double-notify.
- OpenBooks request behavior:
  - Queue-based (sqlite), max 2 sends per run.
  - Per-title cooldown (default 6h or 12h, adjustable).
  - “Min Wanted age” guard to avoid LazyLibrarian bulk/auto-add churn.

## 3) End-to-End Test (agent-run, no manual clicking)

Goal: one command that validates the full pipeline:
1. Add a public-domain test title to the “wanted” allowlist (example: Frankenstein).
2. Trigger a wanted-monitor run (single run, max 1 request).
3. Verify the EPUB appears in webapp Library.
4. Trigger conversion via API.
5. Verify:
   - job reaches `completed`
   - output MP3s exist
   - sync to Audiobookshelf succeeds
   - transcript proxy captured chunks (if enabled)
   - verification report exists

Success criteria
- No job gets stuck at 0% without an actionable error.
- Restarting the webapp does not lose queued items.
- No Telegram spam (<= 1 message for the test run).

## 4) UI

Separately tracked:
- Visual artifacts (pill/toolbar overlap, chips layout) should be fixed after reliability and e2e tests, so UI work doesn’t mask core functional regressions.
