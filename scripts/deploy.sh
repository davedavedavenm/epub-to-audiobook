#!/usr/bin/env bash
set -euo pipefail

REF="${1:-master}"
VERSION="${APP_VERSION:-2.1.0}"
REPO_URL="${2:-https://github.com/davedavedavenm/epub-to-audiobook.git}"
STACK_PATH="${3:-/home/dave/ai/lab/stacks/epub-to-audiobook}"

echo "Deploying git ref ${REF} as app version ${VERSION} to ${STACK_PATH}"
mkdir -p "${STACK_PATH}"

if [ ! -d "${STACK_PATH}/.git" ]; then
  git clone "${REPO_URL}" "${STACK_PATH}"
fi

cd "${STACK_PATH}"
git fetch --tags origin --prune
TARGET="${REF}"
if git show-ref --verify --quiet "refs/remotes/origin/${REF}"; then
  TARGET="origin/${REF}"
fi
# A detached, resolved revision prevents an existing local branch from staying
# on a stale commit when `master` is requested.
git checkout --detach "${TARGET}"

if [ ! -f .env ]; then
  cp .env.example .env
fi

# Full commit, not an abbreviated display SHA: Kaggle finalist kernels fetch
# this exact object and assert parity with the deployed worker before rendering.
GIT_SHA="$(git rev-parse HEAD)"
BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# chatterbox-nano carries the DEFAULT voice, so its container has to be up or
# the default engine is offline on a fresh deploy. It is the 110M model at
# RTF 0.87 (measured) — light enough to run always, unlike Turbo/TADA which
# stay opt-in because they are heavy and slow.
PROFILE_ARGS=(--profile chatterbox-nano)
if [[ "${ENABLE_PIPER_PROFILE:-0}" == "1" ]]; then
  # Legacy/debug only. The controlled Piper 1.2/1.6 + encoding A/B failed the
  # audiobook quality bar on 2026-07-28, so never enable it by default.
  PROFILE_ARGS+=(--profile piper)
fi
if [[ "${ENABLE_CHATTERBOX_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile chatterbox)
fi
if [[ "${ENABLE_TADA_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile tada)
fi
if [[ "${ENABLE_MELOTTS_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile melotts)
fi
if [[ "${ENABLE_OMNIVOICE_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile omnivoice)
fi
if [[ "${ENABLE_CHATTERBOX_V3_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile chatterbox-v3)
fi
if [[ "${ENABLE_VIBEVOICE_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile vibevoice)
fi
if [[ "${ENABLE_QWEN3_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile qwen3)
fi
if [[ "${ENABLE_POCKET_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile pocket)
fi
if [[ "${ENABLE_KITTEN_PROFILE:-0}" == "1" ]]; then
  PROFILE_ARGS+=(--profile kitten)
fi

echo "Enabled Compose profiles: ${PROFILE_ARGS[*]}"
APP_GIT_SHA="${GIT_SHA}" APP_BUILD_TIME="${BUILD_TIME}" APP_VERSION="${VERSION}" \
  docker compose "${PROFILE_ARGS[@]}" up -d --build --remove-orphans

# Build the optional verifier image so the webapp can run it on demand (no services started).
docker compose build audio-verify || true

echo "Waiting for webapp and worker health..."
for attempt in $(seq 1 60); do
  web_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' epub-to-audiobook-ui 2>/dev/null || true)"
  worker_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' epub-to-audiobook-worker 2>/dev/null || true)"
  if [[ "${web_health}" == "healthy" && "${worker_health}" == "healthy" ]]; then
    break
  fi
  if [[ "${attempt}" == "60" ]]; then
    echo "Health timeout: webapp=${web_health:-missing}, worker=${worker_health:-missing}" >&2
    docker compose ps >&2
    exit 1
  fi
  sleep 5
done

HEALTH_JSON="$(curl -fsS http://127.0.0.1:8881/api/health)"
python3 -c 'import json,sys; d=json.load(sys.stdin); assert d.get("overall") == "ok", d' <<<"${HEALTH_JSON}"
LIVE_SHA="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("git_sha", ""))' <<<"${HEALTH_JSON}")"
if [[ "${LIVE_SHA}" != "${GIT_SHA}" ]]; then
  echo "Revision mismatch: expected ${GIT_SHA}, webapp reports ${LIVE_SHA:-missing}" >&2
  exit 1
fi

echo "Deployed ${REF} as ${VERSION} (${GIT_SHA})"
