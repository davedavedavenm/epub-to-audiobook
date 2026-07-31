# Operations Runbook & Incident Log

How the system behaves under failure, what the states mean, how to respond,
and the honest record of incidents found during hardening. **This file is the
documented plan — if it isn't written here or in PLAN.md, it doesn't count.**

## 2026-07-26 — Revoked Evolution notification key repaired

The active Zorin webapp and worker inherited an older revoked global key from the deployed `.env`,
so optional WhatsApp notification attempts authenticated as `401`. The env was backed up and
updated, both consumers were recreated and became healthy, and the exact wanted-monitor test path
logged `WhatsApp notify ok`. Evolution server logs contained the labelled message with no new auth
error. Restore the adjacent timestamped `.env` backup and recreate only `webapp`/`worker` to roll
back. This incident did not touch conversion state or generated media.

## Job states and what they actually mean

| State | Meaning | Action needed |
|-------|---------|---------------|
| `queued` | waiting for a worker slot (MAX_CONCURRENT_JOBS, default 1) | none |
| `converting` | converter container running | none — watch progress |
| `recovering` | **designed behavior, not a new failure**: the converter died mid-book with partial output; the system is re-converting only the missing chapters, one at a time | none unless it loops (see incidents) |
| `failed` | retries exhausted or timed out | read the Log on the job card; Resume re-runs only missing chapters |
| `completed` | all chapters done; ABS sync attempted | check sync badge |

## Capacity truths (zorin: i5-12400, 31 GB RAM, no GPU — upgraded 2026-07-20)

*(Refreshed 2026-07-25 — several bullets here had gone stale.)*

- Kokoro + Piper + Chatterbox (Turbo **and** Nano) + webapp/worker fit
  comfortably on 31 GB.
- **Chatterbox NANO is the default engine** (`DEFAULT_VOICE=uk_male_minter_nano`).
  A/B'd against Turbo on an identical passage: indistinguishable in quality at
  **RTF 0.87 vs 3.33**. A 12.4-hour book takes ~11 h on Nano vs ~41 h on Turbo —
  **faster than realtime on CPU, so full books no longer need a GPU at all.**
  Turbo remains fully selectable; it is simply no longer the default.
- `scripts/deploy.sh` starts **chatterbox-nano** by default — Nano
  carries the default voice, so its container must be up or the default engine
  is offline on a fresh deploy. Piper is legacy/debug and opt-in
  (`ENABLE_PIPER_PROFILE=1`) after failing the controlled quality A/B. Turbo and
  TADA stay opt-in (`ENABLE_CHATTERBOX_PROFILE=1` /
  `ENABLE_TADA_PROFILE=1`) because they are heavy.
  **That describes a fresh deploy, not necessarily the running box.** A live
  check on 2026-07-25 found Turbo *and* kokoro up alongside nano and piper
  (opt-ins from earlier sessions, never brought down). Harmless on 31 GB, but
  read engine state from `/api/engines/health`, not from this paragraph.
- **TADA stays OFF.** #23 is still open: the image builds again since the
  `hume-tada` pin fix and it starts healthy, but the first synthesis exceeds its
  10 GiB cgroup within ~7 s (`OOMKilled=true`). Do not simply raise the cap —
  it consumed 10 GiB while the host had ~10 GiB free.
- **Startup voice-preview caching now defaults ON** (`VOICE_CACHE_ON_START=1`),
  so every voice previews instantly. What makes that safe is the throttle (wait
  for a quiet box, pause between voices) plus per-engine `mem_limit`s, not the
  default — the Jul-18 OOM predates the 31 GB upgrade. Set it to `0` on a
  smaller host.
- GPU engines are now a **quality ceiling, not a throughput answer**: reach for
  CosyVoice 3 (Kaggle/Vast GPU) or TADA for their specific character, not for
  speed.

## Output options

- **Per-chapter MP3s** (default) or a **single chaptered M4B**: choose "Output"
  in the convert panel, or POST `output_format: "m4b"` to
  `/api/library/convert`. The MP3s are always produced; the M4B is built from
  them before the Audiobookshelf sync, so it ships with the book. Audiobookshelf
  reads its chapter index natively.
- **Narration speed** is honoured by Kokoro, Piper, Edge, Polly and CosyVoice.
  Chatterbox (Turbo/Nano) and TADA have **no speed control** — the UI greys the
  field out for them and the job log records that the request was ignored. For
  Chatterbox pacing use `CHATTERBOX_EXAGGERATION` / `CHATTERBOX_CFG_WEIGHT`.

## Proving the delivery chain

`bash scripts/e2e_proof.sh` renders one public-domain chapter on every free
engine and asserts MP3 → chaptered M4B → cover art → files present in
Audiobookshelf, wiping after each success. **Run it after any change to the
render, sync or packaging paths** — every defect it has found so far lived in
the wiring *between* components, where the unit suite is blind.

## Book acquisition pipeline (2026-07-31)

How books get from "wanted" to the audiobook library. This section documents the
full search-to-grab-to-library flow, the infrastructure it runs on, and what to
check when it breaks.

### Topology

| Host | Role | Key services |
|------|------|--------------|
| **docker-vm** (192.168.1.113) | Orchestration + downloads | LazyLibrarian, SABnzbd, qBittorrent (in gluetun), Prowlarr client, Audiobookshelf, book_sync cron |
| **mediahub NAS** (10.77.0.24 / 192.168.1.248) | Storage + indexers | Prowlarr (Docker, port 9696), Synology packages, 7 TB volume |
| **gluetun** (container on docker-vm) | VPN tunnel | ProtonVPN WireGuard → Netherlands, killswitch, SOCKS5 on 127.0.0.1:1080, HTTP proxy on 127.0.0.1:8888 |
| **homelab-pi** (192.168.1.248) | Book library host | OpenBooks (manual, port 6081), sshfs target for zorin |
| **zorin** (192.168.1.41) | Audiobook conversion | epub-to-audiobook webapp+worker, sshfs mount of homelab-pi's books → `/mnt/openbooks` |

### Search paths (LazyLibrarian)

LL has two independent search paths. If one is down, the other still works.

1. **NZB / Usenet** (direct Newznab indexers: NZBgeek, NZBFinder, Nzb.su,
   DrunkenSlug). Own API keys, no Prowlarr dependency. Downloads via SABnzbd,
   which routes through gluetun's SOCKS5 proxy (`socks5://127.0.0.1:1080`).

2. **Torrents** (Prowlarr-proxied Torznab: LimeTorrents, InternetArchive).
   Requires Prowlarr on the NAS (10.77.0.24:9696). Downloads via qBittorrent,
   which runs inside gluetun's network namespace (`network_mode: service:gluetun`).
   If the VPN drops, gluetun's firewall kills all egress.

### Automatic dual-grab (epub + audiobook)

When a book is added to LazyLibrarian with both `Status=Wanted` (ebook) and
`AudioStatus=Wanted` (audiobook), the scheduled search job automatically grabs
**both formats** on the next cycle. No manual intervention needed.

LL's search runs periodically (`cron_search_book` job). It queries all enabled
providers (NZB + torrent) for each wanted item. Ebook results are filtered to
epub/mobi/azw3; audiobook results accept m4b/m4a/mp3. Downloads go to
qBittorrent (torrents, via VPN) or SABnzbd (Usenet, via SOCKS5/VPN).

### Grab → library delivery

```
qBittorrent/SABnzbd download
  → /opt/slskd-stack/downloads/books/  (NAS sshfs mount on docker-vm)
  → book_sync.sh (root cron, */10 min)
      ├── epub/mobi/azw3 → scp to homelab-pi → zorin sshfs → /mnt/openbooks
      │                    → epub-to-audiobook app → conversion → ABS
      └── m4b/m4a/mp3 folders → cp to /opt/stacks/audiobookshelf/audiobooks/
                                 → ABS library scan triggered automatically
```

`book_sync.sh` lives at `/home/dave/scripts/book_sync.sh` on docker-vm. It
handles both formats: ebooks go to the conversion library (homelab-pi),
audiobooks go directly to Audiobookshelf. A `.processed/` sentinel directory
prevents re-syncing. After delivering an audiobook, the script triggers an ABS
library scan so the new title appears immediately.

### VPN coverage

| Component | VPN? | Mechanism |
|-----------|------|-----------|
| qBittorrent (torrent downloads) | ✅ | `network_mode: service:gluetun` — all traffic via ProtonVPN WireGuard, killswitch |
| slskd / soularr (Soulseek music) | ✅ | Same gluetun namespace |
| SABnzbd (Usenet downloads) | ✅ | `socks5_proxy_url = socks5://127.0.0.1:1080` (gluetun SOCKS5) |
| Prowlarr (indexer search queries) | ❌ | Runs on NAS, queries public indexer websites over HTTPS. Low risk: no P2P, no swarm exposure |
| OpenBooks (manual, family use) | ❌ | IRC DCC on homelab-pi. Manual use only |

### Monitoring

`/home/dave/scripts/pipeline_healthcheck.sh` on docker-vm (root cron, daily
09:00). Alerts via Telegram ONLY on failure. Checks:

1. LazyLibrarian API
2. SABnzbd API
3. qBittorrent login (at 10.77.0.7:8086 via WireGuard)
4. Prowlarr API (at 10.77.0.24:9696)
5. Library sync freshness (rsync on homelab-pi)
6. Gluetun HTTP proxy reachability

### Wanted monitor

`/home/dave/scripts/run_wanted_monitor.sh` on docker-vm (root cron, hourly).
Checks LazyLibrarian's Wanted list against the audiobook library, sends
Telegram/WhatsApp notifications when a title appears. The OpenBooks IRC
automated bridge was retired 2026-07-31 (505 consecutive failures; the IRC
network the bridge targeted is unreachable from the script, though OpenBooks
itself still works for manual family use via its web UI).

### Key credentials (stored in configs, not here)

- qBittorrent: admin user, password in LL's `[QBITTORRENT]` section
- Prowlarr API key: in LL's `[Torznab_*]` sections; source of truth is
  `/volume1/docker/projects/prowlarr/config/config.xml` on the NAS (requires sudo)
- SABnzbd API key: in LL's config (`sab_api`)
- Gluetun WireGuard key: `/opt/slskd-stack/.env` on docker-vm

### Failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| LL search returns 0 results | Prowlarr down OR indexers failing | Check `http://10.77.0.24:9696` — NAS may be rebooting. NZB path works independently |
| qBittorrent 403/401 | Password changed or container recreated | Check `docker logs books-qbittorrent` for temp password |
| book_sync not delivering | homelab-pi SSH unreachable | `ssh dave@192.168.1.248 hostname` from docker-vm |
| Healthcheck reports Prowlarr 401 | API key rotated on NAS | `sudo grep ApiKey /volume1/docker/projects/prowlarr/config/config.xml` on NAS |
| Gluetun unhealthy | ProtonVPN connection dropped | `docker logs gluetun` — check WireGuard key expiry |
| Books not appearing in audiobook library | sshfs mount stale on zorin | `sudo umount /mnt/openbooks && ls /mnt/openbooks` (autofs remounts) |

### Reverting tonight's changes (2026-07-31)

All changes have timestamped backups on docker-vm:

- LL config: `/home/dave/docker-apps/lazylibrarian/config/config.ini.bak-20260731-bookpipe`
- qBittorrent config: `/opt/slskd-stack/qbit-config/qBittorrent/qBittorrent.conf.bak-20260731`
- Wanted monitor script: `/home/dave/scripts/run_wanted_monitor.sh.bak-20260731`
- Healthcheck: `/home/dave/scripts/pipeline_healthcheck.sh.bak-20260731`
- Gluetun compose: `/opt/slskd-stack/compose.yaml.bak-20260731-sabvpn`

To fully revert: restore each backup, `docker compose up -d` in `/opt/slskd-stack`,
restart LL and SABnzbd, remove the `book-sync` line from root's crontab.

## Common failures → responses

- **Engine offline** (UI shows OFFLINE, queueing returns 409): start it —
  `docker compose --profile chatterbox|tada up -d`.
- **Job failed with some chapters done**: press *Resume from failure* — only
  missing chapters are re-run.
- **Chatterbox/TADA server unresponsive or restarted**: it now has a hard
  mem_limit; Docker restarts it cleanly and in-flight chapter retries recover.
  If it thrash-restarts, reduce concurrent jobs to 1 and check `free -h`.
- **Vast GPU**: only via `scripts/vast-gpu.sh` (see GPU-SAFETY.md). Always
  `down` after. Health must show `cuda_available:true` or you're paying GPU
  price for CPU speed.

## Incident log

### 2026-07-28 — one incomplete HTTP request wedged the whole web UI

- **Symptom:** the candidate sample links and even `/api/health` accepted TCP
  connections but returned no HTTP bytes. Docker still showed the webapp as
  healthy, so this initially looked like a bad sample URL or dead host.
- **Evidence:** a curl from Zorin itself also timed out. After 300 seconds,
  Gunicorn killed its only synchronous worker while its stack was blocked in
  `sock.recv`; connection state included stalled `CLOSE-WAIT` clients.
- **Cause:** the webapp had one synchronous Gunicorn worker. One client that
  connected and did not finish its request could monopolise that worker, so
  unrelated health, UI and sample requests queued behind it.
- **Fix:** retain one process (the queue/recovery guards are in-memory) but use
  Gunicorn's `gthread` worker with four threads. Sample routes also accept an
  explicit `.mp3` suffix and return the real filename, which makes browsers and
  chat clients recognise them as playable audio more reliably.
- **Do not trust the Docker health badge alone for this failure.** Curl
  `/api/health` and require a timely HTTP response.

### 2026-07-25 — Settings could not save: WAL sidecars owned by the wrong user
- **Symptom:** every write through the Settings page returned
  `{"error":"attempt to write a readonly database"}`, so no API key, token or
  option had ever persisted. `app_settings` was empty, and the app silently
  fell back to `.env` for everything.
- **Not the obvious causes.** `jobs.db` is owned by uid 999 — the container's
  `appuser` — mode 644, and `/data` is a read-write bind mount that passes a
  `touch` test from inside the container. Ownership and mount were both fine.
- **Root cause:** SQLite runs in **WAL** mode (PLAN-V3 #10), which needs to
  write `jobs.db-wal` and `jobs.db-shm` beside the database. Those two files
  were owned by **`dave` (uid 1000)**, not `appuser`. SQLite cannot write its
  own WAL, so it reports the *database* as read-only — which sends you looking
  at the wrong file entirely.
- **How they got that way — my own doing.** Reading `app_settings` from the
  *host* with `python3 -c "import sqlite3..."` as `dave` is enough: opening a
  WAL database creates the sidecars as whoever opened it. A read-only-looking
  inspection silently broke writes for the container.
- **Fix:** stop the app containers, delete the two sidecars (check
  `jobs.db-wal` is 0 bytes first — a non-empty WAL holds committed
  transactions and must be checkpointed, not deleted), restart. They are
  recreated with the right owner.

  ```bash
  ls -la data/jobs.db-wal          # MUST be 0 bytes before deleting
  docker stop epub-to-audiobook-ui epub-to-audiobook-worker
  rm -f data/jobs.db-shm data/jobs.db-wal
  docker start epub-to-audiobook-worker epub-to-audiobook-ui
  ```

- **Standing rule: never open `jobs.db` from the host.** Read it through the
  container (`docker exec epub-to-audiobook-ui python3 ...`) or through the
  app's own API. This is the sixth instance of the non-root migration gap, and
  the first one caused by inspection rather than deployment.

### 2026-07-27 — deploying only `webapp` leaves the worker running old code

- **Symptom:** the API returned `destination: podcast` and wrote
  `source_kind='article'` to the job, and moments later the same row read back
  as `'book'`. Nothing errored. The render then filed itself as an audiobook.
- **Cause:** `webapp` and `worker` are **two containers built from the same
  `webapp/Dockerfile` and sharing `webapp/app.py`.** A hand-rolled
  `docker compose up -d --build webapp` rebuilt only the first. The stale worker
  picked the job up, called `update_job` → `save_job` with its *old* column
  list, and silently dropped the field the new webapp had just written.
- **Why it is nasty:** the health endpoint reports the **webapp's** version, so
  `/api/health` said `9eb4e59` while the code doing the work was older. The
  version banner cannot detect this class of failure.

  ```bash
  # Confirm what each container is actually running:
  docker inspect epub-to-audiobook-ui     --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  docker inspect epub-to-audiobook-worker --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  ```

- **Rule: use `scripts/deploy.sh`.** It runs
  `docker compose up -d --build --remove-orphans` across the stack and does not
  have this hole. Naming individual services is the shortcut that caused this.
- **Lesson (a repeat, in a new costume):** two components deriving one fact
  independently, and the second one drifting — the same shape as the `chapters.py`
  bug and the `_book_meta()` bug in PLAN-V4 §4. Here the two components were two
  *deployments of the same file*.

### 2026-07-25 — SSH to zorin from Windows appears dead; it is a key-permission problem
- **Symptom:** `ssh zorin` from the Windows box exits 255 and prints **nothing**
  — no error, no banner. `ssh -V` also prints nothing. It looks like a broken or
  blocked binary.
- **What it is not:** `C:\Windows\System32\OpenSSH\ssh.exe` is present and
  intact, the `zorin` host entry is correct (`192.168.1.41`, which pings), and
  `ssh` is not in any blocklist. The silence is an artefact of the tooling
  swallowing native **stderr** — every real error message goes there, so the
  failure looks like nothing at all.
- **Root cause (seen once stderr was recoverable, via WSL):**

  ```
  Permissions 0777 for '/mnt/d/Nextcloud/.ssh/dave_pi_key' are too open.
  Load key ...: bad permissions
  dave@192.168.1.41: Permission denied (publickey,keyboard-interactive).
  ```

  The key lives on a **DrvFs mount** (`D:`), which reports 0777 for everything.
  SSH refuses to use a world-readable private key, so it never authenticates.
- **Workaround (same pattern already used for the NAS):** copy the key to the
  Linux filesystem with correct permissions first.

  ```bash
  install -m 600 /mnt/d/Nextcloud/.ssh/dave_pi_key /tmp/zorin_key
  ssh -o BatchMode=yes -i /tmp/zorin_key dave@192.168.1.41 'hostname'
  ```

  For anything multi-line, write the commands to a file and pipe them
  (`ssh ... 'bash -s' < script.sh`) rather than fighting nested quoting.
- **Lesson:** a command that produces *no output at all* is usually a swallowed
  stderr, not a dead binary. Redirect to a file and read the file before
  concluding the tool is broken.

### Host access cheat-sheet (verified 2026-07-25)

| Host | What it is | Access |
|---|---|---|
| **zorin** `192.168.1.41` | Acer Veriton N4690GT mini PC. Runs the whole audiobook stack from `/home/dave/ai/lab/stacks/epub-to-audiobook`. | `ssh zorin` (see the DrvFs key note above) |
| **pve2** `192.168.1.12` | Dell OptiPlex 3000 SFF, Proxmox host for HAOS / n8n / Docker-VM. | **SSH is on port 2222, not 22.** Port 22 is refused, which reads as "host down" if you don't know. API on `:8006`. |

The book **library is `/home/dave/booklib`** on zorin — *not* `<stack>/data/library`,
which is what `LIBRARY_DIR`'s default (`/data/library`) suggests. The env var is
overridden to point at the real folder, so dropping an epub in the stack
directory achieves nothing and the webapp will not list it.

### 2026-07-25 — `docker.io` installed, `docker` missing: PDF + Edge previews broken
- **Symptom:** `Failed to generate preview for en-US-AriaNeural: [Errno 2] No
  such file or directory: 'docker'`, repeating for every Edge voice.
- **Root cause:** Debian **trixie**'s `docker.io` package ships only the DAEMON
  (`dockerd`, `docker-proxy`, `docker-init`) — not the `docker` client — and
  trixie has no `docker-cli` package. So `dpkg -l docker.io` said *installed*
  while `which docker` failed. Every path shelling out to `docker run` died.
- **Why it hid for so long:** book conversion doesn't use Docker at all. It runs
  `convert_book.py` in-process via `sys.executable`; the `audiobook-<job>`
  `container_name` is just a label written to the DB. So the main path worked
  perfectly while PDF upload (`docker run linuxserver/calibre`), Edge previews
  and ASR-verify were all silently broken.
- **Fix:** install the official **static docker client** (DOCKER_HOST already
  points at the socket proxy, so no daemon is needed and the image shrinks).
  Separately, PDF→EPUB now uses the `ebook-convert` **already inside the image**
  instead of spawning `linuxserver/calibre` — that call needed the missing CLI,
  a bind-mounted host path and an image pull to do what a local binary does.
- **Lesson:** "the package is installed" is not "the command exists". When a
  feature shells out to a binary, assert the binary at build time — the
  Dockerfile now ends that layer with `docker --version`, which would have
  failed the build instead of shipping a broken image.

### 2026-07-25 — Long Kaggle renders could burn the whole quota and return nothing
Two independent faults found while rendering a 142,759-word book (~15.4 h of
audio ≈ **13 GPU-hours** for CosyVoice at RTF 0.9):

- **A session that hits Kaggle's cap yields NOTHING.** Kaggle commits kernel
  outputs only when the kernel *finishes*: `kaggle kernels output` against a
  running kernel returned **zero files** (tested live, mid-render). A book
  needing more than one session would therefore consume ~12 h of the 30 h
  weekly quota and produce no MP3s at all.
  **Fix:** `kaggle_render.plan_batches()` packs chapters into contiguous
  batches sized by real per-chapter word counts (`chapters.list_renderable_chapters`)
  against `KAGGLE_SESSION_BUDGET_HOURS` (default 5). `convert_book_kaggle`
  loops the batches; each kernel completes and banks its chapters, and a
  failure mid-way keeps everything already pulled (Resume covers the rest).
  Note the units: the budget is GPU-hours of *audio*, and `ENGINE_RTF` differs
  sharply per engine (tada 0.45 vs cosyvoice 0.9) — halve the RTF and a book
  that needed 3 sessions needs 2.
- **Cancel never stopped the GPU.** `cancel_job()` stopped the container and
  the local process but did nothing about the kernel, so a cancelled Kaggle
  render kept billing quota while the UI said "cancelled". The Kaggle CLI has
  no stop verb; pushing a **new version to the same slug supersedes the running
  one**, which is what `kaggle_render.stop_kernel()` now does (no-op script,
  CPU, no internet). `kernel_slug()` is now the single source of truth for the
  kernel name so cancel targets the same kernel the render created.

**Lesson:** for any batch job on a capped external runner, ask two questions
before trusting it — *when do results become durable?* and *does our stop button
actually stop it?* Both answers here were the bad one.

### 2026-07-24 — Local LLM configured for weeks, never once called
- **Symptom:** none visible. Every LLM feature (chapter front/back-matter
  classification, pronunciation lexicon, metadata) silently did nothing, on a
  box with a perfectly good local model answering on the network.
- **Root cause:** `OLLAMA_URL` was set in compose for both webapp and worker,
  but **no code path read it**. `_llm_chat()` raised `"no LLM configured"`
  without `LLM_API_KEY`, and `llm_metadata._get_llm_settings()` returned `{}`
  the same way. `_llm_chat`'s own docstring claimed *"local Ollama primary /
  cloud fallback"* — intent that was never implemented. Fixed in `c30fc8b`.
- **Second bite:** `.env` pinned `OLLAMA_MODEL=qwen2.5:3b` but the Ollama host
  only had `qwen2.5:7b` — so even after the code fix it would have 404'd.
  Config pointing at a model that isn't installed fails exactly like "the LLM
  is broken".
- **Why it hid so long:** these features are *designed* to degrade silently
  (the guard returns None and callers fall back to the deterministic
  heuristic). That is good design for robustness, but it means "configured but
  never invoked" and "working fine" look identical from the outside.
- **Lesson:** an optional subsystem needs a positive health signal, not just a
  silent fallback. If a feature can be off without anyone noticing, surface its
  state (settings page / health probe) or it will be off for weeks.

### 2026-07-24 — Non-root migration left volumes root-owned (webapp + chatterbox down)
- **Symptom:** after a redeploy, `epub-to-audiobook-ui` and `-worker`
  crash-looped; later, `chatterbox-nano` 500'd on model load.
- **Root cause (one family, three sites):** the audit's switch to a non-root
  `appuser` (UID 999) never reconciled the bind-mounts/volumes, which were owned
  by root or by host UID 1000:
  1. `/data` bind-mount owned 1000 → `PermissionError: /data/toc_cache` at
     import. Fixed: `chown -R 999:1000 data && chmod -R g+rwX data` (container
     writes as its UID; host user keeps group access).
  2. `chatterbox-cache` HF volume owned by root (from a Jul-6 pre-migration run)
     → Nano couldn't create its model dir. Turbo only worked because its model
     was already cached. Fixed: `chown -R 999:999` the volume.
  3. `numba`/`librosa` had no writable cache dir → "cannot cache '__o_fold'".
     Fixed: `NUMBA_CACHE_DIR=/tmp/numba` (Dockerfile + compose).
- **Lesson:** a non-root migration must chown every bind-mount and named volume
  to the container UID, not just `chown` inside the image (the mount shadows it).

### 2026-07-18 — Startup preview cache caused repeated TADA OOM bursts
- **Symptom:** repeated freezes/reboots after Docker and the web app started.
- **Trigger:** there were no queued TADA jobs. Five seconds after web-app start,
  `_cache_all_voices_background()` attempted missing TADA previews directly.
  Model load filled TADA's 10 GiB cgroup; the kernel killed uvicorn and Docker
  restarted it. Four preview attempts produced three kills per startup.
- **Wider finding:** retained journals also contain Chatterbox 6 GiB cgroup
  kills and TADA host-wide OOM events, so the history is a multi-engine memory
  problem rather than one infinite TADA retry loop.
- **Containment:** stop TADA and Chatterbox on the NUC; keep Kokoro/Piper/UI
  available. Preview caching and both heavy deploy profiles now default off.
- **Do not:** raise TADA to 12 GiB on this host; that removes the remaining
  headroom and risks converting a contained cgroup kill into host-wide OOM.

### 2026-07-07a — Full-book job failed 3x instantly (job d67c50ac)
- **Symptom**: "Container died unexpectedly", 0% each retry.
- **Root cause**: UI chapter count off-by-one (end 19 vs converter's 18) made
  the converter exit at startup; self-healing capped the range but every
  retry aborted on a stale `container_name` tripping the duplicate-start
  guard. Second bug: the webapp ran conversions despite QUEUE_RUNNER=0.
- **Fixes**: retries clear container_name + force-remove stale container;
  job spawns gated by QUEUE_RUNNER_ENABLED. Verified: same job re-run
  self-healed and converted.

### 2026-07-07b — Chatterbox server OOM death-spiral mid-book (job ebe7c78d)
- **Symptom**: book died at ch6; each chapter retry ground ~45 min then
  failed; kernel log: `Out of memory: Killed process (uvicorn) rss:10.8GB`.
- **Root cause**: the engine server ran generations **concurrently** (FastAPI
  sync threadpool). When a long chapter made the converter's client time out
  and retry, the server kept generating the abandoned request AND the new
  one → memory ballooned → kernel OOM-killed the server → every retry hit a
  dead/thrashing engine. Compounding: job timeout (375 min) was far below a
  realistic full-book time because partial-range jobs had polluted the
  chars/sec metrics (whole-book char_count recorded for 1-chapter jobs).
- **Fixes**: (1) generation serialized behind a lock + inference_mode + gc in
  BOTH engine servers; (2) mem_limit on engine containers so overruns restart
  cleanly; (3) timeout floored at char_count/4 chars-per-sec for
  chatterbox/tada; (4) metrics recorded only from full-book conversions.
- **Status**: fixes committed; engine images rebuild in CI; the job resumes
  (chapters 1-5 already done) after the fixed image is pulled.


### 2026-07-08b — "endnote numbers read aloud" was actually year-spelling (Apple in China)
- **Symptom (Dave)**: "from its founding in 1970......6", "returned in 1990...7"
  — sounded like endnote citation numbers being spoken.
- **Diagnosis**: NOT endnotes (this book's refs are empty `<span id="ennoteN"/>`
  anchors, correctly stripped). The years 1976 and 1997 were spelled out as
  "nineteen seventy-SIX" / "nineteen ninety-SEVEN"; TADA pauses before the
  final digit, so "six"/"seven" sounded detached — heard as "1970...6".
- **Fix**: number/year/large-number spelling is now SKIPPED for modern
  voice-clone engines (chatterbox/tada) via `normalize_text_for_tts(...,
  modern=True)`, plumbed through preprocess_epub + app + convert_book. Modern
  models read "1976" natively and correctly. Legacy engines (Kokoro/Piper)
  unchanged. Regression-guarded.
- Lesson: several normalization "helpers" tuned for dumb engines actively
  HURT modern models (this + the em-dash→comma fix). Modern path should be
  minimal-normalization.
- **Codified 2026-07-08 (stop finding these one at a time)**: the
  MODERN-ENGINE CONTRACT is now documented at the top of
  `webapp/tts_preprocess.py` and enforced by
  `test_modern_contract_skips_all_plain_number_spelling`. Rule: for
  `modern=True`, SKIP every transform that respells a plain number / year /
  decade / large integer (engine reads them right); KEEP symbol/abbrev
  expansion ($, %, U.S., 1st); anything genuinely ambiguous for one book is
  caught adaptively by the per-book LLM narration profile, NOT by adding
  another regex. Decades (`1990s`) were brought under the guard at the same
  time. Any new numeric transform must go under the single `if not modern:`
  block by default.

### 2026-07-08c — Preprocessing now classifies fiction vs non-fiction
- The narration profile (`generate_narration_profile`) returns
  `form`/`is_fiction` and steers what it hunts for: fiction → character/place/
  invented names and dialogue flow (dashes, quotes); non-fiction → acronyms,
  company/brand names, ambiguous figures. Surfaced in the job log and the
  standalone converter, persisted in `narration_profile`.
- Honest limit: with a single-voice engine this does NOT do per-character
  voices. It biases pronunciation-rule search and pacing handling only.

### 2026-07-08d — TADA image silently ran on CPU (unpinned torch → cu130)
- **Symptom**: fresh Vast TADA instance came up healthy but `/health` showed
  `device:cpu, cuda_available:false` with `torch 2.12.1+cu130`.
- **Root cause**: `tada/Dockerfile` installed `torch --index-url cu124`
  UNPINNED, then `pip install -r requirements.txt`. hume-tada requires
  torch>=2.7 (cu124's max is 2.6.0) and pulls torchaudio/torchvision unpinned,
  so the requirements step re-resolved the whole stack from PyPI to the default
  cu130 build (torch 2.12). cu130 needs an R580+ driver; most GPU hosts have
  older drivers, so torch fell back to CPU. Chatterbox was unaffected because
  chatterbox-tts pins torch==2.6.0, matching its preinstalled cu124 build.
- **Fix**: pin the FULL cu126 stack (`torch==2.8.0 torchvision==0.23.0
  torchaudio==2.8.0 --index-url .../cu126`) BEFORE the requirements install so
  hume-tada finds everything satisfied and touches nothing. cu126 needs only
  R560+ (broad host coverage) and satisfies torch>=2.7. Regression-guarded
  (`test_tada_torch_stack_pinned`). `scripts/vast-gpu.sh` offer filter now
  requires `cuda_max_good>=12.6`.
- **What caught it**: the `/health` cuda_available gate — the standing rule to
  refuse CPU runs. Interim workaround for the run: used a CUDA-13 host so the
  still-deployed cu130 image worked; the cu126 image rebuilds via CI.
- Lesson: an unpinned `pip install torch` is a landmine — a transitive dep with
  a torch floor silently re-pulls the default (newest-CUDA) build. Pin the
  whole torch stack, always.

### 2026-07-08 — Kaggle free-GPU path blocked on phone verification
- Kaggle kernels get NO internet ("Temporary failure in name resolution",
  pip/git/HF all fail) until the account is **phone-verified**
  (kaggle.com/settings), regardless of `enable_internet:true` in
  kernel-metadata.json. One-time, needs Dave's phone.
- The kernel + epub dataset are pushed and ready
  (`davedavedavedavenm/apple-china-tada-ch1-2`); re-run free once verified.
  Alternative if verification isn't possible: attach the ~5GB TADA models +
  hume-tada wheel as offline Kaggle datasets so the kernel needs no internet.

### 2026-07-08 — Duplicate recovery threads across processes (job ebe7c78d)
- **Symptom**: resume + worker startup each launched a chapter-recovery pass
  4 s apart (both logged "Retrying 9 missing").
- **Root cause**: the duplicate-recovery guard was an in-memory dict; the
  resume API runs in the webapp process and orphan cleanup in the worker —
  separate processes, so the guard could not see the other thread.
- **Fix**: cross-process recovery lock in the DB (app_settings key
  `recovery_lock_<job>`, 3 h staleness takeover). Regression-guarded.
- **Correction (same morning)**: NOT benign — the racing threads killed each
  other's retry containers, producing spurious 16-second "Chapter FAILED
  after 3 retries" verdicts while the real generation was still running.
  Lock deployed 2026-07-08 06:05 and verified live ("another process holds
  the recovery lock, skipping").
- **Also fixed**: the UI froze at the pre-crash percentage during recovery
  (looked stuck all night while 4 chapters actually completed — file
  timestamps 21:06/23:49/03:03/06:09). Recovery now updates
  progress_percent/current_chapter as chapters land.

**Speed reality for this class of book**: Inside Apple's chapters are 45-80
MINUTES of audio each; the NUC generates ~one chapter per ~3 h. A ~13 h
audiobook = roughly a day and a half of NUC compute. That is the honest price
of the free path; the GPU runbook does the same book in ~4 h for ~GBP0.5.

### 2026-07-06/07 — GPU images silently ran on CPU
- CPU-only torch + missing NVIDIA envs; no sshd in slim images; GHCR pulls
  stall on slow Vast hosts. All fixed; validated with measured RTFs (TADA
  0.34, Chatterbox ~0.85 on RTX 3090). See LOW-COST-TTS.md.

### 2026-07-08e — real-worker-path deploy surfaced a cluster of latent bugs
Running conversions only through hand-driven scripts hid several bugs; deploying
the day's code to the live worker and submitting a real webapp job exposed them.
The lesson (now a standing rule): **prove fixes through the real worker path.**
- **MP3 concat corruption** (`convert_book.py`): joined per-chunk MP3 *bytes*,
  leaving corrupt frame headers at each boundary. Players tolerate it; strict
  decoders (ffmpeg/PyAV, audiobook-player seek/duration) hit "Header missing"
  and stop after chunk 1 (a 27-min chapter ASR-decoded to 19 words). Fixed:
  concat at WAV sample level via stdlib `wave`, then one clean MP3 encode.
  The web-UI path (upstream p0n1 tool) re-encodes and was already clean.
- **Preprocessing use-before-assign** (webapp `convert_book`): the preprocess
  block referenced the local `tts_engine` ~25 lines before it was assigned, so
  on EVERY real conversion it threw and silently fell back to raw text — none
  of the modern-contract/pronunciation/endnote work applied. Invisible until
  the worker (running 14-hour-old code) was redeployed. Fixed: read the engine
  from the job. Regression-guarded.
- **Recovery resurrects cancelled jobs** (#14): startup orphan-recovery flipped
  a cancelled job back to `converting`, jamming the single MAX_CONCURRENT slot.
  Recovery must exclude terminal states. Open.
- **ABS sync silently broken** (#15): worker's `AUDIOBOOKSHELF_HOST=docker-vm`
  doesn't resolve (ABS must be reached by its LAN IP, not the `docker-vm` alias) and the API token had expired
  2026-06-07 — so conversions weren't reaching AudioBookShelf (jobs showed
  `synced_to_abs=0` with no alert). Token + ABS_API_URL restored in settings;
  host env + rsync SSH key + a restart still needed. Open.
- **Free Kaggle TADA broke on a Kaggle-image clash**: `transformers` (via
  hume-tada) eagerly imported Kaggle's preinstalled TensorFlow, whose protobuf
  was mismatched. Fixed: `USE_TF=0` + uninstall tensorflow in the kernel.
- **LLM configured 2026-07-08**: initially there was no LLM key on zorin so
  `generate_narration_profile` fell back to seed rules. Now Groq
  (`llama-3.3-70b-versatile`, OpenAI-compatible at api.groq.com/openai/v1) is
  stored in app_settings and verified live — production conversions get full
  adaptive pronunciation + fiction/non-fiction. The seed floor remains the
  offline fallback.

## Standing rules for claims

A path may be called "working" in STATUS.md only with evidence: a completed
real conversion (job id / artifact / measurement) recorded alongside it.

**Official docs are the baseline.** Engine behavior claims come from the
engine's official documentation (collected in ENGINES.md), not from
experiment-derived guesses. The TADA reference-transcript requirement and
Chatterbox's cfg_weight/exaggeration pacing controls were both in the docs
all along while we debugged blind (2026-07-09).

**Prove fixes through the REAL worker path, not scripts.** Standalone scripts
and hand-driven GPU rigs hid a cluster of bugs (2026-07-08e). A fix isn't
proven until it has run through the webapp/worker the user actually uses — and
that requires the change to be DEPLOYED (the worker runs the built image, not
the working tree; `git pull` alone does nothing until the worker is rebuilt).

**Canonical output location** (so "where do I look?" is never re-litigated):
finished audio ALWAYS lands in `data/audiobooks/<book>/` on the machine that
ran the conversion — webapp jobs, standalone `convert_book.py`, and the
`scripts/sample.sh` harness (samples go to `data/audiobooks/_samples/`).
AudioBookShelf is the unified listening library the webapp syncs to. Do NOT
add new ad-hoc output dirs.

## End-to-end delivery proof (scripts/e2e_proof.sh)

Renders one public-domain chapter (Poe, *The Raven*) on **every free engine** and
asserts the whole delivery chain per engine — MP3 → chaptered M4B → cover art →
files actually present in Audiobookshelf — wiping local output, the ABS copy and
the job record after each success (failures are left in place for inspection).

Run it on zorin after any change to the render, sync or packaging paths:

```bash
bash scripts/e2e_proof.sh          # ~35 min for all five engines
```

**Result 2026-07-25 — PASS 5/5:** chatterbox_nano, kokoro, piper, edge, chatterbox.

It earned its keep immediately. Four defects it found that 99 unit tests did not,
because every one of them lived in the wiring *between* components:

1. **Audiobookshelf sync was entirely broken.** The SSH key was owned by UID 1000
   while the container runs as 999 → `Permission denied`. The fourth instance of
   the same non-root migration gap (after `/data`, the HF cache volume, numba).
2. **Edge could never render a book.** `convert_book` asks every engine for WAV so
   chunks join losslessly; the Edge path returns MP3 regardless, so `_concat_wav`
   died with "file does not start with RIFF id". Only previews had ever worked.
   Fixed generally with `_ensure_wav()` — any engine that ignores
   `response_format` now works.
3. **The M4B arrived after the job said "completed".** The local render path
   duplicates `_gate_and_sync` rather than calling it, so the M4B hook added
   there never ran locally; the file only appeared because the watchdog later
   re-finalised the job, producing a second sync a minute later. **The
   duplication itself is still there** — anything added to `_gate_and_sync` still
   silently skips local renders. Worth unifying.
4. **A lint autofix broke every sync.** Ruff's F401 pass removed one of two
   duplicate `import shlex` statements inside `copy_to_audiobookshelf`; the
   survivor still made the name function-local, leaving the earlier
   `shlex.quote()` unbound. Guarded now by
   `test_no_local_import_shadows_an_earlier_use`.

**Lesson:** a green unit suite is not evidence that a delivery path works. Each of
these sat in the seams between components, and only an end-to-end run that
checked the *artefacts* — not the exit codes — could see them.

### 2026-07-25 — TADA: image resurrected, engine still OOMs (#23 stands)
- The TADA image had been unbuildable since 2026-07-23 (`hume-tada==0.3.0`
  never existed — see the build incident above). With the pin corrected to
  0.1.9 it builds, starts, and reports healthy with all five voices.
- **But it still cannot render.** The first synthesis request blows past the
  10 GiB cgroup within ~7 seconds and Docker reports `OOMKilled=true`. The
  converter sees `RemoteDisconnected` and the job fails after three retries.
- Also fixed on the way: the `tada-cache` HF volume was root-owned while the
  container runs as UID 999, so model files could not be cached
  (`Permission denied ... models--HumeAI--tada-1b`). Fifth instance of the same
  non-root migration gap. Fixed, but it was not the cause.
- **Raising mem_limit is not the answer** on this box: it blew 10 GiB in
  seconds while the host had ~10 GiB free, so a bigger cap risks the host
  rather than the container. The real question for #23 is why a 1B model needs
  >10 GiB to generate — fp32 weights (~4 GB) plus whatever the 600-char chunk
  size costs in activations is the place to start.
- TADA is therefore **excluded from the default E2E set** and stays behind its
  compose profile. Run it explicitly once #23 is fixed:
  `bash scripts/e2e_proof.sh tada`.
