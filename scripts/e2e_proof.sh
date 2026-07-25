#!/usr/bin/env bash
# E2E proof: render one public-domain chapter on EVERY free engine and verify
# the whole delivery chain each time — MP3, chaptered M4B, cover art, and the
# Audiobookshelf sync — wiping between runs so each engine starts clean.
#
# Run on zorin. Prints one PASS/FAIL block per engine plus a summary.
set -uo pipefail
API=http://localhost:8881
BOOK="/home/dave/booklib/The Raven - Edgar Allan Poe.epub"
STACK=/home/dave/ai/lab/stacks/epub-to-audiobook
OUTROOT="$STACK/data/audiobooks"
ABS_HOST=192.168.1.113
ABS_DIR=/opt/stacks/audiobookshelf/audiobooks

# engine:voice — every FREE option that is currently up
ENGINES=(
  "chatterbox_nano:uk_male_minter_nano"
  "kokoro:bm_george"
  "piper:fable"
  "edge:en-GB-RyanNeural"
  "chatterbox:uk_male_minter"
)

PASSES=(); FAILS=()

for spec in "${ENGINES[@]}"; do
  ENGINE="${spec%%:*}"; VOICE="${spec##*:}"
  echo ""
  echo "=================================================================="
  echo "ENGINE: $ENGINE   VOICE: $VOICE"
  echo "=================================================================="

  RESP=$(curl -s -X POST "$API/api/library/convert" -H "Content-Type: application/json" \
    -d "{\"path\":\"$BOOK\",\"voice\":\"$VOICE\",\"render_target\":\"local\",\"output_format\":\"m4b\",\"start_chapter\":1,\"end_chapter\":1}")
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
    # wipe ONLY on success, as instructed
    [ -n "$DIR" ] && sudo rm -rf "$DIR"
    [ -n "$SYNC_DIR" ] && ssh -o ConnectTimeout=8 -o BatchMode=yes -o StrictHostKeyChecking=no \
        dave@"$ABS_HOST" "rm -rf '$ABS_DIR/$SYNC_DIR'" 2>/dev/null
    docker exec epub-to-audiobook-ui python3 -c "
import sqlite3;c=sqlite3.connect('/data/jobs.db')
c.execute('delete from jobs where id=?',('$JOB',));c.commit()" 2>/dev/null
    echo "  wiped     : local output, ABS copy, job record"
  else
    echo "  RESULT    : FAIL ($NOTES)"; FAILS+=("$ENGINE:$NOTES")
    echo "  (left in place for inspection: $DIR)"
  fi
done

echo ""
echo "=================== E2E SUMMARY ==================="
echo "PASS (${#PASSES[@]}): ${PASSES[*]:-none}"
echo "FAIL (${#FAILS[@]}): ${FAILS[*]:-none}"
