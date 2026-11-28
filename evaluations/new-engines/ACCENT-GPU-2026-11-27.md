# Regional narrators for audiobooks

**28 November listening verdict.** Dave rejected all accent performances on this desk. The speed, waveform and transcript measurements below are retained as technical evidence. The recordings did not pass the regional narration test.

## What Muse does

Muse lets a listener choose among hundreds of voices or describe an accent and speaking pace. The voice system produces speech tokens that carry both the words and their delivery. Meta describes the controls and the conversational product. Its technical post leaves the individual accent-training recipes undisclosed. The public Meta Model API lists transcription as its speech endpoint and has no listed speech-generation endpoint for sending it a chapter. [Muse voice controls](https://www.meta.com/blog/meta-connect-2026-everything-we-announced/) · [November rollout](https://about.fb.com/news/2026/11/introducing-muse-ai-voice-expressive-avatars/) · [Meta research](https://research.meta.ai/blog/bringing-your-muse-to-life) · [Meta Model API catalogue](https://dev.meta.ai/docs/models).

For Studio, there are three ways to obtain a regional narrator. A named Australian voice such as Natasha has an identity the provider reuses on each request. A model with voice design can create a fictional speaker from a description, after which we can save one approved recording and condition every subsequent passage on it. A model with accent steering can apply a learned regional direction to a fixed speaker. A generic reference-upload field establishes only that a model accepts a recording. How much of its accent survives is an empirical question.

## What happened to the Australian Nano voice

Round two used an existing 19.296-second, 24 kHz mono WAV. Its SHA-256 is `22dfb29ebd5125aa28e7b803263b109192f642d677c0b308af86701445527155`. The archive identifies it as synthetic. The record does not establish which synthesizer made it. The resulting CPU Nano take lasted 66.12 seconds. Dave rated it Natural, Clean and Keep and heard no Australian accent. Nano's upstream code conditions the speaker and decoder on the recording, with different crops for its speech tokens and decoder. There is no explicit Australian direction in that generation path. That establishes what Studio requested. It does not isolate which component lost the accent. [Round-two recording and hash](../../VOICES.md#27-november-2026--second-blind-cpu-round) · [pinned upstream conditioning implementation](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py#L222-L290).

For a native Australian voice, Natasha and William are Australian English in Microsoft's catalogue. Dave accepted their accents in an earlier Edge audition and flagged Chinese company names. Studio's Edge book path calls the community `edge-tts` client. Microsoft's Azure API is a separate integration. The two services' available voices and controls differ. [Microsoft's voice list](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts) · [Edge runtime](https://pypi.org/project/edge-tts/7.3.1/).

## Can a machine verify the accent?

We ran the research team's CommonAccent ECAPA classifier on short English windows at five evenly spaced start points in each longer recording. The four supplied Australian, English, US and Irish example files gave their published labels. These examples check the installation. They are not an independent accuracy estimate. The Nano and reference rows below use exactly the recording and input from round two.

| Recording | Windows labelled Australian | Other labels |
|---|---:|---|
| Original synthetic reference | 3 of 5 | England twice |
| Nano clone | 0 of 5 | US five times |
| Native Natasha, current standard | 5 of 5 | — |
| Native William, current standard | 4 of 5 | US once |
| Human Australian VCTK p374 reference | 0 of 5 | Canada twice, England twice, US once |
| Native Natasha, whole chapter | 5 of 5 | — |
| ZONOS3 directed chapter, CPU / T4 | 2 of 5 on each | England three times on each device |
| VoxCPM2 chapter from designed reference, T4 | 0 of 5 | US three times, Canada twice |

The classifier reproduced Dave's concern on Nano and missed a known Australian speaker on every window. Its labels can flag takes for comparison. They cannot grant or revoke a regional listening verdict. Whisper checks speech against the manuscript and cannot substitute for a regional listening verdict either. [Classifier and example recordings, MIT](https://huggingface.co/Jzuluaga/accent-id-commonaccent_ecapa/tree/14bebf44b7e7a34204d0acc2c897935945fb5c51) · [evaluation paper](https://www.isca-archive.org/interspeech_2023/zuluagagomez23_interspeech.html).

The human control is speaker p374 from *CSTR VCTK Corpus v0.92*, Junichi Yamagishi, Christophe Veaux and Kirsten MacDonald, University of Edinburgh (2019), CC BY 4.0. The 18.000-second reference combines microphone-one utterances, adds 120 ms between them, applies a 70 Hz high-pass and loudness normalization, and converts to mono 24 kHz PCM. The resulting SHA-256 is `f1db6a7a352526cdf867b27ec7ebfd00538b8f88375953217c1b212756725c73`. The corpus accent is a property of the input speaker. [University dataset and attribution](https://datashare.ed.ac.uk/handle/10283/3443) · [Licence](https://creativecommons.org/licenses/by/4.0/) · [Preparation script](../../scripts/kaggle/extract_vctk_voices.py).

## Choosing a voice in Studio

| Need | Where to look |
|---|---|
| Australian narration | No voice from this desk qualified. Natasha failed this listening round. William was not on the desk and has only an older quality-floor verdict. |
| Irish narration | **Heard and accepted → Irish** includes the Fish, Higgs and Breeze Cillian voices. Fish delivered the full *Armed Struggle* audiobook. Higgs has a book route and a listening verdict on a chapter. Breeze has an audition. |
| Reuse a personally chosen speaker | **Voices → Clone a voice** offers Chatterbox Nano/Turbo and local ZONOS3. **Female Reference Nov27** uses the synthetic round-two reference and **Vctk P374** uses the credited human recording. Both have cached previews and book-picker entries. Dave rejected the regional performances on this desk. |
| Find engines that can design a new voice | Use **Models with text voice design**. The card distinguishes what the model supports from controls available inside Studio. The November Vox experiment demonstrates designing a voice once and saving it, alongside the damaged chapter it produced. |

The separate procurement or preparation of an accent reference is a once-per-narrator task. A pronunciation mapping, when appropriate, can also be applied centrally. A model that silently deletes ordinary English prose presents a different burden: reject or hold that configuration if a bounded automatic retry still loses the text. The Vox example below illustrates why listening to a pleasant opening does not answer the audiobook question.

The live catalogue contains 34 model cards. Of these, 24 report upstream cloning, five report text voice design, and three accept a WAV in Studio (Chatterbox Nano, Chatterbox Turbo and ZONOS3). The three latest stock additions all support cloning upstream. Marcus has 46 supplied references and a private-personal-use licence for the deployed weights. Imogen's ZONOS3 service can now enroll a user WAV. Reverb offers 16 presets across seven languages and takes a clip plus transcript upstream. Marcus and Reverb still use their selected stock voices in the app. [Inventory, model cards and licences](../../ENGINES.md#stock-cpu-book-narrators-added-24-november-2026).

## Test material

The short comparison uses the Studio shared audition. The sustained reading uses the first 60 complete blocks of the checked-in public-domain *The Yellow Wallpaper* fixture, 1,410 whitespace-delimited words. Its UTF-8 payload with blank lines between blocks has SHA-256 `61c5102cda37a73ee4d95079612f025b34cbc1ca1b26257ba01a86220005f2df`. Each engine receives the same continuous reading through its recorded text and chunking path. Keep the original run when an automatic retry changes the result. A chapter can retain the speaker and still omit a sentence. [Shared audition](../../AUDITION-STANDARD.md) · [chapter source](../../scripts/kaggle/fixtures/yellow_wallpaper_turn_reset_78.txt).

## A chapter on each device

| Narrator and route | Finished audio | Time spent generating | Text check |
|---|---:|---:|---|
| Edge Natasha, deployed Studio proxy | 8:09 | 1:31 across 11 remote requests | 97.1–100% ordered coverage per part. All 11 endings present and no flagged drops. |
| ZONOS3, Australian direction +1, Ryzen 9 8945HS CPU | 7:55 | 14:08 across 11 requests | 98.6% across the joined recording. Every part reached its ending. |
| ZONOS3, same source, reference and steering, free NVIDIA T4 | 7:53 | 0:59 across 11 requests | 99.5% across the joined recording, with no flagged dropped span or missing tail. |
| VoxCPM2, fictional narrator from one saved prompt, free T4 | 6:44 | 13:11 across 14 requests | Two independent recognizers found a damaged second passage. The other 13 each matched at least 96.9%. |
| Qwen3-TTS Base, full reference plus transcript, Radeon 780M | 7:44 | 12:36 across 16 requests | 92–100% ordered coverage per part, 97.2% weighted across parts. No flagged missing span or unmatched tail. |
| OGG TTS 430k, fictional reference and adjacent text, free T4 | 7:40 | 34:44 across 60 requests | 1,392 of 1,401 normalized tokens aligned. Both ends present. The longest unmatched source run was “any one”, heard as “anyone”. |

Times cover synthesis requests, including provider latency for Edge. Finished audio includes joins. Downloading weights, compiling, transcription and retries are separate costs. The ZONOS3 T4 compiled its native runtime in 27:23 on a fresh machine. The cold build alone cost more time than this chapter saved. A warm T4 produced about eight minutes of speech per minute of inference. No paid GPU was used for these chapter trials.

### ZONOS3 and the difference between cloning and steering

We encoded the same original WAV into a 192-value speaker embedding, kept seed 42 and compared two settings. One used that embedding alone. The other added Zyphra’s learned `accents_en.australian` direction at +1. On CPU the single-request plain preview stopped 48 words early. The directed preview reached the end (74.67 seconds, 96.5% ordered coverage). That single pair establishes a failure and a successful take. The 11-part directed chapter checks how it fares over continuous prose. The production Studio upload uses the reference alone, checked in shorter chunks. The learned steering direction is an experiment in the listening desk.

Both CPU and CUDA use the MIT native runtime at `a50e14117d99181ba7f28047b451ba03ba1a09a9` and Apache-2.0 model revision `2921b8821772b0bd10a04456863d21abf9d2f283`, quantized experts/mixers and the keep2 decoder. The optional steering weights act on the embedding. Increasing the amount may also change the speaker's identity. The two CPU standard takes each scored Australian on two of the classifier's five windows. [Native runtime](https://github.com/Zyphra/ZONOS3-Mini/tree/a50e14117d99181ba7f28047b451ba03ba1a09a9) · [Model and control documentation](https://huggingface.co/Zyphra/ZONOS3-Mini).

On T4, the plain standard also ended early (21 unmatched tail words). The directed standard reached the closing April date, with 94.8% coverage and some currency substitutions. The chapter results used 11 bounded requests and the same reference throughout.

We also replaced just the synthetic WAV with the genuine p374 recording and repeated the single-request CPU standard at +1. The new take lasted 82.93 seconds (122.05 seconds synthesis), versus 74.67 seconds with the synthetic reference. Both had 96.5% ordered ASR coverage and reached the ending. One of five windows in the new take was classified as Australian. The genuine recording gives a useful comparison by ear without requiring any edits to the book. The unsteered, chunked Studio uploads separately yielded 73.67 seconds for **Female Reference Nov27** and 81.40 seconds for **Vctk P374**, with independent coverage of 97.1% and 96.5% and intact endings.

### VoxCPM2 and voice design

On the workstation’s Radeon 780M, one written description generated 15.52 seconds of fictional reference speech in 48.57 seconds of generation. Reusing that reference across the standard produced 64.82 seconds on Radeon and 61.78 seconds on T4. The exact round-two WAV also worked as a reference and yielded a separate 66.90-second standard on Radeon. The classifier called the new fictional reference US in all five windows. Dave subsequently rejected the desk’s accent performances, including this designed narrator.

With the saved fictional reference held constant through the T4 chapter, the first 85-word version of passage two matched only 50 words in order. Both Whisper small and base found the damage. Changing only the seed recovered a few words but still lost 24 words in a row. A single chapter-wide figure of 96.6% concealed the omission. This is a reason to transcribe and check individual passages before stitching a book.

In a third run we isolated the same text in three shorter requests. The surrounding sentences matched fully. The 40-word sentence containing the parenthetical still lost 21 consecutive words. The original failure starts at 0:31 in the listening desk's T4 chapter. Hold this exact configuration for unattended books.

The Apache-2.0 weights are OpenBMB revision `7936080b41163874f38610f46f438e2c0757f9fd`. The November 21 GGUF release uses Q8_0 weights and a BF16 companion at `7ea3060b0878d56dc14325b24daadd18de7a943c`. Both devices used llama.cpp b12774. Save the accepted narrator once and reuse the same reference on all calls. Reissuing a design prompt can create another speaker. [Model manual](https://huggingface.co/openbmb/VoxCPM2) · [November port and supported modes](https://github.com/ggml-org/llama.cpp/pull/32443) · [Converted weights](https://huggingface.co/ggml-org/VoxCPM2-GGUF/tree/7ea3060b0878d56dc14325b24daadd18de7a943c).

### Qwen and the missing reference encoder

The 17 November llama.cpp update supports conditioning on the recording and its transcript. The published August Q8 companion lacks the new reference encoder. On the workstation it accepted both inputs, logged a warning about missing reference codes and generated speech using only the speaker embedding. A working audio file therefore did not establish that the requested cloning mode ran.

We converted the companion again from Qwen’s original Apache-2.0 Base weights at `fd4b254389122332181a7c3db7f27e918eec64e3`, with the b12774 converter and `--mmproj --outtype q8_0`. The rebuilt file is 632,374,912 bytes, SHA-256 `1eb4f5308dc79927bec4bd507873d2320a14a7025229655b90cdfe54e55eb84a`. The Q8 backbone stayed identical. Both takes used the same 19.4-second John Kani recording, full transcript and shared text as the earlier liked native L40S take. The resident Vulkan server used a 2,048-token context, one slot and all 29 model layers on Radeon. Its three standard requests took 2:06 plus 11.59 seconds to load. The native L40S baseline made 63.78 seconds in 64.13 seconds. Dave rejected the accents on this desk, which included these Qwen comparisons. [November reference-mode change](https://github.com/ggml-org/llama.cpp/pull/32438) · [Published GGUF revisions](https://huggingface.co/ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF/commits/main) · [Qwen converter](https://github.com/ggml-org/llama.cpp/blob/b12774/conversion/qwen3tts.py).

On b12774 the `/tts` request fields for this mode are `speaker_ref_b64` and `speaker_ref_text`. The helper requires a transcript and at least one encoded reference frame. With the corrected companion, the same reference and a complete transcript, no request produced the fallback warning. The smaller server context reduced the logged Vulkan key/value cache from 3,584 MiB to 224 MiB. Keep the model loaded across chunks when measuring a book. [Server implementation](https://github.com/ggml-org/llama.cpp/blob/b12774/tools/server/server-context.cpp#L7074) · [Reference-mode checks](https://github.com/ggml-org/llama.cpp/blob/b12774/tools/mtmd/mtmd-helper-gen.cpp#L247-L252).

## Other releases checked

OGG TTS has an actual November checkpoint, in addition to the runtime changes above. The 430k preview is a 0.75B multilingual model trained on about 8,200 hours of studio speech. It accepts a recording and transcript plus adjacent unspoken text, which makes testing the flow across book passages worthwhile. The maintainer's published listening evaluation covers pairs of sentences. The public demo was still pinned to the older 120k preview at the time of the review. We tested the 430k weights directly under the Fish Audio Community License, using weights revision `271d038feb9d8030f8eb4a15112787d4bfefb309`, maintainer code `2247da5658f51e8eb278b87ecfbdd20e4ab1bfcb`, seed 42 and guidance 1.5. [430k model card](https://huggingface.co/FashionFlora/ogg-tts/tree/271d038feb9d8030f8eb4a15112787d4bfefb309) · [Maintainer inference code](https://github.com/FashionFlora/ogg-tts/tree/2247da5658f51e8eb278b87ecfbdd20e4ab1bfcb).

The first free T4 run loaded the checkpoint and codec. Using FP16 in place of the upstream BF16 autocast produced invalid sampling probabilities before any speech. A second allocation requested an L4 but exposed no CUDA device. Those failures concern the actual precision and hardware of the respective runs.

The overnight T4 retry used FP32 throughout and completed. Model and reference loading took 60.13 seconds. At 4.53 seconds of synthesis per second of chapter audio, this was the slowest completed GPU configuration here. The 60-part plain-prose chapter had 0.64% normalized word error rate on unprompted Whisper base.en. The 12-part shared challenge took 4:44 to produce 67.95 seconds and was much harder for the recognizer (20.59% word error rate). Dates, prices and other numbers deserve their own check before considering it for nonfiction. Both WAVs and MP3s decode in full. The result justifies further interest in this model for continuous prose. Dave rejected the desk’s accent performances. A separate general-narration rating for OGG is unrecorded.

A second independent, unprompted Whisper medium transcription scored 12.35% word error rate on the challenge. It recovered more names but still disagreed on several numeric phrases, including the final April date. These are transcript discrepancies, with the original recording available for listening.

Fish Drama 3’s November 20 llama.cpp update supports a single reference and transcript. Its published Q4_K_M backbone alone is 20.56 GB. The older native runtime produced a checked and repaired 14.6-minute Cillian reading here. A chapter on the new port would be a new result. Tontaube V1.1 Flash, released November 26, is interesting for fast Marcus narration. Its one English speaker does not expand regional customization. [Drama 3 cloning update](https://github.com/ggml-org/llama.cpp/pull/32586) · [Fish weights and licence](https://huggingface.co/ggml-org/drama-3-GGUF/tree/b11e7887a6cca16f1aa06a2555ece8ad38dad37f) · [Tontaube Flash release](https://github.com/craitech/tontaube/releases/tag/v1.2.0).

## Local recordings and verification files

Open `evaluations/new-engines/output/accent-gpu-2026-11-27/index.html` on Dave's workstation. The page and its MP3s are together in that directory. It plays offline. The source credits and the code and model revisions are in this tracked report. Generated audio and local test receipts stay out of Git.

| Directory under `evaluations/` | Evidence |
|---|---|
| `cpu-engines/output/zonos3-australian-2026-11-27/` | Original WAV, prepared-text hashes, matched CPU/T4 clips, chapter reports, joins and isolated Studio upload/resume receipts under `production-proof/result-fixed/` |
| `new-engines/output/edge-australian-chapter-nov27/` | Deployed proxy version, per-request texts and timings, individual MP3s, transcript reports and joined chapter |
| `new-engines/output/qwen3-q8-vulkan-nov27/` and `qwen3-q8-icl-vulkan-nov27/` in the same parent | Baseline and rebuilt Qwen companion logs, fixed-reference short tests and transcript checks |
| `new-engines/output/qwen3-resident-icl-vulkan-nov27/` | Resident-server command, source hashes, all 16 chapter requests, elapsed times and per-part transcripts |
| `new-engines/output/accent-controls-nov27/` | Classifier revision, input hashes, observation times and labels for the controls and full chapters |
| `new-engines/output/ogg-430k-nov27/v3-output/out/` | OGG 430k FP32 run, request texts and timings, unprompted ASR, reference hash and complete recordings |
| `new-engines/output/accent-gpu-2026-11-27/` | Listening page, enrollment records, served preview hashes and API playback audit |
