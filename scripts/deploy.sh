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

APP_GIT_SHA="${GIT_SHA}" APP_BUILD_TIME="${BUILD_TIME}" APP_VERSION="${TAG}" \
  docker compose --profile piper up -d --build --remove-orphans

echo "Deployed ${TAG} (${GIT_SHA})"
