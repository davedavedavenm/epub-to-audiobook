# EPUB to Audiobook Converter

**Version:** 2.0.x (repo)

A self-hosted web application for converting **any** ebook (EPUB, PDF, MOBI,
and more) into an audiobook using AI text-to-speech, entirely on your own
machine. A clean "Studio Console" web UI with book-cover library, voice
previews, per-book render targets (local or free cloud GPU), job management,
adaptive text preprocessing, and Audiobookshelf integration.

> **New here? Start with the [full walkthrough → GETTING-STARTED.md](GETTING-STARTED.md)** — install, convert your first book, connect an AI for smarter pronunciation, add your own voices, and set up Audiobookshelf.

For current build state and remaining work see [STATUS.md](STATUS.md).

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### TTS Engines
- **Chatterbox Nano** - default local engine with **Beatrice (Nano)** (`uk_female_samuel_nano`) as system default narrator. Fast CPU inference (~0.87x RTF, faster than realtime), voice-cloned British narrators (Beatrice, Arthur, Harriet, Edmund). Runs out of the box with `docker compose up -d`.
- **Kokoro TTS** - neural local engine; very low runtime cost, CPU or Vast.ai GPU
  - British, American, European, and multilingual voice packs
  - Voice mixing support (blend two voices)
- **Chatterbox Turbo** - production narration engine with official pacing
  controls. Enable with explicit `ENABLE_CHATTERBOX_PROFILE=1` compose profile.
- **Hume TADA** - expressive natural-voice model via TADA-1B. Enable with explicit `ENABLE_TADA_PROFILE=1` compose profile.
- **EdgeTTS** - free high-quality Microsoft neural voices via `tts-proxy`
- **Piper TTS** - legacy local fallback (`ENABLE_PIPER_PROFILE=1`)

### Web Application & Media Delivery
- **Studio Console Web UI** - modern dark obsidian slate theme with Google Fonts (Plus Jakarta Sans & JetBrains Mono)
- **Dedicated Articles Tab (`📰 Articles`)** - paste any article URL for instant narration, with fast QA bypass (sub-minute synthesis)
- **Podcast RSS 2.0 Feed (`/api/articles/rss`)** - automatic podcast feed for streaming articles directly in Pocket Casts, Overcast, Apple Podcasts, or Audiobookshelf
- **Library Batch Management** - select all library ebooks, pick narrators and engines, and batch convert in one click
- **Studio Web Audio Player** - sticky glassmorphic bottom bar for listening to audiobooks, articles, and voice auditions across tabs with playback speed controls (1.0x–2.0x)

### Text Preprocessing (mandatory, engine-independent)

Every conversion runs a preprocessing pipeline before any TTS engine sees the
text — see [PREPROCESSING.md](PREPROCESSING.md):
- **Structural sanitization** - strips footnote/endnote markers and note bodies
  at the HTML level (immune to publisher quote styles)
- **Deterministic normalization** - unicode cleanup; numbers, years, currency,
  percentages, abbreviations to spoken form (`$33 billion` → "thirty-three
  billion dollars", `2000` → "two thousand")
- **Adaptive narration profile (QA Layer 1)** - when an LLM is configured, each
  book is analysed and per-book pronunciation rules are generated automatically
  (e.g. "US" → "U S", unusual names, misread numbers). Not hardcoded — adapts
  per book. Plus global and per-job regex rules.
- **Planned (QA Layer 2)** - Whisper ASR verification of the generated audio
  against the source text to auto-catch mispronunciations. See PLAN.md.

The upstream converter's `--remove_endnotes` flag is deliberately not used: it
corrupts decimals and alphanumerics (defect analysis in PREPROCESSING.md).

### Core Features
- **Extended Format Support** - EPUB, PDF, MOBI, AZW3, FB2, TXT, HTML, DOCX
- **Library Browser** - Browse and convert books from a local folder
- **Voice Preview** - Listen to each voice before converting
- **Voice Mixing** - Blend two Kokoro voices (e.g., `Emma+George`)
- **Per-book pronunciation** - Advanced panel regex + global dictionary
- **Chapter Selection** - Convert specific chapter ranges
- **Human-Readable Output** - Files renamed to `01 - Chapter Name.mp3`
- **Progress Tracking** - Real-time progress with ETA and per-job logs

### UI
- **"Studio Console" design** - cool ink neutrals, one signal-coral accent,
  mono for data, on-air motif, real book covers; light + dark. (Legacy note:
  the earlier warm "Narration Press" theme was replaced 2026-07-10.)
- **Tabs** - Library, Upload, Queue, Voices, History, Settings
- **Queue controls** - pause/resume, cancel, retry-all-failed, live log viewer
- **Preprocessing badge** - per-job "PRE ✓" with a summary of what was cleaned
- **Per-book render target** - choose **This machine / Kaggle GPU (free) /
  Vast GPU** right in the Narrate card; Kaggle renders run on a free cloud GPU
  and appear in the Queue
- **Real book covers** - epub cover art in the library, sorted most-recent-first
- **Guided, secure setup** - Settings has step-by-step Kaggle/LLM/ABS config
  with Test-Connection buttons; secrets persist on the `/data` volume, masked

### Integration
- **Audiobookshelf Sync** - Auto-sync completed books to ABS (each in its own
  folder; never overwrites existing audiobooks)
- **EPUB3 Read-Along Packaging** - EPUB output with Media Overlay/SMIL
- **Telegram / WhatsApp Notifications** - optional completion alerts
- **Smart chapter guard** - the convert panel lists chapters by real title and
  auto-selects the actual book body (skips copyright pages, notes, index). Uses
  an LLM when configured, with a deterministic fallback so it works without one
- **LLM Integration** - any OpenAI-compatible provider (Groq, Gemini, OpenAI, …)
  for the chapter guard, metadata + adaptive pronunciation
- **Download as ZIP**

## Quick Start (works on any machine, incl. for friends)

Everything runs in Docker on **local CPU by default** — no GPU and no cloud
account required.

```bash
# 1. Clone
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook

# 2. Configure. Set APP_AUTH_PASSWORD before exposing the web UI.
cp .env.example .env

# 3. Start. Enable the engines you want via profiles:
docker compose up -d                                              # Kokoro only (fast)
docker compose --profile chatterbox up -d                        # + Chatterbox Turbo (best UK voices)
docker compose --profile tada up -d                              # + TADA (expressive; research model)
docker compose --profile vibevoice up -d                         # + VibeVoice (CUDA GPU already attached)
docker compose --profile qwen3 up -d                             # + Qwen3-TTS (CUDA GPU already attached)
docker compose --profile piper --profile chatterbox --profile tada up -d   # everything

# 4. Open the UI
open http://localhost:8881
```

**Cost & privacy:** the default path spends nothing and sends your books to no
one. Optional paid Vast rendering is off by default, cannot be enabled in the
web Settings UI, and is never triggered by queue length. See
[GPU-SAFETY.md](GPU-SAFETY.md).

The UI and private APIs use HTTP Basic authentication from
`APP_AUTH_USERNAME` / `APP_AUTH_PASSWORD`. An empty production password fails
closed. Podcast RSS/audio and health/version probes remain public so podcast
clients and container health checks work. Article URL ingest accepts public
HTTP(S) destinations only and validates each redirect against DNS rebinding and
local/private address access.

First run of each engine downloads its model once (Kokoro ~, Chatterbox
~700 MB, TADA ~5 GB), cached in a Docker volume.

## Where do I find my audiobooks?

**One rule: finished audio always lands in `data/audiobooks/` on the machine that ran the conversion**, one folder per book.

- **Web UI jobs** → `data/audiobooks/<book title>_<jobid>/` (one `.mp3` per chapter), then auto-synced to your **AudioBookShelf** library if configured — that library is the unified place to *listen*, regardless of which machine rendered.
- **Standalone / Kaggle / Vast runs** (`scripts/convert_book.py`) → the same `data/audiobooks/<book>/` convention by default (override with `--out`). Kaggle kernels write to `/kaggle/working`; pull them with `kaggle kernels output`.
- **Quick samples** (`scripts/sample.sh`) → `data/audiobooks/_samples/<book>/` so test snippets never clutter the real library.

If a run finished but you can't find it, check `data/audiobooks/` on the host that did the work first, then AudioBookShelf.

## Iterating on quality (sampling a few pages)

To hear how a book will sound without a full run:

```bash
# Auto-uses a healthy LOCAL engine; else pass a Kaggle/Vast --engine-url
scripts/sample.sh --book "data/library/Some Book.epub" --start 1 --end 2
```

Samples land in `data/audiobooks/_samples/<book>/` and never touch the real library or the job queue. This is the fast local feedback loop for tuning preprocessing/voices.

## Production Deployment

```bash
STACK_PATH=/home/dave/ai/lab/stacks/epub-to-audiobook   # or wherever you like
git clone https://github.com/davedavedavenm/epub-to-audiobook.git "$STACK_PATH"
cd "$STACK_PATH"
cp .env.example .env
./scripts/deploy.sh            # builds webapp/worker + piper; set ENABLE_CHATTERBOX_PROFILE=1 for more
./scripts/smoke-check.sh http://localhost:8881
```

## Available Voices

### Chatterbox Turbo & TADA — British Human-Cloned (Recommended)
| Voice | Gender | Source (public domain) | Engines |
|-------|--------|------------------------|---------|
| Arthur | Male | Andy Minter (LibriVox) | Chatterbox, TADA |
| Edmund | Male | Peter Yearsley (LibriVox) | Chatterbox, TADA |
| Harriet | Female | Ruth Golding (LibriVox) | Chatterbox, TADA |
| Beatrice | Female | Cori Samuel (LibriVox) | Chatterbox, TADA |

Add your own from any ~15 s clip — see [GETTING-STARTED.md](GETTING-STARTED.md) §5.

### Kokoro Voices (Local)
| Accent | Female | Male |
|--------|--------|------|
| British | Emma, Alice, Lily | George, Daniel, Lewis, Fable |
| American | Bella, Nova, Nicole, Sky | Adam, Michael, Eric, Liam |
| European | Dora | Alex, Santa |

### Other Voices
- **Piper:** `fable`, `alloy`, `echo`, `onyx`, `nova`, `shimmer`
- **EdgeTTS:** British/American/Australian incl. Ryan, Sonia, Libby, Ava, Andrew, Brian, Aria, Jenny
- **Inworld (paid):** Graham, Rupert, Olivia, Blake, Elizabeth, Dennis, Ashley, Luna

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KOKORO_URL` | Kokoro TTS endpoint (default: `http://kokoro-tts:8880/v1`) |
| `CHATTERBOX_URL` | Chatterbox Turbo endpoint (default: `http://chatterbox-tts:8004/v1`) |
| `TADA_URL` | TADA endpoint (default: `http://tada-tts:8005/v1`) |
| `VIBEVOICE_URL` | VibeVoice endpoint (default: `http://vibevoice-tts:8010/v1`; opt-in CUDA profile) |
| `QWEN3_URL` | Qwen3-TTS endpoint (default: `http://qwen3-tts:8011/v1`; opt-in CUDA profile) |
| `PIPER_URL` | Piper TTS endpoint (default: `http://piper-tts:8000/v1`) |
| `TTS_PROXY_URL` | Optional proxy for transcript capture / Edge/Polly/Inworld |
| `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME` | OpenAI-compatible LLM for the smart chapter guard, metadata + adaptive pronunciation. Optional (heuristic fallback). Free: Groq or Gemini — see `.env.example` |
| `AUDIOBOOKSHELF_DIR` / `AUDIOBOOKSHELF_HOST` / `AUDIOBOOKSHELF_USER` / `AUDIOBOOKSHELF_PORT` | Audiobookshelf rsync sync target |
| `LIBRARY_DIR` | Folder of ebooks to browse (default: `/mnt/openbooks`) |
| `APP_AUTH_USERNAME` / `APP_AUTH_PASSWORD` | Required environment-owned UI/API credentials; an empty password fails closed |
| `APP_TRUSTED_HOSTS` | Optional comma-separated Flask host allowlist (hostnames/IPs without ports) |
| `GPU_RENDER_ENABLED` | Environment-only host-admin gate for a separate manual paid Vast.ai action (default `0` / off; unavailable through Settings; queueing never provisions) |
| `AUTOSCALE_COST_CAP` | Safety cap for a manually authorized paid-GPU session; not an autoscale trigger |
| `ASR_VERIFY` | Structural source/audio comparison (default `1`); detects gross collapse/mismatch, never voice quality |
| `AUDIO_ASR_VERIFY_ENABLED` | Additional sampled structural ASR check after completion (default `0`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` | Telegram notifications and official webhook-secret validation |
| `INWORLD_API_KEY` / `AWS_*` | Paid engine credentials |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voices` | GET | List available voices (grouped by engine) |
| `/api/version` | GET | Build fingerprint (version + git SHA) |
| `/api/preview/<voice_id>` | GET | Voice preview audio |
| `/api/convert` | POST | Start conversion (upload) |
| `/api/library` / `/api/library/convert` | GET / POST | List / convert library books |
| `/api/jobs` | GET | List jobs |
| `/api/jobs/<id>/cancel` `/retry` `/delete` `/download` `/sync` `/logs` | — | Job actions |
| `/api/queue/status` `/pause` `/reorder` `/retry-failed` | — | Queue controls |
| `/api/settings` `/api/settings/pronunciations` | GET/POST | Settings + global pronunciation dictionary |
| `/api/gpu/status` `/api/gpu/scale-up` | — | GPU status / manual scale-up (environment-gated; cannot be armed through the web app) |

## Documentation

- [GETTING-STARTED.md](GETTING-STARTED.md) — new-user walkthrough
- [STATUS.md](STATUS.md) — current state, caveats & open issues
- [PREPROCESSING.md](PREPROCESSING.md) — the text pipeline & QA layers
- [ENGINES.md](ENGINES.md) — officially-sourced engine facts (the baseline)
- [OPERATIONS.md](OPERATIONS.md) — runbook & incident log
- [LOW-COST-TTS.md](LOW-COST-TTS.md) — engine bake-off, costs & GPU strategy
- [GPU-PLAYBOOK.md](GPU-PLAYBOOK.md) — one-command Vast GPU runbook
- [GPU-SAFETY.md](GPU-SAFETY.md) — cloud GPU cost-safety rules
- [PLAN.md](PLAN.md) — roadmap (adaptive QA, GPU, UI)
- [AGENTS.md](AGENTS.md) — guide for AI agents working in this repo

## Credits

- [Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi) / [Kokoro](https://github.com/hexgrad/kokoro) - neural TTS
- [Chatterbox](https://github.com/resemble-ai/chatterbox) - voice-cloning TTS
- [Hume TADA](https://github.com/HumeAI/tada) - text-audio-aligned TTS
- [Piper](https://github.com/rhasspy/piper) / [openedai-speech](https://github.com/matatonic/openedai-speech)
- [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) - core conversion tool
- Voice references: public-domain [LibriVox](https://librivox.org) narrators

## License

MIT License - see [LICENSE](LICENSE).

---

### Related Projects
- [audible-epub3-maker](https://github.com/funway/audible-epub3-maker) - EPUB3 Media Overlays (synced text + audio) with Gradio GUI.
