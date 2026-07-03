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

## Sample Test 2026-07-02

Method: same 589-char fiction passage (stress-tests pronunciation: "Worcester", "Gloucester", "epitome", "1987"; flow: long comma-laden sentences; robotic delivery: dialogue vs narration) generated through Kokoro `bm_fable`/`bf_emma` and EdgeTTS `en-GB-RyanNeural` on the zorin stack, and through Chatterbox Turbo via the free HF Space `ResembleAI/chatterbox-turbo-demo` driven with `gradio_client` (300-char chunks, fixed seed, default US reference voice). Total cost GBP0.

Result: Dave judged Turbo good; next step is a real-book proof on a known-problem passage before any deployment work. Notes: Turbo needs a ~10s British reference clip to become the house narrator; output carries Resemble's inaudible Perth watermark; Vast.ai balance was USD0 at test time, so GPU deploys need a top-up first (Turbo also runs on CPU).

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
