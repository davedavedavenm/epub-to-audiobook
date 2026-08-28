# August 2026 new-engine auditions

This is an isolated, CPU-only short-sample gate for the three viable engines
identified in `TTS-WATCH-FINDINGS.md`. It does not register an application
engine, start a persistent service, use a GPU, or call a paid/cloud API.

Every service is capped at four CPU cores and is run only while the product
queue is idle. All outputs use the same prepared `webapp.voice_sample.SAMPLE_TEXT`:
the repository's explicit number/currency expansion plus only safe acronym
letter-spacing rules. Audio8 additionally renders the byte-identical raw arm
because it does not document a text normalizer. Scylla retains its documented
normalizer after repository preparation. ZONOS2 uses the prepared text because
the native CLI's optional NeMo/Pynini normalizer is not part of this image.

Official sources checked on 2026-08-22:

| Engine | Exact source and weights | Licence / boundary | Arms |
|---|---|---|---|
| Audio8 TTS Preview 0.6B ONNX | [runtime `421f715`](https://github.com/Audio8-AI/Audio8_TTS/tree/421f71559848572431bd6229af3e1a73f25986a7), [ONNX INT4 `818569c`](https://huggingface.co/Audio8/Audio8-TTS-Preview-0.6B-ONNX-INT4/tree/818569c6b832118ad68d61bbd873abe250fcd68a) | Apache-2.0; authentic, user-authorized Arthur reference with exact transcript; upstream recommends short input, so the harness uses sentence/clause chunks no longer than 150 characters | raw, prepared |
| Scylla's Band v2 | [runtime `ab5d38a`](https://github.com/lowkeytea/scyllasband/tree/ab5d38ad46eec64a8e02a56c38a6e4f3c0cfdeb8), [weights `1cc6936`](https://huggingface.co/spybyscript/scyllasbandv2/tree/1cc69363815254f6a19bd42534a66ee49fc0fae0) | Apache-2.0; managed synthetic voices, not cloning; `ink` is an upstream `en_gb` label that still requires listening | ONNX INT8, ONNX FP32 |
| ZONOS2 | [native runtime v0.5.1 / `39a4d01`](https://github.com/Zyphra/zonos2.cpp/tree/39a4d01558db86dca1219273992c77ebc8e03991), [GGUF `75c877e`](https://huggingface.co/Zyphra/ZONOS2-GGUF/tree/75c877ec8ac86dda42bfc0e9968c87f29e10ef57) | MIT runtime, Apache-2.0 weights; authentic, user-authorized Arthur reference; `en_gb` is only a normalization locale and is not used as accent evidence | Q4_K, Q8_0 |

Run one engine at a time:

```bash
docker compose -f evaluations/new-engines/compose.yaml run --rm audio8
docker compose -f evaluations/new-engines/compose.yaml run --rm scylla
docker compose -f evaluations/new-engines/compose.yaml run --rm zonos2
docker compose -f evaluations/new-engines/compose.yaml run --rm loudkit
docker compose -f evaluations/new-engines/compose.yaml run --rm sopro
```

`render_loudkit.py` accepts `LOUDKIT_ARMS=joe,kathleen,kathleen_cap512` and
`LOUDKIT_BACKEND=onnx|torch`; `render_sopro.py` accepts
`SOPRO_ARMS=default,steps16`.

For a pinned official prebuilt, `render_zonos2.py` also accepts `ZONOS2_CLI`,
`ZONOS2_MODELS_DIR`, `AUDITION_PREPARED_TEXT`, and `ZONOS2_ARMS=q4_k` or
`q8_0`. Model files must still be fetched from the recorded exact revision;
the evidence report retains that revision and the v0.5.1 source commit.

Each successful arm writes WAV, 128 kbps MP3, and JSON evidence to `output/`.
The JSON includes source/runtime/model pins, input and output hashes, duration,
wall time, RTF, peak RSS when measurable, settings, and reference provenance.
The harness fully decodes both WAV and MP3 before reporting success. These are
listening candidates only: ASR can later detect gross truncation or repetition,
but Dave's listening verdict decides voice quality and whether any engine earns
a longer gate.

After rendering, `verify_outputs.py` loads one local `base.en` faster-whisper
model and checks every MP3 against its exact raw/prepared source. Its WER and
diff are gross-completeness diagnostics only and must never rank the voices.

## Measured short gate — 2026-08-22, structurally checked and heard

Audio8 and Scylla ran natively on a Ryzen 9 8945HS Windows host with four
inference threads. ZONOS2 ran under CPU-only WSL on the same host with
`taskset -c 0-3`; WSL exposed 14 GiB RAM. Every listed WAV and MP3 decoded in
full. Local faster-whisper `base.en` produced the structural WER figures below.

| Arm | Audio | Wall | RTF | Peak RSS | ASR boundary |
|---|---:|---:|---:|---:|---|
| Audio8 Arthur raw | 83.084 s | 189.936 s | 2.286 | not available on native Windows | WER 0.0789; transcript omitted the end of the eighteen-hour-days sentence |
| Audio8 Arthur prepared | 86.535 s | 200.946 s | 2.322 | observed working set about 2.29 GiB | WER 0.115; complete content, mostly number-format and acronym diffs |
| Scylla v2 Ink INT8 | 62.387 s | 23.621 s | 0.379 | not available on native Windows | WER 0.145; complete content; proper-name/acronym uncertainty |
| Scylla v2 Ink FP32 | 62.515 s | 39.141 s | 0.626 | not available on native Windows | WER 0.165; complete content; proper-name/acronym uncertainty |
| ZONOS2 Arthur Q4 full | 56.517 s | 409.478 s | 7.245 | 12,284.9 MiB | **Failed:** WER 0.225 and dropped the final 35-word WTO/EU/supply-chain tail |
| ZONOS2 Arthur Q4 first paragraph | 19.888 s | 130.497 s | 6.562 | 7,540.7 MiB | WER 0.100; complete paragraph; number-format/acronym diffs only |

Q8 was not attempted: Q4's measured 12.3 GiB full-arm peak left insufficient
headroom inside the 14 GiB WSL cap. Zorin was also in an active recovery job
with degraded UI latency, so the product host was correctly excluded. This is
a capacity/safety stop, not a Q8 quality verdict.

Dave then heard all six exact MP3s:

- **Audio8:** Arthur's voice was good, but both arms audibly dropped/faded. The
  prepared arm also changed tone and speed between chunks. It is twelve
  independent calls using seeds 42–53 plus 200 ms joins, and its 150-character
  splitter cuts three sentences at “percent / and,” “over / two hundred,” and
  “Dr. / Wang.” Every call's final 100 ms measured only 0.5–12% of the RMS of
  the preceding 500 ms. This directly explains the heard fade-and-restart at
  forced boundaries and the stochastic discontinuity; it does not by itself
  reject a future complete-sentence, fixed-setting Audio8 path. The raw arm's
  audible drop agrees with the ASR omission.
- **Scylla:** both INT8 and FP32 Ink arms were robotic and emotionless and felt
  like one long sentence, although pronunciation was acceptable. The matching
  full-precision control makes quantisation an implausible cause. Both arms fail
  the short quality gate; no longer render is justified.
- **ZONOS2:** the complete short Q4 paragraph was “really good.” The full Q4
  arm audibly dropped its ending and lost the Arthur identity, agreeing with the
  independently detected 35-word omission. It passes only the bounded voice
  audition, not sustained narration. A persistent model/reference load with
  fixed settings and complete sentence/paragraph calls is the next diagnostic;
  its output must be heard before any ten-minute gate.

These are listening outcomes plus measured harness facts. They do not establish
an untested model-side cause for Audio8's raw truncation or ZONOS2's voice drift.

## Corrective continuity gate — 2026-08-22, awaiting listening

The next authorised stage kept Scylla closed and produced one corrective
candidate for each bounded engine:

| Arm | Audio | Wall / generation | Structural result |
|---|---:|---:|---|
| Audio8 Arthur prepared, complete sentences + fixed seed | 82.709 s | 197.658 s; RTF 2.390 | Full decode; ASR WER 0.120 with complete passage coverage |
| ZONOS2 Arthur Q4, first persistent sentence arm | 66.595 s | 832.125 s; RTF 12.495 | **Failed:** the 139-character iPhone sentence omitted its App Store clause |
| ZONOS2 focused iPhone/App Store split | 6.803 s | 120.938 s; RTF 17.777 | Both halves fully decode; focused ASR covers all word content |
| ZONOS2 repaired full audition | 69.718 s | assembled from retained decoded components | Full decode; ASR WER 0.110 with complete passage coverage |

Audio8 uses the exact prepared text as nine complete-sentence calls, seed 42
for every call and no inserted join silence. Sentence lengths are
77/173/85/61/122/235/139/53/187 characters, so three exceed upstream's
recommended 150-character quality range. This arm isolates the heard forced
mid-sentence boundaries without pretending it satisfies that recommendation.

ZONOS2 ran through one CPU server with batch one, fixed documented sampling,
one session-cached Arthur embedding and no inserted join silence. Its first
bounded result proves that sentence chunking alone does not guarantee content:
the model emitted early EOS for the iPhone/App Store sentence. The retained
failed component is `zonos2_continuity_chunk_07.wav`. The repaired candidate
replaces only that component with two same-setting calls split at “revenue. And
the App Store”; punctuation changed, word content did not. ASR establishes
gross completeness only. Neither corrective arm advances until Dave hears the
exact MP3 and accepts its pacing, joins, tone and voice identity.

Dave then heard both exact files. Audio8 was **“better”**, confirming that its
corrective segmentation and fixed settings materially improved the first arm;
that wording is retained as a bounded result, not promoted to a long-form pass.
ZONOS2 still sounded like different voices, with Arthur fading in and out,
although its underlying/base voice was OK. Because that arm kept one server,
one cached Arthur embedding and fixed settings, the current cloned-narrator
continuity path fails even after the harness-side corrections. Audio8 is the
only candidate eligible for a separately authorised longer gate; Scylla and
the current ZONOS2 Arthur path stop here.

## Second gate — LoudKit and Sopro, 2026-08-28, structurally checked, awaiting listening

The two candidates carried forward from the 21–27 August watch log. Both are
Apache-2.0 on code *and* weights, verified at the exact revisions below, so
neither carries the licence boundary that holds Breeze TTS 2 out of production.

| Engine | Exact source and weights | Licence / boundary | Arms |
|---|---|---|---|
| LoudKit 0.1.0 / loudr-1 | [runtime `58fd4a5` (tag v0.1.0)](https://github.com/loudreader/loudkit/tree/58fd4a58de8980b42c1021492728876d67ea2718), [weights `0fe297e`](https://huggingface.co/loudreader/loudr-1/tree/0fe297e449ba4f31113977f6c7f8c438fdfd1be3) | Apache-2.0 code and weights; derived from MIT Chatterbox. No shipped English voice is British — the roster lists `joe` and `kathleen` as the only English profiles, both CC0 OHF-Voice donations — so only the cloned Arthur path is project-relevant | ONNX Runtime CPU, PyTorch CPU |
| Sopro v2 turbo (120M) | [runtime `cb2b2a1`](https://github.com/samuel-vitorino/sopro/tree/cb2b2a1949cd70cca469d689416906a6d181fa22), [weights `0abc556`](https://huggingface.co/samuel-vitorino/sopro-v2-turbo/tree/0abc5561e8ffd7b582b8aea2eb9e5f3bf7637c26) | Apache-2.0 code and weights; single-maintainer project, bus factor one | offline fp32, offline int8 |

Both engines window long text themselves, so the harness passes the whole
prepared passage in **one call** and adds no join silence: LoudKit's own
`manifest.json` declares `max_tokens` 255 with `prefix_tokens` 6 carry-over,
and Sopro splits on `--max-seconds`. Their join handling is the thing under
test; pre-chunking would have measured our splitter instead, which is what
produced Audio8's forced-boundary artefacts. Each engine keeps a same-text
control on a second numeric path, in the role Scylla's FP32 control played.

Sopro's streaming path is excluded: upstream states it is not bit-exact with
the offline path and recommends offline for quality.

The prepared input hash is `8ccd447f2890e5f7…`, byte-identical to the text
Audio8, Scylla and ZONOS2 rendered on 22 August, so these arms are directly
comparable to the files Dave has already heard.

Ryzen 9 8945HS, four inference threads, CPU only, no GPU present on the host.
Peak working set is sampled externally because native Windows has no
`resource.getrusage`; the earlier gate recorded these as "not available".

| Arm | Audio | Wall | RTF | Peak working set | ASR boundary |
|---|---:|---:|---:|---:|---|
| Sopro v2 Arthur fp32 | 82.683 s | 78.132 s | **0.945** | not sampled | WER 0.115; complete content, number/acronym formatting diffs only |
| Sopro v2 Arthur int8 | 82.621 s | 79.567 s | **0.963** | 954 MiB | WER 0.110; complete content, number/acronym formatting diffs only |
| LoudKit Arthur ONNX | 81.960 s | 96.466 s | **1.177** | 2,946 MiB | **WER 0.170; dropped "Rivals — Huawei, Xiaomi, Samsung — circle constantly"** |
| LoudKit Arthur PyTorch | 80.440 s | 608.415 s | **7.564** | 1,485 MiB | **WER 0.170; dropped the same sentence bar the word "Rivals"** |

### What the measurements establish

**Sopro runs faster than real time on x86 CPU and int8 buys nothing.** 0.945
against 0.963 means the quantised arm is marginally *slower* here; if the two
are indistinguishable by ear there is no reason to run int8. Under a gigabyte
of working set is also small enough to sit beside the product on Zorin.

**LoudKit loses a sentence.** Both arms drop the same em-dash-heavy sentence.

> **Retracted 2026-08-28.** This section originally concluded that a shared
> omission across two backends "points at the model or its windowing, not at a
> backend bug." That was wrong, and it was asserted without testing the setting
> responsible. `SamplingConfig.max_new_tokens` and
> `WindowConfig.max_speech_tokens` both default to **255** — the exact cap these
> runs reported hitting — and `lk.load(algorithm=...)` accepts an override that
> was never tried. The raised-cap diagnostic below settles it: the cause is the
> default cap, not the model.

Upstream's own per-chunk detectors agree that something happened there: the
render is 13 chunks, `hit_token_cap` is true in both arms with chunks running
to the full 255-token cap, and three to four chunks report `ended_tail`
(a trimmed hallucinated tail). `suspect` is false in both arms, so no chunk was
judged impossibly long for its text.

**Both engines carried the ending ZONOS2 lost.** The WTO/EU/supply-chain tail
survives in all four arms.

### Harness note — the passage API

`Engine.synthesize()` renders exactly one window and is documented as such. The
first attempt at this gate called it and got 10.2 s of audio for the
1,142-character corpus, with upstream's `hit_token_cap` set and a chunk count of
one. `Engine.synthesize_long()` is the passage API. `render_loudkit.py` now
refuses to write an arm with fewer than two chunks or under 60 seconds, and
`tests/test_new_engine_auditions.py` pins that. `hit_token_cap` is recorded in
the evidence, never used to reject an arm: upstream defines it as worth
surfacing, and the quality verdict is Dave's.

### Awaiting listening

All four exact MP3s were sent to Dave on 28 August. Nothing here is a quality
verdict, a project recommendation or an engine registration. Voice, accent,
pacing, joins and whether LoudKit's missing sentence is audible are decided by
ear. No app engine was registered, no voice added, no deployment state changed.


## Native-voice gate — 2026-08-28

Dave's instruction after hearing the first four arms: evaluate each engine on
its **own native supported voices**, not on a cloned reference. British is
preferred where it exists, but the accent judgement is his, made by ear.

Two corrections to how the previous gate was run, both recorded because they
changed what he was given to listen to:

1. **The cloned Arthur path was never requested.** It was chosen by the harness,
   then written into the README and into a passing test, which made an
   unrequested assumption look like a settled decision. Reference choice is
   Dave's; `tests/test_new_engine_auditions.py` now pins that the harness cannot
   pick one.
2. **Sopro was run at `temperature=0.7`,** a value copied from the Audio8 harness
   and documented nowhere by Sopro, whose own default is 0.8. Those files were
   not default renders. Sampling now resolves to upstream's `GenerationConfig`
   and `DEFAULT_ALGORITHM`; nothing is passed that upstream does not default.

**Sopro ships no native voices at all.** `--ref` is a required argument and the
model repository contains no voice profiles, so it cannot be auditioned the way
this gate asks. It is cloning-only by construction. Dave chose **Beatrice**
(`uk_female_samuel`, the repository's shipped default narrator) as its reference
on 2026-08-28.

**LoudKit ships 20 managed voices**, of which `joe` and `kathleen` are the only
English profiles (both CC0 OHF-Voice donations). Both are rendered here. The
previous gate skipped every shipped voice on the harness's own accent judgement;
that filtering is removed.

Ryzen 9 8945HS, four threads, CPU only, no GPU on the host. No Kaggle, no
rented GPU, no paid API was used at any point in this gate.

| Arm | Voice | Audio | Wall | RTF | Peak working set |
|---|---|---:|---:|---:|---:|
| `loudkit_joe_onnx` | native `joe` | 71.76 s | 90.49 s | 1.261 | 3,207 MiB |
| `loudkit_kathleen_onnx` | native `kathleen` | 73.68 s | 93.04 s | 1.263 | 3,310 MiB |
| `sopro_v2_beatrice_default` | Beatrice ref | 71.14 s | 52.48 s | **0.738** | 1,031 MiB |
| `sopro_v2_beatrice_steps16` | Beatrice ref | 71.14 s | 115.36 s | 1.622 | 1,068 MiB |

The two Sopro arms have identical duration to the millisecond because `steps`
drives only the acoustic solver: same token stream, same reading, same pacing,
finer decode. It is a clean A/B for whether the solver default is leaving
quality on the table.

At upstream's real default temperature Sopro measures RTF 0.738, against the
0.945 reported from the invented-temperature run.

### The 255-token cap — the dropped sentence explained

The first gate reported that both LoudKit backends dropped
"Rivals — Huawei, Xiaomi, Samsung — circle constantly," and concluded that
pointed at the model. **That conclusion was wrong.**

`SamplingConfig.max_new_tokens` and `WindowConfig.max_speech_tokens` both
default to 255. Raising both to 512 on the PyTorch path:

| Run | Token cap | `hit_token_cap` | Chunk verdicts | Audio |
|---|---:|---|---|---:|
| `loudkit_kathleen_onnx` | 255 (default) | **True** | 3–4 chunks `ended_tail` | 73.68 s |
| `loudkit_kathleen_cap512_torch` | 512 | **False** | **all 13 `clean`** | 75.28 s |

Every trimmed tail disappears and the cap stops firing. The omission was a
consequence of the default window, not a model defect.

**But the fix is not available on the fast path.** Raising the cap on ONNX is
refused outright:

> the exported ONNX graphs are static at query 255 / prompt 238; this
> AlgorithmConfig frames None/None. A different window is a different algorithm
> — re-export the graphs rather than silently reframing here.

The cap is baked into the shipped ONNX export. PyTorch accepts the wider window
but measures RTF 6.96, which is not a book path. So LoudKit at 255 tokens trims
tails, and escaping that requires re-exporting the ONNX graphs — upstream's own
documented remedy — not a config change.

### Method note

No ASR was run on this gate. Dave has stated repeatedly that transcript scoring
is not useful to him and that the ear decides voice quality. Files are still
fully decoded and length-checked, and the engine's **own** instrumentation
(`hit_token_cap`, per-chunk `inspections`, chunk counts) is recorded — that is
the engine reporting on itself, not an external transcript check.

### Awaiting listening

The four exact MP3s were sent to Dave on 28 August. No engine registered, no
voice added, no deployment state changed. Nothing here is a quality verdict.
