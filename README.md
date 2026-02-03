# EPUB to Audiobook Converter

**Version:** 0.9.0

A self-hosted web application for converting EPUB and PDF files to audiobooks using AI text-to-speech. Features a modern dark-themed UI with voice previews, job management, and Audiobookshelf integration.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### TTS Engines
- **Kokoro TTS** - High-quality neural TTS (~13.8GB RAM)
  - 22 voices: British, American, European, Italian accents
  - Voice mixing support (blend two voices)
- **Piper TTS** - Lightweight neural TTS (~46MB RAM)
  - 7 high-quality voices
  - Perfect for low-resource systems

### Core Features
- **EPUB & PDF Support** - Upload EPUB files directly or PDFs (auto-converted via Calibre)
- **Voice Preview** - Listen to each voice before converting
- **Voice Mixing** - Blend two Kokoro voices (e.g., `Emma+George`)
- **Chapter Selection** - Convert specific chapter ranges
- **Human-Readable Output** - Files renamed to `01 - Chapter Name.mp3`
- **Progress Tracking** - Real-time progress with ETA

### Integration
- **Audiobookshelf Sync** - Auto-sync completed books to ABS library
- **Telegram Notifications** - Get notified when conversions complete
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

## Available Voices

### Kokoro Voices (High Quality)
| Accent | Female | Male |
|--------|--------|------|
| British | Emma, Alice, Lily | George, Daniel, Lewis, Fable |
| American | Bella, Nova, Nicole, Sky | Adam, Michael, Eric, Liam |
| European | Dora | Alex |
| Italian | Sara | Nicola |

### Piper Voices (Lightweight)
| Voice | Accent | Gender |
|-------|--------|--------|
| Cori | British | Female |
| Lessac | American | Female |
| LJ Speech | American | Female |
| Ryan | American | Male |
| LibriTTS 1-3 | American | Neutral |

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KOKORO_URL` | Kokoro TTS endpoint (default: `http://kokoro-tts:8880/v1`) |
| `PIPER_URL` | Piper TTS endpoint (default: `http://piper-tts:8000/v1`) |
| `AUDIOBOOKSHELF_DIR` | Path to sync completed books (empty = disabled) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications |

### Audiobookshelf Integration

Set `AUDIOBOOKSHELF_DIR` and configure SSH access from the container to your ABS host.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voices` | GET | List available voices |
| `/api/preview/<voice_id>` | GET | Get voice preview audio |
| `/api/convert` | POST | Start conversion job |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/<id>/cancel` | POST | Cancel running job |
| `/api/jobs/<id>/retry` | POST | Retry failed job |
| `/api/jobs/<id>/download` | GET | Download as ZIP |
| `/api/jobs/<id>/sync` | POST | Sync to Audiobookshelf |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features including:
- WhatsApp notifications
- Smart text extraction for better TTS
- Chatterbox voice cloning (experimental)

## Credits

- [Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi) - Neural TTS engine
- [Piper](https://github.com/rhasspy/piper) - Lightweight TTS
- [openedai-speech](https://github.com/matatonic/openedai-speech) - OpenAI-compatible Piper wrapper
- [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) - Core conversion tool

## License

MIT License - see [LICENSE](LICENSE) for details.
