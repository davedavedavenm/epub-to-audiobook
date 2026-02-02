# EPUB to Audiobook Converter

**Version:** 0.9.0

A self-hosted web application for converting EPUB and PDF files to audiobooks using AI text-to-speech. Features a modern dark-themed UI with voice previews, job management, and Audiobookshelf integration.

![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### Core
- **EPUB & PDF Support** - Upload EPUB files directly or PDFs (auto-converted via Calibre)
- **22 English Voices** - Curated selection of British, European, and American accents
- **Voice Preview** - Listen to each voice before converting
- **Background Processing** - Conversions run in Docker containers with progress tracking
- **Job Management** - Queue, cancel, retry, and delete conversion jobs
- **Human-Readable Output** - Files renamed to `01 - Chapter Name.mp3` format

### Advanced Options
- **Voice Mixing** - Blend two voices together using Kokoro's `voice1+voice2` syntax
- **Chapter Selection** - Convert specific chapter ranges for testing
- **Telegram Notifications** - Get notified when conversions complete
- **Progress Tracking** - Real-time progress bar with ETA

### Integration
- **Audiobookshelf Sync** - Automatically copy completed books to your ABS library
- **Download as ZIP** - Download complete audiobooks for offline use

## Screenshots

The UI features 6 dark themes: Midnight (default), Charcoal, Forest, Crimson, Purple Haze, and Ocean.

## Requirements

- Docker and Docker Compose
- ~4GB RAM for TTS engine
- Storage for audiobooks (varies by book length)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/epub-to-audiobook.git
cd epub-to-audiobook

# Configure (optional)
cp .env.example .env
# Edit .env with your settings

# Start the stack
docker compose up -d

# Access the UI
open http://localhost:8881
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KOKORO_URL` | `http://kokoro-tts:8880/v1` | Kokoro TTS API endpoint |
| `HOST_STACK_DIR` | `/home/dave/stacks/epub-to-audiobook` | Host path for volume mounts |
| `AUDIOBOOKSHELF_DIR` | `` | Path to sync completed books (empty = disabled) |
| `TELEGRAM_BOT_TOKEN` | `` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | `` | Telegram chat ID for notifications |

### Audiobookshelf Integration

To enable automatic sync to Audiobookshelf:

1. Set `AUDIOBOOKSHELF_DIR` to your ABS audiobooks path
2. Ensure the webapp container has SSH access to your ABS host
3. Mount your SSH key in the container

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │────▶│    Flask UI     │
│                 │     │   (port 8881)   │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐           ┌───────▼───────┐
              │  Kokoro   │           │ epub_to_audio │
              │   TTS     │◀──────────│   (Docker)    │
              │(port 8880)│           └───────────────┘
              └───────────┘
```

## Available Voices

### British (11 voices)
- **Female:** Emma, Alice, Lily, Emma Classic, Isabella
- **Male:** George, Daniel, Lewis, Fable, George Classic, Lewis Classic

### European (3 voices)
- **Female:** Dora
- **Male:** Alex, Santa

### American (8 voices)
- **Female:** Bella, Nova, Sky, Nicole
- **Male:** Adam, Michael, Eric, Liam

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/voices` | GET | List available voices |
| `/api/preview/<voice_id>` | GET | Get voice preview audio |
| `/api/convert` | POST | Start conversion job |
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/<id>` | GET | Get job status |
| `/api/jobs/<id>/cancel` | POST | Cancel running job |
| `/api/jobs/<id>/retry` | POST | Retry failed job |
| `/api/jobs/<id>/download` | GET | Download as ZIP |
| `/api/jobs/<id>/sync` | POST | Sync to Audiobookshelf |
| `/api/jobs/<id>/delete` | DELETE | Delete job and files |

## Roadmap

### v1.0 - Current Goals
- [ ] Multiple TTS engine support
- [ ] Batch conversion queue
- [ ] M4B single-file output option
- [ ] Chapter metadata from EPUB TOC

### v1.1 - Piper TTS Integration (Planned)
Add [Piper1-GPL](https://github.com/OHF-Voice/piper1-gpl) as an alternative TTS engine:
- Fast, local neural TTS
- Community-trained voices for multiple languages
- Lower resource usage than Kokoro
- No GPU required

### v2.0 - Chatterbox Voice Cloning (Future Ambition)
Integrate [Chatterbox](https://github.com/resemble-ai/chatterbox) for advanced voice capabilities:
- **Zero-shot voice cloning** - Clone any voice from ~5 seconds of audio
- **Emotion control** - Adjust expressiveness from monotone to dramatic
- **Paralinguistic tags** - Add [laugh], [cough], [sigh] for realism
- **25+ languages** - Multilingual support out of the box

This would enable:
- Narrate books in a specific person's voice
- Create custom narrator personas
- Match existing audiobook narrator styles

> Note: Chatterbox requires reference audio files for voice cloning, making it more complex to integrate than preset-voice engines like Kokoro or Piper.

## Development

```bash
# Run locally (requires Python 3.11+)
cd webapp
pip install -r requirements.txt
python app.py

# Run tests
pytest

# Build Docker image
docker build -t epub-to-audiobook-webapp ./webapp
```

## Troubleshooting

### Conversion fails immediately
- Check Kokoro TTS is running: `curl http://localhost:8880/v1/audio/voices`
- Ensure Docker socket is mounted in webapp container

### No audio output
- Verify EPUB has text content (not just images)
- Check job logs in the webapp container

### PDF conversion fails
- PDFs are converted via Calibre - some complex PDFs may fail
- Try converting PDF to EPUB manually first

## Credits

- [Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi) - TTS engine
- [epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook) - Core conversion tool
- [Calibre](https://calibre-ebook.com/) - PDF to EPUB conversion

## License

MIT License - see [LICENSE](LICENSE) for details.
