# EPUB to Audiobook - Roadmap

## Current Features (v1.3.x)

### TTS Engines
- **Kokoro TTS** - High-quality neural TTS with 22 voices (British, American, European, Italian)
- **Piper TTS** - Lightweight TTS with 7 high-quality voices (for low-resource systems)
- **EdgeTTS** - Free Microsoft neural voices through `tts-proxy`
- **AWS Polly** - Legacy paid fallback through `tts-proxy`; avoid for normal audiobook use because good-quality long-form output is too expensive
- **Inworld TTS 1.5** - Experimental premium fallback through `tts-proxy`

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
- EPUB3 read-along packaging work with Media Overlay/SMIL generation
- Optional LLM-assisted metadata and pronunciation lexicon generation

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
- [x] **WhatsApp Integration** - Job notifications via Evolution API
- [ ] **Email notifications** - SMTP-based completion alerts
- [ ] **Webhook support** - Custom HTTP callbacks for automation

### v1.2 - Text Processing Improvements
- [x] **EPUB3 Media Overlays (SMIL) Generation** - Generate enriched EPUB3 files with Media Overlay/SMIL work for read-along syncing.
- [x] **NLP Sentence Tokenization & Pacing** - Replaced prosody-breaking regex breath injection with safer TTS preprocessing.
- [ ] **Smart text extraction hardening** - Improved EPUB parsing for better TTS quality
  - Strip headers/footers
  - Handle footnotes intelligently
  - Detect and skip non-prose content (tables, code blocks)
  - Normalize Unicode characters
- [ ] **Text preprocessing** - Clean up common OCR errors
- [x] **Abbreviation/number/year handling** - Expand common patterns for natural speech

### v1.3 - Low-Cost Quality TTS
- [x] **Budget rule documented** - Keep normal conversions under GBP3/book, preferably much less. See [LOW-COST-TTS.md](LOW-COST-TTS.md).
- [x] **Polly de-prioritized** - Good-quality Polly long-form is too expensive for this project and should not be used as a default path.
- [x] **Chatterbox Turbo proof-of-concept (stage 1)** - Sampled 2026-07-02 via free HF Space against Kokoro Fable/Emma and EdgeTTS Ryan on a stress-test passage; judged a clear improvement. Next: real-book passage test, British reference voice, deploy devnen/Chatterbox-TTS-Server (OpenAI-compatible) beside Kokoro. See [LOW-COST-TTS.md](LOW-COST-TTS.md).
- [ ] **Lemonfox trial** - Only if Chatterbox Turbo disappoints; its advertised pricing fits the budget.
- [ ] **Kokoro latest audit** - Confirm the deployed Kokoro-FastAPI image is using the best current Kokoro model/voice set. (No new Kokoro model since v1.0, Jan 2025.)
- [ ] **Next-gen open-weight tracking** - Monitor Chatterbox, Hume TADA, Voxtral, IndexTTS-2, CosyVoice2, and similar models that could improve quality without per-character billing.

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
