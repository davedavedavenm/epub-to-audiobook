# PLAN: UI/UX Refinement and Feature Adjustments

## Overview
This plan addresses user feedback regarding terminology inconsistencies, UI layout issues, missing functionality in History/Settings, and clarity around job states and GPU usage. All changes will be executed in phases, validated via Playwright browser tests, and pushed to Git.

## Phase 1: Terminology & Layout Alignment
- [ ] **Upload Tab Alignment**: Ensure the tab label and page title both say "Upload" (currently tab says Upload, page says Convert).
- [ ] **Config/Settings Alignment**: Ensure the tab and page title consistently use "Settings".
- [ ] **Queue Button Layout**: Fix the "Resume from failure" button text wrapping/hanging issue to ensure a clean UI.
- [ ] **Default Voice**: Set the default selected voice to Edge TTS `en-GB-RyanNeural`.

## Phase 2: Queue & History Improvements
- [ ] **Queue Status Clarity**: Fix the issue where jobs show 100% alongside "Resume from failure". Clarify whether a job like "Alice at 35%" is actively running or stuck.
- [ ] **History Downloads**: Update the History tab to provide two distinct download options: one for the generated Audiobook (ZIP) and one for the source/instrumented EPUB.

## Phase 3: Settings, API Keys & Documentation
- [ ] **Settings Validation**: Add indicators to show whether current settings are valid/active.
- [ ] **Vast.ai / GPU Settings**: Expose Vast.ai configuration settings so the user knows if/when the GPU will be used.
- [ ] **Amazon Polly**: Add input fields for Amazon Polly credentials.
- [ ] **Documentation**: Restore extensive documentation for non-technical users directly within the app (Settings/Help area). Explain the purpose of the OpenAI API key.
- [ ] **GPU Icon Clarity**: Clarify the bottom-left idle icon (add a tooltip or descriptive text explaining what it means regarding GPU usage).

## Phase 4: Library & Voice Features
- [ ] **Library Existing Audiobooks**: Add a visual indicator in the Library tab if a book has already been converted to an audiobook.
- [ ] **Voice Previews**: Implement caching/previewing functionality for all voices without altering the existing Voices UI layout.

---
*Execution Rule: Each phase will be implemented sequentially and validated with Playwright before moving to the next.*
