# TTS Landscape Review — July 2026

**Purpose:** historical July 2026 state-of-the-art review for best audiobook
audio at lowest cost. It does **not** supersede newer entries in `DECISIONS.md`,
`ENGINES.md` or `LOW-COST-TTS.md`; those files govern wherever this dated
snapshot conflicts. Re-read current official upstream documentation before
acting on any vendor, version, capability, licence or price below.

---

## TL;DR

**Historical July conclusion:** Turbo + TADA looked top-tier for audiobook
narration. Later listening narrowed that claim: Nano + Beatrice is the free
local default, Turbo is conditional per book, Qwen is the full-precision
consistency leader, Gemini/Achernar is the accepted slow free-online option,
and the raw Magpie v2607 path failed its listening gate. Two developments were
measured on 2026-07-24:

1. **Chatterbox Nano** (110M params, MIT) — **VERIFIED WORKING** as a local
   engine. Measured **RTF ~0.83 on Zorin CPU** (faster than realtime, no GPU),
   ASR-confirmed correct output. Runs as its own `chatterbox-nano` container
   (Turbo and Nano can't share a process). This genuinely eliminates the GPU
   dependency for Chatterbox-quality audio. Still owes a Turbo-vs-Nano quality
   A/B for the ear.
2. **CosyVoice 3** (Alibaba, Apache 2.0) — **auditioned, verdict: keep.** Dave:
   "surprisingly good, listenable." Strong on numbers, dates, currency,
   acronyms, units; weak only on insider British surnames (Featherstonehaugh →
   read literally) and spaced phone numbers. **GPU-only**: RTF ~0.85 on a
   T4/P100, but on CPU it is ~10–50× realtime AND produces malformed audio
   (Kaggle Xeon test) — so it is a **Kaggle-render engine**, never a local
   Zorin service. Full webapp render integration is the remaining build; the
   standalone kernel (`scripts/kaggle/build_chapter_kernel.py`) renders whole
   chapters today.

That July statement is retained as history, not current operational guidance.

See **§ Verified results 2026-07-24** at the bottom for the measurements.

---

## CPU-only candidate update (2026-08-13 — official sources checked)

These are candidates for an isolated local listening bake-off, not production
recommendations. Exact upstream HEADs recorded before any experiment:

| Candidate | Official facts | Repo boundary | Trial priority |
|---|---|---|---:|
| [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (`7fc13c7`) | MIT; 100M; CPU-first; two cores; streaming; voice cloning; official README says infinitely long input and about 6x realtime on an M4; does not support pause tags | **Heard:** official Peter Yearsley voice is decent/good; normalized text won and handled the content without a reported residual defect. Cloning weights still require accepting Kyutai's model terms. | **1** |
| [Neuphonic NeuTTS](https://github.com/neuphonic/neutts) (`ac69851`) | NeuTTS-Air is Apache-2.0, ~360M active / ~552M incl. embeddings; Q4 GGUF CPU route; instant cloning needs 3–15s clean WAV plus exact transcript; 2048-token context covers about 30s. Published CPU token benchmarks exclude the codec. | **Rejected:** Shipped voice Jo is American (`en-us`). Severe acoustic token decoder defect vocalizes espeak palatal glides (`ʲ`) into intrusive "ee" syllables (*"I-e often"*, *"the-e-airport"*). Lacks abbreviation handling (`vs.` -> "v s"). Formally rejected. | **Closed** |
| [KittenTTS](https://github.com/KittenML/KittenTTS) v0.8.1 / HEAD `9f3e0d8` | Apache-2.0 developer preview; ONNX CPU models at 15M/40M/80M; 24kHz; speed control; eight preset voices; no documented voice cloning. | **Heard:** normalized text won for Jasper and Rosie. Jasper started slightly scratchy; Rosie gave perhaps the best content handling. Presets only, no UK clone. | **3** |
| [Chatterbox Multilingual V3](https://github.com/resemble-ai/chatterbox) (`5de7a54`, already pinned) | MIT; 500M; official release claims improved speaker similarity, accent preservation and reduced hallucination. | Not a new engine: already containerised and measured at CPU RTF 4.15–4.81. Existing clips need Dave's listening verdict before more work. | **0** |

### Controlled CPU-engine admission path

The 2026-08-13 screens live in `evaluations/cpu-engines/`. Every run was a
one-shot four-core CPU container with no GPU device, queue registration or paid
fallback. A complete short clip is only a listening candidate. None of Pocket,
NeuTTS or Kitten is a production engine or approved default.

1. Run the official pinned runtime in an isolated evaluation container on
   Zorin: CPU-only, four-core cap, explicit memory cap, no queue registration,
   no startup cache and no paid/cloud fallback.
2. Render the same easy prose, canonical hard sample and Arthur reference for
   every cloning engine. Record source hash, upstream commit/model, wall time,
   finished duration, RTF and peak memory.
3. Present blind clips to Dave. ASR may prove gross completeness only; it must
   not rank naturalness, accent, pronunciation or voice similarity.
4. Only a short-sample winner earns a continuous 15–30 minute chapter. Listen
   for drift, joins and comfort before estimating a book runtime.
5. Only a long-form winner gets an OpenAI-compatible adapter, explicit Compose
   evaluation profile and sample endpoint. Production voice registration and
   job routing remain a separate, later decision.

This makes adding a candidate cheap and reversible while preventing model
downloads, background preview caching or ordinary book queues from silently
turning an experiment into production.

---

## Current engine comparison (mid-2026)

| Engine | Params | License | Clone | Long-form | CPU viable | Best for | Status in this repo |
|--------|--------|---------|-------|-----------|------------|----------|---------------------|
| **Chatterbox Turbo** | 350M | MIT | Yes (10s ref) | Chunked | Yes (RTF ~1.3) | Conditional narration candidate | **Per-book audition; latest hard-text gate mixed** |
| **Chatterbox Nano** | 110M | MIT | Yes (10s ref) | Chunked | **Yes (measured RTF 0.83)** | Same quality tier, no GPU needed | **WORKING — default CPU engine** |
| **VibeVoice** | 1.5B | Research | Yes (10s ref) | 77-minute capability reproduced | GPU preferred | Short expressive passages | **SINGLE-PASS BOOK PATH REJECTED — progressive pace drift** |
| **Qwen3-TTS** | 0.5B-1.5B | Apache 2.0 | Yes (3s ref) | Sentence passes | Yes (Q8 RTF 2.70) | Consistency leader, long-form non-fiction | **CURRENT FULL-PRECISION LONG-FORM LEADER — local Q8 / cloud** |
| **Hume TADA-1B** | 1B | Llama 3.2 Community | Yes (ref+transcript) | No (chunked) | **CPU bf16 (RTF 1.68)** | Peak naturalness, fiction/dialogue | **Opt-in engine (#23 fixed)** |
| **CosyVoice 3** | 0.5B | Apache 2.0 | Yes (3s ref) | Streaming mode | **No (GPU-only; CPU malformed)** | Multilingual, prosody control | **AUDITIONED — keep; Kaggle-render, see §Verified** |
| **Kokoro** | 82M | Apache 2.0 | No (preset voices) | Chunked | Yes (fast) | Compatibility/debug | **Rejected from quality contention** |
| **Fish Speech 1.5** | 1.5B | Apache 2.0 | Yes | Chunked | GPU needed | Fast generation, multilingual | Not integrated |
| **Fish Audio S2 Pro beta** | 4B + 400M | Fish Audio Research License | Yes | External chunking required | Official minimum 24 GB VRAM; ordinary free T4 does not fit | Expressive multilingual narration | **WATCH — not viable on current free/local hardware** |
| **IndexTTS-2.5** | official weights | Bilibili Model Use License | Yes | 120-token segments / 200 ms joins | FP32 fits free T4: 10.982 GiB peak reserved | Voice cloning, pace and English pronunciation control | **REJECTED — sentence-safe fix removed corruption but pacing/naturalness failed** |
| **Gemini 3.1 Flash TTS** | hosted preview | Google API terms | 30 presets | Split after a few minutes | hosted | Controllable audiobook narration | **FREE-ONLY ACHERNAR ACCEPTED BY EAR; SLOW MULTI-DAY BOOK PATH** |
| **NVIDIA MagpieTTS v2607** | 364M | NVIDIA Open Model License | No; 5 baked presets | **Stateful English long-form beta** | GPU; free T4 measured RTF 1.081–1.142 but unsupported | Audiobooks/content narration | **RAW NEMO PATH REJECTED — SHARED EARLY CUT; HOSTED-NIM DIAGNOSTIC OPEN** |
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
- Deepgram and paid Google Chirp 3 HD remain above the GBP2/book ceiling
  for full novels.
- **Lemonfox** still $5/mo for 2M chars — the cheapest commercial option if
  quality is acceptable. No one has tested it with audiobook-length content.

### August 2026: Gemini, Chirp, IndexTTS-2.5, Fish S2 and Magpie correction

- Gemini 3.1 Flash TTS standard input/output is free on the Developer API Free
  Tier and Dave's Achernar Studio sample was very good. The repo now has a
  strict free-only integration; its exact 81.576-second app preview is cached,
  fully decoded and served byte-identically. Google documents drift after a
  few minutes, so the app uses paragraph-aware 2–3 minute passages and an
  on-disk resume cache. The first technical long-form gate produced a complete,
  fully decoded 10:10 file from five passages after one zero-output 503 and a
  later manual resume. Dave heard that exact file, called it “one of the best”,
  and selected Achernar as an opt-in book narrator. Ten calls/day means a normal
  novel resumes from cache across roughly four weeks; this is not a fast path.
- Google Cloud Chirp 3 HD includes 1M characters/month per billing account,
  then automatically bills USD30/M; ordinary budgets are alerts, not hard caps.
  `en-GB-Chirp3-HD-Achernar` exists, but Google does not document it as the same
  voice as Gemini Achernar. It is unsafe until an atomic rolling character
  ledger reserves each exact payload and refuses above 900k/31 days.
- IndexTTS-2.5 stable shipped on 2026-08-13. The gate pinned official commit
  `39207d91c30899cad1e7c1b9eb678c241f678e55` and model snapshot
  `c39ce5ba981572cb187443877ff559dfb246ce63`. FP32 capacity is now proven on a
  free Kaggle T4 at 10.982 GiB peak reserved. Its official token-join path
  garbled repeatably; complete-sentence calls fixed the corruption and “one
  point five”, but Dave still rejected the poor pacing/timing and much less
  natural voice. The current Index path is closed. P100 is excluded by Kaggle's
  current CUDA 12.8 image.
- Fish Audio shipped S2 beta on 2026-03-10, but the current official runtime
  recommends at least 24 GB VRAM, uses a single device and does not shard across
  Kaggle T4x2. It remains a release/licence watch item, not a current free-GPU
  render candidate.
- NVIDIA MagpieTTS Multilingual v2607 is a materially different 364M candidate:
  NVIDIA documents a stateful English long-form beta and five baked presets.
  The exact v2607 model and NeMo Speech v3.0.0 runtime completed one bounded
  free-T4 gate: five same-text short arms plus a 9:14 / 79-chunk John arm at RTF
  1.081–1.142. Dave rejected all six files after a shared early cut/clipping
  defect; the accents and tone were good but reliability was unacceptable. The
  defect aligns with the first stateful sentence boundary. One focused hosted
  NIM comparison remains open because the production service differs from the
  raw NeMo path. The older v2602 NeMo-Speech.cpp GGUF path is separate
  and must not be conflated with v2607 Python inference.
- Cartesia Sonic 3.5's free ~27 minutes/month and USD5/~133-minute Pro plan do
  not fund normal novels under GBP2; keep it for bounded samples only.

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
| **Nano @ i5-12400 CPU** | **~9h** | Free | **MEASURED 2026-07-24 (RTF 0.83)** |
| Turbo @ i5-12400 CPU | ~33h (est, 1.24s/word) | Free | Measured (STATUS.md) |
| Turbo @ Kaggle T4 (free) | ~9h | Free | Measured |
| TADA @ Kaggle T4 (free) | ~4h | Free | Measured (RTF 0.34 on 3090; T4 slower) |
| Turbo @ Vast RTX 3060 | ~2-5h | ~GBP0.11-0.20 | Derived |
| TADA @ Vast RTX 3060 | ~3.5-9h | ~GBP0.20-0.45 | Derived |
| Kokoro @ Vast RTX 3060 | ~20 min | ~GBP0.01 | Measured |
| CosyVoice 3 @ Kaggle P100 | ~10h (over 2-3 sessions) | Free | **MEASURED 2026-07-24 (RTF 0.85-0.9)** |
| CosyVoice 3 @ Vast RTX 3060 | ~6-8h | ~$0.35-0.45 | Derived from the P100 measurement |
| CosyVoice 3 @ Vast RTX 3090 | ~3-5h | ~$1.00-1.65 | Derived from the P100 measurement |

**Note on long books:** a Kaggle session is capped (~9-12h) and commits outputs
only on completion, so anything over ~5 GPU-h must be split into batches —
`kaggle_render.plan_batches()` does this automatically. Vast has no such cap and
writes chapters to disk as they finish, which is why paying ~$0.40 can be worth
it for a 12-hour book even though Kaggle is free.

---

## Recommendations (priority order)

### 0. CosyVoice 3 — ATTEMPTED, FAILED (2026-07-22)
Tried to render audition samples via HF ZeroGPU spaces and Kaggle kernels.
- **HF spaces**: all broken — FunAudioLLM official space returns 1s silence;
  recentechstudio/CosyVoice3 throws internal errors; ZeroGPU quota blocked
  without HF token auth, and with auth still returned silence.
- **Kaggle kernels**: pushed 4 iterations (v1-v4). v1-v3 failed (wrong torch
  version, missing submodules, bad prompt format). v4 uses correct official
  deps (torch 2.3.1+cu121, recursive clone, CV3 prompt prefix) but output
  could not be pulled — the KGAT_ token can push/list kernels but not read
  output (`kernels.get` permission denied). Kernel may have succeeded on
  Kaggle's side; check https://www.kaggle.com/code/davedavedavenm/cosyvoice3-uk-audition-v4
- **Status**: UNTESTED. The engine benchmarks well (WER 1.68% EN, speaker
  similarity 69.5%) but we have zero audio to judge. Retry when: (a) a
  working HF space appears, (b) Kaggle auth is fixed (need kaggle.json with
  username+key, not KGAT_ token), or (c) we build a local/Docker integration.

### 1. Keep Chatterbox Nano + Beatrice as the free local default
That listening/capacity gate is complete. It remains the default baseline, not
an open experiment.

### 2. Diagnose NVIDIA Magpie only through one hosted-NIM control
The raw v2607 NeMo gate is rejected. If an NVIDIA API key is supplied, make one
short official hosted-NIM PCM request using the documented path/settings and
compare the early sentence boundary. Do not spend another Kaggle run, repeat
queries, render a book or integrate a voice from this diagnostic alone.

### 3. Check TADA bf16 optimizations
If the `hume-tada` pip package now includes bf16 + encoder caching, rebuild
the TADA image. Free ~20% speedup and lower VRAM.

### 4. Keep Turbo + TADA conditional
Turbo has mixed book-specific evidence; TADA remains expressive on easy text
but weaker on dense nonfiction. Neither is an unconditional quality reference.

### 5. Keep Index closed; watch Fish S2
IndexTTS-2.5 is rejected after its corrective listening gate. Fish S2 waits for
a materially lighter official runtime or free GPU with at least 24 GB VRAM and
explicit research-licence acceptance. F5-TTS, XTTS, Bark, MetaVoice and Parler
remain low priority absent a materially new official release.

### 6. Lemonfox remains the cheapest commercial fallback
$5/mo for 2M chars, OpenAI-compatible API. Worth a 10-minute quality test
if a commercial fallback is ever needed. Not a priority.

---

## Verified results (2026-07-24)

All numbers below are **measured**, not vendor claims. Method: render, then
ASR-transcribe the output and score word-sequence similarity to the input.

### CosyVoice 3 (`Fun-CosyVoice3-0.5B-2512`)
- **Full chapter**: "The Yellow Wallpaper" (Gilman), 30.3 min audio, 105
  chunks, mean ASR similarity **0.966** (min 0.833, none < 0.75). Independent
  local re-ASR of the downloaded file: English p=1.00, verbatim prose.
- **GPU RTF**: ~0.82–0.88 on a Kaggle P100 (26.4 min to generate 30.3 min).
- **Hard-text audition**: numbers/dates/currency/percentages/acronyms/units all
  correct; US date `07/24/2026` → "24 July"; weak on Featherstonehaugh /
  Cholmondeley / Menzies (read literally, need pronunciation inpainting) and on
  spaced phone numbers. Dave's verdict: "surprisingly good, listenable."
- **CPU**: NOT viable. Kaggle Xeon (4 vCPU): model load 48s, then ~118s of
  compute for a single medium sentence (~10× realtime floor) AND the audio came
  out truncated/malformed. → **Kaggle-GPU render only.**
- **Engine, not voices**: no `spk2info.pt` in the model → no preset speakers.
  The UK accent comes entirely from the reference clip; any voice in the roster
  works as a reference.
- **The pins are load-bearing**: 16 earlier runs produced fluent *multilingual
  babble* (Mongolian/Hungarian/Arabic on English input) purely from installing
  CosyVoice's deps unpinned on Python 3.12. Correct path: Python 3.10 +
  `requirements.txt` pins (esp. `transformers==4.51.3` for the Qwen2 backbone).

### VERDICT: Nano ties Turbo on quality at ~4x the speed (2026-07-25)

Dave, after an A/B on the identical passage (Prologue of *London Falling*, same
`uk_female_golding` reference, only the engine differing):

> "honestly nano sounds as good as turbo... not worse anyway"

Measured on zorin (i5-12400, no GPU) for the same 10-minute chapter:

| Engine | Render | RTF | A 12.4-hour book |
|--------|--------|-----|------------------|
| **Nano** | ~9 min | **0.87** | **~11 h** |
| Turbo | ~35 min | 3.33 | ~41 h |

**Nano is 3.8x faster for equal quality**, and *faster than realtime on CPU*.
This is the single biggest change to the cost model in this document:
Chatterbox-grade narration no longer needs a GPU, a quota, or a Kaggle session
at all. A full book goes from a two-day job to an overnight one, free and
unlimited, with chapters written to disk as they finish (no session cap, no
commit-on-completion trap).

Consequences worth acting on:
- Nano is the obvious default for local rendering; Turbo's only remaining claim
  is being the longer-tested path.
- The GPU engines are now for *quality ceilings* (TADA naturalness, CosyVoice
  prosody), not for throughput.

### Chatterbox Nano (`ResembleAI/chatterbox-nano`, 110M, MIT)
- **Measured RTF ~0.83 on Zorin CPU** (i5-12400), faster than realtime — a
  30-min chapter renders in ~25 min with no GPU. Warm synth of a 24-word
  sentence: ~7s wall for ~8.5s audio.
- ASR-verified correct English from the container (first non-HF-Space output).
- **Deployment gotchas found and fixed** (all were "wired but broken"):
  - PyPI `chatterbox-tts>=0.1.7` has `ChatterboxTurboTTS` but NOT the `nano=`
    param → pinned the master commit `5de7a54` in `chatterbox/requirements.txt`.
  - One container = Turbo XOR Nano (model chosen at startup by `CHATTERBOX_NANO`)
    → Nano runs as its own `chatterbox-nano` service (profile `chatterbox-nano`,
    port 8006), routed via `CHATTERBOX_NANO_URL`.
  - `numba`/`librosa` need a writable cache → `NUMBA_CACHE_DIR=/tmp/numba`.
  - The shared `chatterbox-cache` HF volume was root-owned (pre-non-root-migration)
    so Nano couldn't download its model → chown to the container UID.
