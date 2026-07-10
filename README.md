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
- **Kokoro TTS** - default local engine; good quality, very low runtime cost, CPU or Vast.ai GPU
  - British, American, European, and multilingual voice packs
  - Voice mixing support (blend two voices)
- **Chatterbox Turbo** - production narration engine with official pacing
  controls; voice-cloned British narrators (Arthur, Edmund, Harriet, Beatrice)
  from public-domain LibriVox readers. Runs well on **CPU** (a few hours per
  novel) or GPU — no GPU required. Enable with the `chatterbox` compose profile.
- **Hume TADA** - highest natural-voice ceiling and most expressive, via
  TADA-1B; the same British narrators. A research model (no long-form/pacing
  controls) — strongest on shorter or dialogue-heavy text and happiest on a
  GPU. Enable with the `tada` compose profile.
- Which sounds best is **text- and hardware-dependent — judge by ear**; see
  [ENGINES.md](ENGINES.md) for officially-sourced facts and recorded listening
  outcomes.
- **Piper TTS** - lightweight local fallback for low-resource systems
- **EdgeTTS** - free high-quality Microsoft neural voices via `tts-proxy`
- **AWS Polly** - legacy paid fallback via `tts-proxy`; not recommended (good long-form output is too expensive)
- **Inworld TTS 1.5** - optional premium paid voice engine via `tts-proxy`

See [LOW-COST-TTS.md](LOW-COST-TTS.md) for the cost strategy and engine
bake-off, and add your own cloned voices per [GETTING-STARTED.md](GETTING-STARTED.md) §5.

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
- **_legacy_** - Fraunces + Hanken Grotesk, warm
  paper/ink/oxblood palette, light & dark themes
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
- **LLM Integration** - any OpenAI-compatible provider (Z AI, Groq, Gemini,
  OpenAI, …) for metadata + adaptive pronunciation
- **Download as ZIP**

## Quick Start (works on any machine, incl. for friends)

Everything runs in Docker on **local CPU by default** — no GPU and no cloud
account required.

```bash
# 1. Clone
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook

# 2. Configure (optional — defaults work out of the box)
cp .env.example .env

# 3. Start. Enable the engines you want via profiles:
docker compose up -d                                              # Kokoro only (fast)
docker compose --profile chatterbox up -d                        # + Chatterbox Turbo (best UK voices)
docker compose --profile tada up -d                              # + TADA (expressive; research model)
docker compose --profile piper --profile chatterbox --profile tada up -d   # everything

# 4. Open the UI
open http://localhost:8881
```

**Cost & privacy:** the default path spends nothing and sends your books to no
one. Optional **Cloud GPU** rendering (Vast.ai) is **off by default** and must
be enabled in Settings — see [GPU-SAFETY.md](GPU-SAFETY.md).

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
git clone https://github.com/davedavedavenm/epub-to-audiobook.git /opt/epub-to-audiobook
cd /opt/epub-to-audiobook
cp .env.example .env
./scripts/deploy.sh            # builds webapp/worker + chatterbox + tada + piper profiles
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
| `PIPER_URL` | Piper TTS endpoint (default: `http://piper-tts:8000/v1`) |
| `TTS_PROXY_URL` | Optional proxy for transcript capture / Edge/Polly/Inworld |
| `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL_NAME` | OpenAI-compatible LLM for metadata + adaptive pronunciation |
| `AUDIOBOOKSHELF_DIR` / `AUDIOBOOKSHELF_HOST` / `AUDIOBOOKSHELF_USER` / `AUDIOBOOKSHELF_PORT` | Audiobookshelf rsync sync target |
| `LIBRARY_DIR` | Folder of ebooks to browse (default: `/mnt/openbooks`) |
| `GPU_RENDER_ENABLED` | Master gate for paid Vast.ai GPU render (default `0` / off — see GPU-SAFETY.md) |
| `AUTOSCALE_ENABLED` | Vast.ai GPU autoscaling (default `false`) |
| `AUTOSCALE_COST_CAP` | Session cost cap for autoscaled GPU |
| `AUDIO_ASR_VERIFY_ENABLED` | Sampled ASR verification after completion (default `0`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram notifications |
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
| `/api/gpu/status` `/api/gpu/scale-up` | — | GPU status / scale-up (gated by `GPU_RENDER_ENABLED`) |

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
