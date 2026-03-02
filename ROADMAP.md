# EPUB to Audiobook - Roadmap

## Current Features (v1.3.x)

### TTS Engines
- **Kokoro TTS** - High-quality neural TTS with 22 voices (British, American, European, Italian)
- **Piper TTS** - Lightweight TTS with 7 high-quality voices (for low-resource systems)

### Core Features
- **Extended Format Support** - EPUB, PDF, MOBI, AZW3, FB2, TXT, HTML, DOCX (via Calibre)
- **Library Browser** - Browse and convert books from OpenBooks collection
- Voice preview before conversion
- Voice search/filter
- Voice mixing (Kokoro only) - blend two voices
- Chapter selection - convert specific chapter ranges
- Human-readable output file naming
- Job queue with progress tracking
- Audiobookshelf integration (auto-sync completed books)

### UI Features
- **Tab Navigation** - Convert, Queue, Library, Ops, History tabs
- **Design Modes** - Studio, Editorial, Technical, Minimal
- **4 Themes** - Light, Dark, Midnight, Forest
- Responsive design for mobile

### Notifications
- Telegram notifications on job completion
- WhatsApp notifications via Evolution API

### Reliability & Operations
- Queue pause/resume, reorder, and bulk retry controls
- Restart recovery for in-flight jobs
- Auto-retry with capped backoff
- Watchdog monitoring for stalled/dead conversion containers

---

## Planned Features

### v1.1 - Notification Expansion
- [ ] **WhatsApp Integration** - Job notifications via WhatsApp Business API
- [ ] **Email notifications** - SMTP-based completion alerts
- [ ] **Webhook support** - Custom HTTP callbacks for automation

### v1.2 - Text Processing Improvements
- [ ] **EPUB3 Media Overlays (SMIL) Generation** - Move away from raw MP3 folders. Generate enriched EPUB3 files with force-aligned text and audio (SMIL files) to enable "Read-Along" syncing in Audiobookshelf.
- [ ] **NLP Sentence Tokenization & Pacing** - Replace regex breath injection with proper NLP sentence tokenization (e.g., `nltk` or `spacy`). Send individual sentences to the TTS engine and programmatically insert precise millisecond silences between sentences and paragraphs for natural pacing without corrupting prosody.
- [ ] **Smart text extraction** - Improved EPUB parsing for better TTS quality
  - Strip headers/footers
  - Handle footnotes intelligently
  - Detect and skip non-prose content (tables, code blocks)
  - Normalize Unicode characters
- [ ] **Text preprocessing** - Clean up common OCR errors
- [ ] **Abbreviation expansion** - Expand common abbreviations for natural speech

### v1.3 - High-Fidelity & Intent-Aware TTS (Polly Long-Form Alternatives)
- [ ] **Commercial "Long-Form" API Fallbacks** - Integrate pay-as-you-go commercial APIs (like Async Voice API, OpenAI TTS, or ElevenLabs) to offer an on-demand "Polly Long-Form" tier of quality for specific books, bypassing the need for heavy local GPU cloning.
- [ ] **Next-Gen Open-Weight Tracking** - Monitor HuggingFace TTS Arena for zero-cost, intent-aware models (e.g., F5-TTS, advanced Kokoro variants) that match commercial long-form prosody without the API cost.

### Future Considerations
- [ ] Background music/ambient sound mixing
- [ ] Chapter artwork extraction and embedding
- [ ] Batch processing multiple books
- [ ] Web-based audio player preview
- [ ] Multiple output formats (M4B, OPUS)
- [ ] Auto-convert watchdog (monitor folder for new files)

---

## Contributing

Feature requests and pull requests welcome!
