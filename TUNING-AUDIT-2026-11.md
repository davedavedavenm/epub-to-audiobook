# Tuning audit: November 2026

Source audit prepared 2026-11-11. This document compares the exact adapters and revisions used by the liked-voices worktree with current official maintainer/vendor documentation and the pinned runtime implementations. It records implementation settings and documentary defaults; it does not claim a particular setting is optimal by reasoning alone. The initial audit was read-only; follow-up sections distinguish actual experiments, measurements and listening verdicts.

## 12 November — Higgs3 reference-free native default audition

A private text-only evaluation completed using official Boson weights
[`bosonai/higgs-tts-3-4b@239f63fb7b02b1aa085f98d9efae5e35cc5523e8`](https://huggingface.co/bosonai/higgs-tts-3-4b/tree/239f63fb7b02b1aa085f98d9efae5e35cc5523e8),
weight SHA-256 `2f7965264c360b38180885006944aa16bd1de20f4e6cff79f6473bfcf8ae3d5a`.
The runtime is the separate community vLLM-Omni 0.30.0 project, pinned to
`a8576ccb725c4e21cd13c3eb5f9a546b21149d2b`; its
[offline example](https://github.com/vllm-project/vllm-omni/blob/v0.30.0/examples/offline_inference/text_to_speech/higgs_audio_v3/end2end.py)
and matching deployment YAML were inspected and hash-recorded before inference.
The pinned [Boson license](https://huggingface.co/bosonai/higgs-tts-3-4b/blob/239f63fb7b02b1aa085f98d9efae5e35cc5523e8/LICENSE)
permits this private evaluation; no public model API, production approval, named
speaker reference or imitation prompt was used. The older Cillian clip remains.

The canonical raw source/prepared hash is `386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`.
Three paragraph requests use the native default voice. Stage 0 defaults:
temperature 1, top-p .95, top-k 50, max tokens 2048, seed 42, repetition 1.
Stage 1: temperature 0, top-p 1, top-k -1, max tokens 65536, seed 42,
repetition 1. Compatibility overrides are explicitly recorded: Triton attention,
eager execution, FlashInfer sampler disabled, stage-0 context 4096 with checked
prompt/output headroom. The upstream stage-1 context warning (65536 configured
versus 32768 derived) remains documented, not silently corrected. Runtime:
L40S, bfloat16 as observed in startup, Torch 2.13.0+cu130, vLLM/Omni 0.30.0.

A CPU-only model/hash/tokenizer preflight preceded GPU use. The first GPU call
generated all paragraphs but outbound-network blocking also prevented Modal's
result-blob upload. One transport-only corrective attempt allowed that transfer;
HF/Transformers remained offline with the exact snapshot baked into the image.
No synthesis settings or seed were changed. Both apps are stopped; no persistent
volume was created. This is not evidence of bit-identical reruns.

The returned chunks total 66.80 seconds, 24 kHz mono. MP3 SHA-256:
`9561d4f8bcaa163b44bafdae0ec3eca8ee7c2b69dbf011281411b5d0f065b132`.
Unprompted Whisper small/int8 found .976 normalized coverage, no aligned dropped
run and no missing tail; it varied on the opening word and $1.2 million passage.
Those are listening flags, not established pronunciation errors. No human
naturalness or quality verdict exists. Exact render/settings/ASR receipts are
local beside `standard-v1/all-engines/higgs3_default_audition.mp3`; raw chunks
and transport evidence are in `scratch/tts-nov11/higgs3-default-*`.
The MP3 and canonical sample manifest were preinstalled with no-clobber creation
and full hash verification. App registration and endpoint verification are the
next deployment step; this audition has no integrated book route.

## 12 November — TADA-1B Shared Standard v1, cached community-tokenizer CPU audition

- **Purpose and boundary:** After the official Meta tokenizer/config file path
  returned 403, the four configured TADA voices were rendered through the
  historical project adapter using only its already-cached community tokenizer
  snapshot. This is an explicitly identified community-tokenizer path, not the
  fresh official Meta-tokenizer migration. The model runtime was offline: Docker
  `--network none`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and the existing
  `epub-to-audiobook_tada-cache` mounted read-only. No model, tokenizer, or mirror
  asset was downloaded during cold-load or synthesis. The Meta/community
  tokenizer equivalence remains unverified; this experiment does not evade or
  resolve the official access denial.
- **Exact provenance:** The project image was built from the tracked TADA recipe
  at Git commit `1e57fdd2c25131641a89c51e4b3045de61a3153a`, image
  `sha256:e166fd373b1ed4cc947e0cc5fa03f1c41978701534a533260050558ba02942f3`.
  Project adapter `tada/server.py` SHA-256 is
  `538dc97e4ad36b7647aab1ca821da18f5d3889e76d667cb790d40691086a0623`;
  tracked Dockerfile SHA-256 is
  `71b0f689ea8842f63bba426e5425a7c863ff6e9d697300c6d90997b8c8c13d4d`.
  Runtime was published `hume-tada==0.1.9`, Transformers 4.57.6, Torch
  2.8.0+cu126, torchaudio 2.8.0+cu126, torchvision 0.23.0+cu126, and
  descript-audio-codec 1.0.0. Model `HumeAI/tada-1b` snapshot
  `39a987c813d70bc70587757c3ed82c6e9853077d`; codec
  `HumeAI/tada-codec` snapshot `4413b57a1f223c6f1530a8579c24af4238718c83`;
  adapter tokenizer request resolves through its historical redirect to
  `unsloth/Llama-3.2-1B` snapshot
  `9535bd9b1d1dea6acafbdc4813b728796aeb28da`. The TADA model weight SHA-256 is
  `32063b83702a6a9f7527c1541b4e9adb24433f0b3563f4bd8345aebbb8282c39`; codec
  encoder, decoder and aligner hashes and the tokenizer JSON hash are in each
  staged `*.render.json` receipt.
- **Source gate:** Hume's [published 0.1.9 package metadata](https://pypi.org/pypi/hume-tada/0.1.9/json)
  requires Python >=3.10, Transformers >=4.57.1,<5, Torch >=2.7,<3, torchaudio,
  torchvision, and descript-audio-codec >=1.0.0. Hume's
  [official README](https://github.com/HumeAI/tada) describes TADA's Llama 3.2
  base and access prerequisites; the official
  [TADA model card](https://huggingface.co/HumeAI/tada-1b) identifies the public
  checkpoint. The adapter and tokenizer substitution remain project-owned.
  Published 0.1.9 PyPI metadata differs from the current upstream `main`
  `pyproject.toml` Torch upper bound; the observed render used the published
  package and pinned project image above, not an unversioned source install.
- **Frozen input and settings:** All four requests used the same prepared text
  obtained from `voice_sample.sample_text_for('tada')`: sample ID
  `narrator-standard-v1`, source SHA-256
  `386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`
  (147 raw words), prepared SHA-256
  `74de152cc1ed27890fbbcabc88f26d5cf360953e64e70a5d56d897ff1ceb0ee9`
  (151 words). Existing adapter settings were preserved: CPU bfloat16, 600
  character chunks, 250 ms inter-chunk silence, `Right. ` lead-in trimmed by the
  adapter, 24 kHz mono output, no exposed seed. Each voice used its exact
  configured reference WAV and checked-in transcript; hashes are in the per-voice
  receipts. Docker was capped at 4 CPU and 14 GiB RAM. The first container's
  unrestricted swap use filled the remaining host swap and its in-flight request
  was stopped before it wrote an artifact. The same request was rerun unchanged
  with `--memory-swap=14g` equal to `--memory=14g`, which disables swap access for
  that container per the official
  [Docker resource-constraints documentation](https://docs.docker.com/engine/containers/resource_constraints/).
  All four requests then completed within the 300-second per-voice cap. TADA
  container peak observed use was about 8 GiB; host MemAvailable remained above
  8 GiB at sampled checks; app `/api/health` latency stayed 44–247 ms. The owned
  audition container was removed after the batch; no other service was stopped.
- **Observed renders (one run each, not speed benchmarks):** Arthur
  (`uk_male_minter_tada`) took 137.518 s and produced 71.469 s audio; Harriet
  (`uk_female_golding_tada`) 123.290 s / 69.570 s; Edmund
  (`uk_male_yearsley_tada`) 123.440 s / 70.350 s; Beatrice
  (`uk_female_samuel_tada`) 124.765 s / 75.469 s. WAV and MP3 hashes, sizes,
  exact requests, runtimes, references, and official preview manifests are staged
  as per-voice `*.render.json` and `*.sample.json` files beside the audio under
  `evaluations/new-engines/output/november-2026-south-africa/standard-v1/all-engines/`.
- **Unprompted completeness audit:** All four MP3s were audited with
  faster-whisper small, CPU int8, 2 threads, English, beam size 5, no VAD and no
  prior-text conditioning. Harriet, Edmund and Beatrice had no >=3-word internal
  drop flag and no unheard tail; their transcripts nevertheless varied
  materially on proper names and on the 1,250/875 figures, so those details need
  listening. Arthur's small pass flagged a possible internal omission around
  1,250 invited / 875 attended (cover 0.892, tail_unheard 0). An independent
  cached base.en pass differed on that passage (cover 0.862, tail_unheard 0, no
  drop flag). Arthur's number-span completeness is therefore uncertain; both
  exact transcripts/reports are preserved. These ASR results are completeness
  signals, not pronunciation or audio-quality verdicts. Dave has not yet rated
  these four takes by listening.
- **Receipts and status:** `scratch/tts-nov11/tada-standard-v1-build-receipt.json`
  records the image, package freeze, offline cold-load, resource readings and
  initial interrupted attempt. Per-voice provenance and ASR reports remain local
  with the audition artifacts. These clips are staged for the app's Shared Test
  v1 audition; promotion awaits the warning-note deployment and exact API/hash
  verification. No app source was edited in this batch.

## 11 November — Shared Standard v1 GPU preview outcomes

- **CosyVoice 3 (audition-only):** Official [CosyVoice source](https://github.com/QwenAudio/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc), commit `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc`; official [Fun-CosyVoice3-0.5B-2512 snapshot](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4e8d000f4bcd70751be16fa94bf3d85a18), revision `29e01c4e8d000f4bcd70751be16fa94bf3d85a18`. Uses the pinned upstream requirements except optional TensorRT packages; official `AutoModel` eager path (`load_trt=False`), no explicit seed, chunk limit 300 characters, speed 1.0, non-streaming, `You are a helpful assistant.<|endofprompt|>` prompt prefix, and FFmpeg libmp3lame 96 kbit/s output from the project wrapper. Runtime observed: L40S, Torch `2.3.1+cu121`, CUDA toolkit 12.4.131, transformers 4.51.3, NumPy 1.26.4, WeText 0.0.4, Whisper 20231117, pyworld 0.3.4. Reference WAV hashes were checked against both engine asset copies; prompts use checked-in `tada/voices/ref_transcripts.json`, not the historical CosyVoice Whisper cache. Four Standard v1 files were staged, ASR-checked, promoted and verified by exact HTTP/body hashes. Beatrice's ASR flagged two middle spans, with no tail truncation; this is not a confirmed audio error. No new human listening or quality verdict was recorded. Wrapper/provenance receipt: ignored `scratch/tts-nov11/render_cosy_standard_only.py` and per-voice `*.render.json` under `evaluations/new-engines/output/november-2026-south-africa/standard-v1/all-engines/`.
- **Gemini 3.1 Flash TTS:** Exact model `gemini-3.1-flash-tts-preview`, pinned project adapter dependency `google-genai==2.18.1`; official [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation), [Interactions API](https://ai.google.dev/api/interactions-api), [model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-tts-preview), [billing](https://ai.google.dev/gemini-api/docs/billing), [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). The adapter sends one Interactions API request per preset, 24 kHz mono PCM wrapped as WAV, fixed default audiobook/British-English style unless `GEMINI_TTS_STYLE` is set, retries disabled, local cap 10 requests per Pacific quota day. The Standard v1 batch consumed 10/10: nine clips fully decoded; Puck's safety refusal was counted and not retried. Billing API confirmed the dedicated project has billing disabled. The engine-specific explicit-normalized sample SHA-256 was `d13e1b48bdbfb5ed60fab3736f7287b71ffc6a7418955ca976cb1fc7092e77c9`; nine successful outputs were audition inputs only, with no new human verdict. Achernar's older approval does not transfer to this clip.
- **TADA-1B:** Fresh pinned-official migration is blocked because the official [Meta Llama 3.2 1B repository](https://huggingface.co/meta-llama/Llama-3.2-1B) tokenizer/config file request at revision `4e20de362430cd3b72f300e6b0f18e50e7166e08` returned HTTP 403 (not authorized). Readable repository metadata did not establish file access. No alternate mirror was used to bypass the denial, no GPU synthesis was launched, and no cache was changed. The existing community-tokenizer adapter/previews remain distinct and unverified for equivalence; this is not a new audio-quality verdict.
- **Fish Speech S2 Pro (`fish_cillian_irish`):** One bounded Shared Standard v1 audition used the official [Fish Speech inference](https://speech.fish.audio/inference/) and [installation](https://speech.fish.audio/install/) guidance, pinned official runtime commit [`214da3cd841bda85da2496b96cd3c4d7edb1337e`](https://github.com/fishaudio/fish-speech/tree/214da3cd841bda85da2496b96cd3c4d7edb1337e), and official [`fishaudio/s2-pro` revision `1de9996b6be38b745688de084d87a5633f714e4e`](https://huggingface.co/fishaudio/s2-pro/tree/1de9996b6be38b745688de084d87a5633f714e4e). This older runtime loads `DualARTransformer`, matching the locked Cillian recipe; the later upstream Omni loader was not substituted. Runtime was Python 3.10.17, Torch 2.8.0+cu128, CUDA L40S, bfloat16; the CPU preflight loaded the pinned weights, DualAR caches and codec, checked all reference hashes, and passed in 64.29 seconds before GPU inference. Inputs were frozen from `voice_sample.sample_text_for('fish')`, source SHA-256 `386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`, prepared SHA-256 `74de152cc1ed27890fbbcabc88f26d5cf360953e64e70a5d56d897ff1ceb0ee9`. The unchanged recipe used seed 42 per sentence, temperature 0.85, top-p 0.9, top-k 30, iterative prompting, 300-character chunks, bf16, no retries; quote sentences used the expressive Cillian crop and other sentences the full reference. Recipe assembly trims/pads sentence edges, inserts sentence/paragraph gaps, applies the documented EQ/loudness chain, and encodes 192 kbit/s MP3. The render was 64.94 seconds; MP3 SHA-256 `044d971db3abf024d4ffd37df7cb92cf69e85164ced4d3be2c166db9f2d1bd55`. Unprompted Whisper small/int8 coverage was 0.982 with no flagged drops or unheard tail; this does not establish pronunciation or sound quality. The exact endpoint returned HTTP 200 with matching full-body hash and the API marked the preview current for `narrator-standard-v1`. The previous exact MP3 was archived under `/home/dave/ai/lab/stacks/epub-to-audiobook/data/previews-archive/standard-v1/20261111T235314Z`; no previous sample sidecar existed. Promotion receipt: `C:\Users\Dave\repos\epub-to-audiobook\scratch\tts-nov11\promotion-receipt-20261111T235314Z.json`; per-voice render/ASR/staging records are in ignored `evaluations/new-engines/output/november-2026-south-africa/standard-v1/all-engines/` in the main worktree. Historical cache runtime/model pins are not proven; the timestamp-based match to this DualAR-era source is only an inference. The Fish license is the [Fish Audio Research License](https://huggingface.co/fishaudio/s2-pro/blob/1de9996b6be38b745688de084d87a5633f714e4e/LICENSE.md), which permits non-commercial research/evaluation and requires separate written permission for commercial use. No new human listening or quality verdict was recorded. The successful app `ap-b6pKVyfBNxf0n05Nwxaf6W` used USD 0.0846 in its reported CPU, memory and L40S resources; the Fish-labelled Modal rows across the same hourly bucket total USD 0.340662 including other build/preflight attempts, so that aggregate is not the render-only cost.

## 11 November follow-up: shared passage and bounded clone experiments

- **Isolated preparation environments:** the lean Modal/Kitten Python
  environments lacked `num2words`; the optional fallback in the general text
  normalizer silently produced different Cosy/Vibe payload hashes. This was
  caught before their new audio was offered. Shared sample preparation now
  requires that dependency explicitly, including modern profiles, and errors
  instead of changing text. Prepare/freeze text in the app environment, then
  pass JSON plus exact source/prepared hashes to inference. Native Maya/Vox
  audition contracts deliberately receive raw source and are separate exceptions.
- **TADA tokenizer boundary:** the existing adapter redirects to a community
  Unsloth tokenizer; equivalence with Meta is unverified. Hugging Face model
  metadata was readable, but actual official Meta tokenizer/config downloads
  returned 403 (account not authorized). Metadata access was not file-access
  permission. No new mirror was used to route around the denial, and the new
  pinned-official TADA GPU batch remains blocked. Existing cached previews and
  the historical adapter remain unchanged apart from correcting its unsupported
  byte-identical comment; no old-quality root cause is established.

- **Edge client:** 7.2.8 returned HTTP 403 before audio. Maintainer releases
  [7.3.0](https://github.com/rany2/edge-tts/releases/tag/7.3.0) and
  [7.3.1](https://github.com/rany2/edge-tts/releases/tag/7.3.1) document the updated
  service protocol and locale-safe date parsing. Isolated 7.3.1 produced Ryan and
  the Australian/UK samples successfully with default rate/pitch/volume; the app
  dependency is now pinned to 7.3.1. This remains a community client, not a
  Microsoft-supported synthesis API. Andrew returned no audio; all other presets
  are being checked separately, without substituting a different voice.
- **Kitten John Kani:** official KittenML 0.9.7, model
  `c93cb7c271baa51d9ae8204d5277988906f235a2`, packed/stable, seed 42,
  normalize enabled, decoder `749d1c1a46eb10492095d68fbcf55691ccf137cd`.
  Reference SHA `8abbb7e6df836f2b08bc9af2fd498cc3ce3f067e4627a22ddb7c45164e70f8a6`.
  Full standard: 79.59 seconds, CPU4, 983.1 seconds inference. ASR reached the
  ending but flagged possible added Syria/repeated March. Short A/B changes only
  documented `use_reference_prompt` True to False; B is 18.28 seconds and its
  unprompted ASR covers all 40 words. Neither ASR nor duration establishes accent
  quality. The source-prepared payload was frozen outside the inference venv,
  which lacks some production normalizer dependencies.
  The preferred short False setting was also extended to the full standard:
  86.86 seconds audio, 521.1 seconds CPU4 inference. Independent ASR reached
  the ending but flagged a possible missing distance phrase and repeated words.
  It is retained as a separate local audition, not a silently approved app-cache
  replacement. The timing is one observed run, not an isolated speed benchmark.
- **Qwen GPU experiment:** official `QwenLM/Qwen3-TTS` commit
  `022e286b98fbec7e1e916cb940cdf532cd9f488e` (qwen-tts 0.1.1),
  `Qwen/Qwen3-TTS-12Hz-1.7B-Base` revision
  `fd4b254389122332181a7c3db7f27e918eec64e3`, Apache-2.0; official
  [API/README](https://github.com/QwenLM/Qwen3-TTS) read before generation.
  Same John reference plus exact transcript; full conditioning
  (`x_vector_only_mode=False`), English, seed 42, bfloat16/SDPA, generation
  defaults except the existing app's 4096-token ceiling. L4/A10 remained in
  scheduling; L40S completed through authenticated Modal 1.5.5, without a new
  login or Vast. John short/standard and Arthur standard durations are 15.12,
  63.78 and 70.26 seconds; ASR found no multiword drop or missing ending.
  CustomVoice Aiden (weights `0c0e3051f131929182e2c023b9537f8b1c68adfe`)
  also completed at 69.1 seconds. All apps stopped, billed cost zero, existing
  credit consumed. Runtime/model snapshots and actual settings are retained
  with each clip. Dave ranked the short Qwen take above controlled Kitten,
  then the preserved baseline; this does not approve the separate longer takes.

## Material findings first

### Additional GPU source audit (11 November)

Breeze's official runtime `breezeblue-ai/breeze-tts` was inspected at
`daa6cb2efe5471f09369229f322d20bb956cb3c3`, weights
`BreezeBlue/Breeze-TTS-2` at `3e28c5151381a722f1d8661b4118c298caa77aa4`.
The older project renderer supplies materially mismatched reference transcripts
for five of its six voices and applies undocumented post-EQ. ASR identifies
these mismatches but cannot supply authoritative source transcripts for the
uncertain tails. Arthur's matching transcript is in `qwen3/ref_transcripts.json`.
Historical Breeze runtime/weight revisions were not pinned, so remain unknown.

The current [Breeze license](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/3e28c5151381a722f1d8661b4118c298caa77aa4/LICENSE)
requires explicit speaker consent for named-speaker imitation. None was found
for these references; that clone batch was not launched. A fictional, reference-
free Voice Design evaluation is a separate experiment, not a replacement labelled
as an existing speaker. Its [official inference interface](https://github.com/breezeblue-ai/breeze-tts/blob/daa6cb2efe5471f09369229f322d20bb956cb3c3/infer.py)
defaults to CFG 1; the README recommends CFG 4 for instruction-following. Log
the actual override and check output-token capacity against the full passage.

The current [Higgs TTS 3 model card](https://huggingface.co/bosonai/higgs-tts-3-4b)
also explicitly prohibits cloning without consent. No new named-reference
Higgs audition was launched. This audit does not retroactively establish
historical licensing/provenance or alter the locked reproduction recipe.

The findings below describe the earlier CPU/Flux audit.

1. **Chatterbox Turbo/Nano receive controls that their pinned runtime ignores.** The project server passes `exaggeration=0.5` and `cfg_weight=0.5` to Turbo/Nano, matching its own environment defaults and comments. At the exact pinned source commit, Turbo `generate()` warns that CFG, `min_p`, and exaggeration are unsupported and ignored. The app never passes `min_p`; the runtime default is `0.00`. Do not describe those adapter values as effective Turbo/Nano tuning. Runtime defaults that do affect generation include temperature `0.8`, top-p `0.95`, repetition penalty `1.2`, top-k `1000`, and `norm_loudness=True`.
2. **Chatterbox model weights are not revision-pinned by the runtime.** `from_pretrained()` calls `snapshot_download()` without `revision`, and the multilingual implementation explicitly sets revision to `main`. The audited deployed services are Turbo and Nano; V3 is not running. Installed Turbo code SHA-256 reported by the parent is `2f27e8ff2fa35181fdd2849367fb96ecc2cb87a1088ca7520c8bd51946599f08`, and its installed `direct_url.json` identifies commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`; the model weights themselves remain mutable-main provenance.
3. **CPU adapter overrides are supported settings, not documented optima.** Pocket uses 4 sampler steps against runtime default 1; Phonon uses temperature 0.45 against pinned ptts default 0.3; Klein uses pause 0.18 seconds against model-card default 0.12. Their docs establish semantics, not that these overrides are generally best. A preference or quality claim needs an audition of the relevant output/text.
4. **Kitten pins its auxiliary decoder through an internal hook.** The adapter monkeypatches `kittenml.kittentts2.vocoder.hf_hub_download` to request the exact Chatterbox decoder revision. This protects weight provenance but is not the public KittenML API and is project-owned integration behavior.
5. **Current catalogue status differs from older prose.** `webapp/liked_voices.py` marks `kitten2_rosie` and `silencio2_peter` as disliked, even though older `narrators/README.md`/`DECISIONS.md` wording groups them with November likes. The implementation is the current catalogue state. Do not call these two currently liked.

## Scope and provenance inspected

Follow-up live verification on 11 November: the shared Zorin cache contains one
snapshot each for Turbo (`749d1c1a46eb10492095d68fbcf55691ccf137cd`) and Nano
(`71ccd1d0081b430592cea481f4307e764e07bc64`). All ten cached weight/conditioning
files' SHA-256 values match their LFS blob identifiers. The Arthur reference WAV
SHA-256 is `8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252`.
This establishes the observed assets for these CPU controls; it does not fix the
loader's future mutable-main behavior. Full local receipt:
`scratch/tts-nov11/chatterbox-live-provenance.json`. Official snapshot trees:
[Turbo](https://huggingface.co/ResembleAI/chatterbox-turbo/tree/749d1c1a46eb10492095d68fbcf55691ccf137cd),
[Nano](https://huggingface.co/ResembleAI/chatterbox-nano/tree/71ccd1d0081b430592cea481f4307e764e07bc64).

Project files: `narrators/server.py`, `narrators/requirements.txt`, `narrators/Dockerfile`, `narrators/README.md`, `webapp/liked_voices.py`, `tts_proxy/proxy.py`, `chatterbox/server.py`, `chatterbox/requirements.txt`, and the relevant engine decisions/voice notes. CPU adapter/runtime package pins are `pocket-tts==4.0.1`, `ptts==0.5.0`, `kittenml==0.9.7`, `transformers==4.57.1`, `tokenizers==0.22.2`, `torch==2.8.0+cpu`, and `torchaudio==2.8.0+cpu` (from the narrator image requirements/build). The CPU HTTP adapter is project-owned; the model runtimes are the upstream implementations listed below.

## CPU narrator families

### Pocket TTS 4 / English October 100M

- **Adapter in use:** `TTSModel.load_model(language='english_2026-10', temp=.3, sampler_decode_steps=4)`. It obtains reference state from one of the exact `kyutai/tts-voices` voice-zero WAVs at revision `323332d33f997de8394f24a193e1a76df720e01a`, seeds Torch with `42`, and calls `generate_audio`.
- **Pinned weights:** official Pocket TTS v4.0.1 configuration for `english_2026-10` pins the cloning weights at `kyutai/pocket-tts/languages/english_2026-10/model.safetensors@db04f0e653473e5c7333c69686ac92b7460b0c1d`. This is the cloning-capable checkpoint, not the separate non-cloning model.
- **Documented controls/defaults:** temperature is 0.3; runtime default sampler decode steps is 1. Adapter overrides steps to 4. Official docs note fewer steps are faster and lower quality; they do not identify 4 as a universal optimum. Reference-audio conditioning is supported. The reviewed docs do not specify a named-emotion or independent accent-strength control.
- **Licence/boundary:** runtime code MIT; cloning weights CC-BY-4.0; voice-zero entries have their own CC0 terms. Official acceptable-use guidance requires lawful, explicit voice-owner consent and disallows deceptive impersonation.
- **Primary sources:** [v4.0.1 config](https://raw.githubusercontent.com/kyutai-labs/pocket-tts/v4.0.1/pocket_tts/config/english_2026-10.yaml), [v4.0.1 runtime defaults](https://raw.githubusercontent.com/kyutai-labs/pocket-tts/v4.0.1/pocket_tts/default_parameters.py), [v4.0.1 release/source](https://github.com/kyutai-labs/pocket-tts/tree/v4.0.1), [pinned voice catalogue](https://huggingface.co/kyutai/tts-voices/tree/323332d33f997de8394f24a193e1a76df720e01a), [model licence/card](https://huggingface.co/kyutai/pocket-tts).

### Phonon 31M English / ptts 0.5.0

- **Exact model and catalogue:** `gradium/phonon-31m-en@92741c5b07d085ff840e26fea8ce43110b87852f`; catalogue `gradium/phonon-voices@0ee17205f254b5abc43b266c8a0f215565c352f7`.
- **Adapter in use:** `ptts.TTS('hf://gradium/phonon-31m-en@92741c5b07d085ff840e26fea8ce43110b87852f', lang='en', device='cpu', quant='f32', voice_catalog=<pinned catalogue>)`; synthesis passes a catalogue voice, `temperature=.45`, and seed `4242424242424242`. Pinned v0.5.0 API default temperature is 0.3 and default seed is the same value, so temperature is an explicit override. Float32 is supported. This integration uses the official Python binding, not an official container wrapper. The documented `duration_delta` condition is left at default.
- **Clone capability correction:** a `clone_voice(name, pcm)` method exists in the v0.5.0 binding, but method existence alone is not local cloning support. That runtime activates clone support only if the speaker-encoder weights load. The exact pinned public model revision contains the model weights and `default-voice.safetensors`, but no speaker-encoder/projection weights; its model card directs instant voice cloning/design to Gradium Studio. Therefore this checkpoint/runtime pairing supports the pinned catalogue voices, not local raw-audio cloning. The public API also exposes `cfg_coef`, but this adapter does not set it and the reviewed docs do not define it as an accent control.
- **Licence/boundary:** model Apache-2.0; runtime MIT OR Apache-2.0. Voice catalogue terms are separate. ptts 0.7.0 had been released on 2026-11-09; this adapter remains audited at 0.5.0, so newer docs/releases are not silently applied to its behavior.
- **Primary sources:** [pinned v0.5.0 Python API](https://github.com/gradium-ai/xn-ptts/blob/v0.5.0/ptts-pyo3/README.md), [exact binding method](https://raw.githubusercontent.com/gradium-ai/xn-ptts/v0.5.0/ptts-pyo3/src/lib.rs#L350-L360), [runtime clone-support condition](https://raw.githubusercontent.com/gradium-ai/xn-ptts/v0.5.0/ptts/src/synth.rs#L534-L559), [runtime encoder-weight probe](https://raw.githubusercontent.com/gradium-ai/xn-ptts/v0.5.0/ptts/src/synth.rs#L1544-L1549), [exact model file tree](https://huggingface.co/gradium/phonon-31m-en/tree/92741c5b07d085ff840e26fea8ce43110b87852f), [official model card](https://huggingface.co/gradium/phonon-31m-en), [official releases](https://github.com/gradium-ai/xn-ptts/releases).

### Klein TTS X1.5 Pro

- **Exact model:** `klein-ml/Klein-TTS-X1.5-Pro@25e0e73bebba71e5985bc369628ebdcb81bf7116`; Transformers 4.57.1 remote-code path loads model snapshot resources and its compact phonemizer.
- **Adapter in use:** voice Arthur, `speed=1.0`, `pause=.18`, `seed=42`; output is taken from the returned waveform. The adapter path does not use the separate full `kleintts`/Misaki package.
- **Documented controls/defaults:** card describes Arthur as British (`en-gb`), speed 1.0 as normal (trained range 0.9–1.1), seed for repeatability, and pause default 0.12 seconds. Thus 0.18 is an intentional pause override. Same-language voice blending is described as experimental/not trained; it is not a documented accent-preservation dial. No reference-audio clone control is documented for this checkpoint.
- **Licence/boundary:** Apache-2.0. Accent choice is the selected trained voice preset; no independent accent dial was found in the reviewed official documentation.
- **Primary sources:** [exact model revision/tree](https://huggingface.co/klein-ml/Klein-TTS-X1.5-Pro/tree/25e0e73bebba71e5985bc369628ebdcb81bf7116), [official model card](https://huggingface.co/klein-ml/Klein-TTS-X1.5-Pro).

### Silencio 2

- **Exact model:** `BlueRoseLabs/Silencio-2@20930f5f6a6bb564f2a8207152fd5c5d8eecff03`; official model-snapshot package is loaded on CPU.
- **Adapter in use:** reference file `kyutai/tts-voices/voice-zero/peter_yearsley.wav@323332d33f997de8394f24a193e1a76df720e01a`, `seed=42`, `normalize=False`, with no emotion/event tags for ordinary narration.
- **Documented controls/defaults and limits:** official card documents seed and `normalize=False` to preserve raw amplitude; adapter follows these controls. Emotion/event tags are documented but not passed here. English-only; reference-voice cloning is documented. No independent accent control was found. The official card warns delivery varies between takes and recommends checking important lines by ear. This is a stated repeatability limitation, not proof of a particular generated line's quality.
- **Licence/boundary:** weights CC-BY-4.0; included `silencio2/core` code MIT. Voice-owner permission and anti-impersonation/disclosure requirements apply as stated by the model card.
- **Primary sources:** [exact model revision/tree](https://huggingface.co/BlueRoseLabs/Silencio-2/tree/20930f5f6a6bb564f2a8207152fd5c5d8eecff03), [official card, controls, limits and licence](https://huggingface.co/BlueRoseLabs/Silencio-2).

### Kitten TTS 2 / kittenml 0.9.7

- **Exact model and decoder:** `KittenML/kitten-tts-2@c93cb7c271baa51d9ae8204d5277988906f235a2`; auxiliary Chatterbox Turbo decoder `ResembleAI/chatterbox-turbo@749d1c1a46eb10492095d68fbcf55691ccf137cd`, file `s3gen_meanflow.safetensors`, SHA-256 `d65cb687a2ed581ee6cc297e919ffefa63386944f42364ae13b78a594945514f`.
- **Adapter in use:** `kittenml==0.9.7`, CPU, `weights='packed'`, speaker Rosie, `preset='stable'`, `advanced={'seed': 42}`, `normalize=True`. The adapter's partial override of `kittenml.kittentts2.vocoder.hf_hub_download` pins the decoder revision above. This hook is private integration code; it is not a documented KittenML public API guarantee.
- **Documented controls/defaults:** packed weights are the lossless format; default decoder is documented as best quality; stable is the preset default; seed is supported; English normalization is enabled. Model config sets `use_reference_prompt: true`; adapter relies on that model config rather than passing an extra per-call setting. Current Kitten docs describe reference cloning from a clean, single-speaker 5–30 second sample and emotion/event/emphasis markup. This adapter uses a named Rosie voice and does not pass a custom reference or expressive markup.
- **Accent-drift finding:** the official materials describe speaker choice and reference conditioning/cloning, but do not document an independent “accent strength/retention” parameter. The named preset or an appropriately accented clean reference is the documented way to select speaker characteristics; this audit does not infer that either guarantees accent retention on arbitrary text. `expressive`/emotion controls concern delivery, and the documented `normalize=False` caveat concerns non-English normalization; neither is an established accent control. No unsupported `advanced` parameter is recommended.
- **Licence/boundary:** the model uses Stellon Labs Community License (research/non-commercial, limited commercial grant; separate terms above the published revenue/funding threshold and attribution duties). `kittenml` is Apache-2.0; speaker-embedding model is MIT. Auxiliary Chatterbox decoder weights/code have their own provenance/licence. Pinning via the private downloader hook is an adapter maintenance boundary.
- **Primary sources:** [exact model tree/revision](https://huggingface.co/KittenML/kitten-tts-2/tree/c93cb7c271baa51d9ae8204d5277988906f235a2), [official API](https://github.com/KittenML/KittenTTS/blob/main/docs/api.md), [official voices/expression documentation](https://github.com/KittenML/KittenTTS/blob/main/docs/voices-and-expression.md), [pinned model config](https://huggingface.co/KittenML/kitten-tts-2/blob/c93cb7c271baa51d9ae8204d5277988906f235a2/config.json), [pinned decoder tree/licence](https://huggingface.co/ResembleAI/chatterbox-turbo/tree/749d1c1a46eb10492095d68fbcf55691ccf137cd).

## Deepgram Flux (not Aura)

- **Adapter in use:** the project proxy maps `deepgram_flux_jack`, `_colin`, `_rufus`, `_conor`, `_sean` to `flux-jack-en`, `flux-colin-en`, `flux-rufus-en`, `flux-conor-en`, `flux-sean-en`. It posts text to `https://api.deepgram.com/v2/speak?model=<id>&encoding=mp3&expressivity=0&speed=1` with Token auth. This section audits Flux only; the proxy's Aura routes are not the target.
- **Documented controls:** current v2 API and voice catalogue support those Flux voices. `expressivity=0` is the documented/default value; the documented integer range is -2 to +2, but non-default expressivity is beta and carries higher risk of errors. `speed=1` is the documented default and is in range 0.5–1.5 in 0.05 increments, subject to the API's language limitations. These query parameters match the implementation. No custom voice cloning control is documented for Flux.
- **Pricing as of 2026-11-11:** official pricing lists $0.045 per 1,000 characters for Pay As You Go and $0.0405 per 1,000 characters for Growth; $0.045 is not plan-universal.
- **Evidence boundary:** no provider request or paid call was made. Voice metadata is vendor labeling, not an audition. No independent accent manipulation is documented.
- **Primary sources:** [Flux v2 generate endpoint](https://developers.deepgram.com/reference/speak/v-2/audio/generate), [official Flux voice catalogue](https://developers.deepgram.com/docs/flux-tts/voices), [official pricing](https://deepgram.com/pricing).

## Chatterbox Turbo / Nano

- **Project/runtime provenance:** `chatterbox/requirements.txt` installs `chatterbox-tts` from official repository commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`. The installed Turbo module SHA-256 was verified by the parent as `2f27e8ff2fa35181fdd2849367fb96ecc2cb87a1088ca7520c8bd51946599f08`; installed `direct_url.json` identifies that exact source commit. The project-owned adapter is `chatterbox/server.py`. Deployed path is Turbo or its Nano variant, selected by the `CHATTERBOX_NANO` environment flag. V3 is not running and is not audited here as deployed behavior. Runtime is upstream code, adapter and service container are project-owned.
- **Adapter settings and parameter mismatch:** server environment defaults are `CHATTERBOX_EXAGGERATION=0.5` and `CHATTERBOX_CFG_WEIGHT=0.5`; requests may override them. The production webapp request does not set either field, so those server defaults are passed to `model.generate(..., audio_prompt_path=ref, exaggeration=.5, cfg_weight=.5)`. The exact pinned Turbo source defines `min_p=0.00` and emits a warning that CFG, `min_p`, and exaggeration are unsupported by Turbo/Nano and ignored. It then calls `t3.inference_turbo` with temperature, top-k, top-p, and repetition penalty only. Consequently the app's `cfg_weight`/`exaggeration` fields are accepted and forwarded but are not effective Turbo/Nano controls; `min_p` is likewise ineffective and is not set by this adapter. Exaggeration is also used while preparing reference conditionals, but the same implementation explicitly identifies it as unsupported for Turbo/Nano generation; do not represent it as a supported output tuning control.
- **Model-family boundary:** the exact pinned original `ChatterboxTTS.generate()` and multilingual `ChatterboxMultilingualTTS.generate()` implementations do use `exaggeration` and `cfg_weight`; that does not transfer to the Turbo/Nano class. The current service loads Turbo/Nano unless its separate multilingual-V3 environment flag is explicitly enabled, and the deployed path audited here is Turbo/Nano.
- **Defaults that do affect the pinned Turbo/Nano generation:** `temperature=0.8`, `top_p=0.95`, `repetition_penalty=1.2`, `top_k=1000`. `norm_loudness=True` is the default and applies to the reference audio while preparing conditionals. The adapter does not expose or override these values, so the upstream defaults remain in effect. The default prompt preparation requires reference audio longer than five seconds. Turbo/Nano are English models in this path; the relevant model is conditioned on reference speech, with no separate accent slider documented. Reference conditioning does not itself establish an accent-retention guarantee.
- **Mutable-weight provenance gap:** pinned `tts_turbo.py` chooses the official Turbo or Nano model repository but calls `snapshot_download` without `revision`; the corresponding downloaded weights can move with the repository default. The official multilingual loader explicitly requests `revision='main'`, but is not deployed here. Therefore the source/runtime pin is exact while the model-weight revision is not. This report does not assert a pinned Turbo/Nano weight hash.
- **Current official-source status and license:** official repository README now says that, as of August 2026, Chatterbox is retired research and no longer maintained; code is archived under MIT, with no support or updates. The archived README still documents Turbo/Nano properties, but that is historical vendor documentation, not an active maintenance commitment. Runtime model-weight repositories carry their own model-card terms; this audit did not resolve a fixed weight revision because the loader follows the repository default.
- **Primary sources:** [current official README/status](https://github.com/resemble-ai/chatterbox), [exact pinned Turbo implementation](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py#L250-L294), [exact pinned original implementation](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts.py#L192-L236), [exact pinned multilingual implementation](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/mtl_tts.py#L257-L308), [exact source commit](https://github.com/resemble-ai/chatterbox/commit/5de7a54aa4e5e2baadb0182dde554908b48b85c2), [Turbo model card](https://huggingface.co/ResembleAI/chatterbox-turbo), [Nano model card](https://huggingface.co/ResembleAI/chatterbox-nano).

## What this audit establishes

- **Documented/source-verified:** exact adapter calls and source/model revisions listed above; documented parameter meanings/defaults; whether a parameter is accepted, used, or ignored by the pinned implementation; declared voice metadata, limits, and licences.
- **Audition setting only:** the code records the actual settings applied by the adapters. A non-default value's presence does not prove that it is better, and a no-op parameter does not constitute tuning.
- **Listening-only:** naturalness, pronunciation, accent impression, preferred pacing, performance over a particular book, and whether a reference voice sounds convincing. These claims require listening to the exact output. No generic quality assurance is made here.
- **Not established:** newly rendered audio, live cache readiness/playability, full-book quality, or current live deployment state beyond the parent-provided Turbo/Nano runtime verification.

## Scope of the initial audit and subsequent corrections

The initial documentary audit covered the five November CPU families, Flux
and Chatterbox. The dated follow-ups below record later GPU renders and their
separate provenance; none is a full-book quality approval. Breeze's shared
modern text-profile mapping was aligned before its new Voice Design audition.
Its book route remains unintegrated, so cached playback does not establish
book/preview production parity.

## 11 November follow-up: Shared Standard v1 VibeVoice and Maya2 auditions

- **VibeVoice / Arthur (short audition only):** the official Microsoft
  [`VibeVoice-1.5B` model card](https://huggingface.co/microsoft/VibeVoice-1.5B/tree/c00898d257e6b46004e3e2866a47534085fb685a)
  and weights were pinned at `c00898d257e6b46004e3e2866a47534085fb685a`
  (MIT). Inference used the community runtime at
  [`07cb79feadd2d3fd7f47530d4c964a12857936a0`](https://github.com/vibevoice-community/VibeVoice/tree/07cb79feadd2d3fd7f47530d4c964a12857936a0)
  (MIT); this is not Microsoft's TTS runtime. Its pinned processor reads
  `language_model_pretrained_name` from the model's
  [`preprocessor_config.json`](https://huggingface.co/microsoft/VibeVoice-1.5B/blob/c00898d257e6b46004e3e2866a47534085fb685a/preprocessor_config.json),
  which names `Qwen/Qwen2.5-1.5B`; the processor code prioritizes that embedded
  name over an override. The first attempt therefore failed before synthesis
  because only the VibeVoice checkpoint had been fetched. The corrected
  CPU-baked image separately pinned the Qwen tokenizer to
  `8faed761d45a263340a0528343f099c05c9a4323` (Apache-2.0), rewrote the local
  processor config to that snapshot, and initialized the complete processor
  before requesting the GPU. Its four tokenizer asset hashes are in the render
  receipt. A tokenizer class-name warning was emitted at preflight and render;
  initialization and generation completed, but this audit does not infer that
  the warning is harmless. Main-model configuration sets 20 DDPM inference
  steps and the pinned inference method defaults CFG to 1.0. This audition
  applied the prior fixed settings: L40S, fp16 weights, SDPA, CFG 2.0, 10 DDPM
  steps, greedy decoding (`do_sample=False`), seed 12345, `max_new_tokens=None`
  (the runtime derives its limit from the 64K context, with its default
  `max_length_times=2` bound), one Arthur reference
  (`uk_male_minter.wav`, SHA-256
  `8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252`), and
  one `Speaker 1:` passage call. Shared Standard v1 source is pinned by
  `386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`; the
  Vibe-specific prepared input hash is
  `74de152cc1ed27890fbbcabc88f26d5cf360953e64e70a5d56d897ff1ceb0ee9`.
  Result: 54.13 seconds, WAV then 160 kbit/s MP3. Unprompted Whisper small/int8
  checked the final MP3 with 0.982 prepared-token coverage, no detected dropped
  span, and no missing tail. This is a completeness check, not a listening or
  pronunciation verdict. The existing VibeVoice long-form production rejection
  remains in force; this single short audition does not change it.
- **Maya2 Native / Siddhant and Nivedita:** official runtime
  [`MayaResearch/maya2-native`](https://github.com/MayaResearch/maya2-native/tree/c6b376868e268551d065c4206193e96257bef4a1)
  was pinned at `c6b376868e268551d065c4206193e96257bef4a1`; weights
  [`maya-research/maya2-native`](https://huggingface.co/maya-research/maya2-native/tree/87a83efdd6551e038246b6b37836a6264713eec3)
  at `87a83efdd6551e038246b6b37836a6264713eec3` (Apache-2.0). The pinned
  runtime also fetched Mimi
  [`89091b3e466eb6a9d11e537bf26b144f194978f7`](https://huggingface.co/kyutai/mimi/tree/89091b3e466eb6a9d11e537bf26b144f194978f7)
  (CC-BY-4.0) and SpeechBrain ECAPA
  [`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/tree/0f99f2d0ebe89ac095bcc5903c4dd8f72b367286)
  (Apache-2.0). Python 3.12 image versions: Torch/torchaudio 2.8.0+cu128,
  Transformers 5.6.2, Triton 3.4.0, SpeechBrain 1.1.2. These are native
  synthetic personas, not reference clones. The adapter used the raw
  `maya2` Shared Standard v1 helper input/hash `386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`,
  English, `normalize=True`, seed 42, one loaded model with `max_seats=1`, and
  three paragraph calls joined with 0.5 seconds. The pinned official
  [README](https://github.com/MayaResearch/maya2-native/blob/c6b376868e268551d065c4206193e96257bef4a1/README.md)
  recommends normalization for numbers and symbols; this differs from an
  older short audition that used `normalize=False` and did not contain the
  numeric challenge passage. Maya internally normalized the three paragraphs;
  the exact normalized text and SHA-256 (`fe315b330428d6b26c8c81613018ec45fb828acedfdf7e6f9039858480e4bca8`)
  are recorded with each render. No other generation overrides were applied:
  pinned implementation defaults include depth temperature 0.7/top-k 64,
  codebook-0 temperature 0.9/top-k 64/top-p 1.0, and presence penalty 0.8
  over a 12-frame window. Output was 67.70 seconds for Siddhant and 81.86
  seconds for Nivedita, each joined to 24 kHz mono WAV and 160 kbit/s MP3.
  Whisper small/int8 on each final MP3 returned no dropped spans and no
  missing tail (coverage 0.971 and 0.976 respectively). ASR differed on Li
  Na's romanization and inserted a short `me` in Nivedita's middle passage;
  those disagreements are uncertain and are not a pronunciation finding.
- These are private Shared Standard v1 audition files with exact render,
  sample-hash, and ASR receipts. After deployment of the native-input mapping at
  `6ebaa5f`, Maya2 Siddhant/Nivedita and VoxCPM2 Peter were promoted together;
  all three exact preview GETs returned HTTP 200 with matching SHA-256 bodies
  and current sample mappings. The ignored verification receipt is
  `scratch/tts-nov11/promoted-preview-http-verification-verified-maya-voxcpm-promotion.json`.
  No new human listening or preference verdict is recorded for these engines;
  documentation, duration, and ASR cannot establish naturalness, accent quality,
  or production fitness.

## 11 November late follow-up: VoxCPM2 and Breeze fictional Voice Design

- **VoxCPM2 / Peter Yearsley:** official runtime
  [`OpenBMB/VoxCPM`](https://github.com/OpenBMB/VoxCPM/tree/300e4260b509066151d623dc9c0aa922cf82232b)
  commit `300e4260b509066151d623dc9c0aa922cf82232b`, model
  [`openbmb/VoxCPM2`](https://huggingface.co/openbmb/VoxCPM2/tree/7936080b41163874f38610f46f438e2c0757f9fd)
  revision `7936080b41163874f38610f46f438e2c0757f9fd`; code and weights are
  Apache-2.0. This was a private reference-conditioned audition using the
  existing Peter reference (`uk_male_yearsley.wav`, SHA-256
  `4099b7ad89ad5a0e010417da79e2312312d5b1900e3dc7791eddaa5353293524`) and its
  verified transcript. On L40S/CUDA, the adapter made three paragraph calls
  with 0.5-second gaps, `cfg_value=2`, 10 inference steps, seed 42,
  `normalize=False`, `denoise=False`, `retry_badcase=False`, and `optimize=True`;
  no other model defaults are inferred here. It produced 73.64 seconds, then a
  24 kHz mono 160 kbit/s MP3. Unprompted Whisper small/int8 found no aligned
  drops or missing tail (0.965 coverage); it varied on an opening word, the
  romanization of Li Na, and date punctuation. Those are ASR uncertainties, not
  pronunciation or sound-quality verdicts. The exact cache was promoted after
  the mapping deploy and its served bytes were hash-verified. No new human
  listening verdict is recorded.
- **Breeze-TTS-2 / fictional Voice Design:** official inference runtime
  [`breezeblue-ai/breeze-tts`](https://github.com/breezeblue-ai/breeze-tts/tree/daa6cb2efe5471f09369229f322d20bb956cb3c3)
  commit `daa6cb2efe5471f09369229f322d20bb956cb3c3`; weights
  [`BreezeBlue/Breeze-TTS-2`](https://huggingface.co/BreezeBlue/Breeze-TTS-2/tree/3e28c5151381a722f1d8661b4118c298caa77aa4)
  revision `3e28c5151381a722f1d8661b4118c298caa77aa4`. The pinned model uses
  BreezeBlue Research and Non-Commercial License Agreement v1.1 (2026-09-01),
  [license text](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/3e28c5151381a722f1d8661b4118c298caa77aa4/LICENSE): non-commercial personal,
  educational, hobbyist and evaluation use is permitted; the agreement defines
  commercial purpose to include production/product or service use and requires
  a separate written commercial license for that use. This does not establish
  that personal audiobook use is prohibited. Separately, Breeze is not yet an
  integrated/approved book route. The audition ID's app registration has been
  prepared, but endpoint availability still awaits deployment and verification.
  The cache is not a claim of book support.

  The take is a single reference-free fictional adult narrator prompt asking
  for a lightly British accent; it does not imitate a real person, and the accent
  is requested rather than verified. L40S, bfloat16, eager attention, guidance
  4.0, seed 42, `max_new_tokens=1500`, `max_seq_len=2048`, repetition penalty
  1.1, `fast_all` disabled; no parameter or style variants. The official
  implementation documents a 12.5-token/s frame rate, so 1500 output tokens
  permit up to 120 seconds; the result was a complete 74.56-second 24 kHz mono
  take. The first client run's 200-second timeout expired; the same synthesis
  settings with a 600-second bound completed in 213.49 seconds. This is a
  timeout correction, not a model failure or a settings optimization.

  Unprompted Whisper small/int8 reported 0.97 coverage, no aligned dropped span,
  and no missing tail. It decoded the prepared `1,250 people invited` as `150
  people invited`; treat that number difference as a listening flag, not a
  pronunciation verdict. There is no human quality verdict, and ASR does not
  establish the requested accent or naturalness. Both exact cache files were
  preinstalled on Zorin only after confirming the target names were absent;
  the MP3 SHA-256 is
  `cb862bb168b85962f0404442ae5a2f12daf095a0ce7530e28b2c6fd92ac21164` and the
  sample-manifest SHA-256 is
  `c9dd80edf4e9d4aa03c459d0276f910abfbcfb735aa04408f204de347d0887e8` both
  match local and remote copies. The ignored verification receipt is
  `scratch/tts-nov11/breeze-preinstall-remote-verification.json`.
  No Breeze endpoint was opened or represented as available before the pending
  app deployment.

  Billing snapshot saved before the remaining Fish run:
  `scratch/tts-nov11/modal-billing-before-fish-20261111.json` (Modal summary at
  23:10 UTC: metered USD 1.67639669, billed USD 0; USD 1.61 credits and USD
  0.06639669 network-egress allowance offset). This is a cumulative workspace
  snapshot, not a per-engine cost; later Fish usage is excluded.

## 11 November late follow-up: Edge Andrew retry

The earlier no-audio result is superseded: the official `rany2/edge-tts` 7.3.1
tag (`360fa8e1de354e1dda74c09bd695887d6a44df74`) list call included
`en-US-AndrewNeural` among 322 voices; this is a community client for Microsoft's
Edge service, not an official Microsoft SDK. One bounded retry used the exact
Edge Standard v1 payload hash `447286b994ee94f9cdd67e0109d0cc71d2b616ce120034409bf208b738d2b553`,
client defaults (`+0%` rate/volume, `+0Hz` pitch), and no substitution; it
rendered 68.664 seconds in 91.31 seconds (MP3 SHA-256
`dbb592f3f3467ae19faa997b2e646875f619ed20087d1915d985e2933d429bb8`, sample
manifest SHA-256 `c35b3e95596ffc85623219de6b935a0176d48e9d88d38cd46ce158fcd9bb9614`).
Unprompted Whisper small/int8 found no aligned drops but flagged `tail_unheard=1`
for `21 April`/`April 21st` and heard Huawei/Xiaomi as `HWH Wei`/`Shomi`; these
are listening flags, not pronunciation or quality verdicts, and no human verdict
is recorded; the predecessor was archived and the exact preview returned HTTP
200 with the matching MP3 hash, as captured in
`scratch/tts-nov11/promoted-preview-http-verification-verified-edge-andrew-promotion.json`.
