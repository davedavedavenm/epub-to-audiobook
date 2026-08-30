# Voices and accents

**Last updated: 2026-08-15.** What works, what does not, and the wrong turns —
recorded so nobody walks back down them. Every claim here was heard or measured,
not reasoned about; where something is untested it says so.

## The quality gate

**The objective is a great-sounding audiobook.** Naturalness, authentic accent,
pronunciation of ordinary words/proper nouns/numbers, pacing and long-form
listenability are the first gate. Locality, cost, memory and speed matter only
after an engine passes that listening gate.

**Latest regional-accent verdict (Dave, 2026-08-15):** Edge is the only
currently heard option that comes close. The original three Multilingual V3
auditions failed, and the controlled follow-up failed too: Arthur at CFG 0 and
0.5, genuine human Irish Tadhg at CFG 0.5, and genuine human Australian VCTK
p374 at CFG 0.5 were all rejected. Accents, pronunciation and numbers remained
unacceptable. A locale label or human reference is not evidence that generated
speech is an authentic or pleasant audiobook voice.

**The tested Piper path is rejected and fully retired from the product (Dave,
2026-07-28).** Most existing voices sounded bad and inauthentic. A controlled
audit then compared deployed Piper 1.2 at both encodings with current Piper 1.6
direct, using the same official VCTK model and text. Dave's verdict on all three:
*"absolute shit… almost every word wrong, and sounded crap."* This rules out the
old wrapper and MP3 bitrate as meaningful fixes. Accent metadata and speaker
origin do not establish authenticity or audiobook quality.

### Synthesis-path audit SOP

A listening failure establishes that the **output** failed. Before assigning the
cause to an engine or model:

1. Read the vendor's current docs and this repo's history.
2. Verify the deployed model bytes/quality, speaker mapping, phonemizer/language,
   inference parameters, wrapper/runtime, preprocessing, cached sample age and
   final audio encoding.
3. Render the same text directly through current upstream and through the app.
4. Listen to that A/B. Only then classify the failure as setup, model, engine or
   encoding. Until then, the current path can be rejected for production while
   the root cause remains open.

---

## The one rule

**An accent lives in the model, not in the reference clip.**

Zero-shot voice cloning takes *timbre* from your reference and *phonetics* from
its own training data. If that training data is predominantly American English,
an Irish reference gives you an Irish-sounding voice saying American vowels.

**This was tested to destruction on 2026-07-27. Three engines, four attempts,
one result:**

| Attempt | Engine | Reference | Dave's verdict |
|---|---|---|---|
| 1 | Chatterbox Nano | raw VCTK clips | *"those accents are shit"* |
| 2 | Chatterbox Nano | native-accent Piper prose | *"softened the shit out of the voices and made them american"* |
| 3 | Chatterbox Turbo | same | *"irish 'ok'… not amazing"* |
| 4 | **XTTS-v2** | Edge Irish/ZA + Piper Scottish | *"bullshit, americanised crap"* |

XTTS is a completely different architecture from Chatterbox and is widely
described as preserving accent. **It did not.** That is what makes this a rule
rather than a quirk: it is not about which cloner you pick.

**Do not attempt accent cloning again on any engine** without evidence that the
model was *trained* on the accent. A fourth attempt needs a reason, not a hunch.

Training on the target accent is necessary, but it is not sufficient. Edge's
per-locale voices have held up in listening. Piper's `en_GB-vctk-medium` proves
that accented training data and speaker labels do **not** by themselves produce
an authentic, well-pronounced or enjoyable audiobook voice.

`cfg_weight` (below) moves the needle on Chatterbox but does not escape the rule.

---

## The local-vs-cloud problem, and what is being done about it

Dave, 2026-07-27, on the Edge voices: *"those voices are decent. how do we get
those on a local model? did you check? we can't be the only ones to want this."*

He was right that I hadn't checked. The actual landscape for **local** accented
English:

| Model | English accents | Local | Status here |
|---|---|---|---|
| **Kokoro** | US, UK **only** | yes | running — checked live, no Irish/Australian |
| **Piper (historical)** | UK, US; Irish/Scottish/Welsh/Australian via VCTK speaker labels | no longer installed | **fully retired**; old/current runtime and encoding A/B all failed badly |
| **MeloTTS** | US, UK, Indian, **Australian**, default | yes | installed and **rejected by ear**; no Irish |
| **OmniVoice** | US, UK, AU, CA, IN + five non-native-English accents | yes | accents good; slow on CPU; **no Irish/ZA** in fixed upstream vocabulary |
| **Chatterbox Multilingual V3** | cloned reference; official claim is improved accent preservation | yes | **Rejected by ear:** synthetic CFG-zero arms plus seeded Arthur and genuine human Irish/Australian official-default controls all failed |
| **XTTS-v2** | clones from a reference; reported to carry accent | yes | tested and rejected — see below |
| **Chatterbox** Nano/Turbo | none. English-only, American phonetics | yes | proven twice not to hold an accent |
| **Edge** | IE, AU, NZ, GB, ZA, IN, CA, HK, KE, NG, PH, SG, TZ, US | **no** | accents “not bad”, but Chinese company names were all poor; needs internet |

Edge's full English list was checked live and is worth knowing: it has **Irish
male and female** (Connor, Emily), Australian, New Zealand, South African and
five British voices. **No Welsh anywhere**, on any engine, cloud or local.

**Latest Edge listening verdict (Dave, 2026-07-28):** the accent was *"not
bad"*, but all Chinese firms' names were pronounced badly. This is a real
audiobook-quality failure for Chinese-business nonfiction even though the accent
passes. Do not assume the existing seed respellings solve it. The audition and
book share preprocessing, but the exact Edge payload still needs a raw-vs-current
A/B before assigning the cause to Edge or changing the lexicon.

Arthur/Turbo's excellent general-narration result does **not** mean V3 should
sound the same with a different accent. They are different models and inference
paths: Turbo is a 350M English model with `inference_turbo`; V3 is a 500M
multilingual model with a language-aware tokenizer and CFG sampling. The gate
also replaced Arthur's clean human reference with synthetic references: Irish
was generated through the subsequently rejected Piper path; South African is
verified as decoded Edge output; Australian is synthetic but the retained
evidence cannot prove whether Edge or Piper produced it. It therefore changed
model, speaker/reference quality and settings at once—not merely accent.

The initial V3 gate was confounded, so the follow-up isolated it: seeded Arthur
through Turbo and V3 at CFG 0/0.5, then genuine human Irish and Australian
references through V3 at official CFG 0.5. Dave rejected all five outputs.
That closes V3 as a local accent route here. The raw-number payload remains a
separate input defect, but it does not explain the rejected accent, ordinary-word
or voice-character results.

The reference audit found two honest free/local follow-ups that the rejected
gate never tried: human Irish narrator `tadhg_hynes.wav` (18 s, LibriVox) and
human Australian VCTK speaker p374 (18 s, official VCTK 0.92, CC BY 4.0).
Both were rendered through seeded V3 at the official same-language default on
2026-08-15, passed structural validation, and were rejected by ear.
There is **no human South African reference** in
the repo, live stack or retained Git history; do not recycle the Edge clip.

The practical online path worth testing next is Microsoft's supported Azure
Speech API rather than the unofficial `edge-tts` interface. Azure's official
catalogue currently includes 15 GA `en-AU` voices, `en-IE-ConnorNeural` /
`en-IE-EmilyNeural`, and `en-ZA-LeahNeural` / `en-ZA-LukeNeural`. Its supported
SSML `<say-as>`, IPA phonemes, substitutions and custom lexicons directly
address the number, currency and proper-name failures. The F0 tier includes
0.5 million Neural characters per month, no batch API and a 20-transaction/min
limit. The checked UK South S0 rate is about GBP11.36/million characters (about
GBP6.82 for 600k), above this repo's normal target. Azure therefore remains an
optional F0 listening candidate, not an approval or authority to spend.

**Live F0 boundary (2026-08-15):** Dave authorised Microsoft Azure CLI through
the official device flow and a dedicated UK South `SpeechServices` resource was
created at SKU **F0**, tagged `free-only`; no key was printed or committed. The
first harness was stopped when Dave required shorter, focused tests. Seven
Australian requests had already completed: 7 × 1,142 source characters = an
estimated 7,994 billable characters (1.599% of the 500k monthly F0 allowance),
with no Irish or South African synthesis. The replacement harness has no broad
default: it requires one to three exact GA voice IDs, defaults to a 1,000-total-
character ceiling, and refuses an output directory containing an MP3. Do not
make another Azure synthesis request without agreeing the exact shortlist and
text first.

Dave then approved a 300-character, three-request gate using the same normalized
text for `en-AU-DarrenNeural`, `en-IE-ConnorNeural` and `en-ZA-LukeNeural`.
All three clips decode completely and match their evidence hashes. His verdict:
the three accents are **spot on**, but the voices sound **robotic and degraded**.
This is an accent pass and overall quality failure, not an app-integration
approval. That run used an estimated 900 additional F0 characters, bringing
estimated cumulative synthesis text to 8,894 characters (1.7788%).

That gate was not an Edge-versus-Azure endpoint comparison: the app's heard
Australian Edge options are William and Natasha, while the rejected Azure arm
used Darren, and the preview passages/preprocessing also differed. Dave approved
one tightly controlled follow-up. Exact `en-AU-WilliamNeural`, the same pinned
300-character text, neutral prosody and the same 24 kHz/48 kbps MP3 format were
rendered once through `edge-tts==7.2.8` and once through Azure Speech F0. Both
are 16.032 seconds / 96,192 bytes and fully decode; their hashes differ. Azure
estimated cumulative synthesis text is now 9,194 characters (1.8388%), still
with $0 subscription-credit use. Dave judged Azure **only slightly better, but
better**. This rules out the Azure endpoint as the cause of the earlier relative
degradation; different speakers and input confounded that comparison. It is not
an absolute audiobook-quality approval for William or Azure. Do not make another
Azure request without an agreed question and character budget.

Dave subsequently authorised exactly one longer, correctly processed passage
for each accent. The common 737-word source retains real paragraph boundaries,
explicit title/author pauses and the hard number/currency passage. Deterministic
processing left no digits or currency symbols; 12 difficult terms use Azure's
official IPA `<phoneme>` mechanism instead of the rejected legacy respellings.
Australian William, Irish Connor and South African Luke each rendered once to
lossless 48 kHz PCM (3:49–4:12) and fully decoded. Dave judged all three accents
and voices acceptable. They are not great for emotion and none sounds as real
as Arthur, but they pass his minimum standard and are approved as opt-in Azure
regional voices. They are not the default.

Microsoft counts SSML body markup as billable characters, excluding only the
outer `speak` and `voice` tags. The corrected estimate for the gate is therefore
14,367 billable characters (12,111 was only the visible/plain-text count),
bringing cumulative estimated F0 synthesis to 23,561 characters (4.7122%). Any
production estimator must use this boundary. Do not issue another request from
this completed gate.

The files were 24 kHz / 160 kbps mono MP3. Microsoft documents that selecting a
48 kHz format invokes a separate high-fidelity standard model and supports
lossless `riff-48khz-16bit-mono-pcm`, so one same-voice 48 kHz control is a valid
diagnostic for “degraded”. Do not describe it as a fix for “robotic”: Irish
Connor and South African Luke are Standard voices with no official style list,
and prosody only adjusts delivery parameters. Australia's preview MAI-Voice-2
and Dragon HD Omni options are materially different model paths, but they were
not returned by the live UK South catalogue and must not be conflated with the
three heard Standard voices.

Official references: [Chatterbox](https://github.com/resemble-ai/chatterbox),
[Azure language/voice catalogue](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support),
[Azure pronunciation controls](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-pronunciation),
[Azure REST audio formats](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech#audio-outputs),
[Azure Speech pricing](https://azure.microsoft.com/en-gb/pricing/details/speech/),
[`edge-tts` 7.2.8 release](https://github.com/rany2/edge-tts/releases/tag/7.2.8).

OmniVoice's upstream voice-design list is closed, not free-form: American,
British, Australian, Canadian, Indian, Chinese, Korean, Japanese, Portuguese
and Russian accents. Asking it for Irish or South African is rejected during
instruction validation. It does, however, support inline CMU phonemes for
English pronunciation correction, which is the supported route for its Huawei
and Xiaomi failures.

### XTTS-v2 — tested and rejected

**Result: failed, same as Chatterbox.** Dave: *"bullshit, americanised crap"*.
Image reverted to `-min`, the 8 GB reclaimed, `tts-1-hd` entries deleted from the
voice map. Piper natives re-verified working afterwards.

This was the strongest remaining candidate — different architecture, widely
described as accent-preserving, fed genuinely accented references (Edge Connor
and Luke; Piper VCTK p272 for Scottish, since **Edge has no Scottish English
voice at all**). It still flattened them. That failure is what turned "Chatterbox
can't do accents" into the general rule at the top of this file.

Historical note: XTTS was reached by changing the former Piper wrapper image to
`ghcr.io/matatonic/openedai-speech:latest`. That service and configuration were
retired on 2026-08-15; this is evidence, not a current setup instruction.
Licence is Coqui Public Model License, non-commercial.

<details>
<summary>Original write-up, kept for the reasoning (it was sound; the result was not)</summary>

The Piper container was running `openedai-speech-**min**`, which is Piper-only.
The **full** `openedai-speech` image also ships **XTTS-v2**, and
`voice_to_speaker.yaml` already had `tts-1-hd` XTTS entries waiting for it. One
image tag.

XTTS is a different architecture from Chatterbox and clones from a reference
clip while reportedly keeping the accent. That is precisely the property
Chatterbox lacks, so it is the honest local answer to *"can I have the Edge
voices without the cloud"*.

Under test (`tts-1-hd` model): `xtts_irish_m`, `xtts_scottish_m`,
`xtts_southafrican_m`. References are ~16–21 s of continuous prose — Irish and
South African cloned from the Edge locale voices, Scottish from Piper's native
VCTK p272 **because Edge has no Scottish English voice at all**.

**Licence:** XTTS-v2 is Coqui Public Model License, **non-commercial**. Fine for
a personal library; revisit before any commercial use.

</details>

### Gemini 3.1 Flash TTS preset catalogue (official, checked 2026-08-15)

Google documents 30 names with character labels, not guaranteed gender,
nationality or accent: Zephyr (Bright), Puck (Upbeat), Charon (Informative),
Kore (Firm), Fenrir (Excitable), Leda (Youthful), Orus (Firm), Aoede (Breezy),
Callirrhoe (Easy-going), Autonoe (Bright), Enceladus (Breathy), Iapetus
(Clear), Umbriel (Easy-going), Algieba (Smooth), Despina (Smooth), Erinome
(Clear), Algenib (Gravelly), Rasalgethi (Informative), Laomedeia (Upbeat),
Achernar (Soft), Alnilam (Firm), Schedar (Even), Gacrux (Mature), Pulcherrima
(Forward), Achird (Friendly), Zubenelgenubi (Casual), Vindemiatrix (Gentle),
Sadachbia (Lively), Sadaltager (Knowledgeable), and Sulafat (Warm).

All 30 IDs are registered and all 30 exact app-path previews were cached across
Free quota days by 2026-08-21. An independent final sweep opened every
`/api/preview/<voice_id>` path, found HTTP 200 MP3 at 24 kHz mono, and fully
decoded every file; durations span 79.008–89.088 seconds and sizes span
1,580,204–1,781,804 bytes. The UI continues to expose a voice only while its
persisted preview is ready. Achernar's 10:10 production-path file passed Dave's
listening gate as “one of the best”. Catalogue/cache presence is not a voice
verdict: the other 29 remain auditions rather than approved long-form narrators.
The persistent ten-RPD local guard and no-automatic-retry rule remain in force.
See [GEMINI-SETUP.md](GEMINI-SETUP.md).
Official source: [Gemini TTS voice options](https://ai.google.dev/gemini-api/docs/speech-generation#voice-options).

### Deepgram Aura-2 voice catalogue (official, checked 2026-08-30)

Deepgram exposes Aura-2 ($0.030 / 1k chars) via `POST https://api.deepgram.com/v1/speak`.
Pre-cached, registered production voices:
- **Orion** (`deepgram_orion` / `aura-2-orion-en`): American Male. Flagship deep, resonant, expressive narrator.
- **Orpheus** (`deepgram_orpheus` / `aura-2-orpheus-en`): American Male. Smooth, measured cadence.
- **Arcas** (`deepgram_arcas` / `aura-2-arcas-en`): American Male. Warm, natural conversational narrator.
- **Pandora** (`deepgram_pandora` / `aura-2-pandora-en`): British Female. Articulate, clear prose delivery.
- **Hyperion** (`deepgram_hyperion` / `aura-2-hyperion-en`): Australian Male. Engaging natural Australian narrator.

**Aura-1 Rejection (Angus):** `aura-angus-en` (Irish Male) was evaluated on Chapter 1 of *Armed Struggle: The Story of the IRA* and rejected by Dave: flat, monotone across dialogue, and lacking speed/emotional control. Excluded from production.

All 5 canonical audition previews are pre-rendered on canonical `SAMPLE_TEXT` and persisted in `/data/previews/deepgram_<voice>.mp3`. Text is processed under the `'explicit'` numeric/initialism profile with $\le 400$-char clause chunking and 300 ms/650 ms silence joins.
Official source: [Deepgram TTS voice options](https://developers.deepgram.com/docs/tts-models).

### NVIDIA MagpieTTS Multilingual v2607 presets (official, checked 2026-08-15)

The exact v2607 model ships five baked English speaker IDs: `Aria` (0),
`Jason` (1), `John` (2), `Leo` (3), and `Sofia` (4). NVIDIA does not document
those names as regional accents or as guarantees of gender, character or
narration quality. v2607 also removes zero-shot voice cloning, so this is a
fixed preset bank rather than another Arthur/accent-reference route.

None is an app voice or a cached production preview. One private
free-T4 gate has produced local evaluation files for all five on the same
prepared difficult passage, plus a 9:14 John stateful long-form passage. All six
files were independently decoded, then rejected by Dave: each short arm shared
an early defect around five seconds, and the long arm had the same clipping/cut
class. Accents and tone were good, but reliability was unacceptable. The raw
NeMo path is closed and every preset remains unselectable. A single hosted NIM
comparison may diagnose the runtime boundary; it does not approve a voice. See
`ENGINES.md` for the exact model/runtime, free-developer and licence boundaries.

### Candidate models, evaluated 2026-07-27

Dave sent five to look at, with: *"it took me 5 minutes to find these."* Fair —
this should have been my sweep, not his. Evaluated against the one question that
matters: **does it ship accents trained into the model, or is it another
cloner?**

| Model | Mechanism | English accents | Verdict |
|---|---|---|---|
| **[MeloTTS](https://github.com/myshell-ai/MeloTTS)** | **trained per-accent** | `EN-US`, `EN-BR`, `EN_INDIA`, `EN-AU`, `EN-Default` | Installed and fast, then **rejected by ear** for poor pronunciation, number handling and overall TTS quality. **No Irish.** |
| **[Fish-Speech / S2](https://github.com/fishaudio/fish-speech)** | cloning **+ free-form text tags** | 80+ languages; supports a literal `[with strong accent]` tag and 15,000+ free-form delivery descriptors | Not a low-cost Zorin candidate: current S2 Pro is 4B and its official install guide calls for 24 GB GPU memory. CPU packaging exists but does not make it practical here. |
| **[IndexTTS-2.5](https://github.com/index-tts/index-tts/blob/39207d91c30899cad1e7c1b9eb678c241f678e55/README.md)** | zero-shot cloning from one reference | No official named or regional-English preset catalogue | **Rejected for production.** Complete-sentence calls fixed the upstream-splitter corruptions, but the corrected Arthur clip still had poor timing/pacing and was far less natural than Gemini Zephyr or Chatterbox. |
| **[Orpheus-TTS](https://github.com/canopyai/Orpheus-TTS)** | zero-shot cloning + named voices | English voices (tara, leah, jess, leo, dan, mia, zac, zoe); no accent variants | Cloning half will hit the rule. **But it ships fine-tuning tooling and data-processing scripts** — the supported route to a custom local voice. 3B, heavy on CPU. ⚠️ Their own guidance: *"I recommend not using synthetic data for training as it produces worse results"* — a direct warning against distilling Edge output, which is worth knowing **before** attempting the distil path below. |
| **[Dia2-2B](https://huggingface.co/nari-labs/Dia2-2B)** | dialogue TTS, context conditioning | English only, 2-minute cap | Not accent-targeted, and the 2-minute cap rules out narration. |
| **[VibeVoice](https://microsoft.github.io/VibeVoice/)** | long-form multi-speaker | English + Chinese | **See below — I dismissed this wrongly, and it matters more than accents.** |

**Resulting order:** grade Chatterbox V3 → keep Omni as a candidate for its
supported accents and short work → find materially better local models for the
remaining accents. The current Piper path and Melo are rejected for production;
Fish S2 Pro is outside the local/free-GPU hardware budget. Neither Fish nor
Index provides a documented named Australian, Irish or South African voice
catalogue; accent quality depends on a rights-cleared human reference and must
be heard, never inferred from a free-form accent tag.

---

## VibeVoice — the one I got wrong, and why it is the most important of the five

I dismissed this in one line as "same cloning wall, and the repo has pivoted to
ASR". Both halves were wrong, and Dave pushed back: *"you too quickly dismissed
the other ones i gave you. vibevoice, for example. dont do that."* He was right.
What I did was skim a README, see ASR release notes at the top, and pattern-match
to a conclusion I already held.

**What it actually is** (Microsoft Research, [tech report](https://arxiv.org/abs/2508.19205)):

- **Up to 90 minutes of continuous speech in a single generation** (1.5B, 64K
  context). Large does ~45 min.
- **Up to 4 distinct speakers** with consistent identity and natural turn-taking.
- Continuous acoustic + semantic tokenisers at a **7.5 Hz frame rate**, with a
  Qwen2.5 LLM for context and a diffusion head for acoustic detail.

**Why this is bigger than the accent question.** Chunking is the structural wound
in this pipeline, and almost every audio defect found on 2026-07-27 traces back
to it:

- TADA has no long-form mode, so chunks are hard-concatenated and Dave heard
  "weird pacing"; we paper over it with `JOIN_SILENCE_MS = 250`.
- Chunk-initial instability forced the `LEADIN = "Right. "` hack, whose trimmer
  then leaks the word into the audio.
- The entire transcript-capture and ASR-verification apparatus exists to police
  per-chunk rendering.

**A model that renders 90 minutes in one pass deletes that whole problem class**,
and 4-speaker support means distinct character voices in fiction — something
nothing else here can do.

**Availability (checked, not assumed):**

| Weight | Status |
|---|---|
| `microsoft/VibeVoice-1.5B` | **available**, 64K ctx, ~90 min |
| `microsoft/VibeVoice-Realtime-0.5B` | **available**, ~300 ms first audio, single speaker, streaming |
| `microsoft/VibeVoice-Large` | **401 / disabled** — community mirrors exist (`aoi-ot/VibeVoice-Large`, `aoi-ot/VibeVoice-7B`) |
| GGUF quantisations | exist (`wsbagnsv1/VibeVoice-1.5B-gguf`) — relevant for CPU on zorin |

**Constraints to respect:**

- Licensed **for research purposes**. Personal library use is within spirit;
  commercial is not.
- **English and Chinese only.** Other languages "may be unintelligible".
- Microsoft disabled the repo in Sept 2025 over misuse, then restored it. The
  Large weights remain 401.
- **No accent controls.** It will not solve Irish or Welsh. Its value here is
  long-form coherence and multi-speaker, not accent.

**Listening update, 2026-08-13:** the pinned long-form blind comparison selected
`cfg_scale=2.0` (B). Dave heard it as much clearer and otherwise excellent,
apart from one brief garble after “romantic felicity”. `cfg_scale=3.0` (A) was
muffled and distant even though the voice/emotion itself was acceptable;
`1.3` had already been rejected. Acoustic similarity metrics had favoured 3.0,
so this is a useful warning: pitch/timbre statistics cannot replace listening.
The later real-path and documented same-speaker-turn gates did not cure the
progressive pacing failure: both four-turn and seven-turn arms were rejected by
ear. VibeVoice is therefore rejected for audiobook production on this exact
official-weights/community-runtime path. `cfg_scale=2.0` remains only the best
tested Vibe setting, not a production approval.

**The lesson, recorded because it is the same one three times over:** I keep
converting "this doesn't solve the problem I'm currently fixated on" into "this
isn't worth looking at". VibeVoice was worth the full test even though that test
ultimately rejected its audiobook path; the early dismissal and the later
listening verdict are separate facts.

### So what is actually left for local accented English

Ordinary English-only cloning is exhausted. These are experiments, not approved
answers; each still has to pass the quality gate above:

1. **Train or fine-tune on suitable human speech.** A model needs target-accent
   training data, but Piper demonstrates that this alone is not enough. The
   model family and pronunciation quality must also meet the audiobook bar.
2. **Distil a cloud voice into a local model.** Generate a few hours of Edge
   `en-IE-ConnorNeural` audio with known transcripts, then fine-tune a Piper
   or another model on it. This remains an unproven research path, not an
   endorsement of Piper's synthesis quality.

3. **MeloTTS for the accents it has.** Confirmed working on CPU with five native
   English accents, but rejected by ear. Covers Australian and British on
   paper, not at the quality required here. Not Irish.

4. **Chatterbox Multilingual V3.** Unlike the rejected English-only cloners,
   upstream specifically claims improved accent preservation. It now renders
   locally with Irish and South African references at RTF 4.15/4.81. ASR
   sequence ratios are 0.848/0.844, but both clips contain suspect number
   readings. That justifies the experiment; it does not establish quality until
   Dave listens.

### Piper deployment audit — 2026-07-28

The initial response to Dave's latest verdict incorrectly jumped straight from
"these outputs failed" to "the engine is the cause". The actual audit found:

- **Speaker mapping is correct.** All eleven configured numeric IDs match the
  deployed model's own `speaker_id_map` (`p364=106`, `p245=97`, etc.).
- **The model download is correct.** The deployed ONNX SHA-256 is
  `4e9fc85ab9009385319fc6bae7f55577f8a2d7ee77fd9159a5500eb6531f41e6`,
  identical to the current official Hugging Face artifact.
- **But this is a weak model choice for the claim we made.** The only official
  VCTK release is `medium`, 22.05 kHz, and its model card says it was fine-tuned
  from the US English Lessac voice. Every one of its 109 speakers uses the same
  `en-gb-x-rp` eSpeak phonemizer. A VCTK speaker's birthplace therefore does not
  guarantee that generated phonetics preserve that dialect.
- **The serving stack is stale and lossy.** `openedai-speech` is archived; our
  image runs Piper 1.2.0 while current upstream is 1.6.0. The wrapper encodes
  preview MP3s at 64 kbps. It also predates current raw-phoneme injection, so it
  cannot use that control for difficult names.
- **Inference defaults were not accidentally overridden.** The deployed config
  uses the model's official `noise_scale=0.333`, `length_scale=1.4`, and
  `noise_w=0.333`. The model is not truncated or pointed at the wrong speaker.

Three fresh, explicit-extension clips isolated the remaining questions using the
same p364 text: `vctk_audit_piper12_64k.mp3` (deployed path/encoding),
`vctk_audit_piper12_wrapper.mp3` (same synthesis re-encoded from WAV), and
`vctk_audit_piper16_direct.mp3` (current Piper direct, same official model).
All return `200 audio/mpeg`.

**Final listening verdict (Dave, 2026-07-28):** all three were *"absolute shit"*;
almost every word was wrong and they sounded bad. Higher bitrate did not rescue
the deployed synthesis, and current Piper 1.6 did not rescue the model. The
official VCTK-medium path is closed. Do not spend more time tuning, EQing or
repackaging it. This finding is scoped to the models actually tested, but it is
enough to remove Piper from this project's production choices and automatic
fallbacks.

**Note on (2), before anyone starts:** Orpheus's own training guide advises
*against* fine-tuning on synthetic data — it says synthetic voices "lack
diversity and map to the same set of tokens when tokenised". Distilling Edge is
exactly that. It may still work (Piper fine-tunes are less sensitive than a 3B
LLM-based model), but go in expecting to have to prove it, and prefer real
recorded speech if any is available.

---

## What to use

| Need | Current answer |
|---|---|
| Irish or South African, local | **No approved production voice.** The exact Chatterbox Multilingual V3 regional gate failed by ear. |
| OmniVoice-supported accent, local | Candidate for short work: accents sounded good, but pronunciation needs overrides and CPU speed rules out full books. |
| Irish, South African or Australian, online | **Azure William (AU), Connor (IE) and Luke (ZA) are accepted opt-in quality-floor voices** on the proven 48 kHz lossless, correctly processed path. Accents are acceptable; emotion is weak and none is as real as Arthur. F0 first, never automatic paid fallback. |
| General English, free GPU evaluation | NVIDIA MagpieTTS v2607 raw NeMo path is **rejected** after all five presets and the long arm shared an early cut/clipping defect. One hosted-NIM diagnostic remains open; no preset is exposed. |
| Piper regional path | **Fully retired.** Deployed/high-bitrate/current-runtime A/Bs all failed voice quality, authenticity and pronunciation; no service or voices remain. |
| British/general narration, local | **Beatrice (Nano)** (`uk_female_samuel_nano` via Chatterbox Nano) is the system default narrator. Fast CPU inference (~0.87x RTF) with human-cloned British voice. |

The Voices page is an audition surface, not a synthesis trigger. It offers only
voices with a persisted non-trivial preview; Play must be immediate. Paid or
network engines are never warmed in the background merely because their voice
definitions exist.

### Screened CPU-engine voice inventory (official upstream names)

| Engine | Ready upstream names | What “more voices” means |
|---|---|---|
| Pocket TTS 2.1 | English: `alba`, `anna`, `azelma`, `bill_boerst`, `caro_davy`, `charles`, `cosette`, `eponine`, `eve`, `fantine`, `george`, `jane`, `jean`, `javert`, `marius`, `mary`, `michael`, `paul`, `peter_yearsley`, `stuart_bell`, `vera`. Italian `giovanni`; Spanish `lola`; German `juergen`; Portuguese `rafael`; French `estelle`. | Also accepts a WAV/Hugging Face reference; the cloning asset gate must be accepted legitimately. |
| NeuTTS Air 1.4.1 | English: `dave`, `jo`, `emily`, `paul`, `sophie`, `steven`; Spanish `mateo`; German `greta`; French `juliette`. | These are references, not a closed preset bank. A custom clean 3–15 s mono WAV plus exact transcript creates another voice. |
| KittenTTS 0.8.1 | `Bella`, `Jasper`, `Luna`, `Bruno`, `Rosie`, `Hugo`, `Kiki`, `Leo`. | Fixed preset list; no officially documented cloning path. |

Source details and exact upstream links are maintained in `ENGINES.md`.
The app now registers all 21 English Pocket presets and all eight Kitten
presets behind opt-in CPU profiles. It still does not expose a cold Play
button: each voice becomes audition-ready only after its persisted preview is
non-trivial. Peter, Jasper and Rosie are the only voices with a human listening
verdict so far; catalogue presence is not a quality verdict for every voice.
It does guarantee that every offered voice is cached for immediate playback
and can be selected with its owning engine. Dave heard the
same-text long-form Peter (16:27) and Rosie (21:16) files: Rosie led on body
pace/tone; Peter was decent/promising but uneven. Both engines are accepted as
opt-in book choices while Beatrice/Nano remains the default.
Their shared run-on title/author opening was identical malformed Project
Gutenberg metadata supplied by our test path. In the corrected 600-word gate,
Peter's current packing sounded more natural and the paragraph-aware arm had
stranger intonation; Rosie showed no meaningful difference. Current sentence
packing therefore remains for both engines. No new default was set.

Dave's latest grading, 2026-07-28, supersedes the provisional Piper verdict:
most current Piper outputs sound bad, their accents are not authentic enough,
and pronunciation is not good enough for this project's audiobooks. That is an
output verdict, not an engine-level root-cause finding.

### Gaps that are the corpus, not the code

VCTK is 110 speakers and supplies every native accent above. It contains
**exactly two Australians, both male**, and **exactly one Welsh speaker, female**.

- **No Australian female** in VCTK → Edge covers it.
- **No Welsh male** anywhere I could find. Piper ships no `en_AU` model at all,
  and `rhasspy/piper-voices` has only `en_GB` and `en_US` English. Closing this
  needs a fine-tune on accent-tagged Common Voice data, or nothing.

`cy_GB` Piper voices speak the **Welsh language**, not English with a Welsh
accent. Tested: feeding them English produced Welsh gibberish (ASR heard
*"U'n gynill yn ymwandsyn yn gallu srwy"*). Do not try this again.

---

## `cfg_weight` — supported control, previously misinterpreted

`chatterbox/server.py` accepts `cfg_weight` and `exaggeration` per request and
has done since it was written. **Default is 0.5.** Every clip rendered on
2026-07-27 used that default until the very end.

From Resemble's README:

> *"language transfer outputs may inherit the accent of the reference clip's
> language. To mitigate this, set `cfg_weight` to `0`."*

The earlier repo read that sentence backwards and promoted `0` as a general
same-language accent-preservation setting. Upstream does not say that. It says
the default `0.5` works for most prompts, recommends about `0.3` for a fast
reference/pacing problem, and reserves `0` for mitigating unwanted accent when
the reference clip and requested language differ. Our V3 references and
`language_id="en"` matched, so forcing zero was not justified by that guidance.

**Measured by ear (Dave, 2026-07-27):** Nano at `cfg_weight=0` was the best arm
in that particular comparison — *"nano cfg 0 is best, but could be better"*.
That is a listening result, not proof of the discarded mechanism. Neither that
result nor the V3 zero-CFG gate passes the production quality bar.

Other documented settings, untested here:

- `exaggeration` default `0.5`; `~0.7+` for dramatic delivery, speeds speech up.
- Pair higher `exaggeration` with lower `cfg_weight` for slower pacing.

---

## Model zoo (from Resemble's README, which I should have read first)

| Model | Size | Languages | Notes |
|---|---|---|---|
| Chatterbox-Nano | 110M | **English only** | On-device/CPU, 3× realtime on 8 cores. What we render books with. |
| Chatterbox-Turbo | 350M | **English only** | Built for low-latency voice agents. |
| **Chatterbox-Multilingual V3** | **500M** | 23+ | Headline feature: *"improves voice identity and **accent preservation**"*. Installed as isolated `chatterbox-v3`; exact regional zero-CFG gate rejected. |
| Chatterbox (original) | 500M | English | CFG & exaggeration tuning. |

Nano and Turbo are English-only agent models that make **no claim about accent
fidelity**. V3 is the one built for it. That we are chasing accents on Nano is a
consequence of never having read this table.

---

## Failures, 2026-07-27

Recorded because each cost real time and each is repeatable by someone who
doesn't know.

**1. Never read the engine's documentation.** Ran an entire day of accent work
against `cfg_weight=0.5` — the setting Resemble's README says to change for
exactly this problem — and never opened the Model Zoo, which says plainly that
Nano and Turbo are English-only agent models. Dave: *"did you bother to consult
chatterbox docs and repo to actually check?"* No.

**1b. Did not sweep the field.** After four cloning failures I was still
reaching for more cloners instead of asking which models ship *trained* accents.
Dave found MeloTTS, Fish-Speech, Orpheus, Dia2 and VibeVoice in five minutes and
sent them over. MeloTTS — five native English accent variants, exactly the
architecture that works — was the obvious first stop and I had not looked at it.
**When a class of approach fails repeatedly, survey the alternatives instead of
producing another instance of the failing class.**

**1c. Dismissed candidates on a skim instead of a test.** I wrote VibeVoice off
in one line — "same cloning wall, pivoted to ASR" — from README headlines.
Reading it properly showed a model that renders **90 minutes in one pass with 4
speakers**, which attacks the chunking problem that causes most of the audio
defects in this repo. Dave: *"you too quickly dismissed the other ones i gave
you. vibevoice, for example. dont do that."* **A candidate that does not solve
today's problem may still be the most valuable thing on the list. Read it before
ranking it.**

**2. Re-researched what the repo already contained. Three times.**
The VCTK accent voices were already installed. The Edge Australian voices were
already installed. The `LEADIN` cold-start fix was already in `tada/server.py`.
Each was "discovered" from scratch. **Read the code and the voice list before
researching anything.**

**3. Concluded correctly, then argued myself out of it — twice.** I established
that cloning carries timbre but not phonetics, then hypothesised that better
reference audio would fix it, rebuilt nine voices, and shipped them **without
listening**. Dave: *"you softened the shit out of the voices and made them
american"*. Reverted entirely.

Then did the same shape again with XTTS-v2: pulled an 8 GB image on the strength
of a reputation for accent preservation, without a single clip to back it.
Dave: *"bullshit, americanised crap"*. Reverted, image deleted.

The second one was worth running — XTTS is genuinely different architecture, and
its failure is what made the rule general instead of Chatterbox-specific. But
the honest framing is: **the rule was already visible after attempt one**, and
attempts two through four cost hours to confirm it.

**4. Blamed the model for our own bug.** Reported that TADA "invented a word
that was not in the text". It was `LEADIN = "Right. "`, which we prepend
deliberately and `_trim_leadin()` intermittently fails to cut. The answer was in
our source the whole time.

**5. Invented a measurement.** Claimed the hyphen fix "measurably" removed ~1
second of dead air, from a file-size delta between two generations of different
text on a non-deterministic engine. Not a measurement. Retracted in
`tts_preprocess.py`.

**6. Overstepped a contract on inference.** Spelled bare decades for modern
engines, which the MODERN-ENGINE CONTRACT forbids without an ear test. A
regression guard caught it. The guard was right.

**7. Handed over a URL I never opened.** `/api/sample/ab_tada_cpu` 404'd because
the name was never added to the endpoint allowlist. **Test the link before
sending it.**

**8. Deployed half the stack.** `docker compose up -d --build webapp` leaves
`worker` on old code; they share `app.py`. The stale worker silently reverted a
database field. `/api/health` reports the *webapp's* version, so it looked
current. Use `scripts/deploy.sh`. See OPERATIONS.md.

---

## How the pieces fit

- **Piper (historical only)** — its former service, voice map, setup script and
  selectable catalogue were deleted on 2026-08-15. Historical speaker/model
  evidence above is intentionally retained so the rejected path is not
  rediscovered or accidentally rebuilt.
- **Chatterbox** — reference WAVs in `chatterbox/voices/` (baked into the image)
  and `CUSTOM_VOICES_DIR` = `data/voices` (overlaid at `/app/voices/custom`, no
  rebuild needed). That directory is owned by the container uid; **write to it
  through the container**, not from the host.
- **Reference clips** — 8–45 s (`REF_MIN_SECONDS`/`REF_MAX_SECONDS`). Continuous
  prose beats disconnected sentences. Quality of the reference changes timbre,
  **not** accent.

---

## Next, in order

1. **Keep the heard V3 regional path closed.** Do not expose its three labels.
2. If V3 is revisited, first isolate it with the identical human Arthur
   reference/text against Turbo at official defaults. Only then test a genuine,
   clean human regional reference separately; do not infer quality from a
   Piper/Edge-generated prompt.
3. **Piper VCTK is closed.** Its controlled synthesis-path A/B failed at every
   layer. Do not polish or repackage this model; only reopen Piper for a
   materially different model with independently good samples.
4. **Welsh male** — find/train a materially better model on suitable human
   speech, or accept the gap.
