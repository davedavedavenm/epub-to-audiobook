# Kokoro GPU on Vast.ai — Playbook

## Buying a local GPU — the constraints, measured 2026-07-25

Recorded so this isn't re-researched from scratch. The question was whether a
cheap used card could replace the Kaggle/Vast round-trip. **The candidate host
is `pve2`, not zorin** — zorin is an Acer Veriton N4690GT, a ~1 L mini PC with
nowhere to put a card.

**pve2 (verified over SSH — note port 2222, not 22):**

| Fact | Value |
|---|---|
| Machine | Dell **OptiPlex 3000 Small Form Factor** (service tag 4SCB6Q3) |
| CPU | i5-12500, RAPL package limit **65 W** |
| Free slot | `SLOT2` PCIe **x16**, available — but **half-height only** |
| IOMMU | **Active, 11 groups** — passthrough prerequisite already met |
| RAM | 2× DIMM (full-size, so not the Micro), 1×8 GB fitted, 64 GB max |
| PSU | **Unknown** — Dell leaves SMBIOS type 39 blank (`Max Power Capacity: Unknown`), and the wattage sits behind a Dell login. Read the label. SFF shipped as 180 W or 300 W; with a 65 W CPU the 180 W is tight even for a 70 W card. |

**The SFF constraint is what bites.** Half-height means a low-profile card, and
low-profile carries a steep premium. UK used prices, same day:

| Card | VRAM | Used £ | Note |
|---|---|---|---|
| Tesla P4 | 8 GB | 96–125 | **Do not buy** — see below |
| RTX A1000 | 8 GB | 281–360 | Ampere, 50 W |
| MSI RTX 3050 LP | 6 GB | 208 | Safe pick; 70 W slot-powered |
| RTX A2000 | 6 GB | 281 | Same VRAM, more money |
| RTX A2000 | 12 GB | 570 | The "stop worrying" option |
| Tesla T4 | 16 GB | 455–950 | Literally what Kaggle lends free |

**Avoid Pascal (Tesla P4, and any GTX 10-series).** CUDA 13 removed Maxwell,
Pascal and Volta, and PyTorch is deleting those architectures from its CUDA
12.8+ builds. A P4 pins the stack to old wheels forever, and has no tensor
cores, so the fp16 path you'd need to fit a model into 8 GB runs badly.

**Before spending anything, measure.** Run this alongside the next Kaggle or
Vast render of TADA / CosyVoice:

```bash
nvidia-smi --query-gpu=memory.used --format=csv -l 5
```

Peak under ~5.5 GB means a 6 GB card genuinely works. Over it, and every option
below £280 is wasted money — which is also the answer #23 needs about why TADA
wants >10 GiB on CPU.

**Worth remembering why a card is attractive at all:** it isn't speed. A T4 has
320 GB/s against the 3050 6GB's 168 GB/s, so a cheap local card is *slower* than
the free Kaggle GPU. What it buys is **availability** — no weekly quota, no
`plan_batches()` session budgeting, no "kernel hit the cap and returned
nothing", no cancel-doesn't-stop-the-GPU. That complexity exists only because
the GPU is remote and rationed.

---

## Next-gen engines (Chatterbox / TADA) — one-command GPU runbook

**Do NOT pip-install engines on a bare instance** (the 2026-07-06 attempt wasted
~80 min + $ and failed on a dep conflict). Instead the engine images are built
ONCE in GitHub CI (`.github/workflows/build-engines.yml`) and pushed to GHCR;
Vast just pulls a ready image.

```bash
# rent a GPU, pull the pre-built engine image, run it, tunnel it to the worker:
scripts/vast-gpu.sh up chatterbox      # or: up tada
# -> prints the CHATTERBOX_URL/TADA_URL line to set, then:
#    docker compose up -d worker webapp
# batch a WHOLE book (or several) — never a single chapter — then:
scripts/vast-gpu.sh down               # DESTROYS the instance + kills the tunnel
```

Status: **runbook + CI written, not yet validated with a paid run.** First real
`up` will confirm the GHCR pull + tunnel path and finally MEASURE Turbo/TADA GPU
speed (currently unmeasured — see LOW-COST-TTS.md). Batch full books to amortize
the one-time model download.

---


## Overview

Run Kokoro TTS on a rented cloud GPU (RTX 3060, ~$0.05/hr) for **15x faster** audiobook conversion.
Same audio quality, same API, same voices — just faster.

**Cost Strategy:** 
- **Bulk/Standard Quality (Kokoro):** ~$0.01 per book | 11 books in one session = ~$0.18 total using RTX 3060.
- **High-Fidelity/Intent-Aware Quality:** Up to ~$1.00 - $3.00 per book. Willing to scale up to heavier GPUs (RTX 3090/4090 at ~$0.30+/hr) for next-gen models (like F5-TTS or advanced Kokoro variants) to achieve Amazon Polly Long-Form level intonation and prosody. Quality is the absolute priority over chasing zero cost for premium reads.

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
cd "$STACK_PATH"   # e.g. /home/dave/ai/lab/stacks/epub-to-audiobook

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
| Stack path | `$STACK_PATH` (e.g. `/home/dave/ai/lab/stacks/epub-to-audiobook`) on zorin |
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

## Future: High-Fidelity "Intent-Aware" Models

As per the v1.3 Roadmap, the goal is to achieve Amazon Polly Long-Form quality (superior prosody, emotional pacing, intent-awareness) using open-weight models.

When transitioning from standard Kokoro to next-gen models (e.g., F5-TTS, large param Kokoro variants):
- **VRAM Requirements:** RTX 3060 (12GB) will likely OOM. You must search for **RTX 3090 or RTX 4090** instances (24GB VRAM).
- **Concurrency:** Drop `MAX_CONCURRENT_JOBS` from 3 down to 1 to ensure the model has the full GPU.
- **Cost Expectation:** Hourly rates will jump from ~$0.05/hr to ~$0.30 - $0.50/hr. A 10-hour audiobook may cost $1.00 - $3.00. This is acceptable and expected to achieve absolute maximum vocal quality.
