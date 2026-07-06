# Low-Cost TTS Strategy

Goal: keep audiobook generation below GBP3/book, ideally much less.

Last reviewed: 2026-07-02. Rough conversion used for quick screening: USD1 ~= GBP0.75.

## Book Cost Assumptions

Provider pricing is usually per 1M characters. A practical audiobook estimate:

| Book size | Approx words | Approx characters | Max price per 1M chars to stay under GBP3 |
|-----------|--------------|--------------------|-------------------------------------------|
| Short | 50k | 300k | GBP10.00 |
| Typical novel | 90k-110k | 540k-660k | GBP4.55-GBP5.55 |
| Long | 150k | 900k | GBP3.33 |

This means most mainstream premium APIs are too expensive for full-book default use. They can still be useful for samples, short books, or selected premium conversions.

## Current Repo Engines

| Engine | Status | Expected cost/book | Notes |
|--------|--------|--------------------|-------|
| Kokoro CPU | Implemented | GBP0 incremental | Best default if time is acceptable. Memory leak is mitigated by restarts and single concurrency. |
| Kokoro on Vast.ai GPU | Implemented | Usually pennies if batched | Best bulk strategy. Spin up only for queued batches, keep concurrency around 2-3 on RTX 3060. |
| Piper | Implemented | GBP0 incremental | Lowest-resource fallback. Quality is lower than Kokoro but reliable. |
| EdgeTTS | Implemented via `tts-proxy` | GBP0 direct API cost | Good quality and many voices. Treat as unofficial/fragile because it depends on the `edge-tts` package and Microsoft service behavior. |
| AWS Polly Long-Form | Implemented via `tts-proxy` | Avoid | Proven too expensive for good-quality audiobook use. Keep only as legacy code path; do not use for normal conversions. |
| Inworld TTS 1.5 | Implemented via `tts-proxy` | Likely over budget for full books | Keep as experimental/premium unless real account pricing proves otherwise. |

## Current External Options

| Option | Price signal | Rough cost for 600k chars | Fits GBP3/book? | Implementation fit |
|--------|--------------|---------------------------|-----------------|--------------------|
| Lemonfox TTS | USD5/mo includes 2M TTS chars; extra USD0.50 per 200k chars | About GBP1.13 if treated as usage, or GBP3.75 for a one-month minimum | Yes if batched; borderline for one isolated book | Promising because it advertises OpenAI/ElevenLabs-compatible APIs. Needs quality and reliability test. |
| OpenAI `gpt-4o-mini-tts` | Pricing includes text input tokens and audio output tokens; pricing docs estimate USD0.015/min | About GBP5.40 for a 8-hour audiobook by minute pricing | Usually no | Could fit only shorter books. Needs real sample and billing check before trusting. |
| OpenAI `tts-1` | USD15/1M chars | About GBP6.75 | No for typical novels | Easy API shape, but above target except short books. |
| Deepgram Aura-2 | USD0.030/1k chars = USD30/1M chars | About GBP13.50 | No | Good for voice-agent clarity; too expensive for this project's default budget. |
| Google Chirp 3 HD | USD30/1M chars after free tier | About GBP13.50 | No | Quality candidate, but above target except free-tier experiments. |
| ElevenLabs Flash/Turbo | USD0.05/1k chars = USD50/1M chars | About GBP22.50 | No | Use only for samples. |
| ElevenLabs Multilingual v2/v3 | USD0.10/1k chars = USD100/1M chars | About GBP45.00 | No | Premium only; not aligned with this project. |

## Open-Weight Candidates To Test

These are the most relevant low/no-cost options because they avoid per-character billing.

| Candidate | Why it matters | First test |
|-----------|----------------|------------|
| Kokoro latest direct stack | Kokoro is Apache-2.0, 82M params, fast, cheap, and already the repo default through Kokoro-FastAPI. No new model since v1.0 (Jan 2025), so no free upgrade waiting here. | Confirm current Docker image uses the latest stable Kokoro voice/model set; benchmark CPU vs GPU on 1 known book. |
| Chatterbox Turbo | MIT licensed, 350M params, lower compute than original Chatterbox, voice cloning, paralinguistic tags (`[laugh]`, `[sigh]`, `[chuckle]`). Won a widely-cited mid-2026 blind test vs ElevenLabs (65.3% vs 24.5%). **Sampled 2026-07-02 — see below.** | Done for a synthetic passage; next is a real-book chapter test. Deployment path: [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server) exposes OpenAI-compatible `/v1/audio/speech`, Docker (NVIDIA/AMD/CPU), sentence chunking for audiobooks — drop-in beside Kokoro-FastAPI, no custom wrapper needed. |
| Hume TADA (1B / 3B-ml) | Open-sourced March 2026. Built for long-form narration: ~700s audio per context window, prosody consistency across long passages, zero content hallucinations on 1,000+ test samples. MIT code, Llama 3.2 Community License weights. Voice via reference-audio cloning; no OpenAI-compatible server exists yet, so bigger integration lift than Chatterbox. | Sample via HF Space `HumeAI/tada` (needs HF token; demo requests 120s ZeroGPU per call). TADA-1B fits an RTX 3060. |
| Chatterbox Multilingual | MIT licensed, 500M params, 23+ languages and cloning. | Only test if multilingual or cloning quality matters more than speed. |
| KokoClone / Kokoro voice-conversion experiments | Potential route to cheap voice cloning while keeping Kokoro speed. | Watch, but do not productionize until stability and license posture are clear. |

## Tracked But Not Pursued (2026-07 review)

| Model | Verdict |
|-------|---------|
| Voxtral TTS (Mistral, Mar 2026) | Open weights are CC BY-NC 4.0 (fine for personal use) but 4B params; API is USD16/1M chars (~GBP7/novel) — over budget. Track only. |
| MisoTTS 8B (Miso Labs, Jun 2026) | Expressive but conversational-agent-focused and too heavy for the RTX 3060 budget pattern. |
| IndexTTS-2, CosyVoice2 | Recur in 2026 rankings; audition only if Chatterbox disappoints. |

## Cost Model For The Next-Gen Engines (2026-07-04)

Assumptions: typical novel = 100k words ≈ 600k chars ≈ **11 hours of audio**
at ~150 wpm. GBP figures at USD1 ≈ GBP0.75. "RTF" = generation speed relative
to realtime (2x slower means 1 min of audio takes 2 min to make).

**Measured CPU baselines (Dave's Windows box, AMD Ryzen, no usable GPU),
canonical passage 2026-07-06:**
- **Turbo RTF ~1.3** (442s compute → 343s audio; both UK voices agree).
- **TADA-1B RTF ~2.4** (82s → 35s audio). TADA is ~2x slower — 1B vs Turbo's
  350M + 1-step decoder.
Earlier "Turbo ~2.5x" figure superseded by this cleaner same-passage run.
GPU rows are derived/published, marked accordingly.

| Path | Speed (11h book) | Cost/book | Confidence | Notes |
|------|------------------|-----------|------------|-------|
| Kokoro @ Vast RTX 3060 | ~20 min | ~GBP0.01 | Measured (GPU-PLAYBOOK) | Current quality baseline |
| **Turbo @ Vast RTX 3060 ($0.05–0.06/hr)** | ~2–5h GPU | **~GBP0.11–0.20** | Derived: published "up to 6x RT" | Best value; batch several books per session |
| Turbo @ Vast RTX 4090 ($0.30–0.40/hr) | ~1–1.5h | ~GBP0.30–0.45 | Derived | Pay for wall-clock speed |
| Turbo @ Windows box (CPU) | ~14h | ~GBP0.15 electricity | **Measured RTF 1.3** | Overnight-doable, free |
| TADA @ Windows box (CPU) | ~26h | ~GBP0.30 electricity | **Measured RTF 2.4** | Over a day; start-and-check-tomorrow |
| TADA @ Vast RTX 3060 | ~3.5–9h (est) | ~GBP0.20–0.45 | **Unbenchmarked estimate** | Published RTF 0.09 on H100; MUST benchmark on 3060 + build wrapper before trusting |
| zorin NUC (CPU, either) | slower than Windows box | — | Estimated | Not viable + it is the prod server |
| LLM normalization (Stage 5) | minutes | GBP0 | Z AI / Gemini flash free tiers | 150–200 requests/book |

**Homelab check:** no NVIDIA GPU on any fleet device (docker-vm, n8n-vm,
Proxmox, Pis, Hetzner/Oracle VPS — all CPU-only; small VPSes can't even load
the model). The Windows box is the best local option for both engines. AMD
780M iGPU gives no usable acceleration on Windows (no ROCm; DirectML flaky).

Bottom line: **a GBP5–10 Vast top-up converts roughly 25–50 books with
Turbo on the RTX 3060 pattern.** The same GPU rig runs TADA too, so the
top-up is not wasted whichever engine wins.

Consistency on Vast: interruptible instances can be reclaimed mid-book. The
repo already carries the mitigations built for Kokoro GPU runs (onstart
watchdog template, per-chapter retry, missing-chapter recovery). For
guaranteed uninterrupted runs, rent on-demand instead of interruptible at
roughly 2x the hourly rate — still pennies per book.

Deploy path when an engine is chosen: devnen/Chatterbox-TTS-Server as a
compose service or Vast template (OpenAI-compatible `/v1/audio/speech`, same
shape as Kokoro-FastAPI), reference voices from `data/voice_refs/`.

## Sample Test 2026-07-02

Method: same 589-char fiction passage (stress-tests pronunciation: "Worcester", "Gloucester", "epitome", "1987"; flow: long comma-laden sentences; robotic delivery: dialogue vs narration) generated through Kokoro `bm_fable`/`bf_emma` and EdgeTTS `en-GB-RyanNeural` on the zorin stack, and through Chatterbox Turbo via the free HF Space `ResembleAI/chatterbox-turbo-demo` driven with `gradio_client` (300-char chunks, fixed seed, default US reference voice). Total cost GBP0.

Result: Dave judged Turbo good; next step is a real-book proof on a known-problem passage before any deployment work. Notes: Turbo needs a ~10s British reference clip to become the house narrator; output carries Resemble's inaudible Perth watermark; Vast.ai balance was USD0 at test time, so GPU deploys need a top-up first (Turbo also runs on CPU).

## Bake-Off Status (updated 2026-07-04)

Real-book tests on *Abundance* passages, all engines fed identical
preprocessed text. Dave's listening verdicts:

- **Hard rules:** UK voices only (male + female needed). Never clone a
  synthetic voice (cloning EdgeTTS output produced robotic speech — the
  cloner reproduces the reference's prosody). Human reference clips only.
- **Turbo + LibriVox UK references** (Andy Minter male / Ruth Golding female,
  both public domain): clearly better than EdgeTTS Ryan; residual complaint
  is occasional pronunciation trips and slightly robotic pacing. Turbo
  degrades past ~300 chars per generation — always chunk (the devnen server
  does this automatically).
- **TADA + preset voice**: the most natural prosody of anything tested, and
  it spontaneously gives quoted dialogue a different voice (emergent
  speech-language-model behavior; Dave likes it). Artifacts: pacing drift
  within long passes, occasional background noise, and the preset voices are
  American. Next test: TADA with the same LibriVox UK references, shorter
  passes.
- **Kokoro**: retired from quality contention; stays as the cheap bulk
  fallback.

### Canonical test passage

All future engine/voice comparisons use one fixed passage so results are
comparable: the solar-energy section of *Abundance* ch.2 (Hannah Ritchie
quote through "half the price of coal") — chosen by Dave for its endnote
markers, percentages, decades, names (BloombergNEF, Jenny Chase), nested
quotes, and paper-title mouthful. Regenerate it with:

    python scripts/extract_test_passage.py <abundance.epub> canonical_passage.txt

(The text itself is a copyrighted excerpt and is not committed; a preprocessed
copy lives in `data/voice_refs/canonical_passage.txt` on the zorin stack.)

Reference voice clips (LibriVox, public domain): `data/voice_refs/` on the
zorin stack — `uk_male_minter_ref.wav`, `uk_female_golding_ref.wav`
(sources: archive.org `prisoner_of_zenda_librivox` ch.2, Andy Minter;
`mental_efficiency_rg_librivox` ch.2, Ruth Golding; 18s cuts at 120s offset,
24kHz mono).

## Practical Recommendation

Default path:

1. Use Kokoro CPU for one-off conversions when time does not matter.
2. Use Kokoro GPU autoscaling for batches; this is the best cost/speed point.
3. Keep EdgeTTS as a free fallback for books where a Microsoft neural voice sounds better.
4. Progress the Chatterbox Turbo track: real-book passage test, then a British reference voice, then deploy devnen/Chatterbox-TTS-Server beside Kokoro (same OpenAI API shape).
5. Trial Lemonfox only if Chatterbox Turbo disappoints; its economics fit the GBP3/book target and its OpenAI-compatible API should be a small proxy addition.

Avoid:

- Polly Long-Form. It has already proven painfully expensive for the quality tier that matters.
- ElevenLabs, Google Chirp 3 HD, and Deepgram Aura-2 for full novels. They are technically good, but the per-character economics do not fit this project unless the book is short or the conversion is intentionally premium.

## Sources

- Kokoro: https://github.com/hexgrad/kokoro
- Chatterbox: https://github.com/resemble-ai/chatterbox
- Chatterbox Turbo: https://www.resemble.ai/chatterbox-turbo/
- Chatterbox TTS Server (OpenAI-compatible, audiobook chunking): https://github.com/devnen/Chatterbox-TTS-Server
- Hume TADA: https://www.hume.ai/blog/opensource-tada and https://github.com/HumeAI/tada
- Voxtral TTS: https://mistral.ai/news/voxtral-tts/
- Lemonfox TTS pricing: https://www.lemonfox.ai/text-to-speech-api
- OpenAI TTS pricing: https://developers.openai.com/api/docs/models/tts-1
- Deepgram Aura-2 pricing: https://deepgram.com/product/text-to-speech
- Google TTS pricing: https://cloud.google.com/text-to-speech/pricing
- ElevenLabs API pricing: https://elevenlabs.io/pricing/api
- AWS Polly pricing: https://aws.amazon.com/polly/pricing/
