# Tuning audit: November 2026

Source audit prepared 2026-11-11. This document compares the exact adapters and revisions used by the liked-voices worktree with current official maintainer/vendor documentation and the pinned runtime implementations. It records implementation settings and documentary defaults; it does not claim a particular setting is optimal by reasoning alone. The initial audit was read-only; follow-up sections distinguish actual experiments, measurements and listening verdicts.

## 11 November — Shared Standard v1 GPU preview outcomes

- **CosyVoice 3 (audition-only):** Official [CosyVoice source](https://github.com/QwenAudio/CosyVoice/tree/074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc), commit `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc`; official [Fun-CosyVoice3-0.5B-2512 snapshot](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4e8d000f4bcd70751be16fa94bf3d85a18), revision `29e01c4e8d000f4bcd70751be16fa94bf3d85a18`. Uses the pinned upstream requirements except optional TensorRT packages; official `AutoModel` eager path (`load_trt=False`), no explicit seed, chunk limit 300 characters, speed 1.0, non-streaming, `You are a helpful assistant.<|endofprompt|>` prompt prefix, and FFmpeg libmp3lame 96 kbit/s output from the project wrapper. Runtime observed: L40S, Torch `2.3.1+cu121`, CUDA toolkit 12.4.131, transformers 4.51.3, NumPy 1.26.4, WeText 0.0.4, Whisper 20231117, pyworld 0.3.4. Reference WAV hashes were checked against both engine asset copies; prompts use checked-in `tada/voices/ref_transcripts.json`, not the historical CosyVoice Whisper cache. Four Standard v1 files were staged, ASR-checked, promoted and verified by exact HTTP/body hashes. Beatrice's ASR flagged two middle spans, with no tail truncation; this is not a confirmed audio error. No new human listening or quality verdict was recorded. Wrapper/provenance receipt: ignored `scratch/tts-nov11/render_cosy_standard_only.py` and per-voice `*.render.json` under `evaluations/new-engines/output/november-2026-south-africa/standard-v1/all-engines/`.
- **Gemini 3.1 Flash TTS:** Exact model `gemini-3.1-flash-tts-preview`, pinned project adapter dependency `google-genai==2.18.1`; official [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation), [Interactions API](https://ai.google.dev/api/interactions-api), [model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-tts-preview), [billing](https://ai.google.dev/gemini-api/docs/billing), [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). The adapter sends one Interactions API request per preset, 24 kHz mono PCM wrapped as WAV, fixed default audiobook/British-English style unless `GEMINI_TTS_STYLE` is set, retries disabled, local cap 10 requests per Pacific quota day. The Standard v1 batch consumed 10/10: nine clips fully decoded; Puck's safety refusal was counted and not retried. Billing API confirmed the dedicated project has billing disabled. The engine-specific explicit-normalized sample SHA-256 was `d13e1b48bdbfb5ed60fab3736f7287b71ffc6a7418955ca976cb1fc7092e77c9`; nine successful outputs were audition inputs only, with no new human verdict. Achernar's older approval does not transfer to this clip.
- **TADA-1B:** Fresh pinned-official migration is blocked because the official [Meta Llama 3.2 1B repository](https://huggingface.co/meta-llama/Llama-3.2-1B) tokenizer/config file request at revision `4e20de362430cd3b72f300e6b0f18e50e7166e08` returned HTTP 403 (not authorized). Readable repository metadata did not establish file access. No alternate mirror was used to bypass the denial, no GPU synthesis was launched, and no cache was changed. The existing community-tokenizer adapter/previews remain distinct and unverified for equivalence; this is not a new audio-quality verdict.

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

## Remaining boundary outside this rendered cohort

This audit covers the five November CPU families, Flux and Chatterbox. It is
not a claim that all 165 historical catalogue entries have been retuned. A
follow-up mapping inspection found that Breeze uses the historical modern
sample preparation while `app.text_profile_for_engine` still falls through to
legacy for Breeze. No Breeze audio or book was rendered in this cleanup; do not
claim book/preview parity for that integration. Resolve it against the existing
Breeze recipe before a future book run, without silently changing its measured
pronunciation contract. The tested CPU and Chatterbox mappings are aligned.

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
  sample-hash, and ASR receipts. The new Maya IDs await their final application
  mapping deployment before preview-cache promotion. No new human listening or
  preference verdict is recorded for either engine; documentation, duration,
  and ASR cannot establish naturalness, accent quality, or production fitness.
