# v1.2 Implementation Plan: Text Processing & EPUB3 Overlays

## Objective
Implement high-quality NLP-based text tokenization for precise TTS pacing and replace the raw MP3 folder output with a standard EPUB3 file containing synchronized SMIL Media Overlays (Read-Along support).

## Stage 1: Replace Regex Pacing with NLP Tokenization
- **Goal:** Remove the hacky regex in `tts_preprocess.py` that injects commas. Replace it with proper sentence splitting (e.g. using `nltk` or `re` based sentence boundaries) to preserve prosody.
- **Action Items:**
  1. Deprecate `inject_breaths` regex rule in `webapp/tts_preprocess.py`.
  2. Evaluate and add a lightweight sentence tokenizer.
  3. Validate end-to-end processing with Playwright CLI by queuing a book and ensuring the text preprocessing completes without errors.
  4. Commit changes.

## Stage 2: EPUB3 SMIL Media Overlays Generation
- **Goal:** Emulate the approach of `audible-epub3-maker` to embed the output audio and generate SMIL files within the EPUB container for read-along synchronization.
- **Action Items:**
  1. Refactor `app.py` / `worker.py` where `ghcr.io/p0n1/epub_to_audiobook` is invoked.
  2. Implement or integrate EPUB3 packing logic alongside audio generation. (Note: Replacing `p0n1` entirely might be a massive undertaking. A mid-way step is to generate SMIL files post-conversion using the transcripts, or transition fully to a custom parser).
  3. Validate end-to-end conversion via Playwright CLI.
  4. Commit changes.

## Stage 3: High-Fidelity API Integrations Framework (v1.3 Prep)
- **Goal:** Setup the base provider classes for Commercial APIs (Async Voice API) for future high-fidelity usage.
- **Action Items:**
  1. Add provider stubs in `app.py` for API fallbacks.
  2. Add UI toggles (if necessary).
  3. Commit changes.
