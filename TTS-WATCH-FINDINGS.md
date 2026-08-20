# External TTS Research & Watch Findings

> **Scope boundary:** this is the repository's dedicated external-research section. Future watcher findings must update **only this file, between the markers below**. `README.md`, `ENGINES.md`, `DECISIONS.md`, `LOW-COST-TTS.md`, implementation files, tests and settled listening verdicts must remain untouched unless Dave gives a separate explicit instruction.

<!-- TTS_WATCH_SECTION_START -->

## Project test rubric

A discovery is not a production recommendation. It must first pass the repository's existing gates:

1. **Human listening first:** naturalness, authentic accent, proper nouns, companies, numbers/currency, stable voice and pacing, joins, and long-form comfort.
2. **Structural QA only:** ASR can detect collapse, truncation, repetition or gross mismatch; it does not grade voice quality.
3. **Selection after quality:** prefer free local CPU, then free Kaggle GPU, then the lowest measured cost that remains at or below **£2 per finished book**.
4. **No automatic paid GPU route:** local CPU is the default; Kaggle is explicitly selected per job; paid Vast/RunPod use requires separate operator authorisation.
5. **Reproducible evaluation:** use the same hard-text corpus and authentic reference voices, retain source hashes/settings, then advance from short sample → ten-minute gate → full chapter only after each listening pass.

## Current project baseline

These are context for evaluating discoveries, not new decisions:

- **Default local narrator:** Chatterbox Nano with Beatrice; measured faster than real time locally and free.
- **Opt-in CPU choices:** Pocket TTS and KittenTTS after listening tests; neither replaces Nano automatically.
- **Accepted quota-paced cloud option:** Gemini 3.1 Flash TTS with Achernar; excellent heard result, Free Tier only, passage-cached, no paid fallback.
- **Current full-precision long-form GPU leader:** Qwen3-TTS; strongest heard full-chapter consistency, but explicit/free-GPU only.
- **Highest unresolved ceiling:** Hume TADA; potentially exceptional prosody, but blocked by voice/pacing drift, openings, pronunciation and lack of long-form/control guarantees.
- **Known failed or bounded paths:** Piper and Kokoro do not meet the current quality bar; Chatterbox V3 regional voices, IndexTTS-2.5, raw NVIDIA Magpie, MOSS, VibeVoice, Higgs and several regional-label candidates remain rejected or narrowly bounded by the recorded listening evidence in `ENGINES.md` and `DECISIONS.md`.

## Consolidated research findings

### Commercial/API reference points

- The often-quoted **~$0.24/hour** Deepgram figure refers to transcription economics, not generated speech.
- Deepgram TTS is billed by input characters. Research on 12 August 2026 estimated **Aura-1 at roughly $0.69–$0.92 per finished hour** and **Aura-2 at $1.39–$1.84**, before retries. Aura's 2,000-character request cap still requires segmented, cached generation.
- Deepgram is a low-friction audition/reference route, not an open model. Manuscript data terms must be checked before unpublished/private material is sent.
- Raw rented-GPU inference can be very cheap, but setup, model downloads, persistence, retries and listening QA dominate. Marketplace price/RTF combinations are scenarios, not benchmarks. Persistent images and book-sized batches are essential.

Sources: [Deepgram pricing](https://deepgram.com/pricing), [Deepgram TTS docs](https://developers.deepgram.com/docs/text-to-speech), [Vast pricing](https://vast.ai/pricing/), [RunPod pricing](https://www.runpod.io/pricing).

### Open-model landscape already surveyed

- **Qwen3-TTS 0.6B/1.7B:** Apache-2.0, cloning/voice design and strong sustained narration; already tested and currently the full-precision long-form leader.
- **Chatterbox family:** MIT and active; Nano is the relevant CPU/cloning baseline, while Turbo/V3 require per-book audition. Generated audio includes Resemble's PerTh watermark.
- **CosyVoice 3 0.5B:** Apache-2.0, cloning and repetition-aware sampling; credible GPU challenger but not yet a heard project winner.
- **GPT-SoVITS:** MIT code and very attractive batch economics, but a complex stack whose downloaded checkpoints require their own licence review.
- **Kokoro/Kitten/Piper:** small CPU paths; useful references or opt-ins, but small/fast does not override the human audiobook-quality gate.
- **F5-TTS and Fish Speech:** technically strong, but official pretrained-weight licences block ordinary commercial audiobook use without additional permission.
- **IndexTTS-2.5:** strong controls, custom licence and a failed project listening verdict; a packaging change alone does not reopen it.
- **ZONOS/Spark/XTTS/StyleTTS2 and similar older families:** monitor only for material new checkpoints/runtime evidence that changes the existing verdict.

## One-off landscape report — 15 August 2026

### Audio8 TTS Preview 0.6B + ONNX INT4 — **first test priority**

- Apache-2.0 code and weights; zero-shot cloning; official ONNX Runtime route.
- Compact CPU evidence: roughly 586 MiB of ONNX files, with first-party Apple M2 memory measurements around 1.0–1.2 GiB for synthesis.
- Strong fit with the service architecture, but upstream recommends inputs no longer than about 150 characters and publishes no x86 Zorin CPU RTF or audiobook-length result.
- **Next gate:** authentic Beatrice/Arthur references, raw vs prepared hard text, measured x86 RTF/RSS, then ten-minute and chapter listening only if the short gate passes.

Sources: [runtime](https://github.com/Audio8-AI/Audio8_TTS), [weights](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6b), [ONNX INT4](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4).

### ZONOS2 + official GGUF / `zonos2.cpp` — **watch/test after Audio8**

- MIT runtime and Apache-2.0 weights; native C++ pipeline, cloning, speaking-rate/emotion/repetition controls.
- Large 7.6B MoE route; Q4 pipeline is about 5.2 GB. CPU RTF and sustained audiobook behavior remain unproven.
- `en_gb` is a text-normalisation locale, not evidence of an authentic British voice.
- **Next gate:** Q4 vs Q8 blind comparison on authentic regional references, then measured CPU RTF/RSS and long-form controls.

Sources: [runtime](https://github.com/Zyphra/ZONOS2), [GGUF weights](https://huggingface.co/Zyphra/ZONOS2-GGUF), [native implementation](https://github.com/Zyphra/zonos2.cpp).

### FireRedTTS3 Base — **bounded free-GPU capacity test**

- Apache-2.0 code/weights, multilingual zero-shot cloning and a useful text-normalisation frontend.
- Approximately 12.26 GB of published model files with no official safe VRAM, quantised, ONNX/GGUF, CPU or audiobook-length result.
- **Next gate:** one Kaggle T4 model-load/short-generation capacity check only; advance to the ten-minute gate solely if it fits and passes by ear.

Sources: [runtime](https://github.com/FireRedTeam/FireRedTTS3), [weights](https://huggingface.co/FireRedTeam/FireRedTTS3).

### Ruled out or deferred in that report

- **Confucius4-TTS:** legitimate Apache-2.0 August release, but too many runtime dependencies and no useful VRAM/RTF, regional-English or long-form evidence to put ahead of Qwen.
- **dots.tts:** permissive and stable, but CUDA-oriented and lacks the project-specific accent/audiobook evidence needed to displace Qwen.
- **MOSS runtime/GGUF improvements:** deployment improvements do not reverse the heard joins/pacing/expression verdict; wait for a materially different model such as MOSS 2.0.
- Catalogue labels, `en_gb` normalisation and promptable "accent" fields never count as accent-quality evidence without authentic-reference listening.

## Watch log

### 20 August 2026 — Scylla's Band v2 — **test**

- **Released:** 19 August 2026. Apache-2.0 runtime and weights; commercial use permitted. Training data is not distributed.
- **Deployment:** first-party ONNX Runtime and LiteRT bundles. Verified model-repository totals are **296.9 MiB for ONNX INT8** and **470.2 MiB for ONNX FP32**.
- **Capabilities:** managed ten-voice system, long-form planning/chunking, tagged dialogue, affect controls, pronunciation overrides/G2P assets, and public language IDs including `en_gb`.
- **Important limits:** managed voices rather than arbitrary cloning; each voice has one declared English dialect; British labels and synthetic-training claims are not listening evidence. Upstream itself warns of possible timing/voice drift at stronger conditioning.
- **Project relevance:** unusually close to the local CPU/ONNX requirement and small enough for a bounded Zorin test. It must still pass the same prepared-text, authentic-accent, join, ten-minute and full-chapter gates before exposure.
- **Recommended next test:** INT8 vs FP32 on the hard-text corpus using the closest documented British voice, fixed settings, measured cold/warm RTF and RSS; then blind-listen against Nano/Beatrice. Stop after the short gate if voice quality or regional phonetics fail.

Sources: [weights/model card](https://huggingface.co/spybyscript/scyllasbandv2), [runtime](https://github.com/lowkeytea/scyllasband), [samples](https://lowkeytea.github.io/scyllasband/).

## Future finding template

Append newest entries at the top of **Watch log** without altering settled project documents:

```markdown
### YYYY-MM-DD — Model/version — **test | watch | skip**
- What is materially new
- Exact code/weight licence and commercial boundary
- Runtime/model size and honest CPU/GPU evidence
- Long-form, accent, cloning and pronunciation evidence
- Why it changes—or does not change—the current project verdict
- One bounded next test, if justified
- First-party links
```

<!-- TTS_WATCH_SECTION_END -->
