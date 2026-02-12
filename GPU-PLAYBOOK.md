# Kokoro GPU on Vast.ai — Playbook

## Overview

Run Kokoro TTS on a cloud GPU (RTX 3060, $0.05-0.06/hr) for 15x faster conversion.
Same audio quality, same API, same voices — just faster.

**Cost:** ~$0.01 per book (12-15 min per book at $0.06/hr)

## Prerequisites

- Vast.ai account with credit (https://vast.ai)
- Vast.ai CLI: `pip install vastai`
- API key saved: `vastai set api-key <YOUR_KEY>`
- SSH key uploaded to Vast.ai dashboard (Keys > SSH Keys)
- SSH key at `~/.ssh/vastai_ed25519` (copy also in OneDrive/.ssh/)

## Quick Start (3 commands)

### 1. Spin up GPU instance

```bash
vastai search offers "gpu_name=RTX_3060 num_gpus=1 dph<=0.06 reliability>0.95 inet_down>500" --order dph
# Pick an offer ID from the list, then:
vastai create instance <OFFER_ID> --image "ghcr.io/remsky/kokoro-fastapi-gpu:latest" --disk 20 --direct
```

Note the instance ID from the output.

### 2. Wait for it to come up, then start Kokoro

```bash
# Check status (wait for "running")
vastai show instance <INSTANCE_ID>

# Get SSH details
# SSH Addr and SSH Port columns tell you the connection info

# SSH in and start Kokoro (Vast.ai overrides the entrypoint)
ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no root@<SSH_ADDR> \
  "cd /app && DEVICE=gpu nohup bash entrypoint.sh > /tmp/kokoro.log 2>&1 &"

# Wait ~30s for model warmup, then verify
ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> root@<SSH_ADDR> \
  "curl -s http://localhost:8880/v1/audio/voices | python3 -m json.tool | head -5"
```

### 3. Create SSH tunnel from Zorin to GPU

```bash
# On Zorin (or from your machine to Zorin):
ssh -i ~/.ssh/vastai_ed25519 -p <SSH_PORT> -o StrictHostKeyChecking=no \
  -L 8890:localhost:8880 -N root@<SSH_ADDR> &

# Test from Zorin:
curl -s http://localhost:8890/v1/audio/voices
```

### 4. Point your webapp at the GPU

Set `KOKORO_URL=http://localhost:8890/v1` in docker-compose.yml or .env, then restart webapp+worker.

Or for a one-off: update the KOKORO_URL env var in the running containers.

### 5. Convert your books

Queue books via the webapp as normal. They'll use the GPU Kokoro automatically.

### 6. Shut down when done

```bash
vastai destroy instance <INSTANCE_ID>
# Also kill the SSH tunnel on Zorin:
pkill -f "ssh.*8890.*vast"
```

## Cost Estimation

| Book Length | Chapters | CPU Time | GPU Time | GPU Cost |
|-------------|----------|----------|----------|----------|
| Short (3h audio) | ~10 | ~1.5h | ~6 min | $0.006 |
| Medium (7h audio) | ~20 | ~3h | ~12 min | $0.012 |
| Long (13h audio) | ~40 | ~5.5h | ~22 min | $0.022 |

**Batch strategy:** Spin up once, convert ALL queued books, shut down.
10 books in one session = ~2 hours GPU time = ~$0.12 total.

## Vast.ai Account Details

- Account: david@davi... (Individual)
- API key location: `~/.config/vastai/vast_api_key`
- SSH key: `~/.ssh/vastai_ed25519` (also in OneDrive/.ssh/)
- Credit: $5.00 (as of 2026-02-12) = ~80 hours of GPU time

## Troubleshooting

**Kokoro not starting:** SSH in and check `/tmp/kokoro.log`. May need `DEVICE=gpu` env var.

**Tunnel drops:** Re-run the SSH tunnel command. Consider `autossh` for auto-reconnect.

**Instance disappeared:** Vast.ai preemptible instances can be reclaimed. Just spin up a new one.

**Memory leak on GPU:** Unknown if GPU version has the same leak. If it does, Kokoro will crash after ~12 chapters but the recovery system will handle it (restart + retry missing chapters).
