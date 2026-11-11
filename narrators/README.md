# Heard November CPU narrators

This project-owned OpenAI-compatible adapter preserves the exact model families
and settings from Dave's 10 November 2026 ordinary-prose auditions. It adds new
voice IDs instead of relabelling the older Pocket 2.1 / Kitten 0.8 services.
Default narrator and all existing service boundaries remain unchanged.

The wrapper uses official upstream runtimes, one resident model family at a time,
four CPU threads, no CUDA, no cloud fallback. Health and voice-list requests do
not load a model. Speech requests are serialized; model downloads happen on first
use. The 12 GiB ceiling accommodates Kitten 2's much heavier CPU path. Kitten's
short preview Like is historical: Dave subsequently rejected Rosie. That voice
and Silencio 2/Peter remain registered but are no longer shortlisted.

New auditions use [the shared standard](../AUDITION-STANDARD.md). The current
[tuning audit](../TUNING-AUDIT-2026-11.md) distinguishes the audition settings
below from upstream defaults; supported overrides are not proven optimal.

## Authoritative evidence (read 2026-11-10)

Exact model revisions are in `webapp/liked_voices.py`; dependencies are pinned in
`requirements.txt`. CPU PyTorch/torchaudio are 2.8.0.

| Runtime/model | Official source | Audition defaults and licence |
|---|---|---|
| Pocket TTS 4.0.1 | https://github.com/kyutai-labs/pocket-tts | `english_2026-10`, 100M voice-cloning weights at `db04f0e653473e5c7333c69686ac92b7460b0c1d`, temperature .3, 4 decoder steps, seed 42; weights CC-BY-4.0 |
| Phonon 31M / ptts 0.5.0 | https://huggingface.co/gradium/phonon-31m-en and https://github.com/gradium-ai/xn-ptts/blob/main/ptts-pyo3/README.md | float32, en, temperature .45, seed 4242424242424242; model Apache-2.0, runtime MIT/Apache-2.0 |
| Klein X1.5-Pro | https://huggingface.co/klein-ml/Klein-TTS-X1.5-Pro | Official bundled compact phonemizer, speed 1, pause .18, seed 42; Apache-2.0. This frontend differs slightly from the full misaki package and is the one heard in these auditions. |
| Silencio 2 | https://huggingface.co/BlueRoseLabs/Silencio-2 | seed 42, normalize false, no emotion tags for ordinary narration; weights CC-BY-4.0, adapted Pocket core MIT |
| KittenTTS 2 / kittenml 0.9.7 | https://huggingface.co/KittenML/kitten-tts-2 | CPU, lossless packed weights, default decoder, stable preset, seed 42. Stellon Labs Community License: research/noncommercial and limited commercial grant; separate licence above $1m annual revenue or cumulative funding; attribution obligations. Package Apache-2.0. |

Pocket/Silencio voice-zero references are CC0, pinned to
`kyutai/tts-voices@323332d33f997de8394f24a193e1a76df720e01a`:
https://huggingface.co/kyutai/tts-voices. Phonon voice catalogue is pinned to
`0ee17205f254b5abc43b266c8a0f215565c352f7` (Apache-2.0).
No reference recordings, model weights, book excerpts or previews are in git.

Kitten's official runtime also uses the ResembleAI Chatterbox Turbo S3 decoder
(not its text-to-speech model). Its download is pinned by this adapter to
`749d1c1a46eb10492095d68fbcf55691ccf137cd`, file
`s3gen_meanflow.safetensors`, SHA256
`d65cb687a2ed581ee6cc297e919ffefa63386944f42364ae13b78a594945514f`.
Official source/licence: https://huggingface.co/ResembleAI/chatterbox-turbo (MIT).
The adapter adds a `revision` argument to the runtime's decoder downloader;
inference code and decoder settings remain upstream defaults.

## Setup

Enable `ENABLE_NARRATORS_PROFILE=1` in the deployment's private `.env` and use
`scripts/deploy.sh` for the whole stack. Provision the already-authorized HF
credential as `data/narrator-hf-token` (readable by the container user, never git).
It is mounted read-only for the gated Pocket weights. Model cache is persistent.
Pre-seed the exact heard MP3s under `data/previews/<voice_id>.mp3`, then verify
`/api/voices` and each `/api/preview/<voice_id>` before offering the voices.

## Expression and dialogue boundaries

Silencio documents `<happy>`, `<sad>`, `<angry>`, `<fear>`, `<surprised>`,
`<whisper>` and five sound tags. Kitten 2 has beta emotion/event/emphasis markup,
including `[excited]`, `[nervous]`, `[sad]` and `<gasp>`, with an expressive preset.
This ordinary-narration integration does not automatically inject such tags.
Phonon documents duration conditioning and sampling controls, not named emotions.
Klein documents speed, sentence pause and voice blending; a blend is one combined
timbre, not alternating speakers. Pocket offers voice-reference conditioning and
sampling controls, not a documented named-emotion interface.

Rendering attributed quotation spans with another voice is an application-level
casting operation. None of these integrations automatically identifies speakers
or assigns book quotations. That is separate from selecting a narrator.

Deepgram Flux uses `/v2/speak`, the exact `flux-<name>-en` model, expressivity 0
and speed 1: https://developers.deepgram.com/reference/speak/v-2/audio/generate.
It documents expressivity -2..2, a calm-to-animated range with additional error
risk away from the default. Pricing checked 2026-11-10: $0.045/1k characters,
https://deepgram.com/pricing. Existing Aura 2 still uses `/v1/speak`.

Maya 2 and VoxCPM2 Likes are cached, explicitly audition-only catalogue entries.
They cannot start conversion or silently fall through to Kokoro. A full-book
GPU lane needs its own audited integration and explicit GPU authorization.
