# EPUB to Audiobook Converter

**Version:** 2.1.x (repo)

A self-hosted app for turning ebooks and articles into audiobooks. Its normal
path is local CPU, free of charge, with a web library, persisted voice
auditions, queue/recovery, text preprocessing, article podcast RSS and optional
Audiobookshelf delivery.

The product rule is deliberate: **use an existing good audiobook first**. This
app is the fallback when one is unavailable or unacceptable. When external
book acquisition is connected, it should request the audiobook before the
ebook and must not silently queue paid TTS.

> **New here? Start with the [full walkthrough → GETTING-STARTED.md](GETTING-STARTED.md)** — install, convert your first book, connect an AI for smarter pronunciation, add your own voices, and set up Audiobookshelf.

For current build state and remaining work see [STATUS.md](STATUS.md). Settled
choices live in [DECISIONS.md](DECISIONS.md); contributors and agents must check
that file before reopening an engine, cost or deployment question.

## Where this app fits

This repository starts at the **human decision to generate** an ebook or the
human action of sending an article URL. It does not own book discovery,
indexers, torrent/Usenet clients or the reading-list import. On Dave's homelab,
the canonical secret-free cross-host diagram and machine-readable inventory are
in the sibling private `infra` repo at
`docs/protocols/book-audiobook-system-map.md`; detailed acquisition repair stays
in `docs/protocols/book-acquisition-pipeline.md` there.

The boundary is intentional: Goodreads/LazyLibrarian may acquire and notify,
but may not automatically submit a book to this conversion queue. Local CPU is
the default after a person submits; free Kaggle is explicit per job; paid Vast
requires a separately authorised environment-gated session.

## The safe defaults

- **Quality first, then free, then the lowest measured cost per finished book,
  with a hard GBP2/book ceiling.**
- **Local CPU is the default.** No queue state can rent a GPU. Paid Vast
  rendering is an explicit operator-only action and is off by default.
- **Beatrice on Chatterbox Nano** is the default narrator. Piper is fully
  retired after its controlled listening failure; it is not a service, profile,
  fallback or selectable voice.
- **Voice Play buttons are cache reads.** They never start a hidden synthesis
  job. A voice appears in audition pickers only after a non-trivial preview MP3
  is persisted.
- **Human listening decides audio quality.** ASR is retained only to detect
  missing, repeated, truncated or grossly mismatched speech.
- **The LAN app is passwordless.** If published, protect the UI with one SSO
  layer at the reverse proxy. Expose only the exact podcast/feed paths a client
  cannot access through interactive SSO.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### TTS Engines
- **Chatterbox Nano** - default local engine with **Beatrice (Nano)** (`uk_female_samuel_nano`) as system default narrator. Fast CPU inference (~0.87x RTF, faster than realtime), voice-cloned British narrators (Beatrice, Arthur, Harriet, Edmund). The bootstrap helper and deployment wrapper enable its Compose profile automatically.
- **Kokoro TTS** - retained for compatibility/debug comparisons only. Its tested
  voices are retired from quality contention and it is never a paid-GPU target.
- **Chatterbox Turbo** - conditional voice-cloned narration engine. Earlier
  long-form controls were excellent, but the latest hard-text gate was mixed;
  audition it per book. Its official Turbo path does not expose V3's CFG or
  exaggeration controls. Enable with explicit `ENABLE_CHATTERBOX_PROFILE=1`.
- **Hume TADA** - expressive natural-voice model via TADA-1B. Enable with explicit `ENABLE_TADA_PROFILE=1` compose profile.
- **Pocket TTS 2.1** - free CPU-only opt-in book engine with all 21 officially
  documented English presets cached for immediate audition. It uses the
  listener-selected explicit number/currency text profile and current sentence
  packing. Enable with `ENABLE_POCKET_PROFILE=1`; it is not a default/fallback.
- **KittenTTS 0.8.1** - free CPU-only developer-preview book engine with all
  eight official presets cached for immediate audition. Opt in with
  `ENABLE_KITTEN_PROFILE=1`; it is not a default or automatic fallback.
- **Gemini 3.1 Flash TTS** - accepted opt-in **Free Tier only** book engine
  using the current Gemini Developer API. Achernar passed the long-form gate;
  all 30 official presets are registered and become selectable only after their
  exact previews are cached. Dave called Achernar's exact
  10:10 app-path file “one of the best”. The adapter has no paid/Vertex/Batch
  fallback, makes one request per 2–3 minute passage and resumes from a local
  passage cache after quota returns. Ten calls/day means a normal novel may
  take roughly four weeks; enable only with a dedicated unbilled project key.
  See [GEMINI-SETUP.md](GEMINI-SETUP.md) for the complete key, quota, cache and
  recovery walkthrough.
- **NVIDIA MagpieTTS v2607** - its pinned raw-NeMo free-T4 capacity gate passed,
  but all five short voices and the long arm failed listening with a shared
  early cut/clipping defect. It is not integrated or selectable. One focused
  official hosted-NIM comparison remains open to distinguish the public raw
  runtime from NVIDIA's production service. Exact facts: [ENGINES.md](ENGINES.md);
  safe one-request procedure: [NVIDIA-NIM-DIAGNOSTIC.md](NVIDIA-NIM-DIAGNOSTIC.md).
- **EdgeTTS** - free high-quality Microsoft neural voices via `tts-proxy`

### Web Application & Media Delivery
- **Studio Console Web UI** - modern dark obsidian slate theme with Google Fonts (Plus Jakarta Sans & JetBrains Mono)
- **Dedicated Articles Tab (`📰 Articles`)** - paste any article URL for instant narration, with fast QA bypass (sub-minute synthesis)
- **Podcast RSS 2.0 Feed (`/api/articles/rss`)** - automatic podcast feed for streaming articles directly in Pocket Casts, Overcast, Apple Podcasts, or Audiobookshelf
- **Owner-only Telegram capture** - send one URL or a multi-link message; every distinct article enters the same local/default-voice queue as the Articles tab
- **Library Batch Management** - select library ebooks and one cached narrator;
  that narrator determines the engine, so a preview can never be paired with a
  different synthesis backend.
- **Combined History** - completed books and articles in one newest-first record,
  with the actual narrator, engine, timestamp, ABS state, playback and explicit
  local/everywhere deletion.
- **Persistent Studio Player** - keeps playing across app tabs, advances through
  book chapters, and retains seek/playback-speed controls (1.0x–2.0x).

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
- **Structural QA** - optional Whisper comparison catches collapse,
  truncation/repetition and gross source mismatch. It does not grade a voice,
  accent, prosody or an isolated pronunciation.

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
- **Tabs** - Home, Articles, Add a book, Queue, Voices, History, Settings
- **Queue controls** - pause/resume, cancel, retry-all-failed, live log viewer
- **Preprocessing badge** - per-job "PRE ✓" with a summary of what was cleaned
- **Per-book render target** - choose **This machine** or explicit **Kaggle GPU
  (free)**. Ordinary jobs cannot select or provision a paid Vast GPU.
- **Real book covers** - epub cover art in the library, sorted most-recent-first
- **Guided, secure setup** - Settings has step-by-step Kaggle/LLM/ABS config
  with Test-Connection buttons; secrets persist on the `/data` volume, masked

### Integration
- **Audiobookshelf Sync** - Auto-sync completed books to ABS (each in its own
  folder; never overwrites existing audiobooks)
- **Predictable downloads** - one MP3 downloads directly; multi-chapter MP3
  books download as a ZIP so all chapter files arrive together.
- **EPUB3 Read-Along Packaging** - EPUB output with Media Overlay/SMIL
- **Telegram / WhatsApp Notifications** - optional completion alerts
- **Smart chapter guard** - the convert panel lists chapters by real title and
  auto-selects the actual book body (skips copyright pages, notes, index). Uses
  an LLM when configured, with a deterministic fallback so it works without one
- **LLM Integration** - any OpenAI-compatible provider (Groq, Gemini, OpenAI, …)
  for the chapter guard, metadata + adaptive pronunciation
- **Download as ZIP**

## Quick start

Everything runs in Docker on **local CPU by default** — no GPU and no cloud
account required.

```bash
# 1. Clone
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook

# 2. Linux/macOS: configure an absolute host path, start Nano and verify it
./scripts/bootstrap.sh

# Windows PowerShell instead:
# .\scripts\bootstrap.ps1

# 3. Open http://localhost:8881
```

The bootstrap helper does not overwrite an existing `.env`. It is important
because conversion containers need the clone's real absolute host path; copying
the placeholder `STACK_PATH` unchanged is not a working installation.

Do not start every profile “just in case”. Optional engines have different
resource/licence boundaries:

```bash
docker compose --profile chatterbox-nano --profile chatterbox up -d  # Turbo CPU/GPU
docker compose --profile chatterbox-nano --profile tada up -d        # TADA, heavy CPU
docker compose --profile chatterbox-nano --profile pocket up -d      # Pocket, CPU candidate
docker compose --profile chatterbox-nano --profile kitten up -d      # Kitten, CPU candidate
docker compose --profile chatterbox-nano --profile vibevoice up -d   # attached NVIDIA GPU only
docker compose --profile chatterbox-nano --profile qwen3 up -d       # attached NVIDIA GPU only
```

The Linux production wrapper enables Nano automatically and deploys webapp and
worker from the same Git revision:

```bash
./scripts/deploy.sh master
./scripts/smoke-check.sh http://localhost:8881
```

**Cost & privacy:** the default path spends nothing and sends your books to no
one. Optional paid Vast rendering is off by default, cannot be enabled in the
web Settings UI, and is never triggered by queue length. See
[GPU-SAFETY.md](GPU-SAFETY.md).

The app is intentionally passwordless on a trusted LAN. If it is exposed
outside that LAN, put it behind an authenticated reverse proxy such as Pangolin
SSO and include that public hostname in `APP_TRUSTED_HOSTS`; do not stack an
application HTTP Basic prompt behind proxy SSO. Podcast RSS/audio must bypass
SSO by narrowly scoped path rules because podcast clients cannot complete an
interactive login; the Telegram callback needs its own exact-path exception
and remains protected by Telegram's secret header plus the owner chat ID.
Article URL ingest accepts public HTTP(S) destinations only and
validates each redirect against DNS rebinding and local/private address access.

First run downloads model assets into Docker volumes. Voice preview warming is
load-throttled, skip-existing and switchable with `VOICE_CACHE_ON_START=0` on a
small host. `/api/voices` reports `cache.configured_ready` and
`cache.configured_total`; the Voices screen exposes only ready auditions.

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
./scripts/deploy.sh            # builds webapp/worker + Chatterbox Nano; optional engines stay opt-in
./scripts/smoke-check.sh http://localhost:8881
```

## Available Voices

### Chatterbox Turbo & TADA — British Human-Cloned (Opt-in)
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
- **Deepgram (cloud Aura-2 & Aura-1):** Orion, Orpheus, Arcas, Pandora, Hyperion, Angus
- **EdgeTTS:** British/American/Australian incl. Ryan, Sonia, Libby, Ava, Andrew, Brian, Aria, Jenny
- **Inworld (paid):** Graham, Rupert, Olivia, Blake, Elizabeth, Dennis, Ashley, Luna

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KOKORO_URL` | Kokoro TTS endpoint (default: `http://kokoro-tts:8880/v1`) |
| `CHATTERBOX_URL` | Chatterbox Turbo endpoint (default: `http://chatterbox-tts:8004/v1`) |
| `TADA_URL` | TADA endpoint (default: `http://tada-tts:8005/v1`) |
| `VIBEVOICE_URL` | VibeVoice endpoint (default: `http://vibevoice-tts:8010/v1`; opt-in CUDA profile; selected `cfg_scale=2.0`) |
| `QWEN3_URL` | Qwen3-TTS endpoint (default: `http://qwen3-tts:8011/v1`; opt-in CUDA profile) |
| `POCKET_URL` | Pocket TTS endpoint (default: `http://pocket-tts:8012/v1`; opt-in CPU profile) |
| `KITTEN_URL` | KittenTTS endpoint (default: `http://kitten-tts:8013/v1`; opt-in CPU profile) |
| `GEMINI_TTS_URL` / `GEMINI_API_KEY` | Internal free-only Gemini adapter and key from the dedicated `GEMINI_FREE_PROJECT_ID` whose Plan is Free; after verifying it, set `GEMINI_FREE_PROJECT_CONFIRMED=1` and opt in with `ENABLE_GEMINI_PROFILE=1`. Never commit the key or attach billing. Full procedure: [GEMINI-SETUP.md](GEMINI-SETUP.md). |
| `TTS_PROXY_URL` | Optional proxy for transcript capture / Deepgram/Edge/Polly/Inworld |
| `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME` | Optional OpenAI-compatible LLM for metadata and chapter classification (deterministic fallback; generated pronunciation rules are off by default). Groq users must choose a current ID from its official model/deprecation pages; see `.env.example`. |
| `AUDIOBOOKSHELF_DIR` / `AUDIOBOOKSHELF_HOST` / `AUDIOBOOKSHELF_USER` / `AUDIOBOOKSHELF_PORT` | Audiobookshelf rsync sync target |
| `LIBRARY_DIR` | Folder of ebooks to browse (default: `/mnt/openbooks`) |
| `APP_TRUSTED_HOSTS` | Comma-separated Flask host allowlist (LAN addresses and any Pangolin/reverse-proxy hostname; no ports) |
| `PUBLIC_BASE_URL` | Canonical public HTTPS origin used in RSS/channel/enclosure URLs when deployed behind Pangolin or another reverse proxy |
| `GPU_RENDER_ENABLED` | Environment-only host-admin gate for a separate manual paid Vast.ai action (default `0` / off; unavailable through Settings; queueing never provisions) |
| `AUTOSCALE_COST_CAP` | Safety cap for a manually authorized paid-GPU session; not an autoscale trigger |
| `ASR_VERIFY` | Structural source/audio comparison (default `1`); detects gross collapse/mismatch, never voice quality |
| `AUDIO_ASR_VERIFY_ENABLED` | Additional sampled structural ASR check after completion (default `0`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_WEBHOOK_SECRET` | Telegram notifications and official webhook-secret validation |
| `DEEPGRAM_API_KEY` / `INWORLD_API_KEY` / `AWS_*` | Cloud engine credentials |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voices` | GET | Voice catalogue plus configured preview-cache readiness |
| `/api/version` | GET | Build fingerprint (version + git SHA) |
| `/api/preview/<voice_id>` | GET | Persisted voice preview audio; never cold-renders |
| `/api/convert` | POST | Start conversion (upload) |
| `/api/articles/rss` | GET | Podcast RSS feed of completed article narrations |
| `/api/articles/narrate_url` | POST | Fetch a public article and queue it with the current local defaults |
| `/api/telegram/webhook` | POST | Secret- and owner-validated Telegram article capture callback |
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
- [PLAN-V5.md](PLAN-V5.md) — current forward plan
- [AGENTS.md](AGENTS.md) — guide for AI agents working in this repo

## Credits

- [Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi) / [Kokoro](https://github.com/hexgrad/kokoro) - neural TTS
- [Chatterbox](https://github.com/resemble-ai/chatterbox) - voice-cloning TTS
- [Hume TADA](https://github.com/HumeAI/tada) - text-audio-aligned TTS
- [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) - core conversion tool
- Voice references: public-domain [LibriVox](https://librivox.org) narrators

## License

MIT License - see [LICENSE](LICENSE).

---

### Related Projects
- [audible-epub3-maker](https://github.com/funway/audible-epub3-maker) - EPUB3 Media Overlays (synced text + audio) with Gradio GUI.
