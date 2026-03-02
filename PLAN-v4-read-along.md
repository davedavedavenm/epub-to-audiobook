# PLAN v4: The "Read-Along" Transition (Stage 2)

## Status Update (March 2026)
We are actively transitioning the application to support **EPUB3 SMIL Media Overlays** (Read-Along) while improving base TTS pacing using NLP. 
The Windows dev environment has been decommissioned in favor of deploying directly to the primary Zorin host (`192.168.1.88`).

## 1. Stage 1: NLP Pacing (Completed & Deployed)
- Replaced legacy regex comma-injection with `nltk` sentence tokenization.
- **Edge TTS Integration**: Edge TTS is now routed through the `tts-proxy` rather than executing directly inside the `p0n1` container. This ensures Edge conversions benefit from both NLP pacing and the new timing capture.

## 2. Stage 2: Timing Logs & EPUB3 Foundation (Completed)
- **TTS Proxy Upgrades**: `tts_proxy/proxy.py` now imports `mutagen` and `edge-tts`. It intercepts all speech synthesis, calculates the precise audio duration (`duration_s`), and logs it to `chunks.jsonl`.
- **EPUB3 Skeleton**: Added `epub_generator.py` to the webapp. The finalization flow now triggers this module to generate a base EPUB3 container holding the audio files and XHTML documents.
- **Docker Updates**: Added `ebooklib`, `beautifulsoup4`, `lxml` to the webapp image, and `mutagen`, `edge-tts` to the proxy image.

## 3. Immediate Next Steps (Zorin Deployment & Execution)
The immediate focus on the Zorin host is to resolve lingering deployment snags and implement the core SMIL alignment logic.

### A. Environment Recovery
- Restore the UI/UX templates (`index.html`) which were temporarily degraded during UTF-16 debugging.
- Fix the `copy_to_audiobookshelf` SSH permission error. The Docker NTFS mount workaround failed on Windows, but the Zorin deployment requires a robust SSH key configuration (likely using a dedicated volume or correct host permissions).

### B. Stage 2.5: SMIL Generation Engine
- **HTML Parsing**: Update `epub_generator.py` to parse the original EPUB's XHTML content.
- **Instrumentation**: Inject unique `<span>` IDs around every sentence in the text.
- **Alignment**: Map the `duration_s` values from `chunks.jsonl` to the corresponding `<span>` IDs.
- **Assembly**: Generate valid `.smil` XML files and pack them into the final `.epub` container.

### C. Validation (Full E2E)
- Run a multi-chapter conversion using Kokoro or Edge.
- Verify the final EPUB3 imports correctly into Audiobookshelf and that the Read-Along tracking highlights the text in sync with the audio.

---
*Authored during the migration from Windows Dev to Zorin Prod.*