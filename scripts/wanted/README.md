# Wanted Monitor

This is a legal-first wanted-books monitor.

What it does:
- Reads LazyLibrarian's sqlite DB for books with `Status='Wanted'`.
- Checks whether a matching book file exists in the OpenBooks library folder.
- Sends a notification when a wanted item is detected in the library.
- Does not auto-convert books to audiobooks.

## Install / Run (docker-vm)

1. Copy `scripts/wanted/wanted_monitor.py` to `docker-vm` (or run from this repo).
2. Set notification env vars (optional):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

3. Run manually:

```bash
python3 wanted_monitor.py --notify-telegram
```

## Cron suggestion
Run a few times per day (example: 08:00, 14:00, 20:00):

```cron
0 8,14,20 * * * /usr/bin/flock -n /tmp/wanted_monitor.lock python3 /home/dave/scripts/wanted_monitor.py --notify-telegram >> /home/dave/scripts/wanted_monitor.log 2>&1
```

## Configuration
- `--limit`: max titles per run
- `--backoff-base-s`: minimum delay between checks per title
- `--min-score`: fuzzy match threshold

