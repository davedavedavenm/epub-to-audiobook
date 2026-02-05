#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8881}"
KOKORO_URL="${2:-http://localhost:8880/v1/audio/voices}"
PIPER_URL="${3:-http://localhost:5000/v1/models}"

echo "== webapp health =="
curl -fsS "${BASE_URL}/api/health"
echo

echo "== version =="
curl -fsS "${BASE_URL}/api/version"
echo

echo "== voices =="
curl -fsS "${BASE_URL}/api/voices" >/dev/null && echo "voices ok"

echo "== queue status =="
curl -fsS "${BASE_URL}/api/queue/status"
echo

echo "== diagnostics =="
curl -fsS "${BASE_URL}/api/diagnostics"
echo

echo "== kokoro =="
curl -fsS "${KOKORO_URL}" >/dev/null && echo "kokoro ok"

echo "== piper =="
curl -fsS "${PIPER_URL}" >/dev/null && echo "piper ok"

echo "Smoke checks passed."
