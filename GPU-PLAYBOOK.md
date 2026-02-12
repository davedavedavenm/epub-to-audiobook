# Kokoro GPU on Vast.ai — Playbook

## Overview

Run Kokoro TTS on a cloud GPU (RTX 3060, $0.05-0.06/hr) for 15x faster conversion.
Same audio quality, same API, same voices — just faster.

**Cost:** ~$0.01 per book (12-15 min per book at $0.06/hr)

## Prerequisites

- Vast.ai account with credit (https://vast.ai)
- Vast.ai CLI on zorin: `curl -s https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py -o /tmp/vast.py`
  - No pip on zorin; use `python3 /tmp/vast.py` for all vastai commands
- API key saved: `python3 /tmp/vast.py set api-key <YOUR_KEY>`
  - Stored at `~/.config/vastai/vast_api_key` on zorin
- SSH key at `~/.ssh/vastai_ed25519` on zorin
- SSH public key uploaded to Vast.ai dashboard (Account > SSH Keys)

## Quick Start

### 1. Spin up GPU instance

```bash
# On zorin:
python3 /tmp/vast.py search offers "gpu_name=RTX_3060 num_gpus=1 dph<=0.06 reliability>0.95 inet_down>500" --order dph
# Pick an offer ID from the list, then:
python3 /tmp/vast.py create instance <OFFER_ID> --image "ghcr.io/remsky/kokoro-fastapi-gpu:latest" --disk 20 --direct
```

Note the instance ID from the output.

### 2. Wait for it, get SSH info

```bash
# Check status (wait for "running")
python3 /tmp/vast.py show instances
# Look for SSH Addr and SSH Port columns

# Verify Kokoro is running (it auto-starts with this image)
ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no root@<SSH_ADDR> \
  "curl -s http://localhost:8880/v1/audio/voices | head -5"
```

### 3. Create SSH tunnel from zorin to GPU

```bash
# IMPORTANT: Use nohup, not -f (which fails through nested SSH)
# IMPORTANT: Bind 0.0.0.0 so Docker containers can reach it via gateway IP
nohup ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no \
  -L 0.0.0.0:8890:localhost:8880 -N root@<SSH_ADDR> &

# Test from zorin:
curl -s http://localhost:8890/v1/audio/voices
```

### 4. Point your stack at the GPU

The docker-compose.yml now supports `KOKORO_URL` as an env var (defaults to CPU).

```bash
cd /home/dave/ai/lab/stacks/epub-to-audiobook

# Option A: Edit .env (persists across restarts)
echo 'KOKORO_URL=http://172.19.0.1:8890/v1' >> .env

# Option B: Edit docker-compose.yml directly
# Change KOKORO_URL lines to: http://172.19.0.1:8890/v1

# Also set concurrent jobs for GPU (default is 1):
echo 'MAX_CONCURRENT_JOBS=3' >> .env

# Rebuild and restart
docker compose build worker webapp
docker compose up -d worker webapp

# Verify the worker sees the GPU URL:
docker exec epub-to-audiobook-worker env | grep KOKORO
```

**Important:** `172.19.0.1` is the Docker gateway IP — this is how containers
reach the SSH tunnel running on the host. Verify with:
`docker network inspect epub-to-audiobook_default | grep Gateway`

### 5. Queue books

```bash
# Queue a single book:
curl -X POST http://localhost:8881/api/library/convert \
  -H "Content-Type: application/json" \
  -d '{"path": "/mnt/openbooks/My_Book.epub", "voice": "bm_fable", "notify_telegram": true}'

# Queue all books (bash loop):
for epub in /mnt/openbooks/*.epub; do
  curl -s -X POST http://localhost:8881/api/library/convert \
    -H "Content-Type: application/json" \
    -d "{\"path\": \"$epub\", \"voice\": \"bm_fable\", \"notify_telegram\": true}"
  echo ""
done
```

With `MAX_CONCURRENT_JOBS=3`, the worker will run up to 3 books simultaneously.

### 6. Monitor progress

```bash
# Check all active/queued jobs:
curl -s http://localhost:8881/api/jobs | python3 -c '
import json, sys
jobs = json.load(sys.stdin)
for j in jobs:
    if j["status"] in ("queued", "converting"):
        print(f"{j[\"id\"]} {j[\"status\"]:12s} {j.get(\"progress_percent\",0):3d}% {j[\"book_name\"][:50]}")
'
```

### 7. Shut down when done

```bash
# Switch back to CPU Kokoro:
# Edit docker-compose.yml: change KOKORO_URL back to http://kokoro-tts:8880/v1
# Or remove KOKORO_URL from .env
# Set MAX_CONCURRENT_JOBS=1 (CPU can only handle one at a time due to memory leak)
docker compose up -d worker webapp

# Destroy the GPU instance:
python3 /tmp/vast.py destroy instance <INSTANCE_ID>

# Kill the SSH tunnel:
pkill -f "ssh.*8890"
```

## Concurrent Jobs

The worker supports `MAX_CONCURRENT_JOBS` env var:
- **CPU mode:** Keep at 1 (Kokoro CPU leaks ~1GB/chapter, would OOM with multiple jobs)
- **GPU mode:** Set to 2-3 (GPU Kokoro has 12GB VRAM, 62GB RAM on typical instance)

The worker loop fills all available slots each cycle. Each job runs in its own
Docker container (`audiobook-<job_id>`) which calls Kokoro via `OPENAI_BASE_URL`.

## Cost Estimation

| Book Length | Chapters | CPU Time | GPU Time | GPU Cost |
|-------------|----------|----------|----------|----------|
| Short (3h audio) | ~10 | ~1.5h | ~6 min | $0.006 |
| Medium (7h audio) | ~20 | ~3h | ~12 min | $0.012 |
| Long (13h audio) | ~40 | ~5.5h | ~22 min | $0.022 |

**Batch strategy:** Spin up once, convert ALL queued books, shut down.
10 books in one session = ~2 hours GPU time = ~$0.12 total.
With 3 concurrent jobs: ~40 min total.

## Key Details

- **Docker gateway IP:** `172.19.0.1` (containers use this to reach host tunnel)
- **Vast.ai API key:** `~/.config/vastai/vast_api_key` on zorin
- **SSH key:** `~/.ssh/vastai_ed25519` on zorin
- **Vastai CLI:** `python3 /tmp/vast.py` (no pip on zorin)
- **Stack path:** `/home/dave/ai/lab/stacks/epub-to-audiobook/` on zorin
- **EPUB library:** `/mnt/openbooks/` on zorin
- **ABS audiobooks:** `/opt/stacks/audiobookshelf/audiobooks/` on docker-vm

## Troubleshooting

**Kokoro not starting:** SSH in and check `docker logs` or `/tmp/kokoro.log`.

**Tunnel drops:** Re-run the nohup SSH command. Consider `autossh` for auto-reconnect.

**Instance disappeared:** Vast.ai preemptible instances can be reclaimed. Just spin up a new one.

**Converter hitting CPU Kokoro instead of GPU:** The converter container gets
`OPENAI_BASE_URL` from the webapp code. Make sure `KOKORO_URL` env var is set
correctly in docker-compose.yml and containers are rebuilt/restarted.

**Can't install vastai CLI:** apt is broken on zorin. Use `python3 /tmp/vast.py` instead.

**SSH tunnel -f flag fails:** Through nested SSH, `-f` doesn't work. Use `nohup ... &` instead.
