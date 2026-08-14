# Engine Facts — OFFICIAL sources only

The baseline for engine behavior is the **official documentation**, not
inference from experiments. Every claim here cites its source. Anything we
believe but can't source is marked **[unverified]**. When code contradicts
this file, the code is wrong. (This file exists because we spent days
debugging problems the official docs already answered — see OPERATIONS.md
2026-07-09.)

## Listening outcomes (one user, one book — NOT a general ranking)

Recorded so the repo reflects what was verified by ear. The original comparison
used `Apple in China` (dense proper nouns, non-fiction) on 2026-07-10; later
accent-engine verdicts are dated in the table.

| Engine | Verdict | Hardware |
|---|---|---|
| Chatterbox Turbo (`uk_male_minter` / "Arthur") | "really really good" — accepted for full-book use | CPU only (Ryzen 9 8945HS, 16 threads) |
| TADA-1B (v8, cloned voice, after transcript+pacing fixes) | Better than earlier cuts, but residual pacing drift + proper-noun misreads | Kaggle T4 |
| Piper regional/VCTK path (2026-07-28) | **Rejected for production:** deployed 64 kbps, higher-bitrate same-WAV, and current Piper 1.6 direct clips were all “absolute shit”; almost every word wrong and poor sound | CPU only (zorin) |
| MeloTTS (2026-07-28) | **Rejected:** bad overall TTS, poor pronunciation and poor number handling | CPU only (zorin) |
| OmniVoice British/Australian (2026-07-28) | Far better than Melo; accents good, but Huawei/Xiaomi pronunciation bad and CPU throughput unsuitable for full books | CPU only (zorin) |
| EdgeTTS accented English voices (2026-07-28) | Accents “not bad”, but all tested Chinese company names were pronounced badly; not approved for Chinese-business nonfiction without a pronunciation A/B/fix | Microsoft cloud service |
| MOSS-TTS Local Transformer v1.5 (2026-07-29) | Short hard-text clip was **10/10**, but audiobook result is below Vibe/Qwen. The original 105-chunk chapter sounded sentence-stitched; both true single-pass attempts collapsed after ~2.5 min. A corrective 13-section/no-added-silence render was complete but still had audible joins, weaker expression and off pacing. “Not horrible,” but not a finalist. (`v1.5` is the release version, not a 1.5B parameter count.) | Kaggle P100 |
| Qwen3-TTS (2026-08-14 final ranking) | Full 6,166-word chapter **“really good”** and audiobook-listenable throughout. Strongest long-form consistency result; 33:03, RTF 2.056, structural ASR similarity 0.9848. Current full-precision long-form leader, not the system default. | Kaggle P100 |
| VibeVoice 1.5B (2026-08-14 corrected app-path + documented-turn gate) | **cfg 2.0 is the best tested setting; the flattened single-turn path remains rejected.** The opening was very good, then progressively accelerated after ~3 minutes. The community-documented repeated-same-speaker remedy has now rendered in two independent 1,998-word arms (four turns 7:16; seven turns 6:59), both structurally complete; human quality/pacing verdict is open. The corrected `draught, and` source removes that prior input defect from this gate. cfg 3.0 and 1.3 remain rejected. | Kaggle P100 |
| Higgs Audio V2/3B (2026-07-29) | Both repeat-seed renders were listenable: seed 12345 “pretty good”; 54321 also good but felt clipped/joined in several places. Seed-dependent seam stability keeps it behind Vibe/Qwen despite excellent pronunciation. | Kaggle P100 + HF Space |
| Pocket TTS / Peter Yearsley (2026-08-14) | Accepted as an opt-in book choice, not a default. The long-form body was decent/promising but uneven. On clean text, current sentence packing sounded more natural; paragraph-aware packing made intonation stranger. | CPU only (zorin) |
| NeuTTS Air / Jo (2026-08-14) | Decent/good voice. Dave selected the normalized arm, but heard “the e order” around “the order”; retain this as a separate synthesis defect rather than a number-handling failure. | CPU only (zorin) |
| KittenTTS / Jasper and Rosie (2026-08-14) | Accepted as opt-in book choices, not defaults. Jasper's short opening was scratchy. Rosie's long-form body led for pace/tone; her clean current/paragraph A/B sounded decent in both arms with no meaningful difference, so current packing remains. | CPU only (zorin) |

**Read this as a data point, not a recommendation.** It reflects one listener
and one hard passage/book; the hardware used is stated per row. TADA's ceiling is genuinely
higher — mid-generation it spontaneously voiced a quotation in its own native
voice with flawless prosody and pronunciation (v8 002, 03:03–03:55). Its
weakness is *control*, not capability: no long-form mode, no pronunciation
control, no documented sampling params. On a GPU, with shorter chapters, or
with fiction/dialogue, TADA may well win — and if Hume ships long-form support
it likely becomes the default (see issue #21). Both engines stay first-class;
pick by ear on your own hardware.

The Pocket/NeuTTS/Kitten rows record only what Dave heard. The original scripts
used the official APIs but bypassed app normalization. The 2026-08-14 blind
pairs isolated raw versus explicit spoken wording with model, voice and
settings fixed; normalized wording won 4/4. This closes the shared numeric
root cause while leaving the distinct Jo/Jasper artifacts open.

The long-form opening failure is also diagnosed at the input boundary, not by
inference from sound: captured request 1 was identical for Peter and Rosie and
contained Project Gutenberg catalogue fields with no terminal punctuation,
then the first book sentence. The app now removes Gutenberg's exact structural
wrapper. The official [Pocket README](https://github.com/kyutai-labs/pocket-tts/blob/7fc13c7/README.md#unsupported-features)
says adding silence through text input is unsupported, while Kitten 0.8.1
documents only `generate(text, voice=...)`; undocumented engine knobs are not
being invented. Paragraph-boundary preservation was tested in our converter.
It lost for Peter and tied for Rosie, so it is not rolled out: current packing
uses fewer model resets and was equal or better by ear.

## Official voice inventory for the screened CPU engines (2026-08-14)

Only names explicitly documented by each pinned upstream are listed. No gender
or accent label is inferred where upstream does not provide one.

| Engine | Official ready voices/references | Custom voice boundary |
|---|---|---|
| [Pocket TTS 2.1](https://github.com/kyutai-labs/pocket-tts/blob/7fc13c7/README.md) | English: `alba`, `anna`, `azelma`, `bill_boerst`, `caro_davy`, `charles`, `cosette`, `eponine`, `eve`, `fantine`, `george`, `jane`, `jean`, `javert`, `marius`, `mary`, `michael`, `paul`, `peter_yearsley`, `stuart_bell`, `vera`. Other named catalogue voices: `giovanni` (Italian), `lola` (Spanish), `juergen` (German), `rafael` (Portuguese), `estelle` (French). | Accepts a local WAV or Hugging Face voice reference. The tested cloning weights remain behind Kyutai's model-terms/authentication gate; do not bypass it. |
| [NeuTTS Air 1.4.1](https://github.com/neuphonic/neutts/blob/ac69851f28fc63a487917e7c2e27f0d75c759cba/README.md) | Official references: English `dave`, `jo`, `emily`, `paul`, `sophie`, `steven`; Spanish `mateo`; German `greta`; French `juliette`. The four 2E names also work as ordinary references for Air. | Clone-first engine: clean mono 16–44 kHz WAV, 3–15 seconds, natural continuous speech, plus its exact transcript. |
| [KittenTTS 0.8.1](https://github.com/KittenML/KittenTTS/blob/0.8.1/README.md) | `Bella`, `Jasper`, `Luna`, `Bruno`, `Rosie`, `Hugo`, `Kiki`, `Leo`. | No official voice-cloning path is documented for this release. |

Pocket and Kitten now have isolated opt-in CPU services in this repository.
Their OpenAI-compatible wrappers call the official APIs above, reject unknown
voices instead of substituting one, and expose no paid/GPU fallback. Both use
the listener-selected `explicit` number/currency profile across previews and
book/recovery paths. Both are admitted as opt-in CPU book choices after long-
form and corrective listening. They remain excluded from automatic fallback
and do not replace Chatterbox Nano/Beatrice as the default.

The first recorded Vibe GPU-memory measurement comes from a later **short
accent sample**, not the heard full chapter: on a Kaggle P100, Irish peaked at
**5.299 GiB allocated / 5.607 GiB reserved** and South African at **5.166 /
5.604 GiB**. This is useful capacity evidence for a short request only; do not
promote it to a long-form VRAM ceiling.

## Qwen3-TTS / VibeVoice local native runtime audit (2026-07-29)

Sources: [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) ·
[microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) ·
[audio.cpp](https://github.com/0xShug0/audio.cpp) ·
[audio.cpp GGUF packages](https://huggingface.co/audio-cpp/audio.cpp-gguf) ·
[old experimental Vibe GGUF](https://huggingface.co/wsbagnsv1/VibeVoice-1.5B-gguf)

- The official Qwen repo supports local model loading through its Python stack,
  but documents CUDA/BF16 examples rather than an optimised CPU or GGUF route.
  The CPU result below therefore uses the third-party audio.cpp runtime, not an
  official Qwen CPU backend.
- Microsoft's current VibeVoice repo has removed the TTS code and disabled the
  TTS model link. The older `wsbagnsv1` GGUF explicitly says there is no
  inference support. Neither is the tested route: the working local path is
  audio.cpp's newer packaged VibeVoice implementation.
- audio.cpp documents CUDA as its optimised backend and CPU as a portability
  path. Its Q8 test report marks Qwen Q8_v2 as retaining speaker-sensitive
  components at 16-bit to avoid long silence, while Vibe Q8 passes with possible
  drift. These are upstream runtime claims, not listening results in this repo.

Controlled local measurement on zorin (i5-12400, four-CPU cap, no container
swap, UK Minter reference, 36 hard words):

| Runtime/model | Audio | Framework session | Session RTF | Peak container memory | ASR evidence | Claim level |
|---|---:|---:|---:|---:|---|---|
| audio.cpp Qwen3-TTS 1.7B Base Q8_0_v2 | 15.28 s | 41.251 s | **2.70** | **7.937 GiB** | Complete 36/36 | **Short clip passed human listening**; sounded fine |
| audio.cpp VibeVoice 1.5B Q8_0 | 15.60 s | 101.736 s | **6.52** | **4.551 GiB** | Complete 36/36; Whisper's Huawei/Xiaomi substitutions were false positives | **Short clip passed human listening**; sounded fine |

Cold process wall was 46 seconds for Qwen (RTF 3.01) and 107 seconds for Vibe
(RTF 6.86). Vibe exposed 1.113 seconds of component weight-load timings. Qwen
did not expose a separate model-load timer; combined Docker startup, model setup
and teardown outside the session took roughly 4.7–5.7 seconds. The small-sample
session RTFs extrapolate to about
33.5 CPU hours for Qwen and 80.9 for Vibe per 12.4 hours of finished audio, but
that is **not** a long-form benchmark. Production remained healthy during the
bounded tests. The local WAVs were subsequently heard and both short clips
sounded fine. They still do not inherit the long-form verdicts of the
full-precision Kaggle renders; long-form Q8 remains unproven.

### Full-precision production adapter boundary (2026-07-29)

Both candidates are wired as first-class explicit engines. The shared delivery
path is deployed and Vibe has one retained structural production E2E proof.
That proof does not override the later human rejection of Vibe's single-pass
long-form delivery. The local CUDA images remain optional and unpromoted:

- `vibevoice-tts` uses the official `microsoft/VibeVoice-1.5B` weights through
  `vibevoice-community/VibeVoice` pinned at
  `07cb79feadd2d3fd7f47530d4c964a12857936a0`. Microsoft disabled the official
  TTS inference code because of misuse, so this provenance is shown in
  `/health`; it must not be described as an official Microsoft runtime. The
  model card frames the release for research/R&D and warns against real-world
  use without further testing. One request is one chapter (fp16 + SDPA, DDPM
  10, deterministic seed). The selected adapter default is **CFG 2.0**. The
  blind comparison rejected 3.0 as muffled/distant; the corrected cfg-2 app
  path cleared the direct arm's local insertion but failed full-file listening
  because pace/prosody progressively accelerated after ~3 minutes. It is not
  production-approved. The community runtime
  also warns that only FlashAttention was fully tested and SDPA may reduce
  quality, so this backend boundary must remain visible in any verdict.
  The same pinned community README explicitly recommends repeated turns with
  the same speaker label when output becomes too fast. A dedicated blind gate
  now tests four versus seven such turns over one 1,998-word generation per
  arm. Both files are complete and playable; neither is production-approved
  until Dave grades pacing and long-form comfort. This evaluation does not pass
  through the current HTTP adapter, which intentionally accepts ordinary text
  and serializes it as one `Speaker 1:` turn.
- `qwen3-tts` uses the official Apache-2.0 `QwenLM/Qwen3-TTS` package pinned at
  `022e286b98fbec7e1e916cb940cdf532cd9f488e` and the official
  `Qwen/Qwen3-TTS-12Hz-1.7B-Base` weights. Production keeps the accepted
  sentence-boundary strategy: about 450 characters per pass and 350 ms of PCM
  silence between passes.
- Only `uk_male_minter_vibevoice` and `uk_male_minter_qwen3` are registered.
  Arthur is the only reference heard in the full-chapter finalist auditions;
  the other UK references are not silently promoted.
- Local services are explicit CUDA-only Compose profiles (`vibevoice`,
  `qwen3`). They use an already-attached GPU and never provision Vast. The
  default remains free/local Chatterbox Nano. Free Kaggle is the normal
  full-precision target.
- Every local, Kaggle and recovery render uses the canonical converter with
  `--job-id --qa`. Kaggle session reports are merged by chapter. Missing,
  invalid, empty or incomplete `qa_report.json` holds these engines at
  **review needed before M4B or Audiobookshelf sync**.
- Kaggle checks out the exact 40-character `APP_GIT_SHA` deployed on the worker,
  not `master`, and verifies the Git-LFS Arthur reference by RIFF header, size
  and SHA-256 before loading either model.

The retained Raven `output_format=m4b` E2E passed on 2026-07-29 as job
`313aab35`: 1,130 source words, 361.392 seconds of audio, ASR worst WER 0.115,
`qa_verified=1`, one chaptered M4B plus cover, and a byte-identical
Audiobookshelf copy. Generation took 440 seconds (RTF 1.218); end-to-end Kaggle
session/poll handoff was about 15.8 minutes. Full-chapter VRAM was not logged.
Exact-revision GHCR builds for Vibe and Qwen passed in Actions run
`30431465911`. A later 13,666-word / ~77-minute single-pass P100 render proved
the long-form capability behind #44, but the corrected 6,166-word app-path file
failed human listening through progressive speed/prosody drift. Issue #44 is
therefore closed with a negative promotion verdict; an exact-image CUDA smoke
would not change that quality decision. The Yellow Wallpaper timing run
extrapolates to **28.10 free Kaggle GPU-h
for Vibe** and **25.49 h for Qwen** per 12.4-hour book—93.7% and 85.0% of a
nominal 30 h weekly allowance. LOW-COST-TTS.md's Vast figures ($2.99/$2.72) are
scenario estimates, not billed measurements; this integration creates no paid
Vast path.

## Piper deployment audit (2026-07-28)

The listening verdict applies to our outputs, not automatically to every Piper
deployment. The deployed ONNX hash matches the official VCTK-medium artifact and
all configured speaker IDs match its `speaker_id_map`, so there is no evidence of
a corrupt model or wrong-speaker bug. However, the official model is only
medium/22.05 kHz, was fine-tuned from US Lessac, and uses `en-gb-x-rp` for every
speaker. Our archived `openedai-speech` wrapper runs Piper 1.2.0 and transcodes
previews to 64 kbps MP3; current upstream is 1.6.0 and supports raw phoneme
injection. Same-text deployed-encoding, same-WAV higher-bitrate and
current-runtime clips all returned `200 audio/mpeg` and were graded by ear.
All three failed badly: almost every word wrong and poor sound. The old wrapper
and bitrate are therefore not the fix; the tested official VCTK-medium model
path is closed. Keep Piper only as legacy/debug compatibility, not a production
engine or automatic fallback. See VOICES.md.

## Hume TADA-1B

Sources: [HumeAI/tada GitHub](https://github.com/HumeAI/tada) ·
[HF model card](https://huggingface.co/HumeAI/tada-1b) ·
[paper](https://arxiv.org/abs/2602.23068)

- **Reference transcript is load-bearing.** The voice prompt is built by
  aligning reference audio to its transcript; the README's troubleshooting
  says: *"If alignment looks wrong… check that you provided the correct
  transcript."* A garbled transcript corrupts alignment → degraded words/
  pacing in every generation with that voice. Verify with
  `prompt.print_alignment(model.tokenizer)`. (Bit us: our refs were garbled
  ASR until 2026-07-09.)
- **No long-form mode.** The API generates one text passage per call; nothing
  in the docs supports long-form continuity across calls. Chunk joins are OUR
  responsibility → the server inserts a ~250ms sentence-gap between chunks
  (`TADA_JOIN_SILENCE_MS`).
- **No documented sampling/pacing parameters.** `generate(prompt=…, text=…)`
  and `num_extra_steps` (continuation length) are the only documented knobs.
  Anything else we tune is **[unverified]**.
- **English encoder ASR.** For non-English refs the transcript MUST be
  provided (built-in ASR is English-only). Languages: ar,ch,de,es,fr,it,ja,pl,pt.
- **Tokenizer**: pulls `meta-llama/Llama-3.2-1B` (gated). We redirect to the
  byte-identical `unsloth/Llama-3.2-1B` [unverified byte-identical — works in
  practice].
- **Output**: 24 kHz. Model ~1B params, needs ~6.5 GB peak RAM to load
  [measured, not official].

## Chatterbox / Chatterbox-Turbo (Resemble AI)

Source: [resemble-ai/chatterbox GitHub](https://github.com/resemble-ai/chatterbox) (MIT)

- **Official pacing/expressiveness controls** (the ONLY supported ones):
  - `cfg_weight` — default **0.5** ("works well for most prompts");
    **lower (~0.3) improves pacing**, suits expressive/dramatic delivery.
  - `exaggeration` — default **0.5**; higher (~0.7+) **speeds speech up**;
    pair higher exaggeration with lower cfg_weight for slower, more
    deliberate delivery.
  - Wired in `chatterbox/server.py` via `CHATTERBOX_EXAGGERATION` /
    `CHATTERBOX_CFG_WEIGHT` env + per-request overrides (2026-07-09).
  - The OpenAI-style `speed` field is NOT a Chatterbox parameter — our
    servers ignore it (see issue tracker).
- **Turbo (350M, English-only)**: "lower compute and VRAM", built for
  low-latency agents but "excels at narration"; supports paralinguistic tags
  `[cough]`, `[laugh]`, `[chuckle]`.
- **Reference clip**: examples use a ~10s clip; no official length/quality
  spec beyond that.
- **No documented text-length limit or long-form mode.** Chunking is ours.
- **Watermark**: outputs carry the Perth perceptual watermark (survives MP3
  compression/editing). This is built-in and official.
- **Hardware**: no official minimums published. Measured here: ~2–6 GB RAM
  generating on CPU [measured]; OOM-looped in a 6 GB container on a 15 GB
  host under memory pressure [incident 2026-07-09].
- **Multilingual V3 (500M, 23+ languages):** upstream says it improves speaker
  identity and accent preservation across languages. Local CPU evaluation is
  isolated as `chatterbox-v3`; successful hard-sample RTF was 4.15 Irish and
  4.81 South African with `cfg_weight=0`. Accent quality remains **[unverified]**
  until heard.

## OmniVoice

Sources: [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice) ·
[voice-design attributes](https://github.com/k2-fsa/OmniVoice/blob/master/docs/voice-design.md)

- Voice-design accents are a fixed validated vocabulary: American, British,
  Australian, Canadian, Indian, Chinese, Korean, Japanese, Portuguese and
  Russian. Irish and South African are not accepted.
- English pronunciation can be overridden inline with bracketed CMU phonemes.
  This is the official mechanism to address proper names such as Huawei and
  Xiaomi.
- Measured locally at the default 32 diffusion steps: RTF 9.10 British / 9.06
  Australian on CPU. Dave graded the accents good and the result far better
  than Melo, but called out Huawei/Xiaomi pronunciation. Model weights are
  CC-BY-NC.

## Kokoro (82M) via Kokoro-FastAPI

Sources: [hexgrad/kokoro](https://github.com/hexgrad/kokoro) ·
[remsky/Kokoro-FastAPI](https://github.com/remsky/kokoro-fastapi)

- Classical TTS with a real g2p/pronunciation frontend; tiny (82M), runs on
  modest CPU. The OpenAI-compatible layer (incl. `speed`) is provided by
  Kokoro-FastAPI — `speed` IS honored on this engine.
- Best used with the FULL legacy normalization path (numbers/abbrev spelling)
  — it does not read raw numerals/symbols as well as LLM-based engines
  [unverified — established practice].

## Upstream converter (p0n1/epub_to_audiobook)

Source: [p0n1/epub_to_audiobook](https://github.com/p0n1/epub_to_audiobook)

- We drive it with `--tts openai` against our engine shims. Flags we rely on:
  `--voice_name`, `--model_name`, `--no_prompt`, `--speed`, `--newline_mode`,
  `--title_mode`, `--search_and_replace_file`, `--chapter_start/end`.
- `--speed` only has effect on engines whose API honors it (Kokoro via
  FastAPI; Edge). Chatterbox/TADA shims ignore it.
- `--remove_endnotes` must never be used (its regex corrupts decimals and
  alphanumerics — see PREPROCESSING.md).

## Local hardware reality (for "what can run where")

| Host | CPU | RAM | CUDA | Verdict |
|---|---|---|---|---|
| zorin (upgraded 2026-07-20) | i5-12400 (6c/12t) | 31 GB | none | Kokoro/Chatterbox comfortable; TADA works but remains opt-in. Both Q8 short clips passed human listening. Qwen Q8 fits at 7.94 GiB and projects ~33.5h/book; Vibe Q8 fits at 4.55 GiB and projects ~80.9h/book. Long-form Q8 remains unproven. |
| Windows box | Ryzen 9 8945HS (16 threads) | 29 GB | none (Radeon iGPU) | Chatterbox + TADA fit comfortably on CPU; ~3–4× old NUC speed [measured CPU class] |
| Cloud | Kaggle T4 (free) / Vast (paid) | — | yes | fast path for TADA/Chatterbox |

## Standing rule

Before tuning or "fixing" an engine, read its official docs first and cite
them here. Experiments only fill gaps the docs leave, and get marked
[unverified] until sourced or measured.
