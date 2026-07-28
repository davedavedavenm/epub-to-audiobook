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

**Read this as a data point, not a recommendation.** It reflects one listener,
one non-fiction book, and CPU-only local hardware. TADA's ceiling is genuinely
higher — mid-generation it spontaneously voiced a quotation in its own native
voice with flawless prosody and pronunciation (v8 002, 03:03–03:55). Its
weakness is *control*, not capability: no long-form mode, no pronunciation
control, no documented sampling params. On a GPU, with shorter chapters, or
with fiction/dialogue, TADA may well win — and if Hume ships long-form support
it likely becomes the default (see issue #21). Both engines stay first-class;
pick by ear on your own hardware.

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
| zorin (upgraded 2026-07-20) | i5-12400 (6c/12t) | 31 GB | none | Kokoro/Piper/Chatterbox comfortable; TADA off (broken #23); full-book Chatterbox ~45h — use Kaggle |
| Windows box | Ryzen 9 8945HS (16 threads) | 29 GB | none (Radeon iGPU) | Chatterbox + TADA fit comfortably on CPU; ~3–4× old NUC speed [measured CPU class] |
| Cloud | Kaggle T4 (free) / Vast (paid) | — | yes | fast path for TADA/Chatterbox |

## Standing rule

Before tuning or "fixing" an engine, read its official docs first and cite
them here. Experiments only fill gaps the docs leave, and get marked
[unverified] until sourced or measured.
