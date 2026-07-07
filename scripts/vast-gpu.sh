#!/usr/bin/env bash
# One-command Vast.ai GPU runbook for the Chatterbox / TADA engines.
#
# Architecture (lessons baked in from the 2026-07-06/07 validation runs):
#   - Uses the PRE-BUILT engine image from GHCR (CI-built; CUDA torch + NVIDIA
#     envs baked in). NO pip installs on the instance.
#   - The engine server starts via Vast's --onstart-cmd (image CMD does not run
#     in Vast's managed modes) and is reached via DIRECT PORT MAPPING on the
#     instance's public IP. No SSH needed (slim images carry no sshd).
#   - Health is verified via /health, which reports cuda_available — refuse to
#     proceed if the GPU isn't actually visible.
#
# Usage:
#   scripts/vast-gpu.sh up chatterbox|tada [offer_id]
#   scripts/vast-gpu.sh status
#   scripts/vast-gpu.sh down          # ALWAYS run when finished — billing stops only on destroy
#
# After `up` prints the engine URL, point the stack at it, e.g.:
#   TADA_URL=http://<ip>:<port>/v1  docker compose up -d worker webapp
set -euo pipefail

OWNER="${GHCR_OWNER:-davedavedavenm}"
VAST="${VASTAI_CLI:-python3 /tmp/vast.py}"
STATE="/tmp/vast-gpu-state"

engine_port() { case "$1" in chatterbox) echo 8004;; tada) echo 8005;; *) echo "unknown engine: $1" >&2; exit 1;; esac; }

cmd_up() {
  local engine="$1"; local port; port=$(engine_port "$engine")
  local image="ghcr.io/${OWNER}/epub-to-audiobook-${engine}:latest"
  echo ">> selecting GPU offer (RTX 3090, fast net — GHCR pulls can stall on slow hosts)"
  local offer
  offer="${2:-$($VAST search offers "gpu_name=RTX_3090 num_gpus=1 disk_space>=45 reliability>0.99 inet_down>3000 rentable=true" --order dph --raw | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')}"
  echo ">> offer $offer — creating instance with $image"

  local iid
  iid=$($VAST create instance "$offer" --image "$image" --disk 45 --direct \
        --onstart-cmd "cd /app && uvicorn server:app --host 0.0.0.0 --port ${port}" \
        --raw | python3 -c 'import json,sys; print(json.load(sys.stdin)["new_contract"])')
  echo "$engine $iid" > "$STATE"
  echo ">> instance $iid; waiting for running + port mapping..."

  local ip="" pub=""
  for _ in $(seq 1 40); do
    read -r st ip pub < <($VAST show instances --raw | python3 -c "
import json,sys
d=[i for i in json.load(sys.stdin) if i['id']==$iid]
i=d[0] if d else {}
m=(i.get('ports') or {}).get('${port}/tcp') or []
print(i.get('actual_status',''), i.get('public_ipaddr',''), m[0]['HostPort'] if m else '')")
    [ "$st" = "running" ] && [ -n "$pub" ] && break
    sleep 15
  done
  [ -n "$pub" ] || { echo "!! instance never exposed port ${port} — run '$0 down'"; exit 1; }
  echo ">> endpoint http://$ip:$pub — waiting for engine health (first run downloads the model)"

  local h=""
  for _ in $(seq 1 60); do
    h=$(curl -sf -m 10 "http://$ip:$pub/health" 2>/dev/null || true)
    echo "$h" | grep -q '"status"' && break
    sleep 15
  done
  echo ">> health: $h"
  echo "$h" | grep -q '"cuda_available":true' || {
    echo "!! WARNING: engine reports NO CUDA — you are paying for a GPU but running on CPU."
    echo "   Investigate before converting (see GPU-PLAYBOOK.md)."
  }
  echo "$engine $iid $ip $pub" > "$STATE"

  local var; [ "$engine" = chatterbox ] && var=CHATTERBOX_URL || var=TADA_URL
  echo ""
  echo "==============================================================="
  echo " Engine ready:  ${var}=http://${ip}:${pub}/v1"
  echo " Batch WHOLE BOOKS (per-hour billing). When done:"
  echo "   scripts/vast-gpu.sh down"
  echo "==============================================================="
}

cmd_status() {
  [ -f "$STATE" ] && cat "$STATE" || echo "no active vast-gpu instance recorded"
  $VAST show instances | head -4
}

cmd_down() {
  if [ -f "$STATE" ]; then
    read -r _engine iid _rest < "$STATE"
    echo ">> destroying instance $iid"
    $VAST destroy instance "$iid" | tail -1
    rm -f "$STATE"
  fi
  echo ">> verify: instances remaining:"
  $VAST show instances --raw | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'
}

case "${1:-}" in
  up) cmd_up "${2:?engine (chatterbox|tada)}" "${3:-}";;
  status) cmd_status;;
  down) cmd_down;;
  *) echo "usage: $0 {up <chatterbox|tada> [offer_id] | status | down}"; exit 1;;
esac
