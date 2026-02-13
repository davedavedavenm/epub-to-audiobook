# Kokoro GPU on Vast.ai — Playbook

## Overview

Run Kokoro TTS on a rented cloud GPU (RTX 3060, ~$0.05/hr) for **15x faster** audiobook conversion.
Same audio quality, same API, same voices — just faster.

**Cost:** ~$0.01 per book | 11 books in one session = ~$0.18 total

## Prerequisites

- Vast.ai account with credit (https://vast.ai)
- Vast.ai CLI on zorin: `curl -s https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py -o /tmp/vast.py`
  - No pip on zorin; use `python3 /tmp/vast.py` for all vastai commands
- API key saved: `python3 /tmp/vast.py set api-key <YOUR_KEY>`
  - Stored at `~/.config/vastai/vast_api_key` on zorin
- SSH key at `~/.ssh/vastai_ed25519` on zorin
- SSH public key uploaded to Vast.ai dashboard (Account > SSH Keys)

## Template

**Template ID:** 343755
**Template hash:** `e2588a22cf5eef43df3d444ef4f25705`

The template includes:
- Image: `ghcr.io/remsky/kokoro-fastapi-gpu:latest`
- **Auto-restart watchdog** via `onstart` script — if Kokoro crashes, it restarts in 5 seconds
- SSH + direct ports enabled
- 20GB disk
- Pre-filtered search: RTX 3060, 1 GPU, ≤$0.06/hr, reliability >95%, fast internet

**ALWAYS use this template** when creating instances. It eliminates the #1 failure mode
(Kokoro crashing and needing manual restart).

## Quick Start

### 1. Spin up GPU instance FROM THE TEMPLATE

```bash
# On zorin — ALWAYS use the template:
python3 /tmp/vast.py create instance <OFFER_ID> --template e2588a22cf5eef43df3d444ef4f25705

# To browse matching offers first (template pre-filters, but you can also search):
python3 /tmp/vast.py search offers "gpu_name=RTX_3060 num_gpus=1 dph<=0.06 reliability>0.95 inet_down>500" --order dph
# Pick an offer ID from the list, then use the create command above
```

> **DO NOT** use `--image` directly. Always use `--template` so you get the onstart
> watchdog, SSH, and correct settings. Skipping the template is how you get crashes
> that need manual intervention.

### 2. Wait for it, get SSH info

```bash
# Check status (wait for "running"):
python3 /tmp/vast.py show instances
# Look for SSH Addr and SSH Port columns

# Verify Kokoro is running (onstart auto-starts it with watchdog):
ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no root@<SSH_ADDR> \
  "curl -s http://localhost:8880/v1/audio/voices | head -3"
```

If Kokoro isn't responding yet, give it 30-60 seconds — the onstart script launches it
in a watchdog loop that auto-restarts on crash. Check `/tmp/kokoro.log` on the instance.

### 3. Create SSH tunnel from zorin to GPU

```bash
# IMPORTANT: Use nohup, NOT -f (which fails through nested SSH)
# IMPORTANT: Bind 0.0.0.0 so Docker containers can reach it via gateway IP
nohup ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no \
  -L 0.0.0.0:8890:localhost:8880 -N root@<SSH_ADDR> > /tmp/vast-tunnel.log 2>&1 &

# Test from zorin:
curl -s http://localhost:8890/v1/audio/voices | head -3
```

### 4. Point your stack at the GPU

```bash
cd /home/dave/ai/lab/stacks/epub-to-audiobook

# Set GPU mode in .env:
#   KOKORO_URL=http://172.19.0.1:8890/v1
#   MAX_CONCURRENT_JOBS=3

# Restart services (no rebuild needed if only .env changed):
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
  -d '{"path": "/mnt/openbooks/My_Book.epub", "voice": "bm_fable"}'

# Queue ALL unconverted books:
for epub in /mnt/openbooks/*.epub; do
  curl -s -X POST http://localhost:8881/api/library/convert \
    -H "Content-Type: application/json" \
    -d "{\"path\": \"$epub\", \"voice\": \"bm_fable\"}"
  echo ""
done
```

With `MAX_CONCURRENT_JOBS=3`, the worker will run up to 3 books simultaneously.

### 6. Monitor progress

```bash
curl -s http://localhost:8881/api/jobs | python3 -c '
import json, sys
jobs = json.load(sys.stdin)
for j in jobs:
    s = j["status"]
    if s in ("queued", "converting", "recovering"):
        ch = j.get("current_chapter", "?")
        total = j.get("total_chapters", "?")
        print(f"{j[\"id\"][:8]}  {s:12s}  ch {ch}/{total}  {j[\"book_name\"][:50]}")
    elif s == "completed":
        sync = j.get("sync_status", "?")
        print(f"{j[\"id\"][:8]}  {s:12s}  sync={sync:6s}  {j[\"book_name\"][:50]}")
'
```

### 7. Shut down when done

```bash
# 1. Switch back to CPU Kokoro in .env:
#    KOKORO_URL=http://kokoro-tts:8880/v1   (or remove the line entirely)
#    MAX_CONCURRENT_JOBS=1                   (CPU has memory leak, can only do 1)
docker compose up -d worker webapp

# 2. Destroy the GPU instance:
python3 /tmp/vast.py destroy instance <INSTANCE_ID>

# 3. Kill the SSH tunnel:
pkill -f "ssh.*8890"
```

## Concurrent Jobs

The worker supports `MAX_CONCURRENT_JOBS` env var:
- **CPU mode:** Keep at 1 (Kokoro CPU leaks ~1GB/chapter, would OOM with multiple jobs)
- **GPU mode:** Set to 2-3 (GPU has 12GB VRAM, handles concurrent requests well)

The worker loop fills all available slots each cycle. Each job runs in its own
Docker container (`audiobook-<job_id>`) which calls Kokoro via `OPENAI_BASE_URL`.

## Cost Estimation

| Book Length | Chapters | CPU Time | GPU Time | GPU Cost |
|-------------|----------|----------|----------|----------|
| Short (3h audio) | ~10 | ~1.5h | ~6 min | $0.006 |
| Medium (7h audio) | ~20 | ~3h | ~12 min | $0.012 |
| Long (13h audio) | ~40 | ~5.5h | ~22 min | $0.022 |

**Batch strategy:** Spin up once, convert ALL queued books, shut down.
11 books in one session = ~3.5 hours GPU time = ~$0.18 total.
With 3 concurrent jobs: ~1-1.5 hours wall time.

## Key Details

| Item | Value |
|------|-------|
| Template ID | 343755 |
| Template hash | `e2588a22cf5eef43df3d444ef4f25705` |
| Docker gateway IP | `172.19.0.1` |
| Vast.ai API key | `~/.config/vastai/vast_api_key` on zorin |
| SSH key | `~/.ssh/vastai_ed25519` on zorin |
| Vastai CLI | `python3 /tmp/vast.py` (no pip on zorin) |
| Stack path | `/home/dave/ai/lab/stacks/epub-to-audiobook/` on zorin |
| EPUB library | `/mnt/openbooks/` on zorin |
| ABS audiobooks | `/opt/stacks/audiobookshelf/audiobooks/` on docker-vm |
| Kokoro port (GPU) | 8880 (on instance), tunneled to 8890 (on zorin) |
| Kokoro port (CPU) | 8880 (via kokoro-tts container) |

## Troubleshooting

**Kokoro not responding after instance start:**
The onstart watchdog takes 20-60 seconds to boot Kokoro. Check `/tmp/kokoro.log` on the instance.
If it's been >2 minutes, SSH in and check: `ps aux | grep uvicorn`

**Kokoro crashed:**
With the template's onstart watchdog, it auto-restarts in 5 seconds. Check `/tmp/kokoro.log`
for `KOKORO_RESTART` entries. If you created the instance WITHOUT the template, there's
no auto-restart — you'll need to manually run the entrypoint or destroy and recreate
from the template.

**Tunnel drops:**
```bash
# Kill stale tunnel (be specific to avoid killing your main SSH session!)
pkill -f "ssh.*8890.*8880"
# Recreate:
nohup ssh -i ~/.ssh/vastai_ed25519 -p <PORT> -o StrictHostKeyChecking=no \
  -L 0.0.0.0:8890:localhost:8880 -N root@<ADDR> > /tmp/vast-tunnel.log 2>&1 &
```

**Converter hitting CPU Kokoro instead of GPU:**
The converter container gets `OPENAI_BASE_URL` from the webapp. Make sure `KOKORO_URL`
in `.env` points to `http://172.19.0.1:8890/v1` and services were restarted.

**Container name conflict ("already in use"):**
```bash
docker rm -f audiobook-<JOB_ID>
# Then requeue the book
```

**Instance disappeared:** Vast.ai preemptible instances can be reclaimed. Just spin up a new one from the template.

**Can't install vastai CLI:** apt is broken on zorin. Download directly:
`curl -s https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py -o /tmp/vast.py`

**SSH tunnel -f flag fails:** Through nested SSH, `-f` doesn't work. Use `nohup ... &` instead.

## Lessons Learned (Feb 2026)

1. **Always use the template.** Without the onstart watchdog, Kokoro crashes after ~3 hours and needs manual restart. The template's infinite loop fixes this.
2. **SSH tunnel is the weakest link.** If Kokoro seems dead but `curl` works via direct SSH, the tunnel is stale — not Kokoro.
3. **pkill patterns matter.** `pkill -f "ssh.*37840"` will kill your own SSH session. Use `pkill -f "ssh.*8890.*8880"` to target only the tunnel.
4. **MAX_CONCURRENT_JOBS=3** is the sweet spot for RTX 3060. More than that doesn't improve throughput.
5. **Recovery mode works.** If a converter container dies mid-book, the webapp detects missing chapters and retries them one at a time. Let it work.
6. **Some EPUBs have problematic chapters** that crash the converter. If a book fails repeatedly at the same chapter, the EPUB content may need cleaning.
