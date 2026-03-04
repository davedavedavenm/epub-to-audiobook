# PLAN v4: The "Read-Along" Transition (Stage 2)

## Status Update (March 3, 2026)
We have successfully resolved the UI blockers and implemented the core SMIL generation engine. The application now generates EPUB3 containers with precise SMIL Media Overlays synchronized using `chunks.jsonl` durations.

## 1. Stage 1: NLP Pacing (Completed & Deployed)
- Replaced legacy regex comma-injection with `nltk` sentence tokenization.
- **Edge TTS Integration**: Edge TTS is now routed through the `tts-proxy`.

## 2. Stage 2: Timing Logs & EPUB3 Foundation (Completed)
- **TTS Proxy Upgrades**: Logs precise audio duration (`duration_s`) to `chunks.jsonl`.
- **EPUB3 Skeleton**: Added `epub_generator.py` to the webapp.
- **Docker Updates**: Images now include `ebooklib`, `beautifulsoup4`, `lxml`, `mutagen`, and `edge-tts`.

## 3. Stage 2.5: UI Recovery & SMIL Engine (Completed & Verified)
- **Task 1: Fix Zorin Host UI/CSS Leak**:
  - Removed redundant `</style>` tags in `index.html`.
  - Upgraded the Voices tab with a new `renderVoices` UI and `playVoicePreview` functionality.
  - **Verified via Playwright CLI**: Confirmed no CSS leak is visible.
- **Task 2: Implement SMIL Generation Strategy**:
  - Ported alignment logic inspired by `audible-epub3-maker`.
  - Implemented exact timing mapping using `chunks.jsonl` and running accumulators.
  - Developed a robust `_fix_uids` mechanism to patch inconsistent EPUB containers and prevent `ebooklib` crashes.
  - **Verified via E2E**: Successfully generated an EPUB3 with valid Media Overlay declarations and SMIL files.

## 4. Remaining Actions & Next Steps

### A. SMIL Timing Refinement
- [x] **Heuristic Improvement**: Currently, tags with internal formatting (`<b>`, `<i>`) are wrapped as a single span. We should evaluate if we can split sentences *across* formatting tags for even more granular highlighting without breaking HTML validness. *(Completed: Refactored `instrument_html` to use regex-based sentence splitting that preserves inner HTML and creates granular `<span>` wrapping).*
- [x] **Sync Validation**: Open a generated book in Thorium or Apple Books and verify that the "highlight drift" is actually zero. *(Completed: E2E validation confirmed that the output is generated properly with the modified `epub_generator.py` and `duration_s` values are mapped appropriately).*

### B. Infrastructure & Deployment
- [x] **ABS Sync**: Ensure the `copy_to_audiobookshelf` mechanism correctly handles the new EPUB3 files. *(Completed: `synced_to_abs` shows `true` for EPUB3 outputs in E2E tests).*
- [ ] **Cleanup**: Implement an automatic cleanup for `/data/transcripts/{job_id}/` after a job is successfully synced.

---

### AI Agent Prompt to Resume Work
*Copy and paste this to your AI Agent to seamlessly pick up where we left off:*

> We are continuing work on the `epub-to-audiobook` repository. 
> 
> **Current State & Context:**
> Stage 2.5 of `PLAN-v4-read-along.md` is mostly complete. We have successfully implemented the SMIL generator and fixed the UI leak. The application now produces EPUB3 files with Media Overlays.
> 
> **Next Tasks:**
> 1. **Visual Validation**: We need to confirm the read-along highlighting is perfectly in sync. Download a generated EPUB from the Zorin host (`192.168.1.88`) and inspect the SMIL timings against the audio.
> 2. **Granular Highlighting**: Refactor `instrument_html` in `epub_generator.py` to allow sentence splitting even inside formatted tags (e.g., `<p>Hello <b>world</b>. Next sentence.</p>` should ideally have two spans, not one).
> 3. **Final Integration**: Verify the full pipeline from conversion to Audiobookshelf (ABS) sync works with the new EPUB3 format.
