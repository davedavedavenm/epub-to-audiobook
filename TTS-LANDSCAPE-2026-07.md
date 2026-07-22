# TTS Landscape Review — July 2026

**Purpose:** current state of the art for best audiobook audio at lowest cost.
Supersedes the engine tables in LOW-COST-TTS.md where they conflict.

---

## TL;DR

**Your Turbo + TADA stack is still top-tier for audiobook narration.** Two
developments matter:

1. **Chatterbox Nano** (110M params, MIT) — 3x realtime on CPU, voice cloning,
   designed for low-resource. Could eliminate GPU dependency for Chatterbox-quality
   audio. Needs a listening test against Turbo.
2. **CosyVoice 3** (Alibaba, Apache 2.0) — strong new entrant, 30+ languages,
   streaming, fine-grained prosody control. Worth an audition.

Nothing has dethroned TADA for peak naturalness on easy text, or Turbo for
reliable long-form non-fiction.

---

## Current engine comparison (mid-2026)

| Engine | Params | License | Clone | Long-form | CPU viable | Best for | Status in this repo |
|--------|--------|---------|-------|-----------|------------|----------|---------------------|
| **Chatterbox Turbo** | 350M | MIT | Yes (10s ref) | Chunked | Yes (RTF ~1.3) | Reliable narration, non-fiction | Production engine |
| **Chatterbox Nano** | 110M | MIT | Yes (10s ref) | Chunked | Yes (~3x RT) | Same quality tier, 3x faster on CPU | **NOT EVALUATED — priority listen test** |
| **Hume TADA-1B** | 1B | Llama 3.2 Community | Yes (ref+transcript) | No (chunked) | Marginal (RTF ~2.4) | Peak naturalness, fiction/dialogue | Built, broken (#23) |
| **CosyVoice 3** | ~1B | Apache 2.0 | Yes (3s ref) | Streaming mode | GPU preferred | Multilingual, prosody control | **NOT EVALUATED — worth audition** |
| **Kokoro** | 82M | Apache 2.0 | No (preset voices) | Chunked | Yes (fast) | Cheap bulk, fallback | Production fallback |
| **Fish Speech 1.5** | 1.5B | Apache 2.0 | Yes | Chunked | GPU needed | Fast generation, multilingual | Not integrated |
| **F5-TTS** | ~330M | MIT | Yes (ref) | Chunked | GPU preferred | Research, good quality | Not integrated |
| **XTTS v2** (Coqui) | ~1.8B | MPL 2.0 | Yes | Chunked | GPU needed | Was the standard; Coqui defunct | Not integrated |
| **Bark** (Suno) | ~1B | MIT | No | Poor | GPU needed | Sound effects, not narration | Not suitable |
| **MeloTTS** (MyShell) | ~100M | MIT | No | Chunked | Yes (fast) | Lightweight, multilingual | Not integrated |
| **Parler TTS** | ~1B | Apache 2.0 | No (described) | Chunked | GPU preferred | Natural language voice description | Not integrated |
| **MetaVoice** | ~1.2B | Apache 2.0 | Yes | Chunked | GPU needed | Emotion control | Not integrated |

---

## What changed since the LOW-COST-TTS.md review (2026-07-02)

### Chatterbox Nano — the big one
- **110M params, MIT, voice cloning from 10s reference, 3x realtime on CPU.**
- Released alongside Turbo as the "edge" variant. Same architecture family,
  same voice cloning pipeline, dramatically lower compute.
- If it sounds 90%+ as good as Turbo, it eliminates the GPU requirement for
  Chatterbox-quality audio entirely. A 130k-word book would take ~15h on the
  i5-12400 instead of ~45h with Turbo.
- **Action: run the A/B harness** (`scripts/kaggle/render_voice_samples.py`)
  with Nano + the same UK reference voices. Canonical passage + one dense
  non-fiction chapter. Judge by ear.

### TADA optimizations (March 2026)
- bf16 inference + encoder caching shipped. Reduces VRAM from ~8GB to ~5GB
  and speeds generation ~20%.
- The repo's TADA image may not have these — check if `hume-tada` pip package
  includes them. If so, rebuild the image.
- TADA still has no long-form mode and no documented pacing parameters.

### CosyVoice 3 (Alibaba, June 2026)
- Apache 2.0, 30+ languages, streaming mode for long-form, 3-second voice
  cloning, fine-grained prosody/instruction control ("read this sadly").
- Community reports put it competitive with Turbo on English narration.
- Needs a GPU for reasonable speed (CPU is very slow).
- **Action: if a Kaggle session is available, render the canonical passage
  with CosyVoice 3 + UK reference and compare.**

### Kokoro — no v2
- Still at v1.0 (Jan 2025). No new model, no voice cloning. Remains the
  cheapest fast option but quality ceiling is well below Turbo/TADA.
- Kokoro-FastAPI continues to be maintained.

### Commercial API pricing — no material change
- ElevenLabs still $0.05-0.10/1k chars. OpenAI gpt-4o-mini-tts still ~$0.015/min.
- Deepgram, Google Chirp 3 HD unchanged. All still above the GBP3/book target
  for full novels.
- **Lemonfox** still $5/mo for 2M chars — the cheapest commercial option if
  quality is acceptable. No one has tested it with audiobook-length content.

### Dead or stalled projects
- **Coqui TTS** — company defunct since 2024. Forks exist (idiap/coqui-ai-TTS)
  but XTTS v2 is no longer advancing. Not worth integrating.
- **Bark** — Suno pivoted to music. Bark is unmaintained. Not suitable for
  narration (hallucinated sound effects).
- **Voxtral TTS** — CC BY-NC 4.0, 4B params, $16/1M chars. Still over budget.

---

## Updated cost model

| Path | Speed (11h book) | Cost/book | Confidence |
|------|------------------|-----------|------------|
| **Nano @ i5-12400 CPU** | ~15h (est) | Free | **UNMEASURED — needs RTF test** |
| Turbo @ i5-12400 CPU | ~33h (est, 1.24s/word) | Free | Measured (STATUS.md) |
| Turbo @ Kaggle T4 (free) | ~9h | Free | Measured |
| TADA @ Kaggle T4 (free) | ~4h | Free | Measured (RTF 0.34 on 3090; T4 slower) |
| Turbo @ Vast RTX 3060 | ~2-5h | ~GBP0.11-0.20 | Derived |
| TADA @ Vast RTX 3060 | ~3.5-9h | ~GBP0.20-0.45 | Derived |
| Kokoro @ Vast RTX 3060 | ~20 min | ~GBP0.01 | Measured |
| CosyVoice 3 @ Kaggle T4 | Unknown | Free | **UNTESTED** |

---

## Recommendations (priority order)

### 1. Listen-test Chatterbox Nano (highest leverage)
If Nano sounds close to Turbo, it's a free 3x speedup on CPU with zero new
infrastructure. Same MIT license, same voice cloning, same server interface.
Use the existing A/B harness. This is the single highest-leverage action.

### 2. Audition CosyVoice 3 on Kaggle
The streaming/long-form mode and prosody control could be a step change for
audiobook narration. Render the canonical passage + one chapter. Free on Kaggle.

### 3. Check TADA bf16 optimizations
If the `hume-tada` pip package now includes bf16 + encoder caching, rebuild
the TADA image. Free ~20% speedup and lower VRAM.

### 4. Keep Turbo + TADA as production engines
Nothing has displaced them. Turbo for reliability, TADA for peak quality on
GPU. Nano is a potential Turbo replacement pending the listen test.

### 5. Don't chase: Fish Speech, F5-TTS, XTTS, Bark, MetaVoice, Parler
None offer a clear advantage over the current stack for English audiobook
narration with UK voices. Revisit if the project adds multilingual support.

### 6. Lemonfox remains the cheapest commercial fallback
$5/mo for 2M chars, OpenAI-compatible API. Worth a 10-minute quality test
if a commercial fallback is ever needed. Not a priority.
