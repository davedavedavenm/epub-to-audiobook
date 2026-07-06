#!/usr/bin/env bash
# One-command Vast.ai GPU runbook for the Chatterbox / TADA engines.
#
# Uses the PRE-BUILT engine image from GHCR (built by
# .github/workflows/build-engines.yml) — the Vast instance PULLS a ready image
# in seconds instead of pip-installing for ~80 min. This is the lesson from the
# failed 2026-07-06 ad-hoc benchmark (see LOW-COST-TTS.md).
#
# Usage:
#   scripts/vast-gpu.sh up chatterbox      # rent a GPU, run the engine, tunnel it
#   scripts/vast-gpu.sh up tada
#   scripts/vast-gpu.sh status
#   scripts/vast-gpu.sh down               # DESTROY the instance + kill tunnel
#
# After `up`, point the stack at the GPU engine:
#   CHATTERBOX_URL=http://172.19.0.1:<port>/v1   (or TADA_URL)   then restart worker.
# `up` prints the exact line.
#
# Requirements (on the host that runs this — normally zorin):
#   - vast.py + API key (see GPU-PLAYBOOK.md)
#   - SSH key ~/.ssh/vastai_ed25519 registered on the Vast account
#   - the engine image must be public on GHCR (CI builds it on push to master)
set -euo pipefail

OWNER="${GHCR_OWNER:-davedavedavenm}"
VAST="${VASTAI_CLI:-python3 /tmp/vast.py}"
SSH_KEY="${VASTAI_SSH_KEY:-$HOME/.ssh/vastai_ed25519}"
GW="${DOCKER_GATEWAY_IP:-172.19.0.1}"
STATE="/tmp/vast-gpu-state"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=25 -o ServerAliveInterval=15"

engine_port() { case "$1" in chatterbox) echo 8004;; tada) echo 8005;; *) echo "unknown engine: $1" >&2; exit 1;; esac; }
tunnel_port() { case "$1" in chatterbox) echo 8894;; tada) echo 8895;; esac; }   # host-side port (avoid Kokoro's 8890)

cmd_up() {
  local engine="$1"; local port; port=$(engine_port "$engine")
  local image="ghcr.io/${OWNER}/epub-to-audiobook-${engine}:latest"
  echo ">> renting a GPU for $engine ($image)"

  local offer
  offer="${2:-$($VAST search offers "gpu_name in [RTX_3060,RTX_3090] num_gpus=1 disk_space>=45 reliability>0.98 rentable=true" --order dph --raw 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')}"
  echo ">> offer $offer"

  # Run the engine image directly as the instance image; GPU + HF cache volume; expose the port.
  local iid
  iid=$($VAST create instance "$offer" --image "$image" --disk 45 --ssh --direct \
        --env "-p ${port}:${port}" --raw 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["new_contract"])')
  echo "$engine $iid $port" > "$STATE"
  echo ">> instance $iid created; waiting for SSH..."

  local host p
  for _ in $(seq 1 40); do
    read -r host p < <($VAST show instances --raw 2>/dev/null | python3 -c "import json,sys;
d=[i for i in json.load(sys.stdin) if i['id']==$iid]
print(d[0].get('ssh_host',''), d[0].get('ssh_port','')) if d and d[0].get('actual_status')=='running' else print('', '')")
    [ -n "$host" ] && ssh $SSH_OPTS -p "$p" "root@$host" true 2>/dev/null && break
    sleep 15
  done
  echo ">> instance up at $host:$p; waiting for engine health (model download on first run)..."

  # The image's CMD already starts the server. Wait for /health, then warm the model.
  for _ in $(seq 1 40); do
    ssh $SSH_OPTS -p "$p" "root@$host" "curl -sf http://localhost:${port}/health" 2>/dev/null | grep -q '"status"' && break
    sleep 15
  done

  # Reverse tunnel: expose the instance's engine port on the deploy host so the
  # worker's converter containers can reach it at $GW:<tunnel_port>.
  local tport; tport=$(tunnel_port "$engine")
  pkill -f "ssh.*:${tport}:localhost:${port}" 2>/dev/null || true
  nohup ssh $SSH_OPTS -p "$p" -L "0.0.0.0:${tport}:localhost:${port}" -N "root@$host" > "/tmp/vast-tunnel-${engine}.log" 2>&1 &
  echo "$engine $iid $port $host $p $tport" > "$STATE"

  local var; [ "$engine" = chatterbox ] && var=CHATTERBOX_URL || var=TADA_URL
  echo ""
  echo "==============================================================="
  echo " GPU engine ready. Point the stack at it and restart the worker:"
  echo "   ${var}=http://${GW}:${tport}/v1"
  echo "   docker compose up -d worker webapp"
  echo " When done:  scripts/vast-gpu.sh down"
  echo "==============================================================="
}

cmd_status() {
  [ -f "$STATE" ] && cat "$STATE" || echo "no active vast-gpu instance"
  $VAST show instances 2>/dev/null | head -3
}

cmd_down() {
  [ -f "$STATE" ] || { echo "no state file; nothing to destroy"; exit 0; }
  read -r engine iid _ < "$STATE"
  echo ">> killing tunnel + destroying instance $iid"
  pkill -f "ssh.*localhost:" 2>/dev/null || true
  $VAST destroy instance "$iid" 2>&1 | tail -1
  rm -f "$STATE"
  echo ">> remember to point ${engine^^}_URL back to the local service and restart the worker."
}

case "${1:-}" in
  up) cmd_up "${2:?engine (chatterbox|tada)}" "${3:-}";;
  status) cmd_status;;
  down) cmd_down;;
  *) echo "usage: $0 {up <chatterbox|tada> [offer_id] | status | down}"; exit 1;;
esac
