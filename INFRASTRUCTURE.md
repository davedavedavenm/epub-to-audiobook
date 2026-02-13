# Infrastructure Map

## Hosts

### zorin (dave@zorin, 192.168.1.88) — Main Conversion Host
- **Role:** Runs the epub-to-audiobook Docker stack, Kokoro CPU TTS
- **Stack path:** `/home/dave/ai/lab/stacks/epub-to-audiobook/`
- **EPUB library:** `/mnt/openbooks/` (65+ books) — **SSHFS mount** to `dave@192.168.1.248:/home/dave/Downloads/openbooks/books`
- **Key ports:**
  - `8880` — Kokoro TTS (CPU)
  - `8881` — epub-to-audiobook webapp
  - `8882` — TTS proxy (transcript capture)
  - `8890` — SSH tunnel to GPU Kokoro (when active)
- **Docker containers:** epub-to-audiobook-ui, epub-to-audiobook-worker, kokoro-tts, tts-proxy, piper-tts
- **Gotchas:**
  - No pip3 installed (apt repos broken)
  - Stack is NOT a git repo on zorin; deploy via scp + sudo cp
  - Docker gateway IP: `172.19.0.1`

### docker-vm (dave@docker-vm, 192.168.1.113) — Media & Services Host
- **Role:** Runs Audiobookshelf, LazyLibrarian, Calibre Web, Shelfmark, SABnzbd, wanted_monitor
- **Key ports:**
  - `5299` — LazyLibrarian (book discovery/management)
  - `8082` — SABnzbd (NZB downloader) — configured in LL but download method NOT enabled
  - `8083` — Calibre Web Automated (ebook library management)
  - `8084` — Shelfmark / calibre-book-downloader (book search & download via Tor)
  - `8085` — FileBrowser
  - `13378` — Audiobookshelf (audiobook library & player)
- **Key paths:**
  - `/opt/stacks/audiobookshelf/audiobooks/` — ABS audiobook storage
  - `/home/dave/scripts/wanted_monitor.py` — LL→OpenBooks automation script
  - `/home/dave/scripts/wanted_monitor.env` — credentials for wanted_monitor
  - `/home/dave/scripts/wanted_state.db` — state tracking DB
  - `/home/dave/docker-apps/lazylibrarian/config` — LL config

### Dave's PC (192.168.1.248) — OpenBooks & Watchdog Host
- **Role:** Runs OpenBooks (IRC book downloader) and audiobook-watchdog
- **Key ports:**
  - `6081` — OpenBooks web UI (manual IRC book search/download)
- **Docker containers:** openbooks, audiobook-watchdog
- **Key paths:**
  - `/home/dave/Downloads/openbooks/books/` — Downloaded EPUBs (exposed via SSHFS to zorin)
  - `/home/dave/Downloads/openbooks/processed/` — Processed books
- **Cron:** `*/15 * * * *` — `sync_to_library.sh` (rsync books to ABS on docker-vm)

## Book Acquisition Pipeline (FULLY AUTOMATED)

```
1. User adds book to LazyLibrarian (docker-vm:5299)
   │
2. wanted_monitor.py (cron hourly on docker-vm)
   ├── Reads LL wanted list (SQLite DB)
   ├── Checks if book already in epub-to-audiobook library
   ├── Enqueues OpenBooks IRC search request
   │   └── Rate-limited: max 2 requests/run, 6hr cooldown per title
   │
3. OpenBooks (192.168.1.248:6081) receives IRC search
   └── Downloads EPUB to /home/dave/Downloads/openbooks/books/
       │
4. SSHFS mount exposes as /mnt/openbooks/ on zorin
   │
5. epub-to-audiobook webapp sees new book via /api/library
   │
6. User queues conversion (manual or auto-scaling triggers it)
   │
7. Converter (Kokoro TTS) produces MP3 chapters
   │
8. Synced to Audiobookshelf (docker-vm:13378)
```

**To force-process a new book immediately** (bypass hourly cron + cooldowns):
```bash
ssh dave@docker-vm 'cd /home/dave/scripts && source wanted_monitor.env && \
  python3 wanted_monitor.py --process-openbooks-queue --max-queue-sends 2 --bridge-timeout-s 30 && \
  python3 wanted_monitor.py --library-api http://192.168.1.88:8881/api/library \
    --limit 10 --request-openbooks --request-policy all \
    --max-requests-per-run 2 --request-cooldown-s 0 --min-wanted-age-s 0'
```

## API Keys & Credentials

| Service | Location | Key |
|---------|----------|-----|
| LazyLibrarian API | docker-vm:5299 | `eeee0fbe8b3bd0a7643834d3494e424e` |
| ABS API | docker-vm:13378 | See .env on zorin (`ABS_API_TOKEN`) |
| Vast.ai API | `~/.config/vastai/vast_api_key` on zorin | (stored locally) |
| Vast.ai SSH | `~/.ssh/vastai_ed25519` on zorin | (key pair) |
| HuggingFace | N/A | See MEMORY.md (not committed — gated model access) |
| NZBgeek | In LL config | `tm8SXjxXjdFY5q3zOzXrGYpiv5fnA1X2` |
| NZBFinder | In LL config | `b98a13781e7601322a6c51431116bc2c` |
| SABnzbd | In LL config | `474e271becc148feaf080fc23b6296a1` |
| Telegram Bot | In .env on zorin | See `TELEGRAM_BOT_TOKEN` |

## TTS Engine: Kokoro v1.0 (Recommended)

Kokoro is the only TTS engine worth using for audiobook conversion. See evaluation below.

- **Image:** `ghcr.io/remsky/kokoro-fastapi-gpu:latest`
- **API:** OpenAI-compatible at `/v1/audio/speech`
- **Port:** 8880
- **Speed:** 36-210x real-time (GPU), ~5x real-time (CPU)
- **VRAM:** ~2-3GB
- **Voices:** 54+ preset — no voice cloning
- **Best British voices:** `bm_fable` (male), `bf_emma` (female), `bm_george`, `bf_lily`, `bm_lewis`
- **Vast.ai template:** ID 343755, hash `e2588a22cf5eef43df3d444ef4f25705`

## TTS Evaluation Results (Feb 2026)

We evaluated multiple TTS engines for audiobook use. **Kokoro wins decisively.**

| Engine | Quality | Speed (GPU) | VRAM | Voice Clone | Verdict |
|--------|---------|-------------|------|-------------|---------|
| **Kokoro v1.0** | Good+ | 36-210x RT | ~2-3GB | No | **USE THIS** — unbeatable speed, good quality |
| Chatterbox Turbo | Good+ | ~2-6x RT | ~4.5GB | Yes | **Not worth it** — 10-50x slower for marginal improvement on plain narration. Built-in voices all American. Excels at expressive markers ([gasp], [sigh]) not useful for audiobooks. |
| OpenAudio S1-mini | Excellent | ~3-5x RT | ~12GB | Yes | Not tested — 12GB VRAM too tight on RTX 3060 |
| Dia 1.6B | Excellent | Moderate | ~10GB | Yes | Not tested — best for multi-speaker dialogue |
| XTTS v2 | Good | Good | ~4GB | Yes | Not tested — Coqui defunct, no updates |
| Bark | Fair | Very slow | ~10GB | No | **Obsolete** — not competitive |

**Key finding:** Chatterbox sounds amazing in demos because of expressive text markup (`[gasp]`, `[sigh]`, etc.). For plain audiobook narration without markup, the quality difference vs Kokoro is negligible — not worth the 10-50x speed penalty.

**Chatterbox Vast.ai template exists** (ID: 343876, hash: `324515c561ddfb321574777547b26932`) but is not recommended for production use.

## Vast.ai GPU Setup

See [GPU-PLAYBOOK.md](GPU-PLAYBOOK.md) for operational runbook.

**ALWAYS use the Kokoro template** (ID: 343755, hash: `e2588a22cf5eef43df3d444ef4f25705`).

## Deploying Code Changes to Zorin

```bash
# From Windows:
scp webapp/app.py dave@zorin:/tmp/
scp webapp/worker.py dave@zorin:/tmp/
scp docker-compose.yml dave@zorin:/tmp/

# On zorin:
cd /home/dave/ai/lab/stacks/epub-to-audiobook
sudo cp /tmp/app.py webapp/
sudo cp /tmp/worker.py webapp/
sudo cp /tmp/docker-compose.yml .
docker compose build worker webapp
docker compose up -d worker webapp
```

## LazyLibrarian API Examples

```bash
API_KEY="eeee0fbe8b3bd0a7643834d3494e424e"
LL_URL="http://docker-vm:5299/api"

# List all authors
curl -s "$LL_URL?cmd=getIndex&apikey=$API_KEY"

# Get author's books
curl -s "$LL_URL?cmd=getAuthor&id=<AUTHOR_ID>&apikey=$API_KEY"

# Search for a specific book
curl -s "$LL_URL?cmd=searchBook&id=<BOOK_ID>&type=eBook&apikey=$API_KEY"

# Force search all wanted books
curl -s "$LL_URL?cmd=forceBookSearch&wait&apikey=$API_KEY"
```

## epub-to-audiobook API Examples

```bash
# Queue a book for conversion
curl -X POST http://zorin:8881/api/library/convert \
  -H "Content-Type: application/json" \
  -d '{"path": "/mnt/openbooks/My_Book.epub", "voice": "bm_fable"}'

# List available books
curl http://zorin:8881/api/library

# Check all jobs
curl http://zorin:8881/api/jobs

# Check specific job
curl http://zorin:8881/api/jobs/<JOB_ID>
```
