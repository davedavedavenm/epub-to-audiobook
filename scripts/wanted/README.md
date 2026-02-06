# Wanted Monitor

This is a legal-first wanted-books monitor.

What it does:
- Reads LazyLibrarian's sqlite DB for books with `Status='Wanted'`.
- Checks whether a matching book file exists in the OpenBooks library folder.
- Sends a notification when a wanted item is detected in the library (default: single summary message per run).
- Optionally triggers an OpenBooks "request" hook for unfound items (rate-limited; off by default).
- Does not auto-convert books to audiobooks.

## Install / Run (docker-vm)

1. Copy `scripts/wanted/wanted_monitor.py` to `docker-vm` (or run from this repo).
2. Set notification env vars (optional):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `EVOLUTION_API_URL` (for WhatsApp)
- `EVOLUTION_API_KEY` (for WhatsApp)
- `DEFAULT_WHATSAPP_NUMBER` (for WhatsApp)

3. Run manually:

```bash
python3 wanted_monitor.py --notify-telegram --notification-mode summary --max-notifications 1
```

WhatsApp:

```bash
python3 wanted_monitor.py --notify-whatsapp --notification-mode summary --max-notifications 1
```

Per-title notifications (not recommended if you have lots of wanted items):

```bash
python3 wanted_monitor.py --notify-telegram --notification-mode per-title --max-notifications 1
```

Optional OpenBooks requests (very conservative defaults):

```bash
python3 wanted_monitor.py --request-openbooks --request-policy all --max-requests-per-run 1 --request-cooldown-s 43200
```

Allowlist-gated requests (optional safety gate):

```bash
python3 wanted_monitor.py --request-openbooks --request-policy allowlist --request-allowlist-file /home/dave/scripts/wanted_allowlist.txt --max-requests-per-run 1 --request-cooldown-s 43200
```

## Cron suggestion
Run a few times per day (example: 08:00, 14:00, 20:00):

```cron
0 8,14,20 * * * /usr/bin/flock -n /tmp/wanted_monitor.lock python3 /home/dave/scripts/wanted_monitor.py --notify-telegram --notification-mode summary --max-notifications 1 >> /home/dave/scripts/wanted_monitor.log 2>&1
```

## Configuration
- `--limit`: max titles per run
- `--backoff-base-s`: minimum delay between checks per title
- `--min-score`: fuzzy match threshold
- `--notification-mode`: `summary` (default) or `per-title`
- `--max-notifications`: hard cap across all channels per run (default: 1)
- `--request-openbooks`: enable OpenBooks request hook (default: off)
- `--request-policy`: `all` (default) or `allowlist`
- `--request-allowlist-file`: allowlist file (used only with `--request-policy allowlist`)
- `--max-requests-per-run`: hard cap of OpenBooks requests per run (default: 1)
- `--request-cooldown-s`: minimum time between requests per title (default: 12h)
