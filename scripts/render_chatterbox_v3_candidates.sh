#!/usr/bin/env bash
set -euo pipefail

STACK_PATH="${STACK_PATH:-/home/dave/ai/lab/stacks/epub-to-audiobook}"
OUT_DIR="${STACK_PATH}/data/previews"
VOICE_DIR="${STACK_PATH}/data/voices"
mkdir -p "${OUT_DIR}" "${VOICE_DIR}"

# The earlier Edge ZA audition is the only genuinely South African reference
# currently on the box. Convert its first 20 seconds to the WAV format scanned
# by the Chatterbox service. This is evaluation data, not source-controlled.
ZA_REF="${VOICE_DIR}/accent_southafrican_male.wav"
if [[ ! -s "${ZA_REF}" ]]; then
  # ffmpeg lives in the webapp image, not necessarily on the Zorin host. Both
  # paths are in its /data bind mount, and it runs as the matching uid 999.
  docker exec epub-to-audiobook-ui ffmpeg -v error -y \
    -i /data/previews/eg_za_m.mp3 -t 20 -ac 1 -ar 24000 \
    /data/voices/accent_southafrican_male.wav
fi

text_file="$(mktemp)"
payload_file="$(mktemp)"
trap 'rm -f "${text_file}" "${payload_file}"' EXIT
PYTHONPATH="${STACK_PATH}/webapp" python3 - > "${text_file}" <<'PY'
from voice_sample import sample_text_for
print(sample_text_for("chatterbox"))
PY

render() {
  local voice="$1" output="$2"
  if [[ -s "${OUT_DIR}/${output}.mp3" ]]; then
    echo "Skipping existing ${output}.mp3"
    docker exec epub-to-audiobook-ui ffprobe -v error \
      -show_entries format=duration -of default=noprint_wrappers=1 \
      "/data/previews/${output}.mp3"
    return
  fi
  python3 - "${text_file}" "${voice}" > "${payload_file}" <<'PY'
import json, pathlib, sys
print(json.dumps({
    "model": "tts-1",
    "input": pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"),
    "voice": sys.argv[2],
    "response_format": "mp3",
    "cfg_weight": 0,
}))
PY
  echo "Rendering Chatterbox V3/${voice} -> ${output}.mp3"
  /usr/bin/time -f 'wall_seconds=%e' curl --fail --silent --show-error \
    -H 'Content-Type: application/json' --data-binary "@${payload_file}" \
    http://127.0.0.1:8009/v1/audio/speech -o "${OUT_DIR}/${output}.mp3"
  stat --format='size=%s' "${OUT_DIR}/${output}.mp3"
  docker exec epub-to-audiobook-ui ffprobe -v error \
    -show_entries format=duration -of default=noprint_wrappers=1 \
    "/data/previews/${output}.mp3"
}

render accent_irish_male cv3_irish_male
render accent_southafrican_male cv3_southafrican_male
