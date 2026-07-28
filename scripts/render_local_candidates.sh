#!/usr/bin/env bash
set -euo pipefail

STACK_PATH="${STACK_PATH:-/home/dave/ai/lab/stacks/epub-to-audiobook}"
OUT_DIR="${STACK_PATH}/data/previews"
mkdir -p "${OUT_DIR}"

sample_text() {
  local engine="$1"
  PYTHONPATH="${STACK_PATH}/webapp" python3 - "$engine" <<'PY'
import sys
from voice_sample import sample_text_for
print(sample_text_for(sys.argv[1]))
PY
}

render() {
  local engine="$1" port="$2" voice="$3" output="$4"
  local text_file payload_file
  text_file="$(mktemp)"
  payload_file="$(mktemp)"
  trap 'rm -f "${text_file}" "${payload_file}"' RETURN
  sample_text "${engine}" > "${text_file}"
  python3 - "${text_file}" "${voice}" > "${payload_file}" <<'PY'
import json, pathlib, sys
print(json.dumps({
    "model": "tts-1",
    "input": pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"),
    "voice": sys.argv[2],
    "response_format": "mp3",
}))
PY
  echo "Rendering ${engine}/${voice} -> ${output}"
  /usr/bin/time -v curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    --data-binary "@${payload_file}" \
    "http://127.0.0.1:${port}/v1/audio/speech" \
    -o "${OUT_DIR}/${output}.mp3"
  ffprobe -v error -show_entries format=duration,size \
    -of default=noprint_wrappers=1 "${OUT_DIR}/${output}.mp3"
}

render melotts 8007 EN-BR me_british
render melotts 8007 EN-AU me_australian
render omnivoice 8008 british-female ov_british
render omnivoice 8008 australian-female ov_australian

