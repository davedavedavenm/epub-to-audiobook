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

### Audio8 TTS Preview 0.6B + ONNX INT4 — **tested; continuity repair only (Update 2026-09-05: rejected)**

- Apache-2.0 code and weights; zero-shot cloning; official ONNX Runtime route.
- Compact CPU evidence: roughly 586 MiB of ONNX files, with first-party Apple M2 memory measurements around 1.0–1.2 GiB for synthesis.
- The 2026-08-22 four-thread CPU gate measured RTF 2.286–2.322. Dave liked the Arthur voice, but heard drops/fades in both arms and changing pace/tone in the prepared arm. That arm was twelve independent, differently seeded calls with 200 ms joins and three forced mid-sentence boundaries; it is not a viable audiobook path.
- Dave heard the complete-sentence, fixed-seed, zero-added-silence corrective arm and called it “better.” Three exact source sentences exceed the documented 150-character recommendation. *(Update 05 September 2026: tested on continuous 456-word non-fiction chapter; Dave rejected with volume pumping and garbled speech on sentences >150 chars. Formally rejected for audiobooks).*

Sources: [runtime](https://github.com/Audio8-AI/Audio8_TTS), [weights](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6b), [ONNX INT4](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4).

### ZONOS2 + official GGUF / `zonos2.cpp` — **short voice pass; continuity diagnostic**

- MIT runtime and Apache-2.0 weights; native C++ pipeline, cloning, speaking-rate/emotion/repetition controls.
- Large 7.6B MoE route; Q4 measured RTF 6.562 on the short arm and 7.245 on the full arm. Peak RSS rose from 7.5 to 12.3 GiB.
- `en_gb` is a text-normalisation locale, not evidence of an authentic British voice.
- Dave called the complete first-paragraph Arthur Q4 clip “really good,” but the same-setting full call dropped 35 final words and lost the Arthur identity. A persistent-server/cached-Arthur repair restored structural coverage, but Dave still heard different voices with Arthur fading in and out; only the underlying/base voice was OK. **Decision:** close the current cloned-Arthur audiobook path. Q8 remains untested and quantisation has not been shown to cause the identity drift.

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

### 05 September 2026 — Audio8 TTS Preview 0.6B ONNX INT4 — **tested; rejected for audiobooks**
- **What was tested:** Full non-fiction chapter passage from *Breakneck: China’s Quest to Engineer the Future* Chapter 1 ("Engineers vs. Lawyers", first 2 pages, 456 words normalized across 18 complete sentences). Synthesized on Zorin i5-12400 CPU (4 threads, RTF 3.032, peak RSS 3.94 GiB).
- **Listening Verdict:** Dave rejected: *"garbled, loud then soft... not great"*.
- **Diagnosis:** Audio8's architecture is explicitly optimized for short prompts (<150 characters). On continuous multi-sentence passages with longer clauses, INT4 codebook drift and local gain scaling fail severely, causing volume pumping and garbled phonemes.
- **Decision:** Formally rejected and closed for continuous audiobook narration. See `DECISIONS.md`.
- First-party links: [runtime](https://github.com/Audio8-AI/Audio8_TTS), [ONNX INT4](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4).

### 05 September 2026 — Breeze TTS 2 (3.5B) — **tested; Voice Direction impressive, Voice Design drift, compute-heavy**
- **What was tested:** Evaluated on Kaggle Tesla T4 GPU (`davedavedavedavenm/breeze2-breakneck-audition`) across two arms on *Breakneck* Chapter 1 (456 words):
  1. *Voice Design* (pure text prompt "British male narrator", zero audio reference): 17 chunks, 184.48s audio, RTF 7.781 on T4 (wall time 23.9m), 7.91 GB VRAM. Dave's listening verdict: *"voice seems to change each sentence? weird!"*. Cause: prompt-based voice design resamples speaker latents per chunk. Proper pattern requires generating a 15s reference WAV once, then using Voice Direction.
  2. *Voice Direction* (Arthur clone): 17 chunks, 191.84s audio, RTF 7.861 on T4 (wall time 25.1m), 7.97 GB VRAM. Dave's listening verdict: **"very impressive"**.
- **Hardware & License Bounds:** Compute requirement is extreme without FlashAttention (RTF ~7.8 on T4; ~25 mins compute for 3 mins audio). Prohibitive for full-book batching on budget GPUs. Weights governed by BreezeBlue Non-Commercial License.
- First-party links: [runtime](https://github.com/breezeblue-ai/breeze-tts), [model](https://huggingface.co/BreezeBlue/Breeze-TTS-2).

### 05 September 2026 — Qwen3-TTS 1.7B Base & CustomVoice — **tested; Base monotone, CustomVoice studio path**
- **What was tested:** Base 1.7B zero-shot Arthur clone evaluated on Kaggle Tesla T4 GPU (`davedavedavedavenm/qwen3-breakneck-audition`) on *Breakneck* Chapter 1 (456 words across 17 chunks, 174.00s audio).
- **Capacity & Efficiency:** Measured **RTF 2.57**, peak VRAM **4.05 GB** (3x faster than Breeze 2, half the memory; comfortably fits in budget/free T4s).
- **Listening Verdict:** Dave heard: *"really decent... great voice clone, somewhat lacking some emotion or tone in places, a bit monotone"*.
- **Path Forward:** The Base zero-shot clone faithfully copies acoustic timbre but delivers flat prosody. `Qwen3-TTS-12Hz-1.7B-CustomVoice` (with 9 studio speakers including `ryan`, `aiden`, `uncle_fu`, `vivian`) adds natural-language instruction steering (`instruct`) for expressive narration.
- First-party links: [runtime](https://github.com/QwenLM/Qwen3-TTS), [Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), [CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice).

### 05 September 2026 — Kokoro 82M (v0.19) CPU — **tested; caesura/prosody ceiling diagnosed**
- **What was tested:** Baseline `bm_george` and 5 best-practice variations (George/Lewis blends, speed adjustments at 0.92x–0.95x) on Zorin CPU on *Breakneck* Chapter 1.
- **Listening Verdict:** Dave heard: *"decent, a little stilted... pacing is super weird? 'rug... shops' in almost all of them. like, a weird pause? the fable voice sounds so robotic, the other kokoro voices are better but sound stilted"*.
- **Diagnosis:** StyleTTS2 82M lacks an autoregressive language model backbone. `espeak-ng` phonemizer inserts caesuras at compound noun boundaries. Speed adjustments and voice blending soften phonetic edges but cannot fix semantic prosody. Kokoro remains a fast preview tool (RTF 0.32 on CPU), not an audiobook production engine.

### 27 August 2026 — Sopro v2 (sopro-v2-turbo) — **tested and rejected by ear**

- **Released:** open-weight code and the `sopro-v2-turbo` checkpoint landed 25 August 2026, with active stream-gate hardening commits on 27 August. Code and model weights are Apache-2.0; commercial audiobook use is permitted without a separate licence.
- **What is new:** a 120M-parameter lightweight voice-cloning TTS family — zero-shot cloning from 5–20 s reference audio, streaming (~300 ms time-to-first-audio on a laptop CPU) and offline synthesis across English, European Portuguese, French and German. Upstream reports 0.24 RTF offline and 0.21 RTF streaming on an M3 CPU, 0.07 RTF on H100.
- **Runtime:** CPU-first — ONNX demo, CUDA auto-detect, defaults to CPU on macOS, ~120M params (F32). No published x86/Zorin CPU RTF/RSS, quantised/GGUF route, or Kaggle T4 figure.
- **Long-form evidence:** none published. The streaming path (chunked attention + causal vocoder) is explicitly not bit-exact with the offline path, so joins/pacing for sustained narration are unverified; mixed-language text is a noted weak spot.
- **Project relevance:** a permissive, CPU-runnable, English-capable open-weight model with cloning is a credible local audition lead and sits closer to the project's free-local-CPU default than the non-commercial Breeze TTS 2, but it lacks the long-form/authentic-accent evidence needed to displace Nano/Beatrice or Qwen3-TTS.
- **Project result, 28 August:** the bounded CPU gate ran on the hard-text corpus with the authentic Arthur reference, four threads, offline path, whole passage in one call. Measured **RTF 0.945 fp32 / 0.963 int8** on a Ryzen 9 8945HS — faster than real time on x86 CPU, and int8 is marginally slower, so quantisation buys nothing here. Peak working set 954 MiB. Structural ASR covered the complete passage in both arms (WER 0.115 / 0.110), including the WTO/EU/supply-chain tail that ZONOS2 lost; divergences are number-format and acronym only. Exact MP3s sent to Dave; **voice, accent, pacing and joins are not yet judged.**
- **Correction, 28 August:** those first arms ran at `temperature=0.7`, a value copied from the Audio8 harness and documented nowhere by Sopro, whose own default is **0.8**. They were not default renders. Re-run at upstream defaults with Dave's chosen **Beatrice** reference: **RTF 0.738**, 1,031 MiB peak working set. A `steps 16` arm (solver default is 2) has identical duration to the millisecond — `steps` drives only the acoustic decoder — so it is a clean A/B for whether the fast default costs quality; it measures RTF 1.622.
- **Verdict, 28 August:** Dave heard the Beatrice default and `steps 16` arms and rejected both — not good enough. Raising solver steps did not change it, and both arms share one token stream, so the acoustic decoder was not the limitation. Not an application engine, no longer gate. See `DECISIONS.md`.
- **Structural limit:** Sopro ships **no native voices**. `--ref` is a required argument and the model repository contains no voice profiles, so it cannot be auditioned on native supported voices at all. It is cloning-only by construction, and every render needs a reference chosen by Dave.

Sources: [runtime/code](https://github.com/samuel-vitorino/sopro), [weights/model card](https://huggingface.co/samuel-vitorino/sopro-v2-turbo), [blog](https://research.haloneuro.ai/posts/sopro-v2).

### 26 August 2026 — Breeze TTS 2 — **watch (Update 2026-09-05: tested; see Watch log above)**

- **Released:** official PyTorch inference code and usable model weights landed on 25 August 2026. Code is Apache-2.0, but the weights, derivatives and self-hosted outputs use the BreezeBlue Research and Non-Commercial License; commercial audiobooks require separate written permission.
- **What is new:** a bilingual English/Chinese open-weight model with reference-based voice cloning/direction, reference-free voice design, natural-language pace/style control, inline vocal events and streaming inference. The shipped checkpoint components total about 7.65 GB (7.12 GiB).
- **Runtime:** upstream reports about 7.7 GiB VRAM in eager mode and recommends a 12 GB CUDA GPU; its 0.32 RTF and sub-40 ms first-audio figures are H100 fast-path measurements. There is no CPU, ONNX/GGUF, quantised or T4/Kaggle result.
- **Long-form evidence:** upstream positions it for real-time interaction and publishes no chapter/audiobook test, speaker-drift result, pronunciation/custom-lexicon control or authentic regional-English validation. The default generation limit is 750 audio tokens, so sustained narration still needs verified segmentation and joins.
- **Project relevance:** the cloning plus natural-language pacing control and strong published short-form quality make it a credible free-GPU audition lead, but the non-commercial output restriction and missing long-form/T4 evidence prevent production use or displacement of Qwen3-TTS.
- **Recommended next step:** watch for first-party long-form/identity evidence or a measured T4 run; only then attempt one bounded Kaggle short gate against Qwen3-TTS and the hard-text corpus.

Sources: [official runtime/code](https://github.com/breezeblue-ai/breeze-tts), [weights/model card](https://huggingface.co/BreezeBlue/Breeze-TTS-2), [exact model licence](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE).

### 25 August 2026 — LoudKit 0.1.0 / loudr-1 — **tested and rejected by ear**

- **Released:** the public 0.1.0 code and completed `loudr-1` model bundle landed on 25 August 2026. Code and weights are Apache-2.0; the model is derived from MIT-licensed Chatterbox and includes full component/voice provenance.
- **What changed:** this is a new local inference engine and checkpoint package rather than a new architecture: PyTorch, ONNX Runtime and CoreML, five SDKs, 20 managed voices across ten languages, and cloning from roughly ten seconds of permitted audio.
- **Runtime:** synthesis-only downloads are 750 MB for PyTorch, 2.60 GB for ONNX and 1.16 GB for CoreML. First-party end-to-end measurements report 1.21× realtime on an Apple M3 Pro ONNX CPU versus 0.33× for PyTorch CPU; no x86/Zorin CPU result is published.
- **Long-form evidence:** passages are windowed at about ten seconds; six-token carry-over reduces measured join pitch restart from about 74 Hz to about 7 Hz, and tail detectors target hallucinations. Upstream still warns that joins can be audible and difficult punctuation, numbers and abbreviations can mispronounce or alter prosody. No authentic British/Irish/Australian/South-African or chapter-length listening result is published.
- **Project relevance:** the ONNX CPU path, explicit join work, cloning and permissive licence could make this Chatterbox-derived route materially more practical than the previously evaluated variants, but its own limitations hit the project's hard-text and audiobook gates. It does not displace Nano/Beatrice without listening.
- **Project result, 28 August:** the bounded CPU gate ran the cloned Arthur path on the hard-text corpus, four threads, whole passage in one `synthesize_long` call. **ONNX RTF 1.177** (2,946 MiB peak working set); the PyTorch CPU reference control measured **RTF 7.564** and is unusable for books regardless of quality. Both arms rendered 13 windows and **both dropped the same sentence** — “Rivals — Huawei, Xiaomi, Samsung — circle constantly.” Because the two backends run different precisions and therefore different token streams, a shared omission points at the model or its windowing rather than a runtime bug. Upstream's own detectors set `hit_token_cap` in both arms with chunks running to the full 255-token cap, and three to four chunks report a trimmed `ended_tail`; `suspect` is false. ASR establishes gross omission only, not cause.
- **Also material:** no shipped English voice is British. The roster lists `joe` and `kathleen` as the only English profiles, both CC0 OHF-Voice donations, so the managed-voice route cannot clear the authentic-accent gate and only the cloned path is project-relevant.
- **Correction, 28 August:** the earlier claim that the shared omission “points at the model or its windowing” was **wrong and untested**. `SamplingConfig.max_new_tokens` and `WindowConfig.max_speech_tokens` both default to 255. Raising both to 512 on the PyTorch path clears `hit_token_cap` and returns **all 13 chunks `clean`** with no trimmed tails (75.28 s vs 73.68 s). The omission was the default window, not a model defect.
- **The fix is unavailable on the fast path.** Raising the cap on ONNX is refused: the exported graphs are static at query 255 / prompt 238, and upstream instructs re-exporting the graphs rather than reframing. PyTorch accepts the wider window at RTF 6.96, which is not a book path. LoudKit at 255 tokens trims tails; escaping that means re-exporting ONNX graphs.
- **Native voices, 28 August:** `joe` and `kathleen`, the only English profiles, rendered at upstream defaults on ONNX CPU — RTF 1.261 / 1.263, ~3.2–3.3 GiB peak working set. An earlier arm cloned Arthur without being asked and skipped every shipped voice on the harness's own accent judgement; both were corrected.
- **Verdict, 28 August:** Dave heard the native `joe` and `kathleen` arms and the earlier cloned arms and rejected all of them — not good enough. Not an application engine, no longer gate. See `DECISIONS.md`.

Sources: [runtime/code](https://github.com/loudreader/loudkit), [weights/model card](https://huggingface.co/loudreader/loudr-1), [voice samples](https://loudreader.github.io/loudkit/demo/).

### 23 August 2026 — MOSS Voice-Acting 4.55B SFT — **watch**

- **Released:** 23 August 2026. CC-BY-4.0 full checkpoint with model code embedded in the Hugging Face repository; commercial reuse is permitted with attribution. It derives from the Apache-2.0 MOSS voice-acting v2 base.
- **What changed:** unlike yesterday's per-voice LoRAs, all 4.13B parameters were fine-tuned over 3,147,802 English/German utterances for three epochs, mixing synthetic voice profiles with real speech.
- **Evidence:** held-out token loss improved monotonically from 4.7076 to 4.6314 on both constituent datasets, but upstream explicitly says this is not a listening-quality result; speaker similarity was not re-measured.
- **Runtime:** the shipped BF16 checkpoint is 8.26 GB and the official example is CUDA-only. No quantised/ONNX/GGUF route, safe Kaggle VRAM figure, CPU result or audiobook-length benchmark is published.
- **Project relevance:** a full model update could alter the prior MOSS voice/prosody verdict more than packaging changes, but there is still no evidence that joins, pacing, drift, pronunciation or authentic regional English improve. It does not yet justify replacing Qwen3-TTS or reopening a project test.
- **Recommended next step:** watch for first-party or independent long-form A/B audio and measured inference requirements; only then run one bounded Kaggle comparison against the rejected MOSS sample and Qwen3-TTS.

Source: [weights, model card, training and validation details](https://huggingface.co/laion/moss-tts-local-transformer-4.55b-voice-acting-v2-sft).

### 22 August 2026 — MOSS voice-profile LoRAs (500 voices) — **watch**

- **Released:** 22 August 2026. CC-BY-4.0 adapters with shipped weights, per-voice reference audio/profile metadata and a PEFT quickstart; commercial reuse is permitted with attribution.
- **What changed:** 500 rank-4 adapters (about 34.4 MB each; 17.36 GB for the complete set) target fixed synthetic speaker identities and prosodic behaviour on the 4.55B `moss-tts-local` voice-acting base.
- **Evidence:** all 500 improve held-out loss over the frozen base (median 0.1571 nats), but this is not perceptual or long-form evidence. The card says roughly 96% of adapter capacity affects the semantic/prosodic transformer; timbre still depends substantially on the reference clip.
- **Important limits:** English/German only, no published audiobook-length listening, regional-accent validation, RTF/VRAM reduction or demonstrated joins/pacing fix. The 4.55B base remains GPU-oriented; downloading one adapter avoids the 17.36 GB bundle but not the base-model cost.
- **Project relevance:** this directly targets speaker identity/prosody, so it is more material than prior MOSS packaging/GGUF updates, but it does not yet reverse the project's heard MOSS rejection.
- **Recommended next step:** watch for independent long-form samples or a first-party chapter/identity benchmark; only then run one bounded Kaggle comparison against the existing rejected MOSS sample and Qwen3-TTS.

Source: [weights, model card and quickstart](https://huggingface.co/laion/moss-voice-profile-loras-500).

### 20 August 2026 — Scylla's Band v2 — **tested; reject**

- **Released:** 19 August 2026. Apache-2.0 runtime and weights; commercial use permitted. Training data is not distributed.
- **Deployment:** first-party ONNX Runtime and LiteRT bundles. Verified model-repository totals are **296.9 MiB for ONNX INT8** and **470.2 MiB for ONNX FP32**.
- **Capabilities:** managed ten-voice system, long-form planning/chunking, tagged dialogue, affect controls, pronunciation overrides/G2P assets, and public language IDs including `en_gb`.
- **Important limits:** managed voices rather than arbitrary cloning; each voice has one declared English dialect; British labels and synthetic-training claims are not listening evidence. Upstream itself warns of possible timing/voice drift at stronger conditioning.
- **Project result, 22 August:** Ink rendered at RTF 0.379 INT8 and 0.626 FP32 on four CPU threads. Dave found both robotic, emotionless and effectively one long sentence despite acceptable pronunciation. The FP32 control reproduces the failure, so quantisation is not the material explanation.
- **Decision:** stop at the short gate; do not integrate or render a longer Scylla sample.

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
