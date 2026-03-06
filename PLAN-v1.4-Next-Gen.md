# PLAN v1.4: LLM Integration (Metadata & Lexicon)

## Overview
This phase integrates a generic OpenAI-compatible LLM layer (supporting providers like xAI/Z AI, Groq, DeepSeek, or OpenAI) to automate complex metadata generation and custom pronunciation dictionaries (Lexicons), dramatically improving the final polish of the generated audiobooks.

## Phase 1: Configuration UI & Backend Setup
- [x] **UI Update**: Add fields to the Settings tab for `LLM API Base URL`, `LLM API Key`, and `LLM Model Name`. This allows the user to plug in "Z AI" or any other compatible provider.
- [x] **Backend Settings**: Update `webapp/app.py` to persist and test these new LLM credentials via a dedicated `/api/settings/test_llm` endpoint.

## Phase 2: Automated Metadata Generation (Rec 4)
- [x] **LLM Processing Logic**: Write a utility function that takes the first few paragraphs of a book and asks the LLM to generate a JSON object containing a clean `title`, `author`, `summary`, and potential `tags`.
- [x] **Integration**: Inject this utility into the conversion pipeline so the generated metadata is injected into the EPUB's `metadata.json` right before it gets synced to Audiobookshelf.

## Phase 3: Automated Pronunciation Lexicon (Rec 2)
- [ ] **Entity Extraction**: Use the LLM to scan a sample of the book (or chapter by chapter) and identify complex Sci-Fi/Fantasy/Foreign names.
- [ ] **Phonetic Mapping**: Have the LLM return a dictionary mapping these complex names to phonetic spellings (e.g., `{"Daenerys": "Duh-nair-iss"}`).
- [ ] **Preprocessing Injection**: Automatically apply this generated dictionary in `tts_preprocess.py` alongside the existing rules.