#!/usr/bin/env bash
# First-run helper for Linux/macOS. Creates a real absolute STACK_PATH, starts
# the supported local baseline and proves both app and default narrator.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

if [[ ! -f .env ]]; then
  sed "s|^STACK_PATH=.*|STACK_PATH=$ROOT|" .env.example > .env
  echo "Created .env with STACK_PATH=$ROOT"
else
  echo "Using existing .env (not overwritten)"
fi

docker compose --profile chatterbox-nano config >/dev/null
docker compose --profile chatterbox-nano up -d --build

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8881/api/health >/dev/null 2>&1; then
    curl -fsS http://127.0.0.1:8881/api/health
    echo
    curl -fsS http://127.0.0.1:8881/api/engines/health
    echo
    echo "Open http://127.0.0.1:8881"
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for the app. Run: docker compose ps" >&2
exit 1
