# Low-Cost TTS Strategy

Goal: keep audiobook generation below GBP3/book, ideally much less.

Last reviewed: 2026-05-19. Rough conversion used for quick screening: USD1 ~= GBP0.75.

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
| Kokoro latest direct stack | Kokoro is Apache-2.0, 82M params, fast, cheap, and already the repo default through Kokoro-FastAPI. | Confirm current Docker image uses the latest stable Kokoro voice/model set; benchmark CPU vs GPU on 1 known book. |
| Chatterbox Turbo | MIT licensed, 350M params, lower compute than original Chatterbox, voice cloning, paralinguistic tags. | Build a small OpenAI-compatible wrapper and run 3 representative chapters against Kokoro Fable/Ryan. |
| Chatterbox Multilingual | MIT licensed, 500M params, 23+ languages and cloning. | Only test if multilingual or cloning quality matters more than speed. |
| KokoClone / Kokoro voice-conversion experiments | Potential route to cheap voice cloning while keeping Kokoro speed. | Watch, but do not productionize until stability and license posture are clear. |

## Practical Recommendation

Default path:

1. Use Kokoro CPU for one-off conversions when time does not matter.
2. Use Kokoro GPU autoscaling for batches; this is the best cost/speed point.
3. Keep EdgeTTS as a free fallback for books where a Microsoft neural voice sounds better.
4. Trial Lemonfox next because its economics fit the GBP3/book target and its OpenAI-compatible API should be a small proxy addition.
5. Build a Chatterbox Turbo proof-of-concept only if quality testing shows a clear upgrade over Kokoro for plain narration.

Avoid:

- Polly Long-Form. It has already proven painfully expensive for the quality tier that matters.
- ElevenLabs, Google Chirp 3 HD, and Deepgram Aura-2 for full novels. They are technically good, but the per-character economics do not fit this project unless the book is short or the conversion is intentionally premium.

## Sources

- Kokoro: https://github.com/hexgrad/kokoro
- Chatterbox: https://github.com/resemble-ai/chatterbox
- Lemonfox TTS pricing: https://www.lemonfox.ai/text-to-speech-api
- OpenAI TTS pricing: https://developers.openai.com/api/docs/models/tts-1
- Deepgram Aura-2 pricing: https://deepgram.com/product/text-to-speech
- Google TTS pricing: https://cloud.google.com/text-to-speech/pricing
- ElevenLabs API pricing: https://elevenlabs.io/pricing/api
- AWS Polly pricing: https://aws.amazon.com/polly/pricing/
