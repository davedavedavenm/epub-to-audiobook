# Low-Cost TTS Strategy

Goal: produce a genuinely good audiobook for free wherever possible; when a
paid path is necessary to reach that quality, use the lowest measured total
cost per finished book, with a hard maximum of GBP2.

> **Quality is the admission test; free/cheapest is the selection rule among
> engines that pass.** A local, free or fast engine that sounds bad is not a
> successful audiobook engine. Candidates must first pass Dave's listening for
> naturalness, authentic accent, pronunciation (including names and numbers),
> pacing and long-form comfort. Prefer free local/Kaggle generation; if none
> passes, choose the lowest measured paid cost per finished book and reject any
> route that cannot stay at or below GBP2.

> **The premise of this document has largely been won (2026-07-25).** It was
> written when a good local render was impractical and the question was which
> paid or quota-limited service to lean on. **Chatterbox Nano measures RTF 0.83
> on zorin's CPU** — verified end-to-end over a full book, not extrapolated —
> so a book now renders overnight locally for **£0**, no GPU and no quota.
> Cost-per-book comparisons below are still useful for judging the *paid*
> engines, but the default answer is now "render it locally and pay nothing".
> See STATUS.md for the measurement.

Last reviewed: 2026-08-15 (project optimisation order, rejection boundaries,
Vibe/V3 comparison validity and paid-GPU safety). Re-check every commercial price
in the provider's current official documentation before using it. Rough
conversion used for historical screening: USD1 ~= GBP0.75.

## 2026-08-13 CPU voice listening verdict

The four new free, CPU-only auditions all clear the basic voice-quality floor,
but none is ready to replace the default because all four mishandled numbers
and dollar/currency amounts in the heard raw-input evaluation clips. Those
clips were served in the app but did not pass through its text normalizer.

| Engine / voice | Human verdict | Open quality issue / status |
|---|---|---|
| Pocket TTS / Peter Yearsley | Decent/good voice (RTF 0.53x on CPU) | Strict <50 token chunk limit; explicit normalization mandatory |
| NeuTTS Air / Jo | **Rejected** (American `en-us`, phoneme glide defects) | Auditioned on Breakneck Ch 1; rejected by Dave for American accent, intrusive "ee" glides (*"I-e often"*, *"the-e-airport"*), and abbreviation spellout (`vs.` -> "v s"). |
| KittenTTS / Jasper | Decent/good voice (RTF 1.07x on CPU) | Scratchy start cured with pre-warmed audio buffer |
| KittenTTS / Rosie | Decent/good voice (RTF 1.02x on CPU) | Strongest overall CPU cadence and tone |

The initial listening result was not a diagnosis. The engines remain
candidates, not defaults or rejections. The 2026-08-14 follow-up rendered a pinned
corpus of years, decimals, percentages, ranges, pound amounts and dollar
amounts both raw and explicitly normalized, while holding every engine setting
fixed. All eight clips passed source-hash, duration and size validation. Dave
selected the normalized arm for Peter, Jo, Jasper and Rosie: the original
shared numeric failure was our raw-input evaluation path. Jo retained one
“the e order” insertion; Jasper started slightly scratchy; Rosie gave perhaps
the best handling.

In September 2026, CPU candidates were evaluated on a 456-word continuous
excerpt from Chapter 1 of *Breakneck: China’s Quest to Engineer the Future*:
- **NeuTTS Air (Jo)**: **Formally rejected.** Auditioning on continuous text revealed
  critical defects: American accent (`en-us`, no British presets), severe acoustic token
  decoder bug causing intrusive "ee" syllables on espeak palatal glides (*"I-e often"*,
  *"the-e-airport"*, *"v-e-s"*), lack of abbreviation handling (`vs.` pronounced as "v s"),
  and slow CPU RTF (2.25x–5.90x).
- **Pocket TTS 2.1 (Peter Yearsley)**: Generated 156.4s audio at RTF 0.53x on CPU.
  Very fast and articulate, but chunks exceeding 50 tokens risk word dropping.
- **KittenTTS 0.8.1 (Rosie & Jasper)**: Rosie generated 199.1s audio at RTF 1.02x
  with warm, natural pacing. Jasper generated 182.2s audio at RTF 1.07x with its
  scratchy onset resolved via pre-warmed buffers.
Pocket and Kitten are admitted as free, opt-in CPU book choices using the
`explicit` text normalization profile. NeuTTS Air is rejected. They are not automatic
fallbacks and do not replace Beatrice/Nano. Chatterbox Turbo remains the cheapest and
overall production winner for full book rendering.

## 2026-07-28 local accent bake-off

Two candidates were containerised and actually rendered on zorin, using the
same 192-word hard sample and CPU-only OpenAI-compatible endpoints. These are
opt-in evaluation services until the clips are graded by ear.

| Candidate | British RTF | Australian RTF | Peak memory | 12h-book CPU estimate | Current verdict |
|---|---:|---:|---:|---:|---|
| [MeloTTS](https://github.com/myshell-ai/MeloTTS) | **0.34** | **0.33** | 3.86 GiB | **~4.0 h** | **Rejected by ear:** bad TTS, pronunciation and number handling. Speed does not rescue it. |
| [OmniVoice](https://github.com/k2-fsa/OmniVoice) | **9.10** | **9.06** | 1.59 GiB | **~4.5 days** | **Best accent quality of this pair**, but default CPU throughput disqualifies full books. Huawei/Xiaomi need its supported inline CMU overrides. Non-commercial weights. |
| Chatterbox Multilingual V3 | **4.15 Irish** | **4.81 South African** | 5.74 GiB | **~2.1–2.4 days** | **Exact path rejected by ear:** mediocre pacing/tone, average pronunciation, bad numbers; Australian okay, Irish wrong, ZA best but still not good. Synthetic references + unjustified CFG zero confound engine-level cause. |

Whisper `base` sequence ratios were 0.769/0.802 for Melo and 0.826/0.823
for OmniVoice. V3 scored 0.848 Irish / 0.844 ZA, but its ASR transcripts show
material number errors, so the slightly higher aggregate score is not a clean
win. These checks prove the files contain mostly matching English; they do
**not** grade accents or naturalness. Dave's failed listening verdict is the
quality decision; a same-human-reference official-default A/B would be needed
before blaming every defect on V3 itself.
See STATUS.md for exact wall times, durations, memory and clip paths.

## 2026-07-28 next-generation audiobook shortlist

The identical Arthur hard passage was rendered on a free Kaggle P100 (Higgs's
valid full clip used three separately generated paragraphs after its single
full-text call truncated at the first blank line). That short test advanced all
four engines to longer listening tests. **VibeVoice and Qwen initially passed
that gate**;
Higgs was listenable but seed-dependent; MOSS was not a finalist. However, the
Vibe run used the now-rejected `cfg_scale=1.3` and a passage known to handicap
Vibe. Its old relative ranking against Qwen is therefore superseded. The
corrected blind comparison later selected cfg 2.0 over cfg 3.0. The full cfg-2
app-path file was then heard: its opening was very good, but after roughly three
minutes it progressively accelerated, ran on and lost intent. Qwen's complete
33:03 result remained “really good,” so Qwen now ranks above this Vibe path for
long-form consistency.

MOSS received the most corrective testing. Its first chapter used 105
independent chunks plus 104 x 0.35 s joins, so that result was not treated as an
engine verdict. Two true single-pass attempts then collapsed after only 2:21 and
2:36 with near-zero source coverage. The final 13-section, paragraph-aware
render inserted no silence and passed ASR, but Dave still heard joins, weaker
expression and off pacing. It was “not horrible,” but Vibe/Qwen were clearly
better for audiobooks.

| Candidate | Chapter P100 RTF | P100 GPU hours / 12.4h book | Nominal 30h Kaggle week | Full listening result |
|---|---:|---:|---:|---|
| MOSS-TTS Local Transformer v1.5 | **1.245** | **15.44h** | 51.5% | Complete low-seam render, but joins/pacing/expression keep it below finalists |
| VibeVoice 1.5B, old cfg 1.3 timing run | **2.266** | **28.10h** | 93.7% | Timing retained only. Corrected cfg 2.0 opened very well but failed audiobook listening through progressive speed/run-on drift after ~3 minutes. |
| Higgs Audio | **1.558** | **19.32h** | 64.4% | Listenable, but one of two seeds still clipped/joined in places |
| Qwen3-TTS | **2.056** | **25.49h** | 85.0% | **Current full-precision long-form leader:** really good throughout; strongest consistency result |

Production scaffolding mirrors the render structures: Vibe is one generation
per chapter (six-hour HTTP ceiling); Qwen uses
roughly 450-character sentence passes with the audition's 350 ms joins. Both
run on free Kaggle or an explicitly attached local CUDA GPU, and both require a
complete structural `qa_report.json` before delivery. ASR inside that report is
collapse/mismatch evidence only, never a quality ranking. The retained Raven Vibe E2E has
now passed: 1,130 words, 361.392 s audio, ASR worst WER 0.115, RTF 1.218 for
the 440 s generation, chaptered M4B, cover and byte-identical Audiobookshelf
copy. The Vibe app default is now the listening-selected cfg 2.0. In a pinned
direct-versus-app focus A/B, Dave selected the corrected production path and
the older direct arm alone inserted a brief sound at `felicity - but`; both
prompts contained the same hyphen, so no global punctuation rewrite follows.
The full corrected Vibe file failed the long-form comfort gate, so Vibe is not
the production narrator. Qwen outranks it for this role but remains an explicit
GPU choice, not an automatic/default route. Ordinary queueing has no paid Vast
route.

The pinned community runtime separately documents repeated turns carrying the
same speaker label as its remedy when output speaks too fast. A 2026-08-14
free-Kaggle gate has now rendered two complete same-text Arthur arms inside one
generation each: four turns produced 7:16 and seven turns 6:59 for 1,998 words;
a same-text local Chatterbox Turbo reference produced 10:50. All decode and the
Vibe completeness gates pass. Dave rejected both Vibe arms as unacceptable;
the documented reset remedy therefore does not reverse the single-turn
rejection. The Turbo + Arthur control was almost perfect and maintained stable
pacing, with `co-heirs` → `coheirs` the only heard defect. A later seeded hard
sample did not reliably sound like Arthur and failed words, proper nouns and raw
numbers, so Turbo + Arthur now requires a per-book audition and is not an
unconditional quality reference. The system default is unchanged.

Formula: `finished audio hours × RTF`; startup, ASR and retries are additional.
The table now uses the completed chapter runs, not the earlier short-passage
RTFs. A 12.4-hour book consumes nearly the whole nominal weekly Kaggle allowance
with Vibe, about 85% with Qwen, 64% with Higgs or 52% with MOSS. Kaggle is free,
but quota and session fragmentation are real constraints.

Read-only Vast offers checked at 2026-07-28 19:55 BST were about **$0.079/h for
an RTX 3060**, **$0.213/h for an RTX 3090**, and **$0.360/h for an RTX 4090**,
including 45 GB storage but excluding bandwidth. No instance was created. There
is no measured Vast benchmark for these four engines yet: applying the updated
chapter RTFs and an explicitly hypothetical 2x P100 speed on that 3090, a 12.4h
book would be about **$1.64 MOSS, $2.99 Vibe, $2.06 Higgs or $2.72 Qwen**. Do
not treat those scenarios as measurements. The chapter run measured Qwen at
5.26 GiB allocated / 6.75 GiB reserved, so a 12 GB 3060 is capacity-plausible
for Qwen, although its speed and actual cost remain unmeasured. MOSS peaked at
13.23 GiB and does not fit that tier; Vibe and Higgs chapter runs did not record
peak VRAM. A later **short-sample** Vibe P100 accent kernel supplied the first
Vibe measurement: Irish peaked at **5.299 GiB allocated / 5.607 GiB reserved**;
South African at **5.166 / 5.604 GiB**. That makes a 12 GB GPU
capacity-plausible for short Vibe generation, but it is not a full-chapter peak
or a long-form capacity proof.

Vast's [public RTX 3090 pricing page](https://vast.ai/pricing/gpu/RTX-3090)
advertised a **$0.13/h “from” price** on 2026-07-29. That is a marketplace
headline, not a quote for the exact image, disk and network configuration above.
At that rate and deliberately assuming **no speed advantage over the measured
P100 runs**, the compute-only ceiling for the same 12.4-hour book would be
**$3.65 Vibe / $3.31 Qwen**. At the actual $0.213/h offer checked the prior
evening, the corresponding no-speedup ceilings are **$5.99 / $5.43**; the
existing hypothetical 2x cases are **$2.99 / $2.72**. Storage and bandwidth are
additional, and Vast bills them separately. These are cost scenarios, not Vast
benchmarks. Kaggle therefore remains the least-cash path while quota is
available: **$0**, but about **28.10 of 30 nominal weekly GPU hours for Vibe** or
**25.49 hours for Qwen**, before startup, ASR and retries.

Sources: [Kaggle efficient GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage)
(free P100; quota is 30 hours/week or sometimes higher) ·
[Vast pricing](https://docs.vast.ai/guides/instances/pricing) (marketplace,
per-second compute plus storage and bandwidth).

### 2026-07-29 local Q8 feasibility check — measured and heard

The exact finalists were also run locally through the third-party native
[audio.cpp](https://github.com/0xShug0/audio.cpp) CPU runtime, using its packaged
[GGUF models](https://huggingface.co/audio-cpp/audio.cpp-gguf). This is a
**different quantised inference path** from the full-precision Python/Kaggle
clips. Dave subsequently listened to both local outputs and said both sounded
fine. That verdict applies to these short clips; long-form Q8 is still unproven.

Method: zorin i5-12400, four-CPU container cap, 14 GiB/no-swap cap, audio.cpp
image revision `c810a069906f5a20b65094f9b6c755888dbb0d61`, the same UK Minter
reference, and the same 36-word hard sample including `1997`, `Huawei`, `Xiaomi`
and `7,000`. Both outputs were complete 24 kHz mono WAVs.

| Local package | Output | Cold wall / framework session | Cold / session RTF | Peak container memory | ASR completeness | 12.4h CPU extrapolation |
|---|---:|---:|---:|---:|---|---:|
| VibeVoice 1.5B Q8_0 (3.00 GiB) | 15.60 s | 107 s / 101.736 s | **6.86 / 6.52** | **4.551 GiB** | Complete; Dave heard no issue. Whisper's Huawei/Xiaomi guesses were false positives | **80.9 h session / 85.0 h cold** |
| Qwen3-TTS 1.7B Base Q8_0_v2 (2.51 GiB) | 15.28 s | 46 s / 41.251 s | **3.01 / 2.70** | **7.937 GiB** | Complete; Dave heard no issue | **33.5 h session / 37.3 h cold** |

Vibe reported 1.113 seconds of component weight loading. Qwen did not expose a
separate weight-load timer; its Docker startup, model setup and teardown outside
the measured session took roughly 4.7–5.7 seconds (the wrapper wall counter was
whole-second), so that is not a model-load measurement. The production web app
stayed healthy during both runs (worst sampled health latency 13.6 ms for Vibe
and 8.2 ms for Qwen).

**Cost/runtime conclusion:** both Q8 paths pass the short listening gate. Qwen
Q8 is the practical local fallback because it projects to roughly a day and a
half per 12.4-hour book; Vibe Q8 projects to more than three days. Neither is a
production audiobook path until a long-form Q8 render passes human listening.
ASR remains useful for completeness/collapse detection, but its word guesses
must not be used as pronunciation evidence.

## Book Cost Assumptions

Provider pricing is usually per 1M characters. A practical audiobook estimate:

| Book size | Approx words | Approx characters | Max price per 1M chars to stay under GBP2 |
|-----------|--------------|--------------------|-------------------------------------------|
| Short | 50k | 300k | GBP6.67 |
| Typical novel | 90k-110k | 540k-660k | GBP3.03-GBP3.70 |
| Long | 150k | 900k | GBP2.22 |

This means most mainstream premium APIs are too expensive for full-book default use. They can still be useful for samples, short books, or selected premium conversions.

## Current Repo Engines

| Engine | Status | Expected cost/book | Notes |
|--------|--------|--------------------|-------|
| Chatterbox Nano + Beatrice | Implemented; **default** | GBP0 incremental | Accepted free/local baseline; measured full-book RTF ~0.83–0.87. |
| Chatterbox Turbo + Arthur | Implemented; opt-in | GBP0 incremental | Mixed evidence; per-book audition required. The 2026-08-15 hard sample failed while earlier long-form controls were excellent. |
| Kokoro CPU | Implemented; compatibility/debug | GBP0 incremental | Retired from quality contention; speed does not clear the listening floor. |
| Kokoro on Vast.ai GPU | Legacy manual path | Paid marketplace rate | Never automatic and not recommended: paying to accelerate rejected-quality output violates the project objective. |
| Piper | Implemented | GBP0 incremental | Legacy/debug only; **rejected for production by ear**. Deployed 64 kbps, same-WAV higher-bitrate, and current Piper 1.6 direct A/Bs all failed badly. Not an automatic fallback. |
| EdgeTTS | Implemented via `tts-proxy` | GBP0 direct API cost | Good quality and many voices. Treat as unofficial/fragile because it depends on the `edge-tts` package and Microsoft service behavior. |
| Pocket TTS 2.1 | **Accepted opt-in** after 16:27 long-form and corrective listening | GBP0 | 21 official English presets; Peter is decent but imperfect; explicit spoken number/currency profile; no automatic fallback. |
| KittenTTS 0.8.1 | **Accepted opt-in** after 21:16 Rosie long-form and corrective listening | GBP0 | Eight official presets; developer preview; Rosie led on body pace/tone; explicit spoken number/currency profile. |
| Gemini 3.1 Flash TTS / Achernar | **Accepted opt-in narrator**; exact preview and 10:10 app-path gate passed by ear | GBP0 on an unbilled Developer API Free project | Dave called the long file “one of the best”. Five one-attempt paragraph packs produced the complete 1,644-word gate after one zero-output 503 and manual resume. Current official SDK/API only, resumable cache, no paid/Vertex/Batch fallback. Free content may train Google products; ten requests/day means roughly 28 quota-days for a 600k-character novel. |
| NVIDIA MagpieTTS Multilingual v2607 | Free-T4 capacity passed; listening open | GBP0 for the completed free-Kaggle gate | Official 364M stateful English long-form path with five baked presets. Exact v2607 model and NeMo Speech v3.0.0 runtime are pinned. All five short arms plus John's 9:14 / 79-chunk arm fully decode; T4 RTF 1.081–1.142, long-arm peak 11.61 GiB allocated / 14.31 GiB reserved. T4 is unsupported officially and quality remains unverified until Dave listens. |
| AWS Polly Long-Form | Implemented via `tts-proxy` | Avoid | Proven too expensive for good-quality audiobook use. Keep only as legacy code path; do not use for normal conversions. |
| Inworld TTS 1.5 | Implemented via `tts-proxy` | Likely over budget for full books | Keep as experimental/premium unless real account pricing proves otherwise. |

## Current External Options

Prices below were rechecked against the providers' official pages on
2026-08-13. They are screening costs, not approvals: no paid service becomes a
book fallback until Dave hears a representative long-form sample and the
actual account bill confirms the calculation.

| Option | Price signal | Rough cost for 600k chars | Fits GBP2/book? | Implementation fit |
|--------|--------------|---------------------------|-----------------|--------------------|
| [Azure Speech](https://azure.microsoft.com/en-gb/pricing/details/speech/) | F0 includes 500k Neural chars/month; checked UK South S0 retail meter ~GBP11.36/1M chars | F0 free if the monthly hard cap is respected; S0 ~GBP6.82 before SSML overhead | **F0 only** | **Quality-floor pass, integration open:** 48 kHz William (AU), Connor (IE) and Luke (ZA) are acceptable by ear, though weak on emotion and less real than Arthur. Mandatory number/currency processing, paragraph pacing and IPA corrections. Microsoft bills SSML body markup as well as visible text; only outer `speak`/`voice` tags are excluded. F0 first, never automatic paid fallback. |
| [Gemini 3.1 Flash TTS](https://ai.google.dev/gemini-api/docs/pricing) | Standard input/output is free on Free Tier; paid is USD1/M text tokens + USD20/M audio tokens (25 audio tokens/s) | **GBP0 only on Free**; 10 hours is 900k audio tokens, about USD18 output plus text, already far above GBP2 | **Free only** | Achernar's exact 10:10 app-path file passed by ear and is accepted opt-in. Preview model, ten requests/day and documented drift beyond a few minutes. Hard Free-only/no-retry/cache guards are live; a normal novel must resume across roughly four weeks of daily quota. |
| [Google Cloud Chirp 3 HD](https://cloud.google.com/text-to-speech/pricing) | First 1M chars/month per billing account free, then USD30/M; billing is mandatory and overage is automatic | Often GBP0 for one normal book within the allowance; about USD18/600k after exhaustion | **Free allowance only** | Exact control exists as `en-GB-Chirp3-HD-Achernar`, but Google does not promise it matches Gemini Achernar. Budgets are not hard caps. Do not enable until an atomic rolling character ledger reserves payload before every request, preflights the whole book and refuses above 900k/31 days. |
| [Cartesia Sonic 3.5](https://www.cartesia.ai/pricing) | Free ~27 min/month; Pro USD5 for ~133 min; Startup USD49 for ~1,667 min | Free/Pro do not cover a novel; Startup amortization remains well above GBP2 for a typical book | No for normal books | Current model claims better naturalness and alphanumeric reading. Keep for short auditions only unless pricing changes. |
| [Lemonfox TTS](https://www.lemonfox.ai/text-to-speech-api) | USD5/mo includes 2M TTS chars; extra USD0.50 per 200k | USD1.50 of included capacity when batched, but USD5 minimum bill for one isolated month | **Cheapest known paid candidate** if quality passes and books are batched | Advertises OpenAI/ElevenLabs-compatible APIs; controlled quality/reliability test still required. |
| OpenAI `gpt-4o-mini-tts` | Pricing includes text input tokens and audio output tokens; pricing docs estimate USD0.015/min | About GBP5.40 for a 8-hour audiobook by minute pricing | Usually no | Could fit only shorter books. Needs real sample and billing check before trusting. |
| [OpenAI `tts-1`](https://developers.openai.com/api/docs/models/tts-1) | USD15/1M chars | USD9 / about GBP6.75 | No for typical novels | Easy API shape, but above the cheapest candidate. |
| [Inworld TTS-2](https://inworld.ai/pricing) | USD25/1M chars on demand; official page advertises 70 free minutes | USD15 before any free allowance | No for normal books | Sample allowance may be useful; paid rate is not competitive with Lemonfox. |
| Deepgram Aura-2 | USD0.030/1k chars = USD30/1M chars | About GBP13.50 | No | Good for voice-agent clarity; too expensive for this project's default budget. |
| [ElevenLabs Flash/Turbo](https://elevenlabs.io/pricing/api) | USD0.05/1k chars = USD50/1M chars | USD30 / about GBP22.50 | No | Use only for samples. |
| [ElevenLabs Multilingual](https://elevenlabs.io/pricing/api) | USD0.10/1k chars = USD100/1M chars | USD60 / about GBP45 | No | Premium only; not aligned with this project. |

## Open-Weight Candidates To Test

These are the most relevant low/no-cost options because they avoid per-character billing.

| Candidate | Why it matters | First test |
|-----------|----------------|------------|
| Kokoro latest direct stack | Kokoro is Apache-2.0, 82M params, fast, cheap, and already the repo default through Kokoro-FastAPI. No new model since v1.0 (Jan 2025), so no free upgrade waiting here. | Confirm current Docker image uses the latest stable Kokoro voice/model set; benchmark CPU vs GPU on 1 known book. |
| Chatterbox Turbo | MIT licensed, 350M params, lower compute than original Chatterbox, voice cloning, paralinguistic tags (`[laugh]`, `[sigh]`, `[chuckle]`). Won a widely-cited mid-2026 blind test vs ElevenLabs (65.3% vs 24.5%). **Sampled 2026-07-02 — see below.** | Done for a synthetic passage; next is a real-book chapter test. Deployment path: [devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server) exposes OpenAI-compatible `/v1/audio/speech`, Docker (NVIDIA/AMD/CPU), sentence chunking for audiobooks — drop-in beside Kokoro-FastAPI, no custom wrapper needed. |
| Hume TADA (1B / 3B-ml) | Open-sourced March 2026. Built for long-form narration: ~700s audio per context window, prosody consistency across long passages, zero content hallucinations on 1,000+ test samples. MIT code, Llama 3.2 Community License weights. Voice via reference-audio cloning; no OpenAI-compatible server exists yet, so bigger integration lift than Chatterbox. | Sample via HF Space `HumeAI/tada` (needs HF token; demo requests 120s ZeroGPU per call). TADA-1B fits an RTX 3060. |
| [IndexTTS-2.5](https://github.com/index-tts/index-tts/blob/39207d91c30899cad1e7c1b9eb678c241f678e55/README.md) | Stable `v2.5.0` adds voice cloning, token-aware 120-token splitting, 200 ms joins, `duration_factor` pace control and CMU English pronunciation annotations. The Bilibili Model Use License is not permissive OSS. | **Rejected for production after one corrective free-T4 job.** Complete-sentence calls removed the splitter-boundary corruption and fixed “one point five”, but Dave still found timing/pacing poor and the voice far less natural than Gemini Zephyr or Chatterbox. |
| [Fish Audio S2 Pro](https://github.com/fishaudio/fish-speech/releases/tag/v2.0.0-beta) | Official beta is real and not abandoned, but it is a 4B + 400M single-device runtime with an official minimum of 24 GB VRAM and a Research License. Plain single-narrator prose also needs external chunking. | Watch only. Ordinary free Kaggle T4 is 16 GB and T4x2 is not sharded by the official runtime; local CPU is not a realistic audiobook route. Do not spend a render unless the official memory path materially changes. |
| [NVIDIA MagpieTTS Multilingual v2607](https://huggingface.co/nvidia/magpie_tts_multilingual_357m/blob/v2607/README.md) | Official 364M model with five baked English presets, IPA pronunciation control and a beta stateful long-form path explicitly aimed at narration/audiobooks. NVIDIA Open Model License. | **Capacity passed / listening open:** five same-text preset arms plus John's 9:14 stateful continuity arm completed on one free T4 job at RTF 1.081–1.142. T4 is unsupported by NVIDIA's published list; do not integrate or expose voices before listening. |
| Chatterbox Multilingual | MIT licensed, 500M params, 23+ languages and cloning. | Only test if multilingual or cloning quality matters more than speed. |
| KokoClone / Kokoro voice-conversion experiments | Potential route to cheap voice cloning while keeping Kokoro speed. | Watch, but do not productionize until stability and license posture are clear. |

## Tracked But Not Pursued (2026-07 review)

| Model | Verdict |
|-------|---------|
| Voxtral TTS (Mistral, Mar 2026) | Open weights are CC BY-NC 4.0 (fine for personal use) but 4B params; API is USD16/1M chars (~GBP7/novel) — over budget. Track only. |
| MisoTTS 8B (Miso Labs, Jun 2026) | Expressive but conversational-agent-focused and too heavy for the RTX 3060 budget pattern. |
| IndexTTS-2, CosyVoice2 | Recur in 2026 rankings; audition only if Chatterbox disappoints. |

## Cost Model For The Next-Gen Engines (2026-07-04)

> Historical measurement table, not current routing policy. The active order is
> free local, then free Kaggle, then the cheapest paid path that has passed the
> same human listening floor. Paid GPU use is manual and never queue-triggered.

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
| Kokoro @ Vast RTX 3060 | ~20 min | ~GBP0.01 | Measured (GPU-PLAYBOOK) | Historical speed measurement; Kokoro no longer clears the quality floor |
| **Turbo @ Vast RTX 3060 ($0.05–0.06/hr)** | ~2–5h GPU | **~GBP0.11–0.20** | Historical derived estimate: published "up to 6x RT" | Not measured on this GPU; paid/manual only |
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

The old estimate that a GBP5–10 Vast top-up could convert 25–50 books was never
a billed measurement and is not a recommendation. Current official marketplace
pricing must be checked at the time of an explicitly requested paid run.

Consistency on Vast: interruptible instances can be reclaimed mid-book. The
repo already carries the mitigations built for Kokoro GPU runs (onstart
watchdog template, per-chapter retry, missing-chapter recovery). For
guaranteed uninterrupted runs, rent on-demand instead of interruptible at
roughly 2x the hourly rate — still pennies per book.

Deploy path when an engine is chosen: devnen/Chatterbox-TTS-Server as a
compose service or Vast template (OpenAI-compatible `/v1/audio/speech`, same
shape as Kokoro-FastAPI), reference voices from `data/voice_refs/`.




## FREE and CHEAP GPU for TADA (2026-07-08 — answering "prices are fucked")

**Current strategy: free local first, then free Kaggle.** Exhausted Kaggle quota
is not authority to rent anything: wait for quota reset or ask Dave whether the
lowest verified paid fallback should be used for that specific book. No
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
2. Start with free/local Chatterbox Nano + Beatrice; keep Chatterbox Turbo +
   Arthur as a per-book audition alternative, not an automatic quality reference.
3. Use free Kaggle for a better-sounding GPU finalist when it wins the audition.
   Qwen is the current full-precision consistency leader; VibeVoice and
   IndexTTS-2.5 are rejected on their tested paths. NVIDIA MagpieTTS v2607 is
   the current bounded stateful-long-form candidate.
4. Use accepted free-only Gemini/Achernar when its slow quota-paced path suits
   the book. If Free quota cannot sustain books, test Google Chirp 3 HD only
   after implementing a 1M-character monthly hard stop. Keep Fish S2 and
   CosyVoice as watchlist items until their official runtime/hardware boundary
   materially changes.
5. Only then optimise cost and speed. EdgeTTS is conditional (unofficial
   interface and proper-noun failures). Piper and Melo are not production
   fallbacks. Reconsider Piper only for a materially different, independently
   good model—not another wrapper or encoding change around VCTK-medium.

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
