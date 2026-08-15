#!/usr/bin/env bash
# Sample a few chapters of a book through the REAL pipeline, for fast iteration
# without a full-book run. Local-first: auto-detects a healthy LOCAL engine and
# uses it; otherwise pass --engine-url (a Kaggle/Vast URL). Output always lands
# in data/audiobooks/_samples/<book>/ (see README "Where do I find my
# audiobooks?"). Nothing here touches the real library or the webapp queue.
#
# Usage:
#   scripts/sample.sh --book path/to/book.epub [--start 1] [--end 2]
#                     [--voice uk_male_minter_tada] [--engine-url http://host:port/v1]
#                     [--text-profile modern|explicit|legacy]
#
# Examples:
#   scripts/sample.sh --book "data/library/Some Book.epub"            # local engine, ch1-2
#   scripts/sample.sh --book book.epub --end 3 --engine-url http://1.2.3.4:32048/v1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

BOOK=""; START=1; END=2; VOICE=""; ENGINE_URL="${ENGINE_URL:-}"; TEXT_PROFILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --book)       BOOK="$2"; shift 2;;
    --start)      START="$2"; shift 2;;
    --end)        END="$2"; shift 2;;
    --voice)      VOICE="$2"; shift 2;;
    --engine-url) ENGINE_URL="$2"; shift 2;;
    --text-profile) TEXT_PROFILE="$2"; shift 2;;
    -h|--help)    sed -n '2,16p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done
[ -n "$BOOK" ] || { echo "error: --book is required (see --help)" >&2; exit 1; }
[ -f "$BOOK" ] || { echo "error: book not found: $BOOK" >&2; exit 1; }

probe() { curl -fs -m 4 "$1/health" >/dev/null 2>&1; }

# Local-first engine detection. Order: the human-cloned engines first (best
# quality), then the always-CPU guaranteed-completes fallbacks. name|base|voice
CANDIDATES="
chatterbox|http://localhost:8004|uk_male_minter
tada|http://localhost:8005|uk_male_minter_tada
kokoro|http://localhost:8880|bm_george
"
if [ -z "$ENGINE_URL" ]; then
  while IFS='|' read -r name base dv; do
    [ -n "$name" ] || continue
    if probe "$base"; then
      ENGINE_URL="$base/v1"; [ -z "$VOICE" ] && VOICE="$dv"
      echo ">> local engine detected: $name ($base)"
      break
    fi
  done <<EOF
$CANDIDATES
EOF
fi

if [ -z "$ENGINE_URL" ]; then
  echo "no healthy local engine and no --engine-url given." >&2
  echo "  start one:  docker compose --profile chatterbox up -d chatterbox-tts" >&2
  echo "  or pass a cloud engine URL:  --engine-url http://<host>:<port>/v1" >&2
  exit 2
fi
[ -n "$VOICE" ] || VOICE="uk_male_minter_tada"

# Match the webapp's measured text contract. Pocket/Kitten won their numeric
# A/B only with explicit spoken numbers/currency; a standalone sample must not
# silently fall back to convert_book's backwards-compatible auto heuristic.
if [ -z "$TEXT_PROFILE" ]; then
  case "$VOICE" in
    pocket_*|kitten_*) TEXT_PROFILE="explicit" ;;
    uk_*|*_tada) TEXT_PROFILE="modern" ;;
    *) TEXT_PROFILE="legacy" ;;
  esac
fi

label="$(basename "${BOOK%.*}")"
OUT="$ROOT/data/audiobooks/_samples/$label"
echo ">> sampling ch${START}-${END} of '$label'"
echo ">> engine=$ENGINE_URL  voice=$VOICE"
echo ">> text-profile=$TEXT_PROFILE"
echo ">> output -> $OUT"
python "$ROOT/scripts/convert_book.py" \
  --epub "$BOOK" --engine-url "$ENGINE_URL" --voice "$VOICE" \
  --out "$OUT" --start "$START" --end "$END" \
  --text-profile "$TEXT_PROFILE"
echo ">> done. Listen in: $OUT"
