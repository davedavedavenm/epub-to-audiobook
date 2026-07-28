#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-v1.3.0}"
REPO_URL="${2:-https://github.com/davedavedavenm/epub-to-audiobook.git}"
STACK_PATH="${3:-/home/dave/ai/lab/stacks/epub-to-audiobook}"

echo "Deploying ${TAG} to ${STACK_PATH}"
mkdir -p "${STACK_PATH}"

if [ ! -d "${STACK_PATH}/.git" ]; then
  git clone "${REPO_URL}" "${STACK_PATH}"
fi

cd "${STACK_PATH}"
git fetch --tags origin --prune
git checkout "${TAG}"

if [ ! -f .env ]; then
  cp .env.example .env
fi

GIT_SHA="$(git rev-parse --short HEAD)"
BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# chatterbox-nano carries the DEFAULT voice, so its container has to be up or
# the default engine is offline on a fresh deploy. It is the 110M model at
# RTF 0.87 (measured) — light enough to run always, unlike Turbo/TADA which
# stay opt-in because they are heavy and slow.
PROFILE_ARGS=(--profile piper --profile chatterbox-nano)
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

echo "Enabled Compose profiles: ${PROFILE_ARGS[*]}"
APP_GIT_SHA="${GIT_SHA}" APP_BUILD_TIME="${BUILD_TIME}" APP_VERSION="${TAG}" \
  docker compose "${PROFILE_ARGS[@]}" up -d --build --remove-orphans

# Build the optional verifier image so the webapp can run it on demand (no services started).
docker compose build audio-verify || true

echo "Deployed ${TAG} (${GIT_SHA})"
