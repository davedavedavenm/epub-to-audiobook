# Plan (2026-02-06): Reliability, “Wanted” Pipeline, End-to-End Tests

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

Goal: maintain a list of wanted titles; periodically check; when a wanted book becomes available in the library, notify (Telegram/WhatsApp). Do not auto-convert.

Current behavior (docker-vm cron):
- Hourly run of `wanted_monitor.py` checks LazyLibrarian wanted items.
- It detects “FOUND” when a matching file is present in the webapp Library.
- It can optionally request OpenBooks (`--request-openbooks`) but that is not enabled by default.

Planned improvements
- Add an allowlist mechanism (title/author patterns) so OpenBooks requests are only sent for books you explicitly allow (example: public-domain test items). This is now implemented:
  - `wanted_monitor.py --request-openbooks` will only request if `--request-allowlist-file` exists and matches the title/author.
  - Example allowlist file: `scripts/wanted/wanted_allowlist.example.txt`
- Keep strict rate limits:
  - `--max-requests-per-run 1`
  - `--request-cooldown-s >= 43200` (12h)
  - `--max-notifications 1` per run unless you explicitly change it.

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
