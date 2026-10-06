#!/usr/bin/env bash
# Run exactly what GitHub CI runs, in a CLEAN checkout of HEAD (so untracked local files such as
# fixtures/armed_struggle.epub cannot hide a failure). Usage: scripts/ci_local.sh
# Needs: python, git. Installs the CI's deps into a throwaway venv.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git clone -q --local "$ROOT" "$TMP/repo"
cd "$TMP/repo"
python -m venv "$TMP/venv"
# shellcheck disable=SC1091
source "$TMP/venv/bin/activate" 2>/dev/null || source "$TMP/venv/Scripts/activate"
pip install -q flask requests gunicorn num2words nltk ebooklib beautifulsoup4 lxml boto3 kaggle \
  pytest mutagen edge-tts numpy soundfile "ruff==0.16.0"
pip install -q -r gemini/requirements.txt
ruff check webapp/ tests/ scripts/ tts_proxy/ chatterbox/ tada/ vibevoice/ qwen3/ pocket/ kitten/
PYTHONPATH=webapp python -m pytest tests/ -x -q
echo "CI-LOCAL OK"
