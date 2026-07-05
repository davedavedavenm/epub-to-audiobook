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
- [x] **Footnote/endnote handling** - Structural HTML sanitization (2026-07); superseded the upstream `--remove_endnotes` flag, which corrupted decimals. See [PREPROCESSING.md](PREPROCESSING.md).
- [x] **Normalize Unicode characters** - Exotic spaces, soft hyphens, zero-width chars (2026-07).
- [x] **Abbreviation/number/year handling** - Expand common patterns for natural speech
- [ ] **Non-prose detection** - Skip/handle tables, code blocks, headers/footers
- [ ] **Text preprocessing** - Clean up common OCR errors

### v1.5 - Preprocessing-First Direction (2026-07)
**Decision: text preprocessing is mandatory for every conversion, whichever
voice engine is used.** The Abundance listening test proved the worst quality
problems were text defects, not voice defects. Full design: [PREPROCESSING.md](PREPROCESSING.md).
- [x] **Stage 1: Structural EPUB sanitizer** - noteref/sup/digit-link markers and note bodies removed at HTML level; applied to `_tts.epub` copy; recovery paths use the same copy.
- [x] **Stage 2: Deterministic normalization hardening** - unicode cleanup, safe endnote fallback regexes, currency scale-word ordering ($33 billion -> "thirty-three billion dollars").
- [x] **Stage 3: Pronunciation rules** - LLM lexicon + global/per-job `--search_and_replace_file` (pre-existing, kept).
- [ ] **Stage 4: Per-book narration profile** - one LLM pass over sampled excerpts produces a stored, reviewable profile (domain, entity lexicon, structural fingerprint, number style) that steers all other stages.
- [ ] **Stage 5: LLM chunk normalization** - flash-tier LLM pass per ~4k-char chunk with profile in system prompt, length/content guardrails, free-tier throttling.

### v1.6 - Next-Gen Engine + UI Upgrade (planned, blocked on engine decision)
Implementation plan: [PLAN-ENGINE-UI.md](PLAN-ENGINE-UI.md). Bake-off status and verdicts: [LOW-COST-TTS.md](LOW-COST-TTS.md).
- [ ] **Phase A: Chatterbox Turbo engine** - compose service (devnen server, UK LibriVox voices from `data/voice_refs/`), app.py plumbing at all three `tts_engine` sites, UI engine/voice entries, ETA model, Vast template, smoke checks.
- [ ] **Phase B: TADA engine** - only if TADA wins; requires OpenAI-compatible wrapper + RTX 3060 benchmark first.
- [ ] **Phase C: Preprocessing UI** - per-job "preprocessed" badge, narration profile review panel (Stage 4), voice audition helper.

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
