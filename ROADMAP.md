# EPUB to Audiobook - Roadmap

## Current Features (v1.0.0)

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
- **Tab Navigation** - Convert, Queue, Library, History tabs
- **Modern Design** - 2-column layout, glassmorphism effects
- **6 Themes** - Midnight, Charcoal, Forest, Crimson, Purple, Ocean
- Responsive design for mobile

### Notifications
- Telegram notifications on job completion
- WhatsApp notification toggle (UI ready)

---

## Planned Features

### v1.1 - Notification Expansion
- [ ] **WhatsApp Integration** - Job notifications via WhatsApp Business API
- [ ] **Email notifications** - SMTP-based completion alerts
- [ ] **Webhook support** - Custom HTTP callbacks for automation

### v1.2 - Text Processing Improvements
- [ ] **Smart text extraction** - Improved EPUB parsing for better TTS quality
  - Strip headers/footers
  - Handle footnotes intelligently
  - Detect and skip non-prose content (tables, code blocks)
  - Normalize Unicode characters
- [ ] **Text preprocessing** - Clean up common OCR errors
- [ ] **Abbreviation expansion** - Expand common abbreviations for natural speech

### v1.3 - Voice Cloning (Experimental)
- [ ] **Chatterbox TTS** - Voice cloning with emotion control
  - Clone any voice from ~10 seconds of audio
  - Emotion/style control (happy, sad, angry, etc.)
  - Exaggeration control
  - See: https://github.com/resemble-ai/chatterbox

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
