# EPUB to Audiobook Converter

**Version:** 1.3.x (repo)

A self-hosted web application for converting ebooks to audiobooks using AI text-to-speech. Features a modern tab-based UI with voice previews, library browsing, job management, and Audiobookshelf integration.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### TTS Engines
- **Kokoro TTS** - default local engine; good quality, very low runtime cost, CPU or Vast.ai GPU
  - British, American, European, and multilingual voice packs
  - Voice mixing support (blend two voices)
- **Piper TTS** - lightweight local fallback for low-resource systems
- **EdgeTTS** - free high-quality Microsoft neural voices via `tts-proxy`
- **AWS Polly** - legacy paid fallback via `tts-proxy`; not recommended for normal audiobook use because good-quality long-form output is too expensive
- **Inworld TTS 1.5** - optional premium paid voice engine via `tts-proxy`

See [LOW-COST-TTS.md](LOW-COST-TTS.md) for the current cost strategy and sub-GBP3/book options.

### Text Preprocessing (mandatory, engine-independent)

Every conversion runs a preprocessing pipeline before any TTS engine sees the
text — see [PREPROCESSING.md](PREPROCESSING.md):
- **Structural sanitization** - strips footnote/endnote markers and note bodies
  at the HTML level (`epub:type="noteref"`, digit-only `<sup>`/links), immune to
  publisher quote styles
- **Deterministic normalization** - unicode cleanup; numbers, years, currency,
  percentages, and abbreviations to spoken form (`$33 billion` becomes
  "thirty-three billion dollars")
- **Pronunciation rules** - LLM-generated per-book lexicon plus global and
  per-job regex rules
- **Planned** - per-book narration profiles and LLM chunk normalization
  (PREPROCESSING.md stages 4-5)

The upstream converter's `--remove_endnotes` flag is deliberately not used: it
corrupts decimals and alphanumerics (defect analysis in PREPROCESSING.md).

### Core Features
- **Extended Format Support** - EPUB, PDF, MOBI, AZW3, FB2, TXT, HTML, DOCX
- **Library Browser** - Browse and convert books from your OpenBooks collection
- **Voice Preview** - Listen to each voice before converting
- **Voice Search** - Quickly filter available voices
- **Voice Mixing** - Blend two Kokoro voices (e.g., `Emma+George`)
- **Chapter Selection** - Convert specific chapter ranges
- **Human-Readable Output** - Files renamed to `01 - Chapter Name.mp3`
- **Progress Tracking** - Real-time progress with ETA

### UI Features
- **Tab Navigation** - Convert, Queue, Library, Ops, History tabs
- **Design Modes** - Studio, Editorial, Technical, Minimal
- **4 Themes** - Light, Dark, Midnight, Forest
- **Responsive** - Works on desktop and mobile

### Integration
- **Audiobookshelf Sync** - Auto-sync completed books to ABS library
- **EPUB3 Read-Along Packaging** - Generate EPUB output with Media Overlay/SMIL work for synced text/audio workflows
- **Telegram Notifications** - Get notified when conversions complete
- **WhatsApp Notifications** - Optional WhatsApp alerts
- **Audio Fidelity Check (Optional)** - Sampled transcription check to detect dropped words
- **LLM Metadata & Pronunciation Help** - Optional OpenAI-compatible LLM settings for metadata and pronunciation lexicons
- **Download as ZIP** - Download complete audiobooks

## Quick Start

```bash
# Clone the repository
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook

# Start with Kokoro only
docker compose up -d

# Or start with both Kokoro and Piper
docker compose --profile piper up -d

# Access the UI
open http://localhost:8881
```

Note: The compose stack now includes a dedicated `worker` service for queue processing.

## Production Deployment

Use a single canonical stack path and deploy from a Git tag:

```bash
# On the target host
git clone https://github.com/davedavedavenm/epub-to-audiobook.git /home/dave/ai/lab/stacks/epub-to-audiobook
cd /home/dave/ai/lab/stacks/epub-to-audiobook
cp .env.example .env

# Deploy v1.3.0 (includes build metadata)
./scripts/deploy.sh v1.3.0

# Post-deploy smoke checks
./scripts/smoke-check.sh http://localhost:8881
```

## Available Voices

### Kokoro Voices (Local, Recommended)
| Accent | Female | Male |
|--------|--------|------|
| British | Emma, Alice, Lily | George, Daniel, Lewis, Fable |
| American | Bella, Nova, Nicole, Sky | Adam, Michael, Eric, Liam |
| European | Dora | Alex, Santa |

### Other Voices
- **Piper:** `fable`, `alloy`, `echo`, `onyx`, `nova`, `shimmer`
- **EdgeTTS:** British, American, and Australian voices including Ryan, Sonia, Libby, Ava, Andrew, Brian, Aria, Jenny, Natasha, and William
- **Polly legacy/avoid:** Ruth, Danielle, Gregory, Patrick
- **Inworld:** Graham, Rupert, Olivia, Blake, Elizabeth, Dennis, Ashley, Luna

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KOKORO_URL` | Kokoro TTS endpoint (default: `http://kokoro-tts:8880/v1`) |
| `PIPER_URL` | Piper TTS endpoint (default: `http://piper-tts:8000/v1`) |
| `TTS_PROXY_URL` | Optional proxy endpoint for transcript capture and non-Kokoro engines (usually `http://tts-proxy:8882`) |
| `INWORLD_API_KEY` | Inworld TTS key for premium voices |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | AWS Polly credentials |
| `AUDIOBOOKSHELF_DIR` | Path to sync completed books (empty = disabled) |
| `AUDIOBOOKSHELF_HOST` | Target host for Audiobookshelf sync (default: `docker-vm`) |
| `AUDIOBOOKSHELF_USER` | SSH user for Audiobookshelf sync (default: `dave`) |
| `AUDIOBOOKSHELF_PORT` | SSH port for Audiobookshelf sync (optional) |
| `LIBRARY_DIR` | Path to browse for ebooks (default: `/mnt/openbooks`) |
| `LOG_DIR` | Path for per-job log files (default: `/data/logs`) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications |
| `QUEUE_RUNNER_ENABLED` | Enable queue runner in this process (default: `1`) |
| `AUDIO_ASR_VERIFY_ENABLED` | Enable sampled ASR verification after completion (default: `0`) |
| `AUDIO_ASR_VERIFY_MODEL` | Whisper model for sampled ASR (`tiny`, `base`, etc.; default: `tiny`) |
| `AUDIO_ASR_VERIFY_MAX_FILES` | Max MP3 files to sample per job (default: `4`) |
| `AUTOSCALE_ENABLED` | Enable Vast.ai GPU autoscaling for Kokoro queues |
| `AUTOSCALE_THRESHOLD` | Queue depth before GPU scale-up is considered |
| `AUTOSCALE_COST_CAP` | Session cost cap for autoscaled GPU |

### Audiobookshelf Integration

Set `AUDIOBOOKSHELF_DIR` and configure SSH access from the container to your ABS host.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voices` | GET | List available voices |
| `/api/version` | GET | Build/deployment fingerprint (version + git SHA) |
| `/api/preview/<voice_id>` | GET | Get voice preview audio |
| `/api/convert` | POST | Start conversion job |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/<id>/cancel` | POST | Cancel running job |
| `/api/jobs/<id>/retry` | POST | Retry failed job |
| `/api/jobs/<id>/delete` | DELETE | Delete job from history |
| `/api/jobs/<id>/download` | GET | Download as ZIP |
| `/api/jobs/<id>/sync` | POST | Sync to Audiobookshelf |
| `/api/jobs/<id>/timeline` | GET | Derived pipeline stages for active job |
| `/api/jobs/<id>/logs` | GET | Recent job/container logs |
| `/api/queue/status` | GET | Queue paused state + queued count |
| `/api/queue/pause` | POST | Pause/resume queue processing |
| `/api/queue/reorder` | POST | Reorder queued jobs |
| `/api/queue/retry-failed` | POST | Bulk retry failed/cancelled jobs |
| `/api/diagnostics` | GET | Runtime diagnostics summary |
| `/api/library` | GET | List books in library |
| `/api/library/convert` | POST | Convert a library book |
| `/api/history` | GET | List completed conversions |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features including:
- Low/no-cost TTS engine evaluation
- Chatterbox/Kokoro-local experimentation
- Output polish such as M4B/OPUS and read-along improvements

## Deployment Notes

- See [archive/LIVE-DEPLOYMENT-STATUS.md](archive/LIVE-DEPLOYMENT-STATUS.md) for a historical host/runtime audit snapshot.

## Archive

- Historical plans and audits are stored in [`archive/`](archive/).

## Credits

- [Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi) - Neural TTS engine
- [Kokoro](https://github.com/hexgrad/kokoro) - Open-weight TTS model
- [Piper](https://github.com/rhasspy/piper) - Lightweight TTS
- [openedai-speech](https://github.com/matatonic/openedai-speech) - OpenAI-compatible Piper wrapper
- [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) - Core conversion tool

## License

MIT License - see [LICENSE](LICENSE) for details.


---

### Related Projects
- [audible-epub3-maker](https://github.com/funway/audible-epub3-maker) - Companion tool focused on EPUB3 Media Overlays (synced text and audio) with Gradio Web GUI support.
