#!/usr/bin/env bash
# E2E proof: render one public-domain book on selected engines and verify the
# whole delivery chain each time — source-word coverage, MP3 duration, ASR QA,
# chaptered M4B, cover art, and the Audiobookshelf sync. Outputs are retained by
# default so a human can listen to the actual delivered book.
#
# Run on zorin. Prints one PASS/FAIL block per engine plus a summary.
#
# Select a known engine by name, or pass an exact engine:voice pair:
#   bash scripts/e2e_proof.sh vibevoice:vibevoice_uk_male
# Set E2E_CLEANUP=1 only for disposable regression runs after listening.
set -uo pipefail
API="${E2E_API:-http://localhost:8881}"
BOOK="${E2E_BOOK:-/home/dave/booklib/The Raven - Edgar Allan Poe.epub}"
STACK="${E2E_STACK:-/home/dave/ai/lab/stacks/epub-to-audiobook}"
OUTROOT="$STACK/data/audiobooks"
ABS_HOST="${E2E_ABS_HOST:-192.168.1.113}"
ABS_DIR="${E2E_ABS_DIR:-/opt/stacks/audiobookshelf/audiobooks}"
CLEANUP="${E2E_CLEANUP:-0}"
RENDER_TARGET="${E2E_RENDER_TARGET:-local}"

# engine:voice — every FREE option that is currently up
DEFAULT_ENGINES=(
  "chatterbox_nano:uk_male_minter_nano"
  "kokoro:bm_george"
  "piper:fable"
  "edge:en-GB-RyanNeural"
  "chatterbox:uk_male_minter"
)
# Opt-in engines are omitted from an unqualified regression sweep. TADA has
# worked locally in bf16 since 2026-07-27 (RTF 1.68, 10.00 GiB measured); Vibe
# and Qwen require either their CUDA profile or E2E_RENDER_TARGET=kaggle.
OPTIONAL_ENGINES=(
  "tada:uk_male_minter_tada"
  "vibevoice:uk_male_minter_vibevoice"
  "qwen3:uk_male_minter_qwen3"
)
# ALL = selectable by name; DEFAULT = what an unqualified run proves.
ALL_ENGINES=("${DEFAULT_ENGINES[@]}" "${OPTIONAL_ENGINES[@]}")

# Optional args select a subset. An exact engine:voice pair is also accepted so
# a newly integrated engine can be proven before it is added to this list.
if [ "$#" -gt 0 ]; then
  ENGINES=()
  for want in "$@"; do
    if [[ "$want" == *:* ]]; then
      ENGINES+=("$want")
      continue
    fi
    for e in "${ALL_ENGINES[@]}"; do
      [ "${e%%:*}" = "$want" ] && ENGINES+=("$e")
    done
  done
  [ "${#ENGINES[@]}" -gt 0 ] || { echo "no engine matched: $*"; exit 2; }
else
  ENGINES=("${DEFAULT_ENGINES[@]}")
fi

PASSES=(); FAILS=()

for spec in "${ENGINES[@]}"; do
  ENGINE="${spec%%:*}"; VOICE="${spec##*:}"
  echo ""
  echo "=================================================================="
  echo "ENGINE: $ENGINE   VOICE: $VOICE"
  echo "=================================================================="

  RESP=$(curl -s -X POST "$API/api/library/convert" -H "Content-Type: application/json" \
    -d "{\"path\":\"$BOOK\",\"voice\":\"$VOICE\",\"render_target\":\"$RENDER_TARGET\",\"output_format\":\"m4b\",\"start_chapter\":1,\"end_chapter\":1}")
  JOB=$(echo "$RESP" | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p')
  if [ -z "$JOB" ]; then
    echo "QUEUE FAILED: $RESP"; FAILS+=("$ENGINE (queue rejected)"); continue
  fi
  echo "queued job $JOB"

  # wait for terminal state (max 60 min)
  STATUS=""
  for i in $(seq 1 180); do
    STATUS=$(docker exec epub-to-audiobook-ui python3 -c "
import sqlite3;c=sqlite3.connect('/data/jobs.db')
r=c.execute('select status from jobs where id=?',('$JOB',)).fetchone()
print(r[0] if r else 'gone')" 2>/dev/null)
    case "$STATUS" in
      completed|failed|cancelled|"review needed") break;;
    esac
    sleep 20
  done
  echo "final status: $STATUS"

  DIR=$(ls -d "$OUTROOT"/*_"$JOB" 2>/dev/null | head -1)
  OK=1; NOTES=""

  if [ "$STATUS" != "completed" ]; then
    OK=0; NOTES="$NOTES status=$STATUS;"
    ERR=$(docker exec epub-to-audiobook-ui python3 -c "
import sqlite3;c=sqlite3.connect('/data/jobs.db')
r=c.execute('select error from jobs where id=?',('$JOB',)).fetchone()
print((r[0] or '')[:200] if r else '')" 2>/dev/null)
    echo "  error: $ERR"
  fi

  if [ -n "$DIR" ]; then
    MP3=$(ls "$DIR"/*.mp3 2>/dev/null | wc -l)
    M4B=$(ls "$DIR"/*.m4b 2>/dev/null | head -1)
    COVER=$(ls "$DIR"/cover.* 2>/dev/null | head -1)
    echo "  mp3 files : $MP3"
    [ "$MP3" -ge 1 ] || { OK=0; NOTES="$NOTES no-mp3;"; }

    # Compare playable duration with the source word count. This catches the
    # model-collapse failure where an MP3 exists but contains only a fraction of
    # the requested chapter. 260 wpm is deliberately generous for narration.
    TOC=$(curl -s -X POST "$API/api/library/toc" -H "Content-Type: application/json" \
      -d "{\"path\":\"$BOOK\"}")
    WORDS=$(printf '%s' "$TOC" | python3 -c \
      'import json,sys; d=json.load(sys.stdin); print(sum(int(c.get("words",0)) for c in d.get("chapters",[]) if c.get("index")==1))' \
      2>/dev/null || echo 0)
    AUDIO_SECONDS=0
    for f in "$DIR"/*.mp3; do
      [ -f "$f" ] || continue
      D=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" 2>/dev/null || echo 0)
      AUDIO_SECONDS=$(python3 -c "print(float('$AUDIO_SECONDS') + float('$D'))")
    done
    MIN_SECONDS=$(python3 -c "print(float('$WORDS') / 260.0 * 60.0 if float('$WORDS') else 0)")
    echo "  coverage  : $WORDS source words, ${AUDIO_SECONDS}s audio (minimum ${MIN_SECONDS}s)"
    python3 -c "raise SystemExit(0 if float('$AUDIO_SECONDS') >= float('$MIN_SECONDS') > 0 else 1)" \
      || { OK=0; NOTES="$NOTES short-audio;"; }

    QA=$(curl -s "$API/api/jobs/$JOB/qa")
    QA_OK=$(printf '%s' "$QA" | python3 -c \
      'import json,sys; d=json.load(sys.stdin); print(1 if d.get("available") and int(d.get("chapters") or 0)>0 else 0)' \
      2>/dev/null || echo 0)
    QA_WER=$(printf '%s' "$QA" | python3 -c \
      'import json,sys; print(json.load(sys.stdin).get("worst_wer","?"))' 2>/dev/null || echo '?')
    echo "  asr qa    : available=$QA_OK worst_wer=$QA_WER"
    [ "$QA_OK" = "1" ] || { OK=0; NOTES="$NOTES no-asr-qa;"; }

    if [ -n "$M4B" ]; then
      CH=$(docker exec epub-to-audiobook-ui ffmpeg -i "/data/audiobooks/$(basename "$DIR")/$(basename "$M4B")" 2>&1 | grep -c "Chapter #")
      SZ=$(stat -c%s "$M4B")
      echo "  m4b       : $(basename "$M4B") ${SZ}B, $CH chapter marks"
      [ "$CH" -ge 1 ] || { OK=0; NOTES="$NOTES m4b-no-chapters;"; }
    else
      OK=0; NOTES="$NOTES no-m4b;"; echo "  m4b       : MISSING"
    fi

    if [ -n "$COVER" ]; then
      echo "  cover art : $(basename "$COVER") $(stat -c%s "$COVER")B"
    else
      OK=0; NOTES="$NOTES no-cover;"; echo "  cover art : MISSING"
    fi
  else
    OK=0; NOTES="$NOTES no-output-dir;"; echo "  output dir: MISSING"
  fi

  SYNC=$(docker exec epub-to-audiobook-ui python3 -c "
import sqlite3;c=sqlite3.connect('/data/jobs.db')
r=c.execute('select sync_status,output_dirname from jobs where id=?',('$JOB',)).fetchone()
print((r[0] or 'none')+'|'+(r[1] or '') if r else 'none|')" 2>/dev/null)
  SYNC_STATE="${SYNC%%|*}"; SYNC_DIR="${SYNC##*|}"
  echo "  abs sync  : $SYNC_STATE"
  ABS_FILES=$(ssh -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=no \
      dave@"$ABS_HOST" "ls '$ABS_DIR/$SYNC_DIR' 2>/dev/null | wc -l" 2>/dev/null)
  echo "  abs files : ${ABS_FILES:-0}"
  [ "${ABS_FILES:-0}" -ge 1 ] || { OK=0; NOTES="$NOTES abs-empty;"; }

  if [ "$OK" = "1" ]; then
    echo "  RESULT    : PASS"; PASSES+=("$ENGINE")
    if [ "$CLEANUP" = "1" ]; then
      # Cleanup is opt-in and guarded to this exact job id. Never remove a
      # broad or unresolved path.
      if [[ -n "$DIR" && "$DIR" == "$OUTROOT/"*"_$JOB" && -n "$SYNC_DIR" && "$SYNC_DIR" == *"_$JOB" ]]; then
        sudo rm -rf -- "$DIR"
        ssh -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=no \
          dave@"$ABS_HOST" "rm -rf -- '$ABS_DIR/$SYNC_DIR'" 2>/dev/null
        docker exec epub-to-audiobook-ui python3 -c "
import sqlite3;c=sqlite3.connect('/data/jobs.db')
c.execute('delete from jobs where id=?',('$JOB',));c.commit()" 2>/dev/null
        echo "  cleanup   : local output, ABS copy, job record removed"
      else
        OK=0; NOTES="$NOTES cleanup-guard;"
        echo "  cleanup   : REFUSED (path/job guard failed)"
      fi
    else
      echo "  retained  : $DIR (and Audiobookshelf copy)"
    fi
  else
    echo "  RESULT    : FAIL ($NOTES)"; FAILS+=("$ENGINE:$NOTES")
    echo "  (left in place for inspection: $DIR)"
  fi
done

echo ""
echo "=================== E2E SUMMARY ==================="
echo "PASS (${#PASSES[@]}): ${PASSES[*]:-none}"
echo "FAIL (${#FAILS[@]}): ${FAILS[*]:-none}"
