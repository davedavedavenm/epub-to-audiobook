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
  local engine="$1" port="$2" voice="$3" output="$4" container="$5"
  local text_file payload_file output_file probe_file pid cgroup peak_bytes
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
  output_file="${OUT_DIR}/${output}.mp3"
  /usr/bin/time -f 'wall_seconds=%e' curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    --data-binary "@${payload_file}" \
    "http://127.0.0.1:${port}/v1/audio/speech" \
    -o "${output_file}"
  stat --format='size=%s' "${output_file}"
  probe_file="/tmp/${output}.mp3"
  docker cp "${output_file}" "${container}:${probe_file}" >/dev/null
  docker exec "${container}" ffprobe -v error \
    -show_entries format=duration -of default=noprint_wrappers=1 "${probe_file}"
  docker exec "${container}" rm -f "${probe_file}"
  pid="$(docker inspect --format '{{.State.Pid}}' "${container}")"
  cgroup="$(awk -F: '$1 == "0" {print $3}' "/proc/${pid}/cgroup")"
  peak_bytes="$(cat "/sys/fs/cgroup${cgroup}/memory.peak")"
  echo "container_peak_bytes=${peak_bytes}"
}

render melotts 8007 EN-BR me_british melotts-tts
render melotts 8007 EN-AU me_australian melotts-tts
render omnivoice 8008 british-female ov_british omnivoice-tts
render omnivoice 8008 australian-female ov_australian omnivoice-tts
