# Low-Cost TTS Strategy

Goal: keep audiobook generation below GBP3/book, ideally much less.

> **Quality is the admission test; cost is a constraint after that.** A local,
> free or fast engine that sounds bad is not a successful audiobook engine.
> Candidates must first pass listening for naturalness, authentic accent,
> pronunciation (including names and numbers), pacing and long-form comfort.

> **The premise of this document has largely been won (2026-07-25).** It was
> written when a good local render was impractical and the question was which
> paid or quota-limited service to lean on. **Chatterbox Nano measures RTF 0.83
> on zorin's CPU** — verified end-to-end over a full book, not extrapolated —
> so a book now renders overnight locally for **£0**, no GPU and no quota.
> Cost-per-book comparisons below are still useful for judging the *paid*
> engines, but the default answer is now "render it locally and pay nothing".
> See STATUS.md for the measurement.

Last reviewed: 2026-07-02 (cost tables); premise revised 2026-07-25. Rough conversion used for quick screening: USD1 ~= GBP0.75.

## 2026-07-28 local accent bake-off

Two candidates were containerised and actually rendered on zorin, using the
same 192-word hard sample and CPU-only OpenAI-compatible endpoints. These are
opt-in evaluation services until the clips are graded by ear.

| Candidate | British RTF | Australian RTF | Peak memory | 12h-book CPU estimate | Current verdict |
|---|---:|---:|---:|---:|---|
| [MeloTTS](https://github.com/myshell-ai/MeloTTS) | **0.34** | **0.33** | 3.86 GiB | **~4.0 h** | **Rejected by ear:** bad TTS, pronunciation and number handling. Speed does not rescue it. |
| [OmniVoice](https://github.com/k2-fsa/OmniVoice) | **9.10** | **9.06** | 1.59 GiB | **~4.5 days** | **Best accent quality of this pair**, but default CPU throughput disqualifies full books. Huawei/Xiaomi need its supported inline CMU overrides. Non-commercial weights. |
| Chatterbox Multilingual V3 | **4.15 Irish** | **4.81 South African** | 5.74 GiB | **~2.1–2.4 days** | Successfully rendered; quality/accent awaiting listening. MIT, local CPU, isolated opt-in service. |

Whisper `base` sequence ratios were 0.769/0.802 for Melo and 0.826/0.823
for OmniVoice. V3 scored 0.848 Irish / 0.844 ZA, but its ASR transcripts show
material number errors, so the slightly higher aggregate score is not a clean
win. These checks prove the files contain mostly matching English; they do
**not** grade accents or naturalness. Dave's listening verdict is recorded above.
See STATUS.md for exact wall times, durations, memory and clip paths.

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
| Piper | Implemented | GBP0 incremental | Current deployed output is legacy/debug only and **rejected for production by ear**. Root cause is not assumed: speaker/model integrity passed audit; current-runtime and encoding A/B awaits listening. |
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




## FREE and CHEAP GPU for TADA (2026-07-08 — answering "prices are fucked")

**Default strategy: Kaggle-first, Vast-burst** (chosen 2026-07-08). Free Kaggle
covers normal volume; Vast (~$1/book) only when the weekly quota is spent. No
owned hardware unless volume grows — a used 3060 desktop only pays off past
~hundreds of books.

**FREE — Kaggle Notebooks** is the real free-and-fast TADA path:
- 30 GPU-hours/week, Tesla T4 (16 GB — fits TADA), sessions up to 9 h with
  **background execution** (close the tab, it keeps running).
- A full book (~4 h on RTX 3090) runs comfortably inside one free session.
- **GOTCHA (blocked us 2026-07-08):** kernels get NO internet until the account
  is **phone-verified** (kaggle.com/settings) — pip/git/HF all fail with DNS
  errors regardless of `enable_internet: true`. One-time. Now verified.
- Committed runbook: `scripts/kaggle/` (kernel + dataset metadata + README).
  Auth uses the newer self-contained `KGAT_` token via `~/.kaggle/access_token`
  (no username). On Windows the CLI needs the temp upload dir pre-created.
- Colab free tier is similar (T4, ~30 h/wk) but flakier / shorter idle timeout;
  Lightning AI (~15 GPU-hrs/mo credits) and Paperspace free tier are overflow.
- HuggingFace Spaces ZeroGPU: free but small daily quota (used early on).

**CHEAP — Vast.ai consumer GPUs** (the "under $0.10/hr" tier, not the H100s):
- **RTX 3060 (12 GB) ~$0.05-0.10/hr** — TADA-1B fits fine; a ~5 h book ≈ **$0.25-0.50**.
- RTX 3090 ~$0.20-0.25/hr (what we measured: TADA RTF 0.34).
- RunPod community RTX 4090 from ~$0.34/hr if you want "just works".
Use `scripts/vast-gpu.sh up tada <offer_id>` — pass a 3060 offer id to go cheapest.

Bottom line: TADA is NOT stuck behind expensive GPUs. Kaggle = free; Vast 3060
= pennies. The NUC RAM upgrade (32 GB) additionally makes TADA free-and-local.

## Audio-quality fixes 2026-07-08 (from Apple in China listen-through)
- **Weird mid-sentence pauses**: em/en-dashes were force-converted to commas
  (a hack for dumb engines). Now kept as dashes — modern models render them
  naturally. Fixed in tts_preprocess.
- **First words garbled**: TADA cold-start. Server now prepends a throwaway
  lead-in and trims it at the first silence gap (`TADA_TRIM_LEADIN`, default
  on). NEEDS a listen-validation on the next TADA run.
- **Mispronounced Cupertino/Beijing/McDonald's**: the STANDALONE SCRIPT skipped
  the LLM pronunciation layer entirely. Now it runs the narration profile +
  a seed dictionary of common place/brand names. The APP path already had the
  LLM profile; its prompt is strengthened to catch well-known-but-fumbled names.

## GPU MEASURED 2026-07-07 — the runbook works, real numbers at last

Validated end-to-end on a Vast RTX 3090 ($0.248/hr, Czechia) using the
CI-built GHCR images via `scripts/vast-gpu.sh` architecture (onstart + direct
ports + CUDA health gate). Alice ch.1 (2,187 words ≈ 11-12 min audio),
converted with `scripts/convert_book.py` over the public endpoint:

| Engine | Compute time | RTF | 11h-book estimate | Cost/book @ $0.126-0.25/hr |
|--------|-------------|-----|--------------------|------------------------------|
| **TADA (GPU)** | **3m59s** | **0.34** | ~3.7h | ~$0.47-0.93 (~GBP0.35-0.70) |
| **Chatterbox (GPU)** | 9m33s (incl. first-request model load) | ~0.85 | ~6-9h warm, less in practice | ~$0.75-2.2 — needs a warm-run measurement |

Notes: TADA is FASTER than Chatterbox on GPU (bf16 1B batch-friendly vs
Turbo's chunked pipeline); Chatterbox's number includes one-time model load so
its warm RTF is better than shown. Total validation spend: ~$0.25.
Fix history that made this work: images were CPU-only torch + missing NVIDIA
envs (both fixed in CI images); slim images have no sshd (runbook uses direct
ports); GHCR pulls can stall on slow Vast hosts (pick inet_down>3000).

**Bottom line: TADA's practical home is GPU (~GBP0.5/book, 3x realtime);
Chatterbox works well everywhere (local CPU overnight = free, GPU = fast).**

## GPU benchmark attempt 2026-07-06 — FAILED, lesson learned

Tried to measure real Turbo/TADA speed on a Vast RTX 3090 by pip-installing on
a bare `pytorch/pytorch` instance. It FAILED and produced no number:
- pip install of chatterbox-tts pulled ~3GB (torch 2.6 + CUDA wheels + spaCy)
  and took ~80 min on that instance's slow PyPI throughput.
- Then a transformers/chatterbox version conflict ("Could not import
  LlamaModel") broke the import on the bare image.
- ~$0.21 and ~1.5h wasted; no measured RTF.

**Lesson (actionable):** the GPU path MUST use the **pre-built engine Docker
images** we already have (`chatterbox/`, `tada/`) — deps baked in, load in
seconds, no pip/version roulette. Ad-hoc pip-install on a bare instance is too
slow and too fragile. The automated GPU-render path (PLAN.md §3) should:
push the chatterbox/tada images to a registry (or `docker save`/load), run the
container on the Vast instance, tunnel it back to the worker like the Kokoro
GPU playbook. Benchmark AFTER that, not before.

So: **GPU speed for Turbo/TADA is still UNMEASURED.** Do not quote a per-book
GPU time until it is measured via the containerised path.

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
- **TADA + preset voice**: the most natural prosody of anything tested *on easy
  text* (on dense non-fiction it drifts — 2026-07-10 verdict in ENGINES.md chose
  Chatterbox for the full book), and
  it spontaneously gives quoted dialogue a different voice (emergent
  speech-language-model behavior; Dave likes it). Artifacts: pacing drift
  within long passes, occasional background noise, and the preset voices are
  American. Next test: TADA with the same LibriVox UK references, shorter
  passes.
- **Kokoro**: retired from quality contention; stays as the cheap bulk
  fallback.

### TADA detailed verdict (2026-07-06, canonical passage, local CPU + GPU max-quality)

Both TADA UK voices (Minter/Golding) judged "incredibly strong with a few
minor issues." Female (Golding) more emotive; both a little robotic in places.
Open issues to fix before/at integration:

- **Pronunciation:** "US Energy Information" read as the word "us" not letters
  "U-S". Fix via pronunciation lexicon rule (`US==U S` scoped, or LLM
  profile) — a TEXT fix, not a voice fix. Do NOT hold against the engine.
- **First word "Environmental" mangled** on every take — likely a
  cold-start/first-token artifact. Mitigation to try: lead-in padding (a
  short neutral clause or silence token before the real first word), or
  regenerate the opening chunk.
- **Pacing too fast / "no breath taken."** Needs a slower/again-breathing
  setting — try lower `speed_up_factor`, or insert sentence pauses in
  preprocessing.
- **Quote character-voices did NOT reliably emerge** even in long passes; at
  the end one attempt sounded "bizarre — like a recording in a public place,
  couldn't hear the voice." So the emergent dialogue-voice is unstable when
  cloning a fixed reference — treat it as a bonus, not a feature to rely on.
- Max-quality GPU knobs (30 flow steps + best-of-3 candidates) helped
  cleanliness but did not fix the above; these are mostly text/pacing issues.

Turbo remains the lighter, more predictable option; TADA the more natural but
quirkier one. Decision still open pending fixes to the above.

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

1. Audition the target book's hardest passage first. Reject any engine that fails
   naturalness, pronunciation, accent authenticity or long-form comfort.
2. Use the accepted Chatterbox Turbo “Arthur” outcome as the current local
   quality reference, while still sampling each new book.
3. Keep EdgeTTS as the heard-good accent baseline where internet use is acceptable.
4. Keep OmniVoice as a short-form/local accent candidate while pronunciation
   overrides and throughput are evaluated; grade Chatterbox Multilingual V3 by ear.
5. Only then optimise cost and speed. The current Piper path and Melo are not
   production fallbacks; Piper's direct-current-runtime A/B must be heard before
   making an engine-wide claim.

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
