# Cillian Recipe — Fish S2 Pro Production Method (LOCKED 2026-09-22)

This is the locked, proven production method for **The Armed Struggle: The Story of
the IRA** narrated by the **Cillian Murphy** voice, and the baseline recipe for any
book narrated with this voice. Every element below was adopted through Dave's
listening verdicts across 2026-09-20/22 (see `DECISIONS.md` and
`TTS-WATCH-FINDINGS.md` for the full evidence trail).

## Engine & voice

| Component | Value |
|---|---|
| Engine | Fish Speech **S2 Pro** (`fishaudio/s2-pro`, 4.4B Dual-AR + DAC codec) |
| Hardware | **Free Kaggle T4×2** only — NO Modal, NO paid GPU (standing rule) |
| Narration reference | `chatterbox/voices/cillian_irish.wav` (28s clip) — Dave: "perfect" |
| Quote/dramatic reference | expressive crop `crop_expressive_tail.wav` (last 9.9s of the same clip) — Dave: "probably the best" |
| Precision | `--half` (fp16; T4 has no bf16) |
| Temperature | **0.85** (narration AND quotes; 0.7 = flat, 1.0 = drifts American) |
| Sampling | top_p 0.9, top_k 30, iterative_prompt, chunk_length 300, seed 42 (re-rolls 43/44) |
| Licence | Boson-class non-commercial personal use; Fish licence terms per DECISIONS 2026-09-18 entry |

## Text preparation (in order)

1. **Irish lexicon** (`fixtures/irish_pronunciation_lexicon.json`), longest-first exact
   replacement. Includes Dáil Éireann→"Dawl Air-inn", Taoiseach→"Teeshock",
   Tánaiste→"Tawnashta" (corrected 2026-09-22), Dún Laoghaire→"Doon Leery",
   Portlaoise→"Portleesh", Sinn Féin→"Shin Fayn", IRA→"I-R-A", Fianna Fáil→"Fee-na
   Fawl", person names, etc. **Books carry their own glossary additions** (data, not code).
2. **Dates → words**: "12 July 1921" → "the twelfth of July nineteen twenty-one"
   (handles 12th/12 forms; Dave verdict: cardinals are wrong).
3. **Year ranges** ("1923–63" → "nineteen twenty-three to sixty-three") and
   **standalone years** → words. Zero digit-years may remain in the payload (checked).
4. **Numbers/currency → words**: "4,500" → "four thousand five hundred",
   "£15 million" → "fifteen million pounds".
5. **Orphan merge**: fragments without terminal punctuation (<3 words) merge into
   the following sentence (kills the "F." / "At the" defect class).
6. **Quote detection**: sentences containing an opening ‘ are flagged; the flag
   propagates to sentences containing a non-letter-apostrophe ’ (regex
   `(?<![A-Za-z])’`). Quote sentences use the expressive ref.
7. Curly apostrophes are **kept** (verdict: all apostrophe variants sounded the same;
   book default is fine).

## Synthesis (per sentence)

- Single process: model + caches load **once** (RTF 2.6–2.8; the per-sentence
  subprocess harness measured 15x — never use it for books).
- AR model on `cuda:0`; **DAC codec split to `cuda:1`** (S2 Pro stack >16 GB).
  Patch `inference.py`: prepend module-top `CODEC_DEVICE` env read + 4 call sites;
  set `FISH_CODEC_DEVICE=cuda:1`.
- Install order: apt `portaudio19-dev libsox-dev libsndfile1 ffmpeg` BEFORE
  `pip install -e`; **import torch only after pip** (torchaudio ABI mismatch otherwise).
- Weights: `snapshot_download('fishaudio/s2-pro')`.
- **Per-sentence banking** to `/kaggle/working/out/wavs/NNNN.wav` + manifest.json
  (survives crashes; partial output downloadable).
- **Health gate per sentence** (RMS 0.005–0.5, mean|diff|>0.001, peak>0.05);
  **auto re-roll on failure with seed 43, then 44**.
- Reference audio/transcripts ship via **private Kaggle dataset**
  `davedavedavedavenm/cillian-refs` (kernel scripts must stay <1 MB).
- Push with `PYTHONUTF8=1`.

## Assembly

- Silence-trim each banked sentence (−44 dB threshold, 80 ms pads).
- Gaps: **0.18s** between sentences, **0.50s** between paragraphs (mechanical
  0.35/0.65 uniform gaps were rejected: "robotic / run-on").
- Mastering: `equalizer=f=220:width_type=o:width=1.2:g=1.0,
  highshelf=f=7500:gain=-2.0:width=1.0, loudnorm=I=-20:TP=-2:LRA=11`, 192k MP3.
- Final waveform gate + **ASR completeness check** (faster-whisper on the
  `epub-to-audiobook-ui` container) against the source text before delivery.
  No file reaches Dave ungated.

## Measured basis

- RTF **2.56–2.78x** on T4×2 (single-AR-GPU; codec mostly idle → 2-GPU sentence
  sharding could ~halve wall time, not yet built).
- Stress test (2026-09-22): 8/8 sentences, 0 failures, all dates/numbers verified by ASR.
- Whole book (19.8 h audio): **≈ 53 GPU-hours ≈ ~2 weeks of free Kaggle quota**,
  chapter-by-chapter (~4–6 h per chapter kernel), resumable at every step.

## Known limits

- Unrespelled raw Gaelic names mangle — the lexicon is the fix (by design).
- Occasional stochastic per-sentence defects (dropped small words, stray pauses) —
  caught by ASR completeness + re-roll; never ship ungated.
- Flat delivery on dramatic lines was solved by the expressive ref crop, not by
  temperature (0.7 flat, 1.0 drifts).
