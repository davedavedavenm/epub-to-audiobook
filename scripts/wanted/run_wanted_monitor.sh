#!/usr/bin/env bash
set -euo pipefail

set -a
if [[ -f /home/dave/scripts/wanted_monitor.env ]]; then
  # shellcheck source=/dev/null
  source /home/dave/scripts/wanted_monitor.env
fi
set +a

# Check LL wanted items and notify. OpenBooks IRC retired 2026-07-31 (dead network,
# 505 consecutive failures). Torrent path via LL+Prowlarr+qBittorrent replaces it.
exec python3 /home/dave/scripts/wanted_monitor.py \
  --library-api http://192.168.1.88:8881/api/library \
  --limit 10 \
  --backoff-base-s 3600 \
  --backoff-max-s 43200 \
  --notify-telegram \
  --notify-whatsapp \
  --notification-mode per-title \
  --notify-only-downloaded \
  --max-notifications 2 \
  --min-wanted-age-s 3600
