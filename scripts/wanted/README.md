# Wanted Monitor

What it does:
- Reads LazyLibrarian's sqlite DB for books with `Status='Wanted'`.
- Checks whether a matching book exists in the webapp Library (via `--library-api`) or by scanning the library folder.
- Maintains a small sqlite state DB (`wanted_state.db`) so checks/backoff/notifications are stable across restarts.
- Optionally triggers OpenBooks requests for unfound items using a queue (rate-limited, non-spammy).
- Does not auto-convert books to audiobooks.

## Install / Run (docker-vm)

1. Copy `scripts/wanted/wanted_monitor.py` to `docker-vm` (or run from this repo).
2. Set notification env vars (optional). Recommended: keep secrets in `/home/dave/scripts/wanted_monitor.env` (not in git):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `EVOLUTION_API_URL` (for WhatsApp)
- `EVOLUTION_API_KEY` (for WhatsApp)
- `DEFAULT_WHATSAPP_NUMBER` (for WhatsApp)

3. Run manually:

```bash
# Send at most 2 queued OpenBooks requests.
python3 wanted_monitor.py --process-openbooks-queue --max-queue-sends 2 --bridge-timeout-s 30

# Check LazyLibrarian wanted items, enqueue up to 2 new requests, and notify per-title
# only when the item is actually downloaded by the pipeline.
python3 wanted_monitor.py \
  --library-api http://192.168.1.88:8881/api/library \
  --limit 10 \
  --notify-telegram --notify-whatsapp \
  --notification-mode per-title \
  --notify-only-downloaded \
  --max-notifications 2 \
  --request-openbooks --request-policy all \
  --max-requests-per-run 2 \
  --request-cooldown-s 21600 \
  --min-wanted-age-s 3600
```

Send a single test notification (no DB changes):

```bash
python3 wanted_monitor.py --send-test --notify-telegram --notify-whatsapp --max-notifications 1
```

Notes:
- If you delete unwanted titles from LazyLibrarian, the monitor purges them from local state so they stop being requested/checked.
- OpenBooks requests are queued in sqlite so we can keep strict caps and avoid bursts.

## Cron suggestion
Hourly run with a lock (recommended):

```cron
0 * * * * /usr/bin/flock -n /tmp/wanted_monitor.lock /home/dave/scripts/run_wanted_monitor.sh >> /home/dave/scripts/wanted_monitor.log 2>&1
```

## Configuration
- `--limit`: max titles per run
- `--backoff-base-s`: minimum delay between checks per title
- `--min-score`: fuzzy match threshold
- `--notification-mode`: `per-title` or `summary`
- `--notify-only-downloaded`: only notify when the title appears after an actual OpenBooks send
- `--max-notifications`: hard cap across all channels per run
- `--request-openbooks`: enable OpenBooks request enqueueing
- `--request-policy`: `all` (default) or `allowlist`
- `--request-allowlist-file`: allowlist file (used only with `--request-policy allowlist`)
- `--max-requests-per-run`: hard cap of OpenBooks enqueues per run
- `--request-cooldown-s`: minimum time between requests per title
- `--min-wanted-age-s`: wait this long after becoming Wanted before enqueuing (helps avoid LL churn)
