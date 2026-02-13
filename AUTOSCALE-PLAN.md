# Auto-Scaling Plan: CPU ↔ GPU Kokoro

## Goal

When books are queued for conversion, automatically decide whether to use local CPU Kokoro
or spin up a Vast.ai GPU instance. Tear down the GPU when the queue is empty.
No manual SSH commands, no manual .env edits.

## Decision Logic

| Queued Books | Action | Rationale |
|-------------|--------|-----------|
| 1-2 | CPU only | ~3-5 hrs total, not worth $0.05/hr GPU rental + setup overhead |
| 3-5 | GPU (optional) | User can click "Use GPU" button in UI, or auto if enabled |
| 6+ | GPU (auto) | Clear win: 11 books = ~1.5 hrs GPU vs ~30+ hrs CPU |

**Cost threshold**: GPU setup + teardown overhead is ~5 minutes. At $0.05/hr, break-even is
roughly 3 books (GPU saves ~2 hrs wall time, costs ~$0.02 extra).

## Architecture

### Current Flow (manual)
```
User queues books → Worker picks from queue → Converts via CPU Kokoro (1 at a time)
```

### Target Flow (auto-scaling)
```
User queues books
    │
    ├─ Queue depth ≤ 2 → CPU mode (status quo)
    │
    └─ Queue depth ≥ AUTOSCALE_THRESHOLD (default: 3)
        │
        ├─ gpu_manager.scale_up()
        │   1. vast.py search offers (template-filtered)
        │   2. vast.py create instance --template <hash>
        │   3. Poll until instance is "running" (timeout: 5 min)
        │   4. Wait for Kokoro health check on instance (timeout: 2 min)
        │   5. Create SSH tunnel (0.0.0.0:8890 → instance:8880)
        │   6. Verify tunnel works (curl localhost:8890/v1/audio/voices)
        │   7. Update KOKORO_URL in running app config (no .env write needed)
        │   8. Set MAX_CONCURRENT_JOBS=3
        │   9. Log: "GPU active, instance <ID>, cost $X.XX/hr"
        │
        ├─ Worker runs jobs at 3x concurrency via GPU
        │
        └─ When queue empty + all jobs completed:
            └─ gpu_manager.scale_down()
                1. Switch KOKORO_URL back to CPU
                2. Set MAX_CONCURRENT_JOBS=1
                3. Kill SSH tunnel
                4. vast.py destroy instance <ID>
                5. Log: "GPU torn down, session cost: $X.XX"
```

## Implementation Plan

### Phase 1: GPU Manager Module (`webapp/gpu_manager.py`)

New module that encapsulates all Vast.ai + tunnel logic. Runs inside the worker container.

```python
# Key state:
#   gpu_state = "idle" | "provisioning" | "active" | "tearing_down" | "error"
#   instance_id = None | "12345"
#   tunnel_pid = None | 67890
#   session_start = None | datetime
#   session_cost = 0.0

class GPUManager:
    def __init__(self):
        self.state = "idle"
        self.instance_id = None
        self.tunnel_pid = None
        self.cost_per_hour = 0.0
        self.session_start = None

    def scale_up(self) -> bool:
        """Provision GPU, create tunnel, verify Kokoro. Returns True on success."""
        # 1. Search for cheapest matching offer
        # 2. Create instance from template
        # 3. Poll for "running" status
        # 4. Wait for Kokoro health
        # 5. Create SSH tunnel
        # 6. Verify tunnel
        # 7. Update app config (in-memory, NOT .env file)

    def scale_down(self) -> bool:
        """Tear down GPU, kill tunnel, restore CPU config."""
        # 1. Restore CPU config
        # 2. Kill tunnel
        # 3. Destroy instance
        # 4. Log session cost

    def health_check(self) -> bool:
        """Verify GPU Kokoro is responding via tunnel."""

    def get_status(self) -> dict:
        """Return current GPU state for UI display."""

    def session_cost(self) -> float:
        """Calculate running cost based on elapsed time."""
```

**Key design decisions:**
- All Vast.ai CLI calls go through `subprocess.run(['python3', '/tmp/vast.py', ...])`
  since we can't pip install the vastai package
- SSH tunnel uses `subprocess.Popen` with `nohup` equivalent
- Config changes are IN-MEMORY only (modify the global `KOKORO_URL` variable and
  `MAX_CONCURRENT_JOBS`). No .env file writes = no container restart needed
- The module needs access to the Vast.ai API key and SSH key, mounted as volumes

### Phase 2: Worker Integration

Modify `worker.py` to check queue depth and trigger scaling:

```python
def main():
    gpu = GPUManager()
    while True:
        if not is_queue_paused():
            queued = count_queued_jobs()
            running = running_job_count()

            # Scale up: queue is deep enough and GPU not already active
            if queued >= AUTOSCALE_THRESHOLD and gpu.state == "idle":
                gpu.scale_up()

            # Scale down: nothing left to do
            if queued == 0 and running == 0 and gpu.state == "active":
                gpu.scale_down()

            # Fill job slots
            while maybe_start_next_queued_job():
                pass

        # Health check GPU if active
        if gpu.state == "active":
            if not gpu.health_check():
                gpu.handle_failure()  # retry tunnel, or tear down

        time.sleep(10)
```

### Phase 3: UI Integration

Add GPU status to the webapp UI:

1. **Status indicator**: Show GPU state in the header/sidebar
   - 🟢 "GPU Active (RTX 3060, $0.05/hr, running 12 min, ~$0.01)"
   - 🔵 "GPU Provisioning..."
   - ⚫ "CPU Only"

2. **Manual controls** (Settings page):
   - "Force GPU" button — scale up regardless of queue depth
   - "Force CPU" button — tear down GPU even if jobs queued
   - Autoscale threshold slider (default: 3)
   - Cost cap setting (max $/session, default: $1.00)

3. **API endpoints**:
   - `GET /api/gpu/status` — current state, cost, instance info
   - `POST /api/gpu/scale-up` — manual trigger
   - `POST /api/gpu/scale-down` — manual teardown
   - `PUT /api/gpu/settings` — threshold, cost cap, enable/disable

### Phase 4: Docker/Volume Changes

The worker container needs additional mounts for Vast.ai access:

```yaml
worker:
  volumes:
    # ... existing mounts ...
    # Vast.ai CLI (downloaded to host)
    - /tmp/vast.py:/tmp/vast.py:ro
    # Vast.ai API key
    - ${HOME}/.config/vastai:/root/.config/vastai:ro
    # SSH key for Vast.ai instances
    - ${HOME}/.ssh/vastai_ed25519:/root/.ssh/vastai_ed25519:ro
  environment:
    # Auto-scaling settings
    - AUTOSCALE_ENABLED=${AUTOSCALE_ENABLED:-false}
    - AUTOSCALE_THRESHOLD=${AUTOSCALE_THRESHOLD:-3}
    - AUTOSCALE_COST_CAP=${AUTOSCALE_COST_CAP:-1.00}
    - VASTAI_TEMPLATE_HASH=e2588a22cf5eef43df3d444ef4f25705
    - GPU_KOKORO_URL=http://172.19.0.1:8890/v1
    - DOCKER_GATEWAY_IP=172.19.0.1
```

**Note:** The tunnel runs on the HOST (zorin), not inside a container.
The worker container needs to execute `ssh` on the host via `docker.sock` or a helper script.

### SSH Tunnel Problem

**This is the trickiest part.** The SSH tunnel must run on the zorin HOST, not inside
the worker container, because containers reach the tunnel via the Docker gateway IP
(172.19.0.1). Options:

**Option A: Host helper script (Recommended)**
- Place a `gpu-tunnel.sh` on zorin at `/home/dave/ai/lab/stacks/epub-to-audiobook/scripts/`
- Worker calls it via `docker exec` on the host (using docker.sock) or via SSH to localhost
- Script handles: create tunnel, kill tunnel, health check
- Pro: Simple, proven pattern (we did this manually already)
- Con: Needs SSH key for localhost OR docker exec trick

**Option B: Worker runs SSH directly**
- Mount SSH key into worker container
- Worker creates tunnel with `-L 0.0.0.0:8890:localhost:8880`
- Pro: Self-contained
- Con: Container networking makes this awkward — the tunnel endpoint
  needs to be reachable from OTHER containers via gateway IP

**Option C: Worker uses Vast.ai direct port**
- Skip SSH tunnel entirely
- Use Vast.ai "direct port" feature (maps instance port to public URL)
- Pro: No tunnel management
- Con: Public internet latency, requires open port, security concern

**Recommendation: Option A** — a host-side helper script called via `docker.sock`.
The worker already has docker.sock mounted and uses it to launch converter containers.
Pattern: `docker run --rm --network host -v ssh_keys:/keys alpine ssh -i /keys/vastai_ed25519 ...`

### Phase 5: Safety & Guardrails

1. **Cost cap**: Hard limit on session spend. Default $1.00. GPU auto-tears-down when hit.
2. **Idle timeout**: If GPU is active but no jobs for 10 minutes, tear down.
3. **Provision timeout**: If instance isn't ready in 5 minutes, abort and fall back to CPU.
4. **Tunnel watchdog**: Every 30s, verify tunnel is alive. Auto-recreate if dead.
5. **Graceful degradation**: If GPU fails mid-conversion, jobs continue on CPU Kokoro.
   The converter just talks to KOKORO_URL — if we switch it back to CPU, new chunks
   go to CPU. In-progress chapters may fail and get retried (recovery mode handles this).
6. **Notification**: Telegram alert when GPU spins up/down with cost summary.

## File Changes Summary

| File | Change |
|------|--------|
| `webapp/gpu_manager.py` | **NEW** — GPU lifecycle management |
| `webapp/worker.py` | Add auto-scale checks to main loop |
| `webapp/app.py` | Add GPU API endpoints, make KOKORO_URL/MAX_CONCURRENT_JOBS mutable |
| `docker-compose.yml` | Add volume mounts for Vast.ai keys, new env vars |
| `scripts/gpu-tunnel.sh` | **NEW** — Host-side tunnel management script |
| `webapp/templates/*.html` | GPU status indicator and controls in UI |
| `.env.example` | Document auto-scale env vars |

## Milestones

1. **M1: gpu_manager.py** — Core scale_up/scale_down working from CLI
   - Test: manually call `gpu_manager.scale_up()`, verify Kokoro responds, tear down
2. **M2: Worker integration** — Auto-scaling triggers from queue depth
   - Test: queue 4 books, watch GPU spin up, convert, tear down
3. **M3: UI** — Status display and manual controls
   - Test: see GPU status in header, use Force GPU/CPU buttons
4. **M4: Safety** — Cost cap, idle timeout, tunnel watchdog, notifications
   - Test: set $0.10 cap, verify teardown when hit

## Open Questions

1. Should the threshold be configurable per-queue or global?
   → **Global** (one GPU instance serves all jobs)

2. What if Vast.ai has no available instances matching our filters?
   → Fall back to CPU, retry search every 5 minutes, notify user

3. Should we support multiple GPU instances for very large queues (20+ books)?
   → **No** for v1. One GPU instance with 3 concurrent jobs is sufficient.
   One RTX 3060 at 3 concurrent jobs can do ~20 books/hour.

4. What about the KOKORO_URL being an env var read at import time?
   → Need to make it mutable. Currently `KOKORO_URL = os.environ.get(...)` at line 34
   of app.py. Change to a function `get_kokoro_url()` that checks a mutable global,
   or use `app.config['KOKORO_URL']` which can be updated at runtime.
