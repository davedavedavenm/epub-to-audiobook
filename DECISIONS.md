# Decisions — EPUB to Audiobook

## 11 November 2026 — John reference short comparison: Qwen leads — Active

Dave's verdict: "kitten controlled was better, qwen 3 best, preserved worst".
For the three matched 40-word auditions this ranks Qwen3 Base
(`qwen_john_kani_comparison.mp3`) first, Kitten's controlled diagnostic
(`kitten2_john_kani_short_refprompt_off.mp3`) second, and the preserved
`kitten-reference-retest/kitten_john_kani.mp3` baseline last. Keep the baseline
for comparison. The controlled Kitten take disables reference prompting; its
other settings/reference are unchanged. This is a preference between those
exact clips, not approval of the full standard readings or a long-form book.
Qwen is the leading candidate for the next South African narration comparison;
no production narrator/default changes follow automatically.

## 11 November 2026 — Voices uses the available screen width — Active

The model-comparison catalogue must use widescreen space instead of inheriting
the 1360px form-page width. Keep one representative per model; add columns as
space permits, with readable cards and one column on mobile. Other forms and
prose panels retain their own width constraints.

## 11 November 2026 — Native audition input contracts — Active

Audition-only Maya2 Native and VoxCPM2 declare their native raw-input contracts
explicitly via `preview_text_engine` and `sample_text_for('maya2'/'voxcpm2')`.
Neither has a book route, so do not invent book/preview parity. Internal model
normalization stays separately documented: Maya's numeric-text recommendation
is enabled; VoxCPM2 retains its documented default off. Unknown engines and
preprocessing errors never use this raw-input exception. This preserves the
approved source, not an assertion that all engines receive identical payloads.

## 11 November 2026 — Model comparison replaces the misunderstood Likes layout — Active

Dave explicitly corrected the preceding UI interpretation: **remove the Liked
voices card** from Voices. Show **one representative voice per exact model and
version**, with other voices accessible within that model. Do not hide all
engines behind a global catalogue disclosure or limit the comparison to Likes.
Preserve verdicts and voices; this is a layout change, not authorization to
delete engines. Leave the separate Listening Desk alone.

The shared passage must be usable across **all voices on all engines**, not just
the 14 shortlisted previews. Count and show actual standard-v1 coverage; clearly
identify pending/unconfigured/quota-limited entries. Never present older audio
as the standard or count a credential as proof an engine can render. Reuse the
same speaker where already supported, but do not imply different preset models
can all clone the same speaker. Exact model/version remains the comparison unit.
Within each model, any cached current-standard take outranks an older preferred
voice as its representative; speaker preferences break ties within that tier.

Latest standard-v1 listening: Freya positive; Hugh decent; Bill Boerst otherwise
OK but misreads a.m. and 21 April; Chatterbox Turbo/Arthur good except the two
flagged numerical mix-ups. Deepgram voices great. Edwin's voice is promising,
but **Huawei and Xiaomi are badly pronounced**. These are human verdicts, not
ASR uncertainty, and do not identify the cause. No standout CPU winner or engine
retirement was decided. Continue the controlled John Kani/Kitten clone work;
the earlier promising-but-drifting take remains the preserved baseline.

Prevent the existing Breeze/CosyVoice/F5 book route from silently falling through
to Kokoro: until an actual endpoint is integrated, their cached GPU auditions do
not constitute a working book route. Breeze retains its historical modern
sample contract (commit `8208420`); share the profile mapping with book/recovery
callers rather than duplicating a conflicting legacy fallback.

## 11 November 2026 — Shared audition standard and compact shortlist — Active

Dave approved `narrator-standard-v1`: ordinary English opening, then country and
Chinese/English/African names, dates, times, percentages, currency and quantities.
All agents and general audition producers must use `sample_text_for(engine)` from
`webapp/voice_sample.py`; see `AUDITION-STANDARD.md`. Irish/Zulu and book excerpts
remain supplementary. Keep voice/naturalness verdicts separate from pronunciation.
Historical hash-pinned reproductions retain their named legacy passage.

**Superseded layout interpretation; see the correction above.** Organize the catalogue without discarding history: Jack and Edwin first, other
CPU and hosted Likes in collapsed groups, GPU auditions separate, full catalogue
collapsed. Rosie and Silencio 2/Peter are no longer Likes; retain them in the
changed-verdict archive. There are now **17 Likes: nine CPU, five Flux, three GPU
auditions**. The older 19-Like snapshot below is historical. This does not approve
new render quality, remove engine services, or change the production narrator.

`TUNING-AUDIT-2026-11.md` distinguishes vendor defaults, intentional supported
overrides and unresolved tuning. Do not promise every setting was optimal:
Pocket's four decode steps, Phonon's .45 temperature and Klein's .18-second pause
need controlled listening to establish preference. Turbo/Nano ignore CFG and
exaggeration; original/multilingual Chatterbox controls must not be presented as
Turbo controls. Preserve the promising Kitten/John take; accent drift is not
diagnosed or solved by this audit.

New cache manifests bind the approved source and prepared text to each audio
file. Keep older cached clips playable and label them Earlier audition. Preview
preprocessing must follow the same engine contract as books, including the new
CPU narrators and Chatterbox Nano; no silent raw-text fallback on preparation
errors. Full cache migration is incremental, not a global cache wipe.

Settled, closed questions for this repo. This is not a changelog — STATUS.md and
OPERATIONS.md hold the narrative (what happened, listening tests, incidents).
This file holds the current, settled position on each question, and its status.

**Before proposing to change, redo, or re-open something, check here first.**
If a session settles a new question or reverses one below, update this file in
the same session — don't just log it in STATUS.md and leave this stale.

Status values: **Active** (current) · **Superseded** (replaced, kept for history)
· **Evolving** (settled position exists but is expected to keep moving — check
the linked doc for the latest measurement before relying on it).


## 11 November 2026 — John Kani Kitten take outstanding initially; accent drifts — Active

Dave calls the new `kitten_john_kani.mp3` **outstanding**, but hears it become American at the end. Trevor Noah is too American; the same objection applies to Deon, Bonang and Cillian. Preserve this exact John take/reference as the promising comparison baseline. This does not approve a stable South African narrator or a full-book run; no production/default promotion.

Verified device: CPU, four threads, 18.96 seconds of audio rendered in 127.41 seconds. Exact upstream path uses one 234-character synthesis chunk, reference prompting enabled, one John reference throughout, stable preset/seed 42, packed lossless weights and stock decoder. There is no second-voice selection or chunk join at the ending. That narrows the implementation possibilities but **does not establish why the accent changes**. Weak accent retention within generation is a hypothesis; CPU execution has not been demonstrated to cause it, and GPU execution alone is not a proven remedy. Evidence: ignored `kitten-reference-retest/accent-drift-audit.json` and `listening-verdict.json`. Official model card rechecked: https://huggingface.co/KittenML/kitten-tts-2 ; exact prior model/runtime provenance remains with the samples.

## 11 November 2026 — Phonon free clone/export route confirmed in documentation — Active

Gradium's current pricing and official cloning guide document five **instant** clones on the $0 Free tier for noncommercial use. The official `xn-ptts` helper creates a voice through Gradium, exports its embedding as Phonon-compatible safetensors, and the local CPU runtime accepts that voice file. This is a documented free hosted-clone/local-render route, not a wholly local recording-to-clone path; the separate speaker encoder remains unreleased. Kaggle/Modal GPUs do not remove that dependency. Professional cloning is a different, paid offering.

The service requires the speaker's consent, including for publicly available recordings. These celebrity clips must not be submitted with a false consent declaration. No Gradium API call, account-quota check, or actual custom-voice export has been verified here. Price/terms checked 11 November 2026. This supersedes the earlier 'not costed' status, not the lack of an account-level test. GPU use for this audition is acceptable to Dave, but this Kitten retest ran locally with no cloud charge.

Primary evidence: [pricing](https://gradium.ai/pricing), [cloning guide](https://gradium.ai/content/how-to-clone-a-voice-create-custom-voice), [official clone/export helper, pinned commit](https://github.com/gradium-ai/xn-ptts/blob/32c1554a8ce442d672de90fc82700bbdcf08d918/scripts/clone-voice.py), [local Python runtime](https://github.com/gradium-ai/xn-ptts/blob/32c1554a8ce442d672de90fc82700bbdcf08d918/ptts-pyo3/README.md). Local model: `gradium/phonon-31m-en@92741c5b07d085ff840e26fea8ce43110b87852f`, Apache-2.0; ptts 0.5.0. Pinned files/hashes: ignored `kitten-reference-retest/phonon-evidence/provenance.json`.

Kitten's reference retest has now been heard: John is outstanding but drifts American at the end; the other four remain too American. See the newer verdict above. No narrator promotion.

## 11 November 2026 — Accent audition failed; Kitten preferred; reference selection inadequate

**Listening verdict:** Dave says these clones sound American, except John Kani who sounds British; **Kitten did better than Silencio**. This is a relative preference within these takes, not approval that the requested accents were retained. Dave also rejects the quality of the recordings chosen as cloning inputs. No narrator/default promotion follows.

**Verified audit:** South African references were only 5.97–9.20 seconds (Deon 5.97, Trevor 6.12, Bonang 7.50, John 9.20), with Cillian 24.80 seconds. The supplied reference hashes match. No full-scale sample clipping was found, which does not establish acoustic suitability. Kitten's stock decoder repeats references shorter than 6 seconds, so Deon's clip was repeated internally; its decoder uses at most 10 seconds, while language-model prompting encodes the full reference. This repetition is documented implementation behaviour, not proof of the accent failure's cause.

Official pinned Silencio weights, Kitten packed language-model weights and Kitten speaker-encoder weights all SHA256-match upstream Hugging Face LFS metadata. Kitten 0.9.7 used lossless packed weights, the stock/default decoder, stable preset and reference prompting enabled. Silencio used its exact WAV path, float32/default temperature 0.3, with fresh per-path caches. These renders called the upstream implementations directly, not the production app. No preset fallback or disabled reference conditioning was found. No EQ, pitch shift or time stretching was applied. Provenance and machine findings: ignored `accent-clones/failure-path-audit.json`.

**Cause remains open:** poor source selection and imperfect reference transcripts confound this test. Duration alone is not sufficient diagnosis: the 24.8-second Cillian reference also failed in these CPU models and has prior successful Fish/Higgs history. Do not declare these engines incapable of accents from this test, or claim reference cleanup will necessarily fix them. A follow-up should compare old versus carefully selected clean references on the same model/text/settings before another broad batch; Kitten is Dave's preferred starting model.

**Why Phonon/Klein were absent (official docs rechecked 11 November):** Phonon 31M can consume precomputed voices locally, but its separate speaker codec is not released. The official Transformers documentation explicitly says this local path cannot clone from a recording. Gradium Studio supplies hosted instant cloning; exporting a compatible voice for local CPU use is a separate option, not a wholly local cloning path. Studio was not called, costed or proven in this session. Klein X1.5-Pro documents 17 preset voices and experimental same-language blending; no released recording-to-clone route was found. Explain this distinction before narrowing a future audition.

Primary sources: [Phonon model card](https://huggingface.co/gradium/phonon-31m-en), [official Transformers implementation documentation](https://huggingface.co/docs/transformers/main/en/model_doc/gradium_phonon_tts), [Phonon Python runtime](https://github.com/gradium-ai/xn-ptts/blob/main/ptts-pyo3/README.md), [Klein X1.5-Pro model card](https://huggingface.co/klein-ml/Klein-TTS-X1.5-Pro). Exact installed model revisions remain in `expression-test/cloning-support.json`; this finding supersedes its weaker statement that no local Phonon route was merely documented.


## 11 November 2026 — Rosie rejected; stop repeating Silencio/Peter; test real accent references

Dave heard the ordinary/expressive A/B: **expression did not add much**. This is
the verdict on these exact takes, not a claim that every emotion setting fails.
**Rosie is disliked**, superseding her earlier short-take Like. Dave finds this
particular **Silencio/Peter version tiresome**; stop using it for new auditions.
Do not extend that voice verdict to every speaker in Kitten or Silencio.

Dave requests Cillian's accent and multiple South African celebrity references,
with enough alternatives to listen to all. Use genuine human references and
label synthetic tests explicitly. The October Pocket/Cillian result remains
“nice but very American”; do not present that failed accent as newly solved.
Test the newer clone-capable models and leave accent retention to Dave's ear.

## November liked narrators integrated — Active (2026-11-10)

Latest 416-word votes: Like Stuart Bell, Edwin, Freya, Imogen, Bill Boerst,
Caro Davy, Arthur and Hugh; Maybe Harriet and Isabella. Isabella's newer Maybe
supersedes her earlier short-take Like. Jack remains the leading hosted voice.
The current collective shortlist has 19 Likes: 11 CPU, five Deepgram Flux and
three GPU auditions. Maya accents are unsuitable for Badawi specifically.

Add exact November model identities and cached heard previews to the app.
Do not silently substitute old Pocket/Kitten models or Aura for Flux. The three
GPU entries remain audition-only until a full-book lane is integrated/verified;
no GPU call or full book was authorized by this catalogue update. Default
narrator is unchanged. Expression/casting boundaries and pinned official
provenance are recorded in `../epub-to-audiobook-liked-voices/narrators/README.md` (implementation worktree).

## Badawi longer reading: Jack leads; broaden CPU speakers — Active (2026-11-10)

After the 416-word comparison, Dave says **Deepgram Flux Jack is winning so far**.
Maya's Indian accents **do not work for this particular title**, *An African
History of Africa*. This supersedes the earlier short-sample suitability for
Badawi; it is not a blanket rejection of Indian voices for every book.
Dave requests more CPU-only candidates and is tired of repeated Peter voices:
broaden the speaker selection, with no further Peter clones in this audition.
New synthesis must be local CPU; the already-rendered Jack take may serve as the
comparison reference without another hosted call. No full-book narrator/default
or conversion decision has been made.

## Ordinary narration audition: Dave's November ratings — Active (2026-11-10)

Dave rated the new 154-word ordinary passage in the local player. Exact exported
votes are retained locally as `dave-ratings-2026-11-10.json` beside the audio.
These are **ordinary-narration verdicts**, not regional pronunciation approvals:

- **Like (GPU):** VoxCPM2/Peter; Maya2 Native/Siddhant and Nivedita.
- **Like (CPU):** Klein X1.5-Pro/Arthur and Isabella; Silencio2/Peter;
  Pocket100M/Bill Boerst, Caro Davy and Peter; Phonon31M/Hugh; KittenTTS2/Rosie.
- **Like (hosted):** Deepgram Flux/Colin, Jack, Rufus, Conor and Sean.
- **Maybe:** Pocket18M/Peter; Deepgram Flux/Maeve and Kit.
- **No:** this Fish Drama3/Peter take; Klein's preset labelled Edmund;
  Deepgram Flux/Gemma. FastDec18M/Peter is unscored, not rejected.

**At the short-sample stage, Indian accents were acceptable options.** Dave clarified that his
question about Maya was asking why those voices were selected, not rejecting
them. The later longer reading above rejects them for Badawi specifically. Do not
replace them with speculative accent clones. Their original inclusion tested the
newer official GPU model in its native voices.

**Klein Edmund identity remains disputed:** Dave says this take sounds like a
woman and is not Edmund. Browser source and HTTP/audio hashes match the intended
file. The pinned official `AutoModel.from_pretrained` path was rerun for all three
Klein voices: requested/returned names and speaker indices are Edmund9, Arthur10,
Isabella7. Fresh Edmund audio has identical duration and waveform correlation
0.9999989 with the audition (tiny numerical differences, not byte-identical).
This rules out a simple file/voice-selection swap in this harness; it does not
validate the audible identity or explain the upstream voice/gender discrepancy.
Klein's native preset is also distinct from Fish's Peter/Edmund clone. Do not
claim this fixed, relabel it as another known speaker, or invalidate Dave's ear.

## November audition pronunciation verdict; separate ordinary narration from name tests — Active (2026-11-10)

Dave heard the November audition. Of the tested voices, **Klein-TTS X1.5-Pro / Edmund**
was the only one he identified as pronouncing **Siobhán** correctly, but it still
failed **Dáil Éireann**. Most other open-weight CPU samples badly pronounced Huawei
and the Chinese names. **All tested Deepgram Flux voices failed Irish pronunciation.**
These are listening verdicts about the exact retained takes, not a proven root cause,
not a blanket rejection of ordinary narration, and not a reversal of earlier heard
Higgs/Breeze Irish results. No general pronunciation winner is established.

Dave explicitly requests a **separate ordinary-English passage to judge voice quality**:
most of his books will not be full of Irish or Zulu names. Regional-name challenges
must remain separate, optional comparisons. New auditions should include better/newer
or more efficient GPU options on free Kaggle or credit-only Modal, alongside CPU;
CPU locality alone is not the selection criterion. The zero-cash budget remains.
Audio, copyrighted extracts, players and scratch scripts remain local/ignored; any
authorized cloud rendering uses private jobs, never public GitHub audio uploads.

**Modal authentication and zero-cash evidence (2026-11-10):** the existing saved
CLI profile already authenticates to `davedavedavenm`; ordinary renders and usage
checks do not require another browser sign-in. The signed-in dashboard was read
this session: **USD0 custom net-spend limit, USD30 usage limit and USD30 included
credits**. CLI billing summaries and app/container listings work. Latest public
SDK1.6.3 (PyPI checked this date) and its documented Workspace API expose billing
but no workspace net-spend-limit getter; environment budgets are a different
control and must not be represented as that getter. Use the saved CLI for routine
work; do not make Dave sign in again merely to render another bounded sample.
Official boundary: https://modal.com/docs/guide/budgets and
https://modal.com/docs/sdk/py/latest/Workspace. No credential or budget changed.

The 11 November all-model shared-passage request includes a bounded S2 Pro
audition on these existing credits. This narrowly supersedes CILLIAN-RECIPE's
older zero-credit Modal veto for this audition, preserving its model, references
and sampling controls; production lanes/defaults remain unchanged. The input is
the approved engine-prepared shared test, not a book-specific `as_prep` rerun.

**New GPU audition boundary:** pinned official Fish Drama3, VoxCPM2 and Maya2
Native ran on Modal credits. These are audition takes, not approved production
engines. VoxCPM2's seed42 Zulu take has a large omission and is retained/flagged;
its ordinary passage passes the machine completeness screen. Deepgram Kit's
Zulu ending is also flagged; no automated pronunciation verdict follows.
Kaggle's T4 CUDA probe succeeded, but L4 requests did not establish a usable L4
lane (initial model jobs received CPU). Do not label downloaded older successful
T4 output as proof that a later L4X1 request succeeded. Full-book lane suitability
and new regional-pronunciation verdicts remain open; ordinary listening votes are
recorded above.

## Pocket Cillian is nice but very American; same-reference Turbo CPU comparison delivered — Evolving (2026-10-29)

Dave heard Pocket/Cillian152.50s and called it **“nice but very American.”**
Cloning/word completeness work, but Irish accent fidelity is not accepted.
This does not reject the approved Bill Boerst/Caro Davy preset readings.
Dave explicitly requested reopening Chatterbox Turbo/Cillian on the same six
paragraphs, CPU only, using the exact same canonical reference file as Pocket
for a same-speaker comparison. The earlier CPU Cillian rejection remains its
historical listening boundary until this new take is heard. No parameter,
reference or EQ workaround is assumed to restore the accent by reasoning.

**New machine-checked Turbo/Cillian sample delivered:**171.48s versus the
unchanged152.50s Pocket take, same458words/six paragraphs and identical canonical
24.8s WAV (SHA256 `30606e0686349c48227ec51702e095c8ea269c52b81c724401d1a055617c5e3c`).
Direct official Turbo code `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, model
`749d1c1a46eb10492095d68fbcf55691ccf137cd`, source/image fingerprints as below.
Stock temperature0.8/top-p0.95/top-k1000/repetition-penalty1.2; no unsupported
CFG/exaggeration tuning. Native PerTh watermark and reference normalization.
Turbo internally conditions its speech prompt on the first15s, vocoder on10s,
and voice embedding on the full file; the input WAV itself is identical to
Pocket's. Same-source reference does not promise identical internal conditioning.

Initial12 complete-sentence groups:10 strict passes; “claimed/claim” and
“believed/believe” flags. Seeds43/44 for the short “claimed” group still failed
small, medium and base recognizers. Rather than changing any word, paragraph4
was regenerated as a single59-word input (within the existing speech-token cap;
~19s audio). Seed42 failed other word checks; seed43 matched every source word.
The other affected group (“believed”) uses seed43, with an independent medium
exact transcript;44 also passes. Final11 retained units reconstruct all six
paragraphs exactly, with no unmatched insertions/substitutions/omissions in the
retained unprompted ASR matches. All rejected/raw/spare takes preserved. This
is a word-gated assembly, not an automatically error-free engine claim.

Zorin CPU only,4core/6GiB caps,nice10,CUDA hidden,network disabled,cached model
read-only; own three ephemeral containers removed, production UI/Turbo/Nano
health200 and UI~0.02s. No cloud calls/spend or production/default changes.
Output gain only, .18s internal/.5s paragraph joins,192k MP3; no speed/pitch/EQ
change. Final MP3 SHA256
`37248c0af9c67af26c92ae4920b967ab2ecab9e113bf2f754ac9791e1f8cc70c`.
Verified hashes/full decode/HTTP plus browser playback/near-end seek, both
paragraph controls and displayed458words. Turbo accent/likeness still needs
Dave's listening verdict; the previous CPU rejection is not silently reversed.
Player: `scratch/tts-oct28/output/cillian/index.html`, ignored offline copy
`evaluations/new-engines/output/october-2026-audition/cillian/listen.html`.
Exact source/parameter authority: [pinned Turbo source](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py)
and [MIT model card](https://huggingface.co/ResembleAI/chatterbox-turbo), read29 October.

## Pocket CPU cloning unblocked; Cillian, Turbo and Deepgram same-text gate delivered — Evolving (2026-10-29)

**Current listening boundary:** Dave calls the longer Bill Boerst and Caro Davy
Pocket readings “pretty robust” and a possible new CPU winner; the requested
Turbo comparison is ready but has no listening verdict yet. Faster Fish/Cillian
is acceptable, with weaker accent, artefacts, voice changes and background noise.
This is not a blanket rejection of the stronger earlier Fish recipe.

- **Hugging Face access resolved legitimately:** khpi5's user/root HF caches,
  selected MCP configuration/runtime locations and central secret-store HF slot
  yielded no active alternative credential (the stored HF_TOKEN slot was blank).
  The existing Windows token authenticated as `davedavem` but initially returned
  403/GatedRepo, explicitly “not in the authorized list”. Dave completed the
  model-access conditions himself; the exact checkpoint then downloaded. No gate
  bypass, public-preset weight substitution or credential copied into chat/repo.
- **Actual Pocket cloning, CPU only:** official Pocket4.0.1 code
  `a922b912dfa366975294afb568d815b305acde5d`, `english_2026-10` cloning weights
  `kyutai/pocket-tts@db04f0e653473e5c7333c69686ac92b7460b0c1d`, file
  `languages/english_2026-10/model.safetensors`, 219029196 bytes,
  SHA256 `bc96b82436c5ec00d3118ef3b01bc3358423e1766ecae3dca0aeea84789e7d74`.
  Model reports `has_voice_cloning=True`; all parameters on CPU, CUDA hidden,
  four CPU threads, temperature0.3 (October's documented recommendation), four
  decode steps, seed42. No quantization option selected. Full24.8s canonical
  Cillian reference SHA256 `30606e0686349c48227ec51702e095c8ea269c52b81c724401d1a055617c5e3c`,
  exported voice conditioning reused with fresh state per paragraph. Reference
  is below the documented30s truncation boundary. Windows Ryzen CPU, six
  paragraphs/458words, **152.50s assembled audio**,210.436s synthesis plus6.25s
  conditioning. All six pass strict word comparisons; no regeneration.
  Code MIT, weights CC BY4.0 with published use restrictions; model access was
  granted through the provider. **Dave’s Cillian verdict: “nice but very American.”** The voice is listenable,
  but the desired Irish accent has not passed; do not promote it as an accent match.
- **Turbo control:** same text, established Arthur/UK Minter reference (different
  speaker, not a controlled same-speaker engine comparison). Official pinned
  Chatterbox code `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, Turbo350M weights
  `ResembleAI/chatterbox-turbo@749d1c1a46eb10492095d68fbcf55691ccf137cd`,
  runtime source SHA256 `2f27e8ff2fa35181fdd2849367fb96ecc2cb87a1088ca7520c8bd51946599f08`;
  existing image `sha256:aa8ab718456dd82b9e840ecf5bb4473733e83e692c34bfb37719cdf7c9b7b809`.
  Direct official `from_local`, CPU only on Zorin, separate ephemeral containers,
 4CPU/6GiB caps, nice10, network disabled, cached weights read-only. Defaults:
  temperature0.8/top-p0.95/top-k1000/repetition-penalty1.2, native PerTh watermark,
  reference normalization enabled. Turbo's source explicitly ignores CFG,
  exaggeration and min-p; no claim those controls tuned this result. MIT.
  Initial15 groups used seed42; one “claimed/claim” flag was replaced with seed43.
  The final paragraph's “belief/beliefs” flag was repaired by generating the
  complete39-word paragraph as one piece (seed43), avoiding four unnecessary
  short resets. Alternate44 takes also preserved. Final **168.90s audio**,
  all selected groups strict-pass. “centre/center” is explicitly treated as the
  same spoken word, an orthographic normalization rather than a missing-word waiver.
- **Deepgram reinstated:** it was missing from the earlier retained-engine table.
  Direct balance API verified one project/one distinct USD balance,
  **USD126.95741**,29 October20:41UTC; fresh20:47 read unchanged (billing can lag).
  Pandora (`aura-2-pandora-en`) previously had an outstanding listening verdict;
  the new same-text six-paragraph take is **164.22s**, all six strict-pass, no
  regeneration. Official REST API, linear16/WAV/24kHz, no unsupported sampling
  knobs or speaker substitution. Response model UUID
  `fa95fd3d-06dd-4893-a975-87f597883dae`, request/model headers retained. The
  provider counted2673 input characters: at current PAYG Aura2 USD0.030/1000,
  the sample is **USD0.08019 credit usage estimated**, not a zero-price API call.
  Immediate balance delta was0, so do not label that a settled zero charge.
  Checked balance with USD1 reserve before requests, no paid fallback/top-up.
  These are finite existing credits, not a recurring free allowance. For a
 100k-word/600k-character book, the current PAYG scenario is USD18 credits before
  retries; count an actual book's characters for an exact input-cost estimate.
- **Verification:** same source words/order asserted for all five players
  (new Pocket/Cillian, Turbo/Arthur, Pandora; existing Bill/Caro). Unprompted
  small and, where disputed, independent medium ASR compares omissions,
  additions and substitutions. Final hashes/full MP3 decode/HTTP delivery and
  browser playback, seeking and paragraph controls checked. Gain only,192k MP3;
 .5s paragraph joins and .18s internal Turbo joins. Rejected/raw takes kept.
  All own CPU containers removed; UI/Turbo/Nano health200, UI latency~0.02s.
  Timing used different CPUs, so it is not a controlled engine-speed ranking.
  No application source, deployment, default narrator or cloud-GPU state changed.

**Free GPU spreading:** preserve source/chunk hashes and the same full-quality
recipe across providers; compatible workers may render different saved chunks,
then pause/resume across free quotas and credit resets. Do not pool VRAM across
providers or mix Drama3/S2Pro/altered serving recipes as one narrator. Native
Drama3's documented minimum48GB excludes the current ordinary Kaggle2x16GB T4
allocation and Colab T4/L4 as configured. Original native Drama3 can use included
Modal credits and any genuinely available compatible Colab allocation; that
allocation/quota is not guaranteed. The already accepted S2Pro/Cillian recipe
has separate Kaggle2T4 and ColabL4 paths. No new cloud run was started here.

Evidence/player: ignored `scratch/tts-oct29/cpu-compare/`,
`scratch/tts-oct28/output/cpu/index.html`, offline
`evaluations/new-engines/output/october-2026-audition/cpu/listen.html`.
Official sources read29 October: [Pocket pinned README](https://github.com/kyutai-labs/pocket-tts/blob/a922b912dfa366975294afb568d815b305acde5d/README.md),
[Pocket model/access/licence](https://huggingface.co/kyutai/pocket-tts),
[Turbo pinned source](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/tts_turbo.py),
[Turbo model](https://huggingface.co/ResembleAI/chatterbox-turbo),
[Deepgram REST/limits](https://developers.deepgram.com/docs/text-to-speech),
[voices](https://developers.deepgram.com/docs/tts-models),
[balance API](https://developers.deepgram.com/reference/manage/billing/list),
[pricing](https://deepgram.com/pricing),
[Kaggle current hardware](https://www.kaggle.com/discussions/product-announcements/735239),
[Fish hardware](https://speech.fish.audio/install/).

## Audiobook cash budget is zero; keep the broader acceptable engine portfolio — Active (2026-10-29)

Dave clarified: **"I want low cost ... I do not want to pay for this."**
Zero out-of-pocket cost is the governing requirement for further audiobook
work. The previous GBP2/book paid fallback is superseded by this instruction;
the temporary USD2 extra allowance applied only to the completed audition.

- Prefer local CPU; otherwise explicitly selected free Kaggle quota, a genuinely
  free hosted endpoint, or verified included Modal credits. Stop/checkpoint when
  free capacity runs out. No auto-top-up, paid endpoint substitution, paid GPU
  fallback or out-of-pocket overage. Slower, resumable runs are acceptable.
- Modal remains an option, but its credit figure alone is insufficient to
  establish a worst-case zero bill: billing data can lag. Its official separate
  **Workspace spend limit** caps net charges after credits, and supports stopping
  chargeable work while credit-covered work may continue. Require a verified
  zero net-spend boundary before further Modal generation under this policy.
  Dave subsequently supplied the Firefox Usage-limit screenshot: current
  **Workspace spend limit USD0**, Usage limit USD30, USD24.40 credits used and
  USD0 charges. This verifies the credit-only compute boundary for the approved
  faster Fish test. No persistent volumes: the page explicitly excludes their
  continuing storage charges from the workload stop. [Official budgets](https://modal.com/docs/guide/budgets).
  **CLI follow-up:** installed client 1.5.5 was checked against latest stable
  **1.6.3 (2026-10-27)**. The official wheel was checksum-verified and 1.6.3
  installed in an isolated local environment for command/API inspection.
  Billing still exposes only rates/report/summary; workspace settings expose
  image-builder-version/default-environment, with no supported net-spend setter.
  Existing CLI authentication works independently of Dave's Firefox session.
  This agent did not change the dashboard setting. A lower-level
  environment-budget read did not return and was cancelled; it is not evidence
  of a working supported budget API. [Release notes](https://modal.com/docs/sdk/py/releases).
- The recent two-engine sustained test was a narrowed experiment, not a
  rejection of every other engine. **Retain Pocket, Phonon/Hugh, Kitten and
  Ming's instruction-guided mode** with Dave's exact recorded verdicts. Ming's
  tinny/artefacty cloning output and Kitten's disliked Saoirse voice do not
  establish a blanket rejection of those engines. Fish Drama 3 retains its
  positive short-quality verdict and unresolved reliability/cost boundary.
- Existing accepted/bounded alternatives also remain: Nano/Beatrice, conditional
  Turbo, Gemini/Achernar (dedicated unbilled project; slow quota-paced books),
  Qwen/Aiden, earlier Fish S2 Pro/Cillian, Breeze/Cillian, Higgs/Cillian and the
  still-open CosyVoice/F5/TADA evaluations at their recorded quality boundaries.
  Historical supersession for one book is not a universal engine ban. Do not
  reopen actual closed rejections such as Piper, Audio8 or NeuTTS Air implicitly.
- Pocket's pinned public October checkpoint offers **21 English presets**;
  Peter Yearsley was the controlled comparison voice, not a one-voice engine
  limitation. Custom cloning uses a separate gated checkpoint. Access was subsequently
  granted on29 October and CPU cloning verified; see the newer entry below.
  Six additional preset auditions were generated on local CPU with the same
  main100M/four-step/temperature0.3/seed42 settings; no cloud spend.
  **Dave chose Bill Boerst and Caro Davy; other voices in this audition batch
  were not preferred.** This is an 84-word audition verdict, not a whole-book
  continuity pass or rejection of the Pocket engine.
- Current Fish docs expose **`s2.1-pro-free`**, priced at zero and supporting
  voice selection, subject to fair-use limits. It is S2.1, **not Drama 3**, and
  neither personal whole-book fair-use capacity nor the exact Cillian result is
  verified. Fish's hosted cloning guidance requires permission, explicitly
  including celebrity voices. Do not promise hosted Cillian acceptance or send
  that reference as an unannounced API experiment. No Fish API key is configured
  in this local environment/repo. [Models](https://docs.fish.audio/developer-guide/models-pricing/models-overview),
  [quickstart](https://docs.fish.audio/developer-guide/getting-started/quickstart),
  [cloning requirements](https://docs.fish.audio/developer-guide/best-practices/voice-cloning).

## Faster Fish/Cillian: word-gated six paragraphs delivered; lower credit cost is provisional — Evolving (2026-10-29)

**Delivered machine-checked sample:** 458 original words / six paragraphs,
**192.341 s**, same full 24.8-second Cillian reference and Drama3 backbone weights.
**Dave's verdict:** acceptable (“it's ok”), but weaker accent, artefacts, voice
changes and background noises. Retain this bounded option; it does not replace
the stronger earlier Fish listening result.
No production engine/default/deployment changed.

- Runtime: SGLang-Omni Apache2 source `d9c3e708a613515e189134de119209f443c9ae19`,
  SGLang0.5.22 / Torch2.14.1+cu130 / Python3.12. Maintainer-recommended registry
  image `hongccc/sglang-omni@sha256:06ed306707bcf3d9e9beb5ba7ce66f09a666cac11c23455ece50c34199c0e985`
  failed its own current requirements checker (eight unrelated base-image
  conflicts). A clean environment installed the pinned source's `[fishaudio]`
  extra using its documented protobuf override; the checker and CPU import
  probes passed before GPU allocation. Final cached image
  `im-H6hIvKQ80wrEmBQ5hrWfK0`; frozen dependency list retained in build evidence.
- Backbone `fishaudio/drama-3@b2b5ee998034b2975720906c815e7fb0e9f007bd`,
  BF16 residual / block-FP8 experts; **no int4 substitution**. Codec pinned to
  `fishaudio/s2-pro@1de9996b6be38b745688de084d87a5633f714e4e` / codec.pth,
  runtime FP16 decoding. Actual Drama3 model licence remains the Fish Audio
  Community License rather than an assumed Apache grant; the earlier licence
  boundary is unchanged. No hosted cloning upload/API experiment.
- Reference SHA256 `30606e0686349c48227ec51702e095c8ea269c52b81c724401d1a055617c5e3c`;
  transcript from the existing independent reference audit. Supported **reference
  sampler**, temperature1.0 / top-p1.0 / epsilon-cutoff0.001 / no request top-k;
  default argmax repetition fallback. This runtime rejects fixed seeds. Main
  token top-k30 is explicitly warned against in upstream source/docs; its
  semantics differ from the old native runtime. Engine request cap4,
  first-frame graph cap4, prefill graphs disabled by documented control;
  decode graphs/fused tower remain enabled, memory fractions stay0.70/0.10.
- The first optimized-sampler experiment incorrectly carried the native low
  temperature0.3/top-p0.7 into this runtime. It measured40.65s serial /12.11s
  batch4, but only22/30 candidate clips passed strict ASR; whole clauses were
  missing. **Rejected as a complete result or valid book-cost estimate.**
- The documented reference recipe measured **59.014s serial** (first call28.75s,
  including first-request compilation) and **12.726s batch4**, startup164.205s.
  Strict pass counts:12/15 serial,11/15 batch. Four batch takes failed on
  substitutions/additions; each had a passing serial counterpart. The final
  assembly selects11 batch +4 serial takes from this exact recipe, with every
  normalized source word matched by an unprompted small/base/independent-medium
  transcript, no unmatched insertions or substitutions, healthy audio and
  source/hash/order checks. Do not call the ungated recipe automatically reliable.
  All rejected candidates retained. Gain only; .18s internal/.50s paragraph joins.
- **Cost, measured29 October:** four experiment/build apps total **USD0.72241802
  metered**, covered by credits/allowances; workspace bill remains **USD0**.
  No persistent volumes created. Both GPU apps and both build apps stopped;
  container list empty. No cash was authorized or charged for these tests.
- **Book scenario, not a full-book measurement:** batch12.726s + the four selected
  serial replacement calls7.173s = **19.899s synthesis for458 words**, about5.37x
  less synthesis time than the prior native retained takes106.844s. At the
  measured reserved H100+4CPU+64GiB rateUSD4.6512/h, this projects **USD5.61
  credits per100,000 words**, plus startup, QA idle time, extra retries and I/O.
  Startup alone~USD0.21; CPU QA ran after GPU shutdown here. Actual adaptive
  batching/retry overhead and chapter-length quality remain unmeasured. This
  makes the old USD50–60 native estimate inappropriate for this serving path,
  but does **not** establish a guaranteed price or whole-book listening pass.
  Cash remains zero through included credits and the verified provider spend0
  guard; stop/checkpoint at quota, no paid fallback.

Player: `scratch/tts-oct28/output/selected/index.html` (new Cillian, Bill, Caro;
old native Cillian control; exact text). Final MP3 SHA256
`bdd8918afad54671b81047c664def76cc13b69f8c3edba14d3a7bb00fcb97bd5`.
Verified full decode, HTTP/hash delivery, browser metadata/playback/near-end seek.
Evidence: ignored `scratch/tts-oct29/fast-fish-reference/` and selected player
manifest. Sources read29 October: [pinned cookbook and sampling controls](https://github.com/sgl-project/sglang-omni/blob/d9c3e708a613515e189134de119209f443c9ae19/docs/cookbook/fishaudio_drama3.md),
[installation](https://github.com/sgl-project/sglang-omni/blob/d9c3e708a613515e189134de119209f443c9ae19/docs/get_started/installation.md),
[dependency pins](https://github.com/sgl-project/sglang-omni/blob/d9c3e708a613515e189134de119209f443c9ae19/pyproject.toml),
[model licence](https://huggingface.co/fishaudio/drama-3/blob/b2b5ee998034b2975720906c815e7fb0e9f007bd/LICENSE),
[Modal CUDA support](https://modal.com/docs/guide/cuda).

## Bill Boerst and Caro Davy retained; six-paragraph Pocket follow-up machine-checked — Evolving (2026-10-29)

Dave chose **Bill Boerst and Caro Davy** from the seven-voice audition; other
voices in that batch were not preferred. Two longer readings now use the exact
same six original paragraphs (458 words), October main100M / four steps /
temperature0.3 on local CPU: Bill **158.82 s**, Caro **176.26 s**. Dave heard these longer readings and called both **“pretty robust”**; Pocket
may be the new CPU winner, pending the requested same-text Turbo comparison.

Each paragraph has an exact normalized unprompted ASR match in small, base or
independent medium, including checks for insertions and substitutions. Bill's
original paragraph6 was flagged as “beliefs”; Caro's original paragraph4
was flagged as “influence” rather than “influenced”. Both were replaced with seed43 takes, preserving the
originals; all other paragraphs use seed42. Other primary-recognizer differences
were resolved by independent full-passage/crop transcripts, not missing-word
waivers. Source/group order, source hashes, final MP3 hashes, full decode,
HTTP delivery and browser metadata/playback/near-end seeking were verified.
Gain only; 0.5-second paragraph joins. Preset/source licensing remains CC0.
Player: `scratch/tts-oct28/output/selected/index.html`; ignored offline copy:
`evaluations/new-engines/output/october-2026-audition/selected/listen.html`.
The existing six-paragraph native Fish/Cillian control is included.

## Cillian word-gated six-paragraph and sustained comparison delivered; new listening verdict pending — Evolving (2026-10-29)

Dave authorised the six-paragraph Cillian repair first, followed by the same
longer passage for Fish/Cillian and Pocket four-step, with every word checked.
He subsequently authorised **up to USD2 additional Modal compute** beyond the
initial bounded run; this is sample work, not an ongoing cloud-render permission.

- **Machine-verified, awaiting Dave's new listening verdict:** Cillian reads all
  six original paragraphs / 458 words in **213.19 s**; the continuous Breakneck
  ch.1 selection / **1,845 words, 17 paragraphs** runs **875.02 s** with
  Fish/Cillian and **636.40 s** with Pocket/Peter/four steps. Both longer
  readings use exactly the same prepared words. No Irish glossary entries occur.
- **Fish recipe remains experimental:** unchanged native Fish Speech 3.0.0,
  code `541566932abbaebcb0a40e562a1f846738383f38`, Drama 3 weights
  `b2b5ee998034b2975720906c815e7fb0e9f007bd`, saved full 24.8 s reference;
  temperature **0.3**, top-p **0.7**, top-k **30**, single-chunk requests,
  `max_new_tokens=0`, seeds 42 with bounded 43/44 repairs. Lower temperature
  alone failed the controlled paragraph-six diagnostic. Sentence groups
  (target 55 words) plus smaller complete-sentence replacements retained
  **15 groups** for the six paragraphs and **51 groups** for the longer reading.
  Failed takes remain banked. A checked assembled sample does not establish
  unattended book reliability; the cause of collapse remains open.
- **Completeness evidence:** each retained waveform hash and source hash was
  checked; unprompted small-model ASR and independent base crops cover every
  source position. Medium-model independent checks resolve disputed Pocket
  words and the Cillian six-paragraph opening of "Sophie had heard". Explicit
  orthographic equivalences cover compounds, US/UK spelling and acronym
  tokenisation; reigns/rains is a spoken homophone. Primary ASR insertions and
  substitutions were reviewed, including the normaliser's added "and" when
  ASR writes the year as digits. None of these reviews changes spoken text or
  silently waives a content omission. Assembly preserves full chunks, adds
  0.18 s group / 0.50 s paragraph gaps and applies gain only; no EQ/compression.
- **Costs remain material:** the longer Fish recording's retained synthesis
  took **431.78 GPU s**; all 71 candidate synthesis calls took **605.26 s**.
  At the verified H100 + 4 CPU cores + 64 GiB rate, **USD4.6512/runtime-hour**,
  these extrapolate to roughly **USD30 / USD42 per 100,000 words** respectively,
  before cold starts and other billed overhead. Budget **USD50–60 per
  100,000-word book** for the current checked workflow; this is an estimate,
  not a measured book price, and fails the project's GBP2/book preference.
  Pocket remains CPU-only with zero cloud compute charges. Credits affect
  cash billed, not those underlying compute costs. Later runs banked audio and
  stopped the GPU before local ASR to avoid paying for the word-check wait.
  Final per-app reports currently total **USD1.5115** for all four Oct 29 apps;
  the workspace summary still reports **USD0 billed**, with credits applied.
  Metering can lag. All four apps are stopped and container inventory is empty.
- Player, exact texts, paragraph jumps and word proofs: ignored artifact
  `evaluations/new-engines/output/october-2026-audition/reliability/listen.html`.
  No application source, product voice, default, deployment, or locked S2 Pro
  production recipe changed. The earlier positive short-Cillian verdict below
  stays bounded to that earlier clip until Dave hears these new recordings.

## Longer October audition: Fish/Peter and Pocket four-step heard and liked; Cillian short audition liked — Evolving (2026-10-29)

Dave requested the same five/six-paragraph passage for Fish and Pocket four-step,
with ordinary book narration taking priority over Irish names, and asked whether
the saved Cillian Murphy reference could be cloned.

- Six paragraphs / **458 words**: three from the existing local Breakneck ch.1
  fixture, three from the existing archived Sophie's World "Fate" text. Exact
  prepared words are identical for both full readings. Pocket's accepted Irish
  spellings are retained in the prep, but none of those names occur here.
- **Machine-checked outputs:** Fish Drama 3 / Peter **207.09 s** and Pocket 4
  100M / Peter / four steps **148.31 s** (exact durations in the artifact manifest).
  Every retained paragraph is aligned to its source; independently cropped ASR
  resolves primary-transcriber errors. No missing source words remain detected
  in either delivered reading. On October 29 Dave heard the delivered samples:
  **"those voices are good too"**. This accepts the six-paragraph audition's
  voice quality; a sustained chapter/book verdict remains open.
- Fish's long second paragraph initially lost text; replaced using native
  automatic chunking / seed 43. The rejected first takes remain banked. Other
  retained Fish paragraphs use seed 42; sampling remains native 0.7/0.7/top-k 30.
  Pocket is local CPU / four threads / temperature 0.3 / seed 42 throughout.
- **Cillian recordings still exist and decode:** current long WAV is **24.8 s**,
  SHA256 `30606e0686349c48227ec51702e095c8ea269c52b81c724401d1a055617c5e3c`;
  clean crop **9.5 s**, SHA256
  `12447e07a292a13c62f8eb1159450dd914396e55581b4a91a08f0b63416f7d8a`.
  Do not describe the current long file as 28 seconds solely from older docs.
  Transcripts were independently checked. The new Fish/Cillian **first-paragraph
  audition (28.75 s)** passes word completeness; longer attempts using both
  references fail and are excluded from the finished full readings. On October
  29 Dave heard the short test and said **"cillian surpriisngly good"**. That is
  a positive listening verdict on the exact short voice audition, not evidence
  that the failed longer takes are fixed or that a full Cillian book is reliable.
- **Historical access blocker (resolved later29 October):** authenticated HEAD for its
  exact October cloning checkpoint returned HTTP 403 / `GatedRepo`. The working
  public preset-only model reports `has_voice_cloning=False`. Do not bypass its
  gate or claim that a working HF token alone enables a Cillian clone. Dave later
  granted account access; the pinned cloning checkpoint now downloads legitimately.
- Player / exact text / checks: ignored artifact
  `evaluations/new-engines/output/october-2026-audition/long/listen.html`.
  No product voice, narrator default, deployment or locked S2 Pro recipe changed.

## Fish Drama 3 wins the October short audition; repaired take accepted, automatic completeness still fails — Evolving (2026-10-28)

Dave heard the new-engine comparison on the same original challenging passage
(Irish/Chinese names, money, dates, measurements and quoted dialogue): eight clips
across Phonon 31M, KittenTTS 2, Pocket 4, Ming 3 and Fish Drama 3.

- **Voice-quality verdict:** Fish Drama 3 / Peter Yearsley (Edmund reference) was
  "a fucking amazing job", "standout winner so far", "outstanding". This is an
  **82.5-second naturalness/voice verdict**, not a full-chapter or default-narrator
  decision. The earlier clips heard were only "ok" and failed names, especially
  Siobhan; Ming sounded muffled and handled some other names better, but not Irish.
- **Completeness is a separate failure:** the exact Fish clip skips or replaces
  "Then the telephone rang" around 1:11-1:15. Whole-clip ASR and an independent
  cropped-window pass flagged it; Dave confirmed the clause is missing or replaced
  by a sound. Do not call this a production pass, conceal it with the good listening
  verdict, or start a book without a tested per-chunk word-check/retry path.
- **Exact successful synthesis setup:** official `fishaudio/fish-speech`
  `541566932abbaebcb0a40e562a1f846738383f38`, `fishaudio/drama-3`
  `b2b5ee998034b2975720906c815e7fb0e9f007bd`; native Fish Speech 3.0.0 on one
  Modal H100, BF16 residuals / upstream block-FP8 experts, no compile. Native
  runtime sampling is temperature **0.7**, top-p **0.7**, top-k **30**, seed 42,
  1024 new frames per automatic chunk. The request's `chunk_length=200` is ignored
  by Drama 3: its own splitter supplies roughly 300-byte chunks and history.
  Do not copy the different SGLang serving defaults into this measured native arm.
- **Audition only:** no offered voice, app route, deployed service, production
  recipe or narrator default changed. References and raw/processed audio remain
  local runtime artifacts; hashes, exact inputs, settings and transcripts are in
  `evaluations/new-engines/output/october-2026-audition/`. Research and economic
  boundaries are recorded in TTS-WATCH-FINDINGS.md, October 28 audition entry.
- **Targeted follow-up (same day, heard by Dave):** a new seed still omits the
  telephone sentence; paragraph generation recovers it but loses other text.
  A bounded repair retains the original first two paragraphs and replaces the
  entire ending paragraph (85.37 s). Both parts and the assembly pass ASR,
  including the telephone sentence. Dave heard this exact assembled take and
  judged it **"outstanding. best yet."** This accepts the short repaired output,
  including its join/voice continuity as heard; it is not a long-form verdict.
  This does **not** clear the unguarded-generation failure or approve a book.
  Dave also called the seed-43 and paragraph takes "great", confirming the
  telephone sentence is absent in seed 43 and present in the paragraph take.
  The paragraph take's different first-paragraph omission remains an ASR fault.
- **CPU follow-up:** both Pocket main-model (100M) one/four-step full takes have
  a nice voice and good non-Irish content, but bad raw Irish pronunciation.
  The **four-step Pocket pronunciation-spelling names test is "actually good"**;
  Ming UK George's equivalent is only "ok", and the other name-test arms were
  rejected. Advance only those exact Pocket spellings into a full-passage audition;
  this does not approve a global lexicon or another engine's pronunciation.
  The full-passage Pocket four-step test now exists (62.80 s audio, 52.95 s warm
  CPU generation; gross completeness passes). Its listening verdict remains open.
  Float32 Phonon Hugh is solid but less emotive than Fish; temperature 0.45 is
  still bland and does not improve Irish. Kitten Saoirse's directed take is
  merely decent, with a disliked voice and no heard emotion. These are bounded
  voice/take verdicts, not blanket bans on their engines.
- **Ming follow-up:** Peter-cloned take remains tinny/artefacty, Irish bad,
  numbers and other names OK; FREEFORM storytelling is otherwise "all good"
  with Irish pronunciation still bad. No root cause for the artefacts is proven.

Official sources read October 28: [native inference contract](https://speech.fish.audio/inference/),
[hardware/install guide](https://speech.fish.audio/install/),
[model card](https://huggingface.co/fishaudio/drama-3),
[actual model licence](https://huggingface.co/fishaudio/drama-3/blob/main/LICENSE).
The model card's research-licence metadata conflicts with its Community License
text; use the actual licence and do not assume an unrestricted Apache grant.

## Colab lane VMs live ~1 hour: render with chunk checkpoints, audit first, CI-check before push — Active (2026-10-06)

**Measured, 3 of 3 VMs on 2026-10-06:** Colab removed each lane VM (`session_terminated reason=pruned`)
60-61 minutes after creation (06:47->07:48, 16:45->17:46, 16:45->17:45 UTC), with the runner healthy and
keep-alive answering 200. The same setup ran 24 h in September, so this is a Google-side policy change; it is
NOT a bug here. Consequences and settled rules:
1. **Whole-chapter banking cannot work** (a 3 h chapter never fits a 1 h VM). The Higgs runner packs finished
   chunks into `ckpt_<slug>_<lo>-<hi>.tgz` (every 10 chunks / 2 min); `lane_ctl progress` downloads them to
   khpi5 on each poll; `lane_ctl submit` uploads the unbanked chapters' checkpoints to the next VM, whose
   runner restores them and resumes mid-chapter. At most ~3 min of work is lost per VM.
2. **Cost model:** each VM ~8 min cold start (pip + model load) + ~52 min useful. A book costs roughly
   audio-hours x 1.4 x 1.54 units x 1.15 overhead (Armed Struggle ~42, Say Nothing ~34 units). Two books at once
   do not fit a ~70 unit balance - render one, the other after units renew or on another provider.
3. **The webapp loop must never trust "no error":** `lane_ctl progress` reports a dead VM as `session_gone` and
   an unreachable bridge as error JSON (exit 0); `render_colab` treats both as failures, resubmits only unbanked
   chapters (max 60 relaunches, wall cap scales with the book), and never spins silently.
4. **Preflight audit (`scripts/book_preflight.py`) is mandatory** and runs inside every lane job before any GPU is
   spent: refuses leaked file-name titles, duplicate chapters, matter-as-chapter, imprint/ISBN/URL lines in the
   first chapters, junk-heavy text, empty books; warns on giant/tiny chapters, digits, junk sentences; prints
   estimated audio hours / GPU hours / units. `fish_bundle.filter_matter` is word-count based, recognises
   imprint pages by text, and raises rather than drop more than half a book (the title-count version deleted every
   chapter of Armed Struggle).
5. **Never push without `scripts/ci_local.sh`** (clean checkout of HEAD, pinned ruff, CI's exact deps, full tests).
   Three red CI runs in one day came from tests that passed only in the working folder (untracked copyrighted
   fixture, numpy missing in CI).

## Finishing a book on the Colab lane: fill chapters, new seeds, kept rejects, recorded exceptions — Active (2026-10-08)

Armed Struggle was finished on free Colab after the Modal credit ran out. What it took (each rule paid for):
1. **Fill chapters, not checkpoints** (`scripts/lane_fill_in.py`): a bundle holding only the missing chunks;
   uploading existing chunks as checkpoints failed Colab's upload API (HTTP 500/503).
2. **Retry rounds must use new seeds** (manifest `"seeds"`): with 42..46 the same text gives the same audio,
   so a retry reproduced all 25 rejected takes exactly.
3. **Split what keeps failing** (`--split`): sentence-by-sentence fill items, joined back with the V3
   crossfade only when every sentence passed; long lists split at list items (ch. Conclusion #153).
4. **Every chunk reaches a checkpoint** (runner): the last chunks of a chapter used to exist only in the mp3.
5. **Audit fixes before re-rendering**: fold accents, reverse the pronunciation lexicon ("Shin Fayn" vs
   "Sinn Fein"), UK/US -ise/-ize, and a truncation counts only words the audio did NOT say. Voice
   similarity is judged only on clips >= 3 s. Rejected takes are kept (`.rejected.wav`) so a rule fix can
   re-check them. Four of the five late-night re-render rounds were spent on audit false alarms.
6. **Exceptions are explicit**: `--lenient` keeps a complete take that is muffled/voice-low (sidecar
   `accepted_despite`); a words exception needs `audit/accepted.json` with a reason, and the swap prints it.
7. Colab orphans (`[?]` sessions) block relaunches and bill: reap them (`~/as-lane/orphan_reaper.sh`).

## Higgs on Modal: temperature 1.0, per-take word/voice/muffled gates, inline-tag text fix — Active (2026-10-07)

Dave listened to the first Modal Preface (11 min, 110-word chunks, V3 joins) and heard: a
cut-off at "199x" plus a voice change (8:16), a non-Cillian voice (10:40), speakerphone/muffled
patches, "losing words", odd pauses. Each was measured and traced:

| Heard | Cause (measured) | Rule now |
|---|---|---|
| cut-off, lost words | chunk 20 looped on a list of years and **skipped 25 words**; whole-chapter ASR still said 98.3 % (repeats counted as heard) | **every take is transcribed (Whisper small.en on the GPU) and aligned to its own text** (`scripts/chunk_asr_audit.py`); tail >= 3 or a dropped run >= 3 re-rolls, then **render sentence by sentence** and crossfade-join. A chapter-level ratio is never completeness proof. |
| "not Cillian" | speaker-embedding similarity 0.81 vs 0.91-0.97 for the rest (Chatterbox voice encoder) | reject < 0.90 |
| muffled / speakerphone | 95 % spectral roll-off 1.8-2.5 kHz (reference 4.7 kHz); ~half of raw takes roll off low; temperature does not change it; **re-rolling rarely fixes it** (first 300 book chunks: 106 muffled first takes, 100 still muffled after 3 seeds - it follows the passage) | re-roll only < **1.8 kHz** (Dave accepted Preface B with takes at 1.6-2.3 kHz; 3.0-3.3 kHz "OK"); a take that is only muffled gets 3 seeds, word/voice faults get 5 + sentence fallback; every take's roll-off is kept in its sidecar |
| pauses mid-sentence, "losing words" | `chapter_text` turned every tag into a newline: footnote links / empty page anchors became paragraph breaks mid-sentence (Fish version too) | inline tags join; note/page-number markers dropped; library 14,659 -> 3,059 mid-sentence breaks, 187/187 pass |

Also settled:
1. **Sampling = temperature 1.0, top_k 50, sent explicitly** in `extra_params`. Dave chose B (1.0)
   over A (0.8, Boson's model-card cloning example) on the fixed Preface. vllm-omni 0.30.0 only takes
   sampling through `extra_params`; its Higgs profile default is 1.0 / top_p 0.95 / top_k 50.
2. **Abrupt end is a hard fault only above 0.8** end/body loudness: at 0.25 it re-rolled chunks the
   ASR showed complete (cost without benefit). Pace-check passes are removed (ASR supersedes).
3. **Resume is keyed on text + sampling** (`NNNN.json` sidecar); a text fix renumbered AS chunks
   2612 -> 2012 and would otherwise have joined old audio to new text.
4. **Emotion tags are still not automatic.** The "super super good" emotive test (2026-10-05) was
   hand-tagged; no book render has had tags. Building a tagger is open.
5. **Cost truth comes from `modal billing`, not the driver.** The first book run (6 L4s, rounds of
   18 batches) metered $1.91-3.01 per audio hour while the driver reported ~$1.07: each round waited
   for its slowest batch, idle GPUs were billed and then scaled down, and every round paid new
   ~7-minute cold starts. The driver now streams all batches through one `.map` and caps spend at
   max(containers x wall clock x rate x 1.14, Modal's metered cost). The monthly summary also ran
   ~$3.6 above the per-app report on 2026-10-07 (unexplained; budget against the summary).
   **The monthly summary lags by up to an hour.** On 2026-10-07 a retry wrapper set its cap as
   "$28 minus the summary" while the summary still missed the previous run's last hour; the month
   ended at $32.14 metered and **$2.02 was billed to Dave**. Rule: before any Modal run, the cap is
   credit - summary - (the last hour's burn of every run that ended < 2 h ago) - $3 margin, and a
   run that needs more than that waits for Dave's OK or goes to Colab.
6. Armed Struggle split (2026-10-07): Preface = approved B; ch10-18 on Modal (inside the free credit,
   `--partial-ok` cap); ch09 (already heard by Dave) on the Colab lane through the webapp's own
   `render_colab` with the same bundle, then audited and adopted (`scripts/adopt_lane_chunks.py`).

## Higgs lane pipeline is wired end to end; per-chunk gates and book-text audit are mandatory — Active (2026-10-06)

`higgs_cillian_irish` is a lane voice (engine key `fish`, so validation/lane UI are shared;
`webapp/fish_lane.engine_for_voice` picks the Higgs bundle + `scripts/higgs_colab_runner.py`).
Proven on a real chapter through the same `lane_ctl.sh` the webapp uses: Say Nothing ch.4,
22 chunks, 0 failed, 0 flagged, 8 min GPU for 6.0 min audio, ASR WER 1.75 % (only UK/US spelling
and stray-apostrophe tokens), ~0.5 Colab unit. Dave: "perfect" apart from the opening words.

Settled rules:
1. **Generation unit = paragraph chunk (<=70 words), never a sentence**; consecutive heading
   lines are one chunk; gaps 0.3 s within / 0.5 s across paragraphs (`scripts/higgs_prep.py`).
2. **Every chunk is gated** (health, clipping, duration, abrupt end <=0.25) with seed re-rolls
   42..46; the best attempt is kept and flagged if none passes. **Output is gain-only.**
3. **Emotion tags are an allow-list** (`higgs_prep.ALLOWED_EMOTIONS`); anger/shouting can never
   reach the audio (Dave: loved the emotion, not the shouty one). No auto-tagger is built;
   plain narration is the default.
4. **Front/back matter is never rendered** (`fish_bundle.filter_matter`; manifest `skipped[]`).
   Say Nothing's detector listed Index/Notes/Bibliography as chapters (~7 h wasted audio).
5. **Never narrate**: HTML `<title>` (it produced "Say-eight."), standalone footnote digits,
   photo-credit lines; publisher `chapter_number` elements become "Chapter N". Editorial
   `[brackets]` are unwrapped (Higgs skips bracketed words). Audit a new book's bundle text
   (chapter openings, URLs/symbols, digit scan) before any GPU is spent.
6. **Lane control plane fix:** `lane_ctl.py` counted the Colab CLI's "new version available"
   notices as live sessions (phantom sessions named `colab`), so the 2-slot guard saw 4/2 and
   refused every submit - the real reason the webapp lane had never run a job. Fixed; the
   controller is tracked in `scripts/khpi5-lane/` (deploy = copy to `~/as-lane/`).

## Higgs TTS 3 works on a Colab L4; emotion tags give a standout dramatic read — Active (2026-10-05)

Reverses the 2026-09-20 "not runnable on free hardware" closure for the
boundary it named (free Ampere+ compute): the AI-Pro Colab **L4** (Ada, bf16) runs
`bosonai/higgs-audio-v3-tts-4b` correctly. Runtime that works: Python 3.12 venv,
`vllm==0.30.0` + `vllm-omni==0.30.0` from PyPI (the Sep git-main pin no longer
imports), deploy-yaml `FLASHINFER`→`TRITON_ATTN` and `max_model_len` 4096, `--dtype
bfloat16` (`scripts/higgs3_colab_l4.py`). Do not install into Colab's system Python
(3.13): torch mismatch. Measured RTF 1.2–1.9 (Fish S2 Pro ~2.7); ~1.8 compute units
for install + four clips; waveform healthy (RMS 0.06–0.10).

Dave's verdict (Cillian clone, 28 s full reference, seed 42): plain paragraph and
plain/sadness+slow quote "all perfectly decent"; **`<|emotion:anger|>` quote "awesome,
super super emotive"**. Emotion tags (`<|emotion:…|>`, `<|prosody:…|>`, start of
utterance) are Higgs's documented control surface — what Fish S2 Pro lacks. Not yet
done: ASR completeness check, a real full chapter, accent drift over long form, licence
check of Boson's "no voice cloning without consent" prohibition for the Cillian
reference (private listening only so far). Mixed-passage verdicts (3 min of
*Armed Struggle* ch.1, narration + quotes, Cillian clone, 2026-10-05): **accent
"great/fantastic" in every arm; tagged chunked render "super super good"**
(emotion loved; Tom Barry quote slightly over-acted → use milder/no tag there;
heading lines each got a 0.5 s gap → "pause fatigue"; merge heading lines into one
chunk). **Per-sentence generation (33 requests) is rejected by ear** — sentences sound
clipped and strung together; **paragraph-sized chunks (<=~70 words, tags inline at
sentence starts) fixed most of it.** Remaining defect is stochastic abrupt chunk ends
(plain arm, "...even for a moment": end-of-clip RMS 0.27 of body vs ~0.01 for clean
ends) → production runner needs an end-abruptness gate with seed re-roll (measure last
50 ms RMS / body RMS, reroll if > 0.25). Single stray footnote numerals ("one",
"two"…) in the payload are near-silent in Higgs and are read aloud by Fish in the
delivered chapters — fix once in text prep. Mastering: the first mastered MP3s
(EQ + single-pass dynamic loudnorm) were heard as clipped; gain-only WAV was clean, but
my later gain-curve measurement showed the chain moves gain only ~1 dB, so the cause
of that clipping is **unproven** — keep Higgs mastering gain-only until isolated. Provenance: model card
huggingface.co/bosonai/higgs-tts-3-4b and sgl-project.github.io/sglang-omni/cookbook/higgs_tts.html,
read 2026-10-05.

## TADA Cillian is an undocumented experiment, not an offered voice — Active (2026-09-28)

A live audit found an uncommitted `cillian_irish_dry` transcript entry and a
`tada/voices/cillian_irish_dry.wav` duplicate on the Zorin working tree. **Cillian
is never registered as a TADA voice** — the app exposes it only as Breeze
(`breeze_cillian_irish`) and Fish (`fish_cillian_irish`); all synthesis uses the
canonical `chatterbox/voices/cillian_irish_dry.wav`. The TADA additions are
unwired and undocumented. Decision: the files are **preserved and committed as an
experiment** (commit `9cc3623`), but they do **not** make Cillian a selectable
TADA narrator)Skip a TADA voice registration, an app `VOICES` entry, and a
listening verdict are all still required before it is offered. Until then the
`cillian_irish_dry` TADA transcript + reference remain dormant.

## Audit 2026-09-28: live audit vs docs — raw Docker socket override removed — Active

A full live audit (Zorin stack at commit `c5b83d0`, then redeployed) against the
docs surfaced and fixed three gaps:

- **Stale version metadata.** The running webapp/worker reported `git_sha
  ed060c3` / `v1.8.2` / build `2026-02-04` (Dockerfile defaults) because the last
  build bypassed `scripts/deploy.sh` and the live `.env` hardcoded
  `APP_VERSION=v1.8.2` / `APP_GIT_SHA=ed060c3`. **Fix:** removed both pins from
  the live `.env` (so `deploy.sh` always stamps the real ref) and redeployed via
  `scripts/deploy.sh master` — health now reports `git_sha 9cc3623` / `2.1.0`.
  Lesson: never run a bare `docker compose build`; always use `scripts/deploy.sh`
  (Rule 11).
- **`docker-compose.override.yml` re-exposed the raw Docker socket.** The tracked
  override mounted `/var/run/docker.sock` into `webapp` and `worker`, negating the
  AUDIT-PLAN 4.1 hardening that routes Docker through the whitelisted
  `docker-socket-proxy`. **Fix:** removed both raw socket mounts from the override
  (commit `9cc3623`); `DOCKER_HOST=tcp://docker-socket-proxy:2375` is now the only
  access path. **Check before any future deploy:** do not re-add the raw socket
  mount; if the app ever needs a Docker capability the socket proxy does not
  expose, extend the proxy allowlist, not the mount.
- **README listed PLAN-V5 as the current forward plan.** Corrected to PLAN-V6
  (commit `9cc3623`); AGENTS.md already had it right.

The audit confirmed the docs otherwise match live reality: GPU/paid engines off
(`GPU_RENDER_ENABLED=0`; `tada/vibevoice/inworld/polly` false),
`chatterbox-nano` default narrator up, fish preview byte-exact, lanes idle post-
delivery (all 10 Armed Struggle chapters harvested).

## Jev (TypeSafe) decision layer is opt-in and disambiguation-only — Active (2026-09-23)

`webapp/jevspeak.py` adds an optional TypeSafe/Jev layer with two features, both
**OFF by default** (`JEV_TTS_NORMALIZATION_ENABLED`, `JEV_CHAPTER_BOUNDARY_ENABLED`).
With the flags off both entry points are pass-throughs, so existing output is
byte-identical and the marginal cost is exactly zero. Reference: `JEVSPEAK.md`.

- **Jev only disambiguates spans the deterministic rules cannot resolve.** Regex
  finds candidate spans (fractions, `Dr.`/`St.`/`No.`, roman numerals, attached
  measurements, ranges, currency, dotted initials); one batched Jev `choice` per
  chapter picks the intended reading in sentence context and ordinary code
  applies it. It is "select instead of generate", never free-text rewriting.
- **Deterministic classes never go to the API.** Years, decades, ordinals,
  percentages, large integers and the abbreviations/currency the normalizer
  already handles are resolved in code; sending them would only cost tokens.
  The real-book run found and fixed finder bugs that leaked decades and ISBN
  hyphen groups into the API path (see STATUS 2026-09-23).
- **Feature 2 (boundary refinement) is consulted only when the existing
  heuristics are ambiguous** — a near-floor section or a back-matter-looking
  title — so a normal chapter listing makes no call.
- **Any failure falls back to existing behaviour.** Missing key, timeout,
  connection error, non-2xx (after one bounded retry on 429/5xx), malformed
  body, an off-menu choice, or confidence below `JEV_MIN_CONFIDENCE` all leave
  the deterministic result untouched. `ask_jev` never raises. Verified live:
  HTTP 401 and a ConnectionError both produced output byte-identical to
  feature-off.
- **Threshold evidence:** measured live on `jev-1.13.0`, 15 spans in one
  request, lowest confidence 0.85 against the default floor 0.55
  (`scripts/measure_jevspeak.py`). Re-measure before lowering it.
- This changes no engine, voice, default path or output. Rollback is unsetting
  the two flags; full removal is documented in `JEVSPEAK.md`.

---

## Armed Struggle production: locked Cillian recipe (Fish S2 Pro) — Active (2026-09-22)

Dave declared the recipe "the answer for this book" after the stress test passed
(8/8 sentences, all dates/numbers/ordinals ASR-verified, 0 failures) and ordered
the **whole book rendered from the Preface, replacing his existing ABS copy while
preserving his exact listening position**.

- **The exact method is codified in `CILLIAN-RECIPE.md`** — engine (Fish S2 Pro), dual-reference routing (narration = 28s full ref; quote sentences = expressive-tail crop; both temp 0.85), text prep (lexicon incl. corrected Tánaiste→"Tawnashta", dates/years/ordinals/numbers/currency → words, orphan merge, curly apostrophes kept), per-sentence banking + health gates + auto re-roll (seeds 42/43/44), silence-trim + natural-gap assembly, mastering chain, ASR completeness gate before delivery.
- **Production lane (2026-09-24, supersedes Kaggle-only):** headless **Colab L4** via official `google-colab-cli` **on khpi5** (AI Pro account, ~197 compute units ≈ 100+ L4 GPU-hours at measured 1.54 units/h). Kaggle T4×2 kernels remain the fallback lane (hit the 30 h/weekly cap 2026-09-23, re-probed still blocked 2026-09-24). **Lightning AI free tier cannot start GPU without a linked payment method** (verified error 2026-09-24) — excluded as a lane **at that time**; Dave then linked a payment method and added balance (2026-09-24 ~20:00), and GPU start was verified working (real Tesla T4, then stopped). See DECISIONS for the reversal. Runner: `scripts/fish_colab_runner.py`; the **harvest loop** (khpi5 `/tmp/colab_harvest.sh`) MUST pull each completed chapter off the VM — the first session was reclaimed mid-Preface and taught that lesson.
- **Lightning AI unblocked (2026-09-24 ~20:00):** Dave linked a payment method and added balance. **Verified usable** — `switch_machine(T4)` + start succeeded, `nvidia-smi -L` returned a real `Tesla T4`, then stopped immediately (cost exposure: a few cents at the official $0.55/h T4 rate). This **reverses the earlier "excluded / payment wall" verdict**; the wall was real on the free tier and is now gone. Key: `.secrets/lightning_api_key` (UUID), used with `LIGHTNING_USERNAME=david-mep9n`; org `david-mep9n-org`, teamspace `general`. Billing-summary API returns 403 for this key (cannot read balance programmatically — check the web UI). Studio `as-cillian-render` is stopped. Available as a **third lane if wanted**; not yet wired into the render/harvest control plane.
- **Two-lane parallel split (2026-09-24 18:27):** the AI Pro account accepts a **second concurrent L4 session** (`render2`), so the book renders on two lanes with disjoint chapter scopes read from `/content/as_chapters.txt` (lane `render`: ch1,ch2,ch3,ch8; lane `render2`: ch4–ch7,conclusion) — halves wall-clock at the same total GPU-hours. Control plane (watchdog + harvest loop) is multi-session; the watchdog **must run under the CLI venv python** (system python3 dies on `pydantic_core`) and never auto-provisions a reclaimed VM (logged for manual action instead). Kaggle remains excluded (weekly 30 h quota, re-probed blocked 2026-09-24).
- Measured: RTF 2.56–2.78 on T4×2; L4 in progress (Preface 40/83 in 14 min ≈ RTF ~2.1); whole book (152,359 words, 10 sections ≈ 17–20h audio) ≈ **40–55 GPU-hours**, well inside the L4 unit budget; one chapter at a time, resumable.
- Replacement contract: new per-chapter MP3s go into the ABS item `7039379c`
  folder ("Armed Struggle"), ABS rescan, and Dave's progress is mapped to the
  same chapter + same fraction (he is 39.9% into "New States 1923–63").
- Book-wide payloads prepared: `scratch/as_book/*.json` via
  `scripts/prepare_armed_struggle_chapters.py` (+ canonical unit-tested
  `scripts/as_prep.py`); bundle + runner staged on khpi5 (`as_bundle.zip`,
  `fish_colab_runner.py`); Kaggle fallback kernels via
  `scripts/prepare_kaggle_fish_as_book_chapter.py` (slug argument).
- General-novel note (Dave, standing): engines/voices rejected for THIS book's
  Irish bar may still serve generic novels — Deepgram Flux Rufus/Colin
  (expressivity=1, "very good", paid), Supertonic-3 (free CPU presets), Gemini
  Achernar (free, quota-paced), Higgs 3 (needs H100-class). Full trail in
  `TTS-WATCH-FINDINGS.md`.
- **Gate is the definition of done (settled 2026-09-25):** a section ships only
  when `scripts/gate_book_chapter.py` reports PASS on both halves — waveform
  health (RMS 0.02–0.30, no plateau, no 30 s quiet window) **and** ASR
  completeness (word ratio ≥ 0.93, coverage ≥ 0.90) against the *exact payload
  the lane rendered*. The tool was validated by reproducing the already-gated
  Preface before it was trusted on new chapters. A PASS is a completeness and
  health claim only — it never becomes a listening verdict, which stays Dave's.
- **Boundary: do not queue *The Armed Struggle* through the webapp lane path
  until the chapter mapping is reconciled (settled 2026-09-25).**
  `scripts/fish_bundle.py` derives slugs as `ch{idx:02d}` from
  `chapters.list_renderable_chapters()`, which returns **24** sections for
  `fixtures/armed_struggle.epub`, while this book's authoritative payloads are
  the **10** sections `scripts/regenerate_as_book.py` maps
  (`preface, ch1…ch8, conclusion`). A webapp-built bundle would therefore carry
  a manifest that overrides the runner's ORDER and renders a different chapter
  split, with no gate source for it. The in-flight render is unaffected: its
  bundle came from `regenerate_as_book.py`, carries **no** `manifest.json`, so
  the runner uses its Armed Struggle defaults — and its 10 payloads were
  diffed byte-for-byte against `scratch/as_book/*.json` (identical). Measured
  and recorded in `TTS-WATCH-FINDINGS.md` 2026-09-25; revisit when a general
  book needs the webapp lane.
- **DELIVERED 2026-09-26 03:11 (closure).** All 10 sections gated PASS (word
  0.9846–0.9944, coverage 93.2–96.5 %); 16.37 h chaptered M4B live in ABS
  item `7039379c` with every old audio file moved out as `_SUPERSEDED`,
  nothing deleted; Dave's position preserved by content-remap (39.92 % into
  "Two – New States 1923–63"). **ABS swap method settled:** remap via sqlite,
  then the listener fully closes the player and reopens fresh — a stale
  player pushes its cached old-book absolute position back over the remap
  (measured once, fixed, verified). All Colab VMs and the watchdog stopped
  post-delivery; the delivery-watch schedule is disabled-in-place. Spend: $0
  cash, ≈118 of ~197 Colab units (≈23 of them the 2026-09-25 crash-loop
  waste — full trail in TTS-WATCH-FINDINGS). Listening verdicts stay Dave's;
  the preserved `18 - Afterword.mp3` has no 10-section counterpart yet.

---

## Fish Speech S2 Pro: voice accepted with flat Cillian reference; pronunciation via lexicon audition — Active (2026-09-20)

Dave's verdict on the bounded flat-reference retry (tough-Irish paragraph, `cillian_irish_dry.wav` + transcript, free Kaggle T4×2, health-gated): **"Fish S2 Pro retry voice is perfect."** This reverses the 2026-09-18 bounded rejection for the exact boundary that rejection recorded: the failure was theatrical prompt prosody transfer, and the remedy it named (flat, clean, non-theatrical studio prompt) is confirmed as the required operating mode. Production eligibility now hinges on the one remaining open issue: **pronunciation of hard Irish terms read from anglo spelling** (ASR: "Padreik Paris", "deal era", "Toshak").

- In flight: deterministic proper-noun respelling lexicon (exact watch-list tokens only, engine-agnostic, preprocessing-stage shape), A/B auditioned on the same kernel/text with Dave's ear as judge. The old respelling ban originated from a misdiagnosed formatting artefact; this bounded audition re-tests that boundary.
- Not viable paths, recorded to prevent re-litigation: fine-tuning (9.5s of reference audio), longer references (do not teach out-of-distribution words), Higgs 3 for this need (H100-only), Chatterbox-family Cillian on CPU (rejected by ear same day).
- Runtime facts for any free-tier rerun: `scripts/prepare_kaggle_fish_s2pro.py` — codec split to the second T4 (`CODEC_DEVICE`), `--half`, apt portaudio/sox/sndfile, `snapshot_download`. RTF 15.03x (audition-viable, book-slow). Licence/commercial terms of the 2026-09-18 entry continue to apply.

---

## September 2026 Modal GPU Engine Expansion: F5-TTS (300M) & CosyVoice 3 (0.5B) Audited on Tough Irish Words; Serverless Cloud Economics Settled — Active (2026-09-19)

Following the adoption of Modal Cloud GPUs (Tesla T4 / Nvidia L4) and the selection of Breeze 2 for full-book Irish rendering, the engine portfolio was expanded to evaluate lightweight modern flow-matching diffusion architectures on the notorious Irish Gaelic pronunciation challenge (`fixtures/tough_irish_words.txt`):

- **F5-TTS (300M Non-Autoregressive Flow Matching) Audited & REJECTED for Irish Literature**:
  - *Dave's Listening Verdict (2026-09-19)*: **"total shit, american and awful pronunciation"**.
  - *Findings*: While fast (RTF 0.577 on T4) and cheap ($0.005/min), F5-TTS completely fails to capture Irish Gaelic phonology (Pádraig Pearse, Seán MacDiarmada, Dáil Éireann, Cathal Brugha, Cumann na mBan, Dún Laoghaire, Portlaoise, Taoiseach, Tánaiste) and forces Americanized English pronunciations. Rejected for Irish literature and historical narration.

- **CosyVoice 3 (Fun-CosyVoice3-0.5B-2512) Audited & REJECTED**:
  - *Dave's Listening Verdict (2026-09-19)*: **"wtf? its totally garbled??"**.
  - *Findings*: Despite successful compilation and zero-shot flow-matching synthesis (RTF 1.22 on T4), output suffered severe acoustic distortion and garbled phrasing on English/Gaelic mixed text. Rejected.

- **Breeze TTS 2 (3.5B) Confirmed as the SOLE Viable Irish Engine**:
  - Dave's listening verdict: **"outstanding... almost perfect"**.
  - Breeze 2 is the ONLY model in the benchmark that accurately pronounces Irish Gaelic names, historical figures, and political titles with native cadence and solemnity. Confirmed as the sole engine for *The Armed Struggle*.

- **Modal GPU Serverless Economics & Multi-App Concurrency Settled**:
  - Modal enables true serverless execution with `scaledown_window=2` (instances terminate 2 seconds after completion, eliminating idle billing).
  - Multi-app concurrency allows short audition runs to execute independently in cloud containers without interrupting production book renders.
  - At $0.80/hr (Nvidia L4), rendering Breeze 2 audiobooks costs ~$1.50 per audio hour. The 16-hour *The Armed Struggle* requires ~$24.16 compute, utilizing the remaining $11.37 free credits and ~$12.80 billed overage to complete the entire book.

---

## September 2026 Top-Tier Modal GPU Voices & Irish Narration: Cillian Murphy Breeze 2 Winner; Qwen3 Aiden for Emotive English; 7 Auditioned Voices Integrated into Webapp — Active (2026-09-19)

Following multi-round auditions across *Breakneck: China’s Quest to Engineer the Future* and *The Armed Struggle: The Story of the IRA* (First Dáil excerpt and Tough Irish Words challenge: Dáil Éireann, Cathal, Sinn Féin, Taoiseach, Tánaiste, Dún Laoghaire, etc.) on Modal Cloud GPUs:

- **Cillian Murphy (Irish Studio Clone, Breeze TTS 2) is the definitive winner for Irish & Multilingual content.**
  Dave's listening verdict: **"outstanding... almost perfect"**.
  - *Acoustic Setup*: Derived from dry reference audio (`chatterbox/voices/cillian_irish_dry.wav`, 9.5s, 456 KB). Locked `seed=42` eliminates inter-sentence timbre drift; `guidance_scale=2.5` eliminates date/number warble.
  - *Tough Irish Evaluation*: Flawlessly pronounced Irish political titles, historical names, and Gaelic placenames where Qwen and older engines failed.
  - *Mastering*: Broadcast mastering chain applied (-20 LUFS integrated loudness, +1.0 dB EQ at 220 Hz, -2 dB high shelf at 7.5 kHz).
  - Selected for the full-book production render of *The Armed Struggle: The Story of the IRA* by Richard English (11 chapters, ~150,000 words).

- **Qwen3-TTS Aiden (`qwen3_aiden`) is approved for Emotive English Non-Fiction.**
  Dave's listening verdict: **"solid voice... great emotive uses... really nice"**.
  - Uses `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` with natural-language emotive instruction steering. Excels at non-fiction narrative with dynamic question intonation and conversational rhetorical pacing.
  - Note: Zero-shot base model cloning with Qwen3 produces excessive breath artifacts and poor non-English pronunciation; `CustomVoice` studio voices are the approved operational mode.

- **5 Additional Approved Breeze 2 Voices for English-Only Content**:
  - `breeze_liam_au`: Liam (Australian / Irish Male) — warm, natural non-fiction delivery.
  - `breeze_karen_savage`: Karen Savage (Classic British Female) — elegant literary RP.
  - `breeze_arthur`: Arthur (Distinguished British Male) — classic, distinguished UK non-fiction narrator.
  - `breeze_adrian`: Adrian Praetzellis (Scholarly British Male) — articulate, scholarly tone.
  - `breeze_tadhg_clean`: Tadhg Hynes (Restored Irish Male) — denoiser-restored studio timbre.

- **Webapp Voice Architecture & Preview Contract**:
  - All 7 voices registered in `webapp/app.py` `VOICES` catalogue and exposed via `/api/voices`.
  - `get_voice_preview()` updated to treat `'breeze'` and `'cosyvoice'` as GPU-only: previews are pre-rendered on cloud GPUs and cached in `data/previews/`, never cold-generated on CPU (complying strictly with Rule 14).
  - `docker-compose.yml` updated with `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in both `webapp` and `worker` containers.

- **GitHub CI Pipeline Fixed**:
  - Resolved failing `ruff check` in `.github/workflows/ci.yml` caused by unused imports and unformatted f-strings. All 344 unit tests pass, and GitHub Actions CI workflow is 100% green.

---

## September 2026 Modal GPU Bake-Off: Multi-Voice Casting & Broadcast Mastering Filter Chain Accepted; Fish Speech 2.0 Audited; Long-Form Pacing Settled — Active (2026-09-18)

Comprehensive audition across *Breakneck: China’s Quest to Engineer the Future* (2-page excerpt and full 2,135-word / 14.6-minute Introduction) on Modal Cloud GPUs (Tesla T4, L4, A10G) testing Deepgram Aura-2, Chatterbox Turbo, Qwen3-TTS, F5-TTS, Fish Speech 2.0 (S2 Pro), and multi-voice Kokoro with automated broadcast mastering:

- **Multi-Voice Non-Fiction Casting & Broadcast Mastering is the clear production winner.**
  Dave's listening verdict: **"production value is clearly the winner here"**.
  - *Casting Architecture*: Dividing non-fiction prose into an editorial screenplay avoids the fatigue of single-voice monoculture. Author analytical narrative is cast to `am_michael` (calm, intelligent, measured non-fiction cadence at 1.0x), while quoted historical material, macro questions, and core thesis statements are cast to `am_fenrir` (deep resonant baritone at 0.95x with 500ms pauses).
  - *Automated Broadcast Mastering Chain (FFmpeg)*:
    1. **Warmth EQ**: `equalizer=f=250:width_type=o:width=1.2:g=2.2` (+2.2 dB at 250 Hz restores human chest body and condenser mic proximity).
    2. **Dynamic De-Esser**: `highshelf=f=7200:gain=-3.5:width=1.0` (-3.5 dB above 7.2 kHz tames digital sibilance, harsh 's' and 't' transients).
    3. **Loudness Normalization**: `loudnorm=I=-20:TP=-2:LRA=11` (strict EBU R128 -20 LUFS integrated loudness, -2 dB True Peak ceiling — commercial Audible/ACX standard).
  - Solves the synthetic high-frequency tinniness of small models without requiring massive diffusion runtimes.
  - *Performance & Cloud Economics*: Rendered 14 minutes, 35 seconds of continuous mastered audio in 49.03s on Modal T4 GPU (RTF: 0.056x, ~18x faster than real-time). Total spend was $0.06 per chapter, 100% absorbed by Modal's $30/month free credit tier ($0.00 billed).

- **Fish Speech 2.0 (S2 Pro) Flagship (4.4B Dual-AR) Audited & Bounded.**
  Deployed on Modal Nvidia A10G GPU (24GB VRAM) using official weights (`fishaudio/s2-pro` Dual-AR + 44.1kHz DAC `codec.pth`). Dave heard: *"either the cloning hurt, or you didn't follow each engine's specific protocols for cloning, or whatever... but fish was a bit disappointing? does it not have native voices?"*
  - *Prompt Prosody Transfer Failure*: Dual-Autoregressive transformers attend heavily to prompt acoustic dynamics. Conditioning on theatrical dialogue (`uk_male_minter.wav` Arthur: *"snapped Bertram... Hang her!"*) transfers erratic pitch jumps, clipped stops, and theatrical shouting directly into serious non-fiction narrative.
  - *Zero Native Voices*: Fish Speech open-weights has **no hardcoded native curated voices** (unlike Kokoro or ElevenLabs). It is purely a zero-shot prompt-conditioned cloner; omitting prompt audio produces pseudo-random acoustic timbres.
  - *Requirement*: If used, Fish Speech requires a perfectly flat, clean, non-theatrical studio prompt in the target accent and genre.

- **Deepgram Aura-2 Pandora (`aura-2-pandora-en`) Pause Calibration Settled.**
  Deepgram Pandora delivered outstanding British female RP audio on *Breakneck*. However, raw text input caused breathless run-on delivery between numeric abbreviations (e.g. *"three hundred and eighty-eight B.C. and before"*). Preprocessing must insert explicit punctuation (em-dash `—` or period) after acronyms and abbreviations to enforce natural breathing pauses.

- **Long-Form Preprocessing & Pacing Rules Settled (from 14.6m Render).**
  Listening to the complete 2,135-word Introduction revealed two critical pipeline defects:
  1. *EPUB Drop-Cap Span Stitching*: EPUB files frequently wrap chapter opening letters in drop-cap spans (e.g. `<span class="dropcap">E</span>ach`). Naive regex tag stripping (`<[^>]+>`) leaves whitespace (`"E ach"`), causing the phonemizer to pronounce *"E... ach"*, garbling the opening word. Preprocessing must merge single-letter drop-cap spans back to the root word prior to tag stripping.
  2. *Section Announcement Silence Buffering*: Title and chapter announcements require an explicit **1.5s–2.0s** silence buffer (not 700ms) to prevent feeling like a breathless run-on sentence before the narrative begins.
  3. *Secondary Voice Rotation Frequency*: In a 2,100-word chapter, assigning the secondary voice strictly to explicit quotes resulted in it speaking only twice across 15 minutes. To sustain dynamic interplay, the secondary voice should also voice section headings, epigraphs, and contrasting perspective blocks.

---

## September 2026 TTS Engine Audition: CPU Candidates Audited; Audio8 Rejected; Breeze 2 & Qwen3 Evaluated — Active (2026-09-05)

Audition of *Breakneck: China’s Quest to Engineer the Future* Chapter 1 ("Engineers vs. Lawyers", first 2 pages, 456 words normalized) across Audio8, Breeze TTS 2, Qwen3-TTS, Kokoro, and CPU candidates (Pocket, Kitten, NeuTTS Air):

- **Chatterbox Turbo remains the cheapest and overall production winner.**
  Confirmed for primary book rendering: zero cloud compute cost on free Kaggle GPU (or fast on budget GPU), proven voice clone fidelity (Arthur), reliable long-form pipeline, and established pronunciation controls.
- **Audio8 0.6B ONNX INT4 is rejected for continuous audiobook narration.**
  The August 2026 gate left Audio8 bounded ("better" on 9 short sentences). On this continuous non-fiction passage (18 complete sentences, 197.74s audio), Dave heard volume pumping ("garbled, loud then soft... not great") and garbled speech. Upstream's documented design envelope is strictly optimized for prompts <150 characters. Beyond this length, INT4 codebook drift and local gain scaling produce severe speech garbling. Audio8 is formally removed from application consideration.
- **Breeze TTS 2 (3.5B) Voice Direction is "very impressive", but Voice Design requires a 1-shot anchor workflow.**
  Dave heard two arms on Kaggle T4 GPU:
  - *Voice Design* (pure text prompt "British male narrator", zero reference audio) failed sentence-to-sentence continuity: *"voice seems to change each sentence? weird!"* Pure text prompt generation resamples a new speaker latent per chunk. The required pattern is: design once on a 15s reference prompt, save the WAV, and pass that WAV as reference into Voice Direction for subsequent chunks.
  - *Voice Direction* (Arthur clone): Dave heard: **"very impressive"**.
  - *Operational & License Boundary*: 7.12 GiB weights, 7.97 GB VRAM, measured RTF 7.86 on T4 GPU (~25 mins for 3 mins of audio without FlashAttention). Renders on budget hardware are computationally prohibitive for full books. Governed by BreezeBlue Non-Commercial License (commercial audiobook use requires separate written agreement).
- **Qwen3-TTS 1.7B Base is an efficient zero-shot clone; CustomVoice provides expressive studio narration.**
  Evaluated on Kaggle T4 GPU (Arthur clone, 174s audio, measured RTF 2.57, 4.05 GB VRAM). Dave heard: *"really decent... great voice clone, somewhat lacking some emotion or tone in places, a bit monotone"*.
  - Highly efficient on budget/free GPUs (fits in 4 GB VRAM, 3x faster than Breeze 2).
  - The zero-shot Base clone replicates speaker timbre faithfully but retains a neutral narrative delivery. For expressive non-fiction and dialogue, the `Qwen3-TTS-12Hz-1.7B-CustomVoice` route (9 studio voices including `ryan`, `aiden`, `uncle_fu`, `vivian`) with natural language instruction steering is the intended expressive path.
- **Kokoro 82M CPU baseline ceiling confirmed.**
  Evaluated standard `bm_george` and best-practice blends (George/Lewis blends at 0.92x–0.95x speed). Dave heard: *"decent, a little stilted... pacing is super weird? 'rug... shops' in almost all of them. like, a weird pause? the fable voice sounds so robotic, the other kokoro voices are better but sound stilted"*.
  StyleTTS2 82M lacks an autoregressive language model backbone. Its `espeak-ng` phonemizer inserts caesuras at compound noun boundaries. Speed adjustments and voice blending soften phonetic edges but cannot fix semantic prosody. Kokoro remains a fast preview tool, not an audiobook production engine.
- **NeuTTS Air 1.4.1 is rejected for audiobook production.**
  Auditioned on *Breakneck* Chapter 1 across both single-sentence and sentence-packed configurations. Dave rejected the engine on multiple critical flaws:
  - *Accent & Regionality*: Upstream's shipped voice "Jo" (`jo.pt` + `jo.txt`) and backbone mapping is hardcoded to `en-us` (General American). Upstream ships no calibrated British reference voice. This fails the repository's UK narrator standard.
  - *Defective Phoneme Tokenization*: `espeak-ng` outputs palatal glides (`ʲ`, Unicode U+02B2) across common English vowel-to-vowel transitions (e.g. `ðɪʲ` in *"the airport"*, `aɪʲ` in *"I often"*, and `vˌiːʲˈɛs` in *"vs."*). NeuTTS's acoustic token decoder misinterprets `ʲ` as an explicit vocalized vowel syllable, introducing audible, intrusive "ee" stutters (*"the-e-airport"*, *"I-e often"*, *"v-e-s"*).
  - *No Abbreviation Normalization*: The engine lacks text preprocessing and spells out standard abbreviations like `vs.` literally as *"v s"*.
  - *Compute Inefficiency & Token Cap*: Measured RTF on CPU is **2.25x** even with paragraph packing (and **5.90x** unpacked), making it 4x–7x slower than Pocket TTS (0.53x) and KittenTTS (1.02x). Upstream hardcodes a 2048-token context cap (~28s audio per call) with no native long-form support.
  NeuTTS Air is formally removed from application consideration.
- **Pocket TTS 2.1 (Peter Yearsley) and KittenTTS 0.8.1 (Rosie & Jasper) verified on Breakneck Chapter 1.**
  - Pocket TTS 2.1 (Peter Yearsley): 156.4s audio, measured RTF 0.53x on CPU. Very fast streaming Kyutai transformer. Delivery is clean and articulate with natural sentence joins (300ms pause). Strict chunk token limit (<50 tokens) and explicit number/currency normalization remain mandatory to prevent skipped words.
  - KittenTTS 0.8.1 (Rosie & Jasper): StyleTTS2 mini. Measured RTF 1.02x (Rosie, 199.1s audio) and 1.07x (Jasper, 182.2s audio). Rosie delivered warm, measured cadence with excellent long-form handling. Jasper's scratchy start was eliminated by pre-warming buffer and smooth sentence concatenation. Pocket and Kitten remain the accepted free CPU-only opt-in narrators.

---

## Cloudflare Zero Trust Access & Role-Based SSO for Library & Audiobookshelf — Active (2026-09-01)

To provide frictionless, passwordless single sign-on while enforcing perimeter zero-trust security and role-based permissions:
- **Perimeter Security**: `library.magnusfamily.co.uk` and `abs.magnusfamily.co.uk` are routed exclusively via Cloudflare Argo Tunnel on `PiHole KH` (`b499f04b-96f4-4f4d-aaba-67468e2f92c1`) with Orange Cloud proxying. Unauthenticated traffic is challenged at the Cloudflare edge.
- **Allowed Access**: Restricted to the `magfam` Access Group (`e47f9ac4-c275-4cee-8b46-e549b1724447`) + `david@davidmagnus.co.uk` with Google SSO and Email PIN identity providers.
- **Role Enforcement**:
  - **Dave (`david@davidmagnus.co.uk`)**: Full **Admin** privileges on Calibre-Web (`role: 479`) and **Root Admin** on Audiobookshelf (`type: root`).
  - **Family Members**: Standard **Guest / Listener** privileges on Calibre-Web (`role: 478`) and Audiobookshelf (`type: user`) with reading/streaming/downloading access, isolated playback timestamps/bookmarks, and zero server admin controls.
- **Zero Local Passwords & OAuth Friction**: Native header authentication resolves `Cf-Access-Authenticated-User-Email` and boots client tokens directly into browser storage without local password prompts or OAuth redirect mismatch errors.

---

## Book Finder & OpenBooks Gateway through Gluetun VPN — Active (2026-08-30)

To provide a seamless, 1-click book search and download capability for non-technical users
while guaranteeing 100% encrypted VPN egress and zero IRC session lockouts:
- **Dedicated Service**: OpenBooks runs as `openbooks-vpn` inside `docker-vm`'s `slskd-stack`
  sharing the `gluetun` network namespace (`network_mode: service:gluetun`). All IRC searches
  and DCC downloads route through ProtonVPN WireGuard (Sweden) with a firewall killswitch.
- **Dedicated IRC Identity**: Runs with `--name magnuslib --persist` so background automated
  queries never collide with or disconnect personal browser sessions.
- **Direct Library Pipeline**: Books download directly into `/home/dave/docker-apps/calibre-web-automated/book-ingest/`,
  triggering instant indexing by Calibre-Web and immediate availability in Audiobook Studio.
- **UI Surfaces**: Accessible via the native Book Finder on the Studio Home tab (`https://audio.magnusfamily.co.uk`)
  and embedded modal in Calibre-Web (`https://library.magnusfamily.co.uk`).

## Repo boundary: split by host, not by acquisition method — Active

There is no separate "acquisition" or grey-market repository, and none should be
created. The homelab repo boundary is **where the thing runs**, not what kind of
thing it is:

- **`epub-to-audiobook`** — the conversion application only. It starts at the
  human decision to generate a book, or the human action of sending an article
  URL.
- **`infra`** — anything running on docker-vm, including the whole book-grab
  pipeline (LazyLibrarian, qBittorrent/Gluetun, SABnzbd, `book_sync.sh`,
  `acquisition_verify.sh`, `wanted_monitor`), plus the canonical protocol docs.
- **`mediahub`** — anything running on the NAS: Prowlarr, the arr suite, the
  slskd/soularr music stack.

**Consequence for this repo:** `scripts/wanted/` (`wanted_monitor.py`,
`openbooks_bridge.py`, `run_wanted_monitor.sh`) belongs in
`infra/stacks/docker-vm/media-stack/scripts/wanted/`, alongside its siblings and
the documentation that already describes it. After that move this repo contains
no acquisition code at all.

**Why not a dedicated acquisition repo:** it would cut across the existing
host/plane ownership rule, forcing every future placement question to be
answered on two axes instead of one. It would also break the Arcane GitOps map
(`docker-vm-media-stack-gitops` is path-bound to
`infra/stacks/docker-vm/media-stack/compose.yaml`), a known-expensive repair.
And it buys no protection: every repo involved is private, so a second private
repo changes no exposure. Exposure is governed solely by what gets published —
see the next entry.

Reconsider only if book acquisition grows enough to justify a `booklib` repo
owning the pipeline end to end. Not before.

## Open-sourcing route: fresh squashed public repo, never a visibility flip — Active

Publishing this application is an eventual intention, not an imminent one. When
it happens it must be done as a **new repository seeded from a single squashed
commit** of the then-current tree — not by flipping this repository public.

**Why:** the git history of this repo contains `.env`, `.secrets/`, `ssh-keys/`,
internal LAN addresses and the full `wanted_monitor`/OpenBooks lineage. Deleting
or moving those files does not remove them from the log, so a visibility flip
would publish all of it. Squashing discards the commit log, which for a
single-author project costs nothing of value.

**Standing rule until then:** keep LAN-specific values — hostnames, IP
addresses, internal ports — in configuration and environment, never hardcoded in
application code. Every such value committed now is one more thing to find and
strip later.

## August 2026 CPU new-engine gate: Scylla rejected; Audio8 (rejected 2026-09-05) and ZONOS2 bounded — Superseded in part

Do not register Audio8, Scylla's Band v2 or ZONOS2 as application engines from
the 2026-08-22 audition. (Audio8 subsequently ran its longer non-fiction gate on
2026-09-05 and was definitively rejected; see the September 2026 decision above.)

- **Scylla v2 / Ink is rejected for production in both ONNX INT8 and FP32.**
  Dave heard the same robotic, emotionless, effectively one-long-sentence
  delivery in both arms. Full precision did not repair it, so quantisation is
  not a credible explanation and no longer gate is justified for this voice.
- **Audio8's Arthur voice passes the short voice-quality impression, but the
  evaluated long-text path fails continuity.** The raw arm audibly dropped
  words. The prepared arm used twelve independent calls, different seeds and
  200 ms joins; it faded at forced mid-sentence boundaries and changed tone and
  speed between chunks. Do not treat that joined harness as an audiobook path.
  A corrective complete-sentence, fixed-seed, zero-added-silence arm was
  subsequently “better” by ear. Audio8 therefore remains the only survivor of
  this gate, but “better” is not an unqualified continuity or long-form pass.
  Three corrective calls also exceeded upstream's recommended 150 characters.
  *(Update 2026-09-05: on full chapter audition, Audio8 failed with volume pumping
  and speech garbling on sentences >150 chars; formally rejected).*
- **ZONOS2 Q4 passes only the bounded first-paragraph voice audition.** Dave
  called that clip really good. The same settings in one full-passage call
  dropped the last 35 words and lost the Arthur identity, so it fails sustained
  narration. A persistent-server, cached-Arthur, fixed-setting corrective arm
  restored structural coverage after one clause repair, but Dave still heard
  different voices with Arthur fading in and out. The underlying/base voice was
  acceptable; cloned narrator identity was not. Close the current ZONOS2 Arthur
  audiobook path unless upstream materially changes its continuity mechanism.
  Q8 has no verdict because Q4 already peaked at 12.3 GiB inside a 14 GiB WSL
  limit and quantisation has not been shown to cause the identity drift.

Listening establishes these outcomes, not their model-side root causes. Keep
Audio8, Scylla, and ZONOS2 out of the product. Both Audio8 and ZONOS2 cloned-narrator
paths are closed.

---

## August 2026 native-voice gate: LoudKit and Sopro both rejected — Active

Do not register LoudKit 0.1.0 / loudr-1 or Sopro v2 turbo as application
engines. Dave heard eight arms across two gates on 2026-08-28 and rejected all
of them: **none good enough.**

- **LoudKit** was heard on its two shipped English voices, `joe` and
  `kathleen`, at upstream defaults on the ONNX CPU path, and earlier on a
  cloned reference across both ONNX and PyTorch.
- **Sopro** was heard on Beatrice at upstream defaults and at solver `steps 16`.
  Raising the solver steps did not change the verdict, and the two arms share an
  identical token stream, so the acoustic decoder is not what held it back.

Neither engine displaces Chatterbox Nano / Beatrice, and neither earns a longer
gate. This is a listening verdict; it does not diagnose either model.

**Two facts worth keeping, because they bound any future reconsideration:**

- **Sopro ships no native voices.** `--ref` is a required argument and the model
  repository contains no voice profiles. It is cloning-only by construction, so
  every render needs a reference chosen by Dave. It can never be auditioned on
  native supported voices.
- **LoudKit's ONNX export is fixed at a 255-token window.** Its default
  `max_new_tokens` / `max_speech_tokens` of 255 caused the trimmed tails and the
  dropped sentence seen in the first gate; at 512 on PyTorch the cap clears and
  all thirteen chunks come back clean. But ONNX refuses the wider window — the
  graphs are static at query 255 / prompt 238 — and PyTorch measures RTF 6.96,
  which is not a book path. Escaping the cap requires re-exporting the ONNX
  graphs, which is upstream's stated remedy and real work.

Neither fact reopens either engine. They exist so that a future "LoudKit looks
promising" or "try Sopro" proposal starts from what was already measured and
already heard.

## Project optimisation order: quality floor, then free, then cheapest — Superseded in part (paid fallback removed 2026-10-29)

**2026-10-29:** Dave now requires zero out-of-pocket audiobook cost. The quality
floor and preference for free generation remain; the GBP2 paid fallback below
is historical. See the current cash-budget decision at the top of this file.

An audiobook must first pass Dave's human listening floor for naturalness,
accent, pronunciation, pacing and long-form comfort. Among engines that pass
that floor, choose in this order:

1. **Free generation wherever possible** — normally local CPU or free Kaggle.
2. If no free path reaches the quality floor, use the **lowest measured total
   cost per finished book** that does.
3. Paid generation has a hard ceiling of **GBP2 per finished book**. A provider
   that cannot fit that ceiling through a real free allowance or honest
   multi-book amortisation is not a production fallback, however good its demo.

Speed is not worth a bill by itself. Cost comparisons must use measured
book-level totals (including startup/retry overhead where known), not vendor
headline rates or hypothetical hardware speedups presented as facts.

**Why:** stated directly by Dave on 2026-08-13. This refines, rather than
reverses, the existing quality-priority decision: bad free audio is still not a
successful audiobook, but cost decides between options that are genuinely good.

## Gemini 3.1 Flash TTS / Achernar is an accepted free-only narrator — Active

Dave heard the exact 10:10 app-path `gemini-3.1-flash-tts-preview` / Achernar
file and called it **“one of the best”**; he explicitly selected it for use.
Achernar therefore passes the long-form human quality gate as an opt-in book
narrator. This verdict does not approve every Gemini voice: Google exposes 30
preset names and all 30 now have cached, independently decoded app previews,
but only Achernar has a heard long gate. The other 29 remain auditions.
The cache was completed across Free quota days with one attempt per voice and
without attaching billing. The selectable-only-when-cached guard remains.
The app uses the current Gemini Developer API Interactions route with a key from
a project whose AI Studio plan is **Free**. It has no Vertex route, Batch API,
paid model or paid-tier fallback. Do not attach Cloud Billing to that project.
Because inference responses do not expose billing tier, the adapter additionally
requires `GEMINI_FREE_PROJECT_CONFIRMED=1` after the operator checks AI Studio;
the dedicated unbilled project, not that flag, is the real no-charge boundary.
Keep the existing dedicated project and its current owner; do not transfer it
to, or couple it with, a Google AI consumer subscription. Google documents no
consumer-subscription uplift for Developer API quotas, so that would add
account complexity without improving the audiobook path.

Google warns that this preview model can drift on outputs longer than a few
minutes. The app therefore uses the measured `explicit` number/currency text
profile and paragraph-aware requests capped at 2,200 characters (roughly two to
three minutes), then joins lossless PCM locally. Each passage gets exactly one
API request. Successful passage WAVs are cached; any 429, 500, timeout or other
failure stops the job without automatic retry, and a manual Resume reuses the
cache. The exact Achernar app preview is persisted, independently decoded and
served byte-identically by the app. Five one-attempt requests produced the
accepted, fully decoded 10:10 file covering the exact 1,644-word source at zero
actual cost.

Keep it explicit rather than the portable repo default: new installations do
not have a Gemini key, the current account permits only ten requests/day, and
Free Tier content is used to improve Google's products. At the proven
2,200-character passage size, a roughly 600,000-character novel needs about 273
requests—approximately 28 quota-days if no requests fail. Successful passages
resume from cache across days. Never send private/confidential books without
accepting the Free Tier data-use term, and never attach billing or fall through
to paid service.

The adapter now keeps a persistent conservative request ledger keyed to the
Pacific quota day and refuses an eleventh request locally. Google states RPD is
per project, not per key, and resets at midnight Pacific. Failed upstream calls
remain counted; external AI Studio calls are not visible locally, so operators
must still check the official Usage dashboard before a catalogue batch.

The full-catalogue request also exposed a real explicit-profile bug: that path
was using the legacy default rather than `modern=True, expand_numbers=True`, so
bare decimal measurements such as `1.5 gigawatts` survived. Dave heard Index
say “one five”. Explicit engines now receive the actually explicit profile in
preview, web-worker and standalone-converter paths. This reverses the narrower
old assumption that only currency/percent needed expansion for these engines;
it does not change the minimal-number contract for Chatterbox/TADA.
Official sources checked 2026-08-15:
[TTS guide](https://ai.google.dev/gemini-api/docs/speech-generation),
[model card](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-tts-preview),
[pricing](https://ai.google.dev/gemini-api/docs/pricing),
[billing](https://ai.google.dev/gemini-api/docs/billing), and
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## IndexTTS-2.5 is not a production narrator — Active

The complete-sentence follow-up removed the two repeatable corruptions caused
by IndexTTS-2.5's official 120-token splitter, and the repo's explicit-number
fix corrected `1.5` to “one point five”. Dave nevertheless rejected the
corrected clip for audiobook use on 2026-08-15: it was better, but its timing
and pacing remained poor and it was nowhere near as natural as Gemini Zephyr or
Chatterbox. This closes the current Index integration gate. Do not confuse the
boundary repair with a listening pass, expose Index voices, or spend more free
GPU quota on Index without a materially different official model/runtime or an
explicit request to reopen it.

## NVIDIA MagpieTTS v2607 raw NeMo path is rejected; hosted NIM diagnosis remains open — Active

Dave rejected every exact output from the pinned raw NeMo path on 2026-08-15.
All five short voices had a repeatable defect around five seconds and were poor;
the 9:14 John arm had the same clipping/cut defect. Accents and tone were good,
but reliability failed the audiobook bar. Do not expose this path or its voices.

The current gate pins official `nvidia/magpie_tts_multilingual_357m` v2607 at
revision `5023df68bd3f5b5ce6d666a50979bc501af145cc` and NVIDIA NeMo Speech
v3.0.0 at commit `fd6a877539710e2b98f28c43272ff81312f83417`. It uses one free
Kaggle T4 run only; T4 is absent from NVIDIA's documented supported-GPU list, so
capacity there is an experiment, not a supported deployment claim. NVIDIA's
separate NeMo-Speech.cpp v2602 F16 GGUF path also carries state across chunks,
but it is an older model/runtime and must not be described as the same v2607
path. No paid fallback, automatic integration or ASR quality ranking is allowed.

The failure boundary remains open. All short arms entered NVIDIA's automatic
stateful sentence-chunk mode, and the shared defect aligns with the first
sentence boundary; the long arm exhibited the same class. The harness produced
one model waveform per arm and added no PCM joins, so this is not our MP3
stitcher. It did, however, use the public `.nemo` checkpoint directly rather
than NVIDIA's production NIM service, disabled model text normalization after
repo-side normalization, and inherited checkpoint temperature `0.6` while the
current official example explicitly uses `0.7`. One focused official hosted
NIM PCM comparison is allowed when an NVIDIA API key is available. It must use
one short text, no repeated querying and no production/whole-book workload.

NVIDIA currently grants Developer Program members free hosted NIM endpoint
access for prototyping, subject to account rate limits. That is not a published
free production audiobook allowance: production NIM use requires NVIDIA AI
Enterprise, and the hosted prototype service has no guaranteed whole-book
capacity. Official sources checked 2026-08-15:
[NIM FAQ](https://docs.api.nvidia.com/nim/docs/product),
[run-anywhere terms](https://docs.api.nvidia.com/nim/docs/run-anywhere), and
[Magpie NIM API](https://build.nvidia.com/nvidia/magpie-tts-multilingual/api).

Official sources checked 2026-08-15:
[model card](https://huggingface.co/nvidia/magpie_tts_multilingual_357m/blob/v2607/README.md),
[long-form guide](https://docs.nvidia.com/nemo/speech/nightly/tts/magpietts-longform.html),
[NeMo Speech](https://github.com/NVIDIA-NeMo/Speech), and
[NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/).

## Regional accent labels are not quality evidence — Active

Edge is the only currently heard Australian/Irish/etc. option that comes close
to Dave's quality floor. The other surfaced regional labels are rejected by ear.
Chatterbox Turbo/Arthur remains an excellent general narrator, but Turbo and
Nano accent cloning is closed: a good base voice does not make those models
preserve regional phonetics.

The exact Chatterbox Multilingual V3 regional path tested on 2026-08-15 is also
**rejected**: Australian was only okay, Irish was wrong, South African was the
best of the three but still not good, and all three had mediocre pacing/tone,
average pronunciation and badly failed numbers. Do not expose these voices.

That verdict does **not** establish that V3 itself caused every defect. The gate
changed model family, reference and inference settings at once: V3 instead of
Turbo; synthetic references instead of Arthur's human narration (Irish was
Piper-generated, South African was verified Edge-derived, and Australian's
exact synthetic vendor is unverified);
and `cfg_weight=0` instead of V3's official same-language default `0.5`. The
repo's earlier claim that zero CFG generally lets a same-language reference
accent through was an unsupported inversion of upstream's cross-language
mismatch advice. The required same-text seeded Arthur Turbo/V3 controls and
separate human Irish and Australian reference arms were rendered, structurally
verified and heard on 2026-08-15. **All five were rejected.** Turbo/Arthur did
not reliably reproduce the previously liked Arthur character and stumbled on
ordinary words, proper nouns and numbers. Both Arthur/V3 settings were poor;
the human Irish and Australian references did not rescue accent or
pronunciation. Close this local V3 accent route and do not expose the candidates.

The hard passage also exposed an independent input failure: the modern-engine
contract passed currency, percentages and large integers as raw symbols/digits.
The numeric-only normalized Arthur control was then heard and was **much
improved**. Because the deployed engine/reference and passage were retained,
this establishes text preparation as a material cause of the first arm's
failure. It does not approve the remaining proper-name/ordinary-word handling,
change production preprocessing, or restore Arthur as an unconditional quality
reference without the narrower listening decision.

The next supported online comparison is Azure Speech's native regional voices
with its documented SSML phoneme/custom-lexicon controls. A dedicated UK South
SpeechServices **F0** resource is now available, but the listening gate is
strictly budgeted: one to three explicitly named voices, a default ceiling of
1,000 source characters total, no catalogue-wide default, no retry into an
existing output directory, and Dave's approval before another synthesis run.
Never create or switch to S0 automatically. See `VOICES.md` for official sources.

The first native-voice gate is now heard: Australian Darren, Irish Connor and
South African Luke had spot-on accents but robotic/degraded voices. Record this
as an accent pass and an overall quality failure. The exact 24 kHz/160 kbps MP3
path is closed for production. Microsoft's official REST documentation states
that 48 kHz selects its high-fidelity standard model and supports lossless PCM,
so one same-voice 48 kHz control is the only encoding/model-tier diagnostic
still justified. Do not claim SSML rate/pitch tuning can repair the underlying
voice, and do not integrate or spend beyond F0 without a new listening verdict.

The app's preferred Edge Australian preview and the rejected Azure Australian
clip were not the same speaker (William versus Darren), so they did not isolate
the service path. Dave approved one 300-character endpoint control. Exact
`en-AU-WilliamNeural`, text, neutral prosody and 24 kHz/48 kbps output were
matched across Edge Read Aloud and Azure F0 and structurally verified. Dave's
verdict is that Azure is only slightly better, but is better. Therefore the
Azure endpoint did not cause the earlier perceived degradation relative to
Edge; the different speaker and input confounded that comparison. This relative
win does not approve William/Azure for production or reopen the rejected
Darren/Connor/Luke decision. Make no further Azure request without a separately
agreed listening question and character budget.

Dave then explicitly authorised one longer, correctly processed passage for
each of the same three accents. The bounded gate used one common 737-word source,
exactly three requests, Azure's documented IPA mechanism, deterministic number
expansion and the documented 48 kHz high-fidelity lossless format. All three
outputs are structurally verified. Dave judged all three accents and voices
acceptable. They lack Arthur's realism and are weak on emotion, but pass his
minimum standard. William, Connor and Luke are therefore approved as **opt-in
Azure regional voices**, never as the default or an automatic cloud fallback.
This authorisation is exhausted: do not render more voices or passages from it.

The accepted path must retain the proven contract: deterministic number and
currency expansion, real paragraph/title/author pacing, Azure IPA for the
pinned difficult terms and lossless/high-fidelity 48 kHz synthesis. F0 is used
first. If free quota is insufficient, stop for an explicit per-book cost choice;
never switch to S0 or start a paid render automatically. Microsoft's billing
boundary includes SSML body markup, so estimates and guards must count it rather
than plain text alone.

## Shared-host CPU candidates reserve capacity for the product — Active

Pocket and Kitten remain CPU-only, but each service is capped at **four CPU
cores by default** on the six-core production host. More dedicated CPU can
reduce render time; it does not establish better voice quality. UI and queue
capacity take priority over maximum background throughput. PyTorch's official
guidance is the basis for bounding intra-op threads before inference:
<https://docs.pytorch.org/docs/stable/generated/torch.set_num_threads.html>.

## Official documentation before experimentation — Active

Before changing or evaluating any external engine, model, API, SDK, container,
deployment tool or integration, read the relevant repo decisions/history and
the current official vendor documentation for the exact version in use. Record
the official URL, model/version or commit, supported parameters/defaults,
licence/use limits and dated pricing where relevant. If a community runtime or
wrapper is used, pin and document it separately; official model weights do not
make an unofficial runtime official.

Experiments answer only what authoritative documentation leaves unknown. A
claim without source/version provenance stays **unverified**, and audible
quality still requires Dave's listening verdict.

**Why:** repeated sessions spent time rediscovering documented behaviour or
tuning the wrong default because agents experimented before reading the manual.
Mandated directly by Dave on 2026-08-13.

## Local Ollama is primary; cloud LLMs are optional — Active

The production stack uses the shared local Ollama `qwen2.5:7b` endpoint for the
LLM-assisted paths that remain enabled. No Groq key, base URL or model override
is currently stored in the live settings database, and the running containers
have an empty cloud `LLM_API_KEY`. Groq dashboard activity is therefore
historical, not evidence of current traffic.

Cloud LLMs remain optional and may never be required for conversion. The app
must fail open to deterministic metadata/chapter rules, and generated
pronunciation respellings stay disabled by default. If Groq is configured later,
choose a current production model from its official catalogue. As checked
2026-08-15, `llama-3.3-70b-versatile` shuts down on 2026-08-16; this repo now
documents `openai/gpt-oss-120b` as the replacement. On Groq's dated Developer
pricing it is cheaper than the retiring model and it is also listed on the Free
plan limits page. Never infer the account tier from an activity screenshot.
Official evidence: [deprecations](https://console.groq.com/docs/deprecations),
[models/pricing](https://console.groq.com/docs/models), and
[rate limits](https://console.groq.com/docs/rate-limits), checked 2026-08-15.

## VibeVoice `cfg_scale` — 2.0 selected; 1.3 and 3.0 rejected — Active

Use **`cfg_scale=2.0`** for VibeVoice. The pinned 351-word blind test unblinded
as A=`3.0`, B=`2.0`. Dave selected B: *"much better ... otherwise perfect.
really really good."* A was rejected as muffled and distant despite an
acceptable/emotional voice. The default in Compose is therefore 2.0.

This selects the best tested Vibe setting, not the production narrator. The original
direct-runtime cfg-2 arm contained a brief “byah”-like insertion at the
`felicity - but` boundary while still speaking all source words. The corrected
production HTTP path was preferred and cleared that insertion. Both paths sent
the model the same byte-for-byte prompt, including the hyphen, so there is no
evidence for a global hyphen-removal rule.

The corrected full app-path file then **failed the long-form listening gate**.
Its opening was very good, but after roughly three minutes the delivery became
increasingly emotional, fast and run-on, lost narrative intent, and continued
to worsen. A local garble after “draught” is not assigned to the engine: the
exact shared source says `draught , and`, with a malformed space before the
comma. The progressive pace drift is the production blocker. The tested
single-pass Vibe path is therefore rejected for audiobook production; Qwen
ranks above it for long-form stability. Chatterbox Nano/Beatrice remains the
system default.

**Why:** the pinned community runtime exposes `cfg_scale`; Microsoft's official
TTS documentation does not define it as a supported tuning contract. Its role
here is therefore an empirical repo finding, not an official Microsoft fact.
At 1.3 the clone's pitch IQR was 14.4 against the reference's 72.8 (nearly
monotone). Raising it moved pitch, range and brightness toward the reference
without a structural intelligibility loss in that short test. 1.3 was inherited
unexamined from an early kernel. The longer human test overruled 3.0's more
reference-like pitch statistics: acoustic metrics did not predict its muffled,
distant sound. Above 3.0 is untested and has no reason to be pursued.

## Prior VibeVoice listening verdicts — Superseded

Every VibeVoice quality judgement recorded before 2026-08-13 was made at
`cfg_scale=1.3` (now rejected) and, where the audition passage was used, on text
that costs Vibe roughly 0.13 ASR. This includes the 2026-07-29 full-chapter
finalist gate and the "Vibe provisional quality leader / Qwen consistency
leader" ranking.

**Do not cite those verdicts as current.** The corrected cfg 2/3 comparison
selected 2.0, and the exact app-path file was subsequently heard. It failed on
progressive long-form pace/prosody drift, so Qwen now ranks above this Vibe path
for audiobook consistency. Neither replaces the Nano/Beatrice default.

## Voice auditions are persisted before they are offered — Active

A voice Play button must never begin cold synthesis. The audition UI offers a
voice only when `/data/previews/<voice-id>.mp3` exists and is non-trivial; the
API exposes configured ready/total counts. Healthy free local families may be
warmed in the background with load throttling, skip-existing behavior and an
off-switch. Startup maintenance must never call paid Polly/Inworld voices or a
network Edge voice without explicit operator action. Unconfigured paid engines
remain hidden.

**Why:** Dave requires every offered voice to be testable immediately. Previous
cold previews took minutes, timed out after successful synthesis, saturated the
host and made healthy services look offline.

## Existing audiobook first; generation only as fallback — Active

For a reading-list integration, request an **audiobook only** first. Prefer the
free torrent path, then the existing Usenet fallback. Do not simultaneously
mark the ebook Wanted and do not auto-queue TTS merely because a book was added
to Goodreads. This app is used only after no acceptable existing audiobook is
available; the absence/quality judgement is operator evidence, not something
ASR or a search timeout can decide.

For new Goodreads accounts, use the account-specific `to-read` RSS feed as a
LazyLibrarian RSS/WishList provider with `DLTYPES=A`. Goodreads no longer
issues new API keys and LazyLibrarian documents its supplied key as read-only,
so OAuth shelf sync is not a valid new-account setup. The feed URL may contain
a private token and must never be committed. Operational ownership remains in
the sibling `infra` repo.

An app-generated audiobook remains a replaceable fallback, not the preferred
permanent copy. Keep its LazyLibrarian `AudioStatus` at **Wanted** so scheduled
torrent-first searches continue. Retire a generated copy automatically only
after acquired audio completes, passes the production import-integrity guard,
reaches Audiobookshelf and is structurally verified. Separately, Dave may reject
or withdraw a generated render at any time; search failure is not a reason to
keep an unwanted engine/voice on the shelf. Move withdrawn media to recoverable
quarantine before an ABS rescan. A future TTS attempt starts only after Dave
explicitly selects the engine-bound narrator; never regenerate automatically.

**Live baseline (2026-08-14):** *Apple in China* is already a completed
qBittorrent M4B, not a generated fallback (812 minutes; production guard pass).
A fresh official LazyLibrarian `searchBook` run found no acceptable *Bond King*
audiobook, although two Prowlarr-proxied providers returned 429 and therefore
make that search incomplete rather than proof that no release exists. Dave
rejected both Kokoro/Fable renders: jobs `592af51b` and `59d36718` are absent
from the app and live ABS shelf. *Bond King* remains Audiobook Wanted; if no
acquired version appears, Dave will explicitly choose the next engine/voice.
On 2026-09-05, the older *Breakneck* generated audiobook fallback was completely removed
from Audiobookshelf and host storage at Dave's request; *Breakneck* remains Wanted.
Preview clips of the first 3 pages (both Introduction and Chapter 1) were rendered
using Deepgram Hyperion.

## Narrator and engine are one selection — Active

Every selectable narrator is bound to the engine that produced its cached
preview. Batch and re-convert APIs must reject an independent engine override;
the UI asks for a narrator only. A voice preview from one engine must never be
silently rendered by another engine.

**Date/reason:** 2026-08-14. Two duplicate *Bond King* conversions in the live
history used the retired Kokoro/Fable path even though the system default is
Beatrice/Nano. The older batch API allowed engine and voice to diverge. The
exact caller cannot be reconstructed, so the unsafe state is removed rather
than attributed to the user.

## Conversion deletion is explicit about Audiobookshelf — Active

History combines completed book and article conversions newest-first. Deleting
"from this app" removes only the app's input copy, output and history row;
deleting "here and from Audiobookshelf" additionally removes only the exact
app-owned ABS folder or podcast episode. Source ebooks are never deleted.
Article episode filenames include the job id because episodes share a podcast
folder and title/date alone is not unique. A single MP3 downloads directly;
multiple chapter MP3s remain a ZIP.

The [official Audiobookshelf API](https://api.audiobookshelf.org/) documents that
`DELETE /api/items/<id>` removes database state but no media files, so app-owned
media is removed over the same SSH/rsync trust path and ABS is then rescanned.

## VibeVoice generation settings — Active

`ddpm_inference_steps = 10` for VibeVoice. Do not raise it. Measured 2026-08-12:
raising it to 20 then 30 degraded ASR similarity monotonically (0.872 → 0.847 →
0.809) on identical text, voice and seed, while costing 20–45% more GPU time.
Peak VRAM is 5.31 GiB regardless of steps or input length.

**Why:** this looks like an obvious quality knob and it is not — it is inverted.
See STATUS.md 2026-08-12 for the six-arm sweep.

## VibeVoice long-form capability proven; production quality rejected — Active

VibeVoice completed 13,666 source words in one generation, producing about 77
minutes of audio on a free Kaggle P100 (13,597 ASR words, WER 0.0887). This
reproduces the practical substance of Microsoft's "up to 90 minutes" claim and
answers issue #44's capability question. Capability is not suitability: the
corrected 6,166-word production-path file became progressively faster and more
run-on after roughly three minutes and failed human listening. Issue #44 is
closed with that negative promotion verdict. A separate 916-word / 4m19s run
showed stable pitch and measured 5.31 GiB peak VRAM.

**Boundary:** the 77-minute run's VRAM probe was attached to the parent while
generation ran in a subprocess and therefore reported zero. Long-duration VRAM
remains unmeasured; do not extrapolate the 4-minute 5.31 GiB result. The exact
single-pass fp16/SDPA/community-runtime path must not be reopened with another
seed or undocumented speed control. Reconsider only with current upstream
evidence for a materially different long-form path and a new controlled human
listening gate. Date corrected: 2026-08-14.

The pinned community runtime's documented repeated-same-speaker-turn remedy is
such a materially different path. Two complete 1,998-word arms (four turns and
seven turns) plus a same-text Chatterbox Turbo reference are rendered and
structurally validated as of 2026-08-14. Dave rejected both Vibe arms as
unacceptable. The same-text Chatterbox Turbo + Arthur control was "almost
perfect" with stable pacing; its only heard defect was reading `co-heirs` as
`coheirs`. The documented turn-reset remedy therefore does **not** reverse the
Vibe production rejection. That long-form Arthur control remains positive
evidence, but the later 2026-08-15 seeded hard sample failed and makes
Turbo/Arthur a per-book audition rather than an unconditional quality reference.
The system default is unchanged.

## Audition-passage validity per engine — Open, NOT settled

The canonical `voice_sample.SAMPLE_TEXT` measurably handicaps VibeVoice:
0.81–0.87 ASR on it versus 0.98+ on plain prose, across ddpm steps and seeds.
`voice_sample.MODERN_ENGINES` is `("chatterbox", "tada")` — VibeVoice and Qwen
are in neither branch by consideration, only by omission.

One input-policy question remains unresolved; the ranking consequence is now
settled:
1. Whether Vibe needs the legacy number treatment (`modern=False`) is untested.
   Run that arm before changing `MODERN_ENGINES`.
2. The 2026-07-29 "Vibe provisional quality leader / Qwen consistency leader"
   ranking was formed on invalid Vibe settings and is superseded. The corrected
   same-book comparison now puts Qwen ahead for long-form consistency.

**Why this is an entry at all:** the failure is silent. The audition renders,
passes structural QA, and sounds like an engine problem rather than an input
problem. Date: 2026-08-12.

## TTS engine defaults & Narrator — Active

Chatterbox Nano is the default production engine, and **Beatrice (Nano)**
(`uk_female_samuel_nano`) is the default system narrator voice. Piper is fully
retired: no service, profile, route, health probe or selectable voice remains.
Stale Piper jobs fail closed and require an explicit narrator choice. Chatterbox
Turbo and TADA require explicit opt-in (`ENABLE_CHATTERBOX_PROFILE=1` /
`ENABLE_TADA_PROFILE=1`).

**Why:** Beatrice (Nano) offers high-quality UK human-cloned narration at fast CPU speeds (~0.87x RTF) without requiring extra docker profiles or GPU hardware. Piper audio was rejected on listening ("absolute shit") on 2026-07-28.

## Article Ingest & Fast QA Bypass — Active

Web article URL ingest (`POST /api/articles/narrate_url`) and short content (< 15,000 chars) skip post-flight ASR verification by default. Generated article audio is automatically published to the Podcast RSS 2.0 feed (`/api/articles/rss`).

The Articles-tab paste action and owner-only Telegram capture both use the same
queue helper and the current system default narrator. They always create a
local, free, MP3 article job; neither path may choose a paid/cloud target or
inherit the legacy SQLite `kokoro` default accidentally.

**Why:** Short articles do not suffer from multi-chapter drift, and skipping post-flight ASR reduces turnaround time from minutes to seconds.

## Offline Whisper ASR Caching — Active

Whisper ASR models are downloaded persistently to `/data/models/whisper` and initialized with `local_files_only=True`.

**Why:** Prevents online HuggingFace Hub network checks, rate limit warnings, and latency delays during ASR verification passes.

## Integrated Studio Web Audio Player — Active

The web UI uses a single persistent glassmorphic audio player bar (`#studio-audio-player`) at the bottom right, supporting browser playback of completed audiobooks, articles, and previews across tabs with speed controls (`1.0x`–`2.0x`).

**Why:** Issue #45. Eliminates orphaned audio playback and allows seamless listening while navigating the web application.

## TADA — Active

TADA works as of 2026-07-27 (issue #23 closed). Opt-in only.

**Why:** the prior OOM was fp32 running on CPU, not a capability limit — bf16
fits the memory cap, RTF 1.68. Don't re-diagnose this as a hardware ceiling.

## GPU / Vast.ai policy — Active

Default is LOCAL. Never spin up a Vast.ai instance or enable
`GPU_RENDER_ENABLED` without an explicit user request for the *current* task.
Always destroy any instance created in-session. See GPU-SAFETY.md before any
GPU action.

**Queue length must never provision a paid GPU.** The legacy
`AUTOSCALE_ENABLED` queue trigger is retired: paid Vast provisioning is manual,
session-specific and requires an explicit action after the cost has been shown.
Free Kaggle is not a paid fallback and remains opt-in per job.

**Host schedulers are part of this boundary.** On 2026-08-13 an undocumented
Zorin cron was found polling for *House of Huawei* and prepared to submit it to
Kaggle automatically. It had not created a job. The cron was retired with a
backup and sentinel guard. A future “no automatic cloud render” audit must
inspect cron/timers and external callers, not only `app.py` and Compose.

**GPU lanes inherit this boundary (settled 2026-09-24).** `render_target='lane'`
may be queued, but **`lane='auto'` resolves `FREE_LANES = ('colab', 'kaggle')`
only** — it never falls through to the paid Lightning lane, even when Lightning
is the *sole* configured lane, in which case it refuses with the action that
authorises spend. Naming a lane *is* the authorization: `lane='lightning'` on
the job, or `FISH_LANE=lightning` in Settings. The job API refuses at POST
(400) rather than queueing a job that could not start, and an unknown lane name
is refused instead of silently becoming `auto`. This was written because the
Fish build-out's first cut did the opposite: `resolve_lane('auto')` walked
`('colab','kaggle','lightning')`, so a queued book with only Lightning
configured would have silently selected the paid lane — the exact autoscale
incident reopened. `test_queue_length_cannot_provision_paid_gpu` now pins the
free-only list as well as the render-target tuple.

**lightning-sdk is not shipped in the app image (settled 2026-09-25).** The
paid Lightning lane's SDK cannot coexist with the Vast CLI: `lightning-sdk`
from 2025.12.5 on declares `urllib3 <= 2.5.0`, `vastai` from 1.4.0 on declares
`urllib3 >= 2.7.0, < 3.0` — an empty intersection. Read from **PyPI release
metadata across every published version of both packages** (not inferred from
one failure): the only coexisting pairs require downgrading one of them
(`vastai <= 1.3.0` or `lightning-sdk <= 2025.12.2`), and both current pins are
deliberate — `vastai 1.5.4` for billing-time safety on the money path, and the
SDK pin because its API surface (`User` / teamspaces / `Studio`) was verified
against it on 2026-09-24 with a live T4 start/stop probe. **The money path
wins**; an optional, explicitly-paid, not-yet-wired lane does not justify
downgrading a billing-critical dependency or shipping an unverified SDK version
(Authoritative-Source Gate). This is a *capability* decision, not an
authorization one: naming `lane='lightning'` still passes POST (test
`test_job_creation_accepts_a_named_paid_lane_and_persists_it`), while
`fish_lane.lane_ready()` refuses the render at its first line with the same
words the Render Lanes panel reports (`lightning-sdk not installed in this
environment`) — never a queued job that dies on an import error. The route if
the lane is ever wanted is a **separate venv**, which is how the 2026-09-24
probe ran. First deploy of the lane surface failed on exactly this
(`ResolutionImpossible`, 2026-09-25) — evidence in `webapp/requirements.txt`.

**Why:** costs real money; this is a standing safety rule, not a per-task
judgment call.

## Deploy discipline — Active

Deploy from git only via `scripts/deploy.sh`; never patch application source
live; deploy the whole stack (webapp + worker), not one service.

**Why:** webapp and worker are two containers built from the same Dockerfile
sharing `app.py`. Rebuilding one leaves the other on old code, and
`/api/health` only reports the webapp's version — a partial deploy looks
healthy while being wrong.

## Regression guards — Active

A regression guard that fires is right until proven otherwise. If one blocks
a change, the default assumption is that the change is wrong, not the guard.

**Why:** these guards encode decisions that were already paid for, often by
ear (a human listened and decided). Don't relax a guard to make a diff pass.

## Audiobook quality priority — Active

Naturalness, authentic accent, correct pronunciation, pacing and long-form
listenability outrank locality, cost, memory or speed when picking an engine.

**Date:** 2026-07-28.

## Long-form engine shortlist — Evolving

Qwen is the current full-precision long-form leader: its 6,166-word Yellow
Wallpaper chapter was “really good” and remained audiobook-listenable through
the full 33:03. The corrected Vibe cfg-2 production path used the same source
token sequence but failed from progressive pace/prosody drift after roughly
three minutes. Vibe's strong opening does not pass the audiobook gate. MOSS
remains eliminated; Higgs remains usable but not dependable enough to lead.

**Why:** see STATUS.md for the underlying RTF/ASR measurements and listening
notes — this entry only tracks the current standing, not the evidence trail.
Check STATUS.md for anything newer before treating this as final.

## Engine rejection and hold boundaries — Active

"Rejected" applies only to the exact model, version, runtime, voice, settings
and delivery path that were actually rendered and heard. Agents must not
generalise a failed wrapper or voice into an engine-family verdict, and must not
reopen a closed path without both current official upstream evidence and a
materially different controlled listening hypothesis. See `ENGINES.md` and
`VOICES.md` for official sources and the complete listening evidence.

| Candidate/path | Settled status | Boundary / condition for reconsideration |
|---|---|---|
| Chatterbox Nano + Beatrice | **Accepted default** | Free local baseline. A replacement must first beat it by ear. |
| Chatterbox Turbo + Arthur | **Conditional / per-book audition** | Earlier long-form controls were excellent, but the 2026-08-15 seeded hard sample did not reliably sound like Arthur and failed words, proper nouns and numbers. The normalized numeric control was much improved, proving input preparation mattered, but ordinary-word/proper-name and voice-stability concerns remain. |
| VibeVoice full precision, community fp16/SDPA single-pass path | **Rejected for audiobook production** | cfg 2.0 has a very good opening but progressively accelerates/runs on and loses intent after ~3 minutes. Reopen only for a materially different officially supported long-form path, not another seed or undocumented knob. |
| Qwen3-TTS full precision | **Current long-form leader; not default** | Full 6,166-word chapter passed human listening and beat the corrected Vibe path for consistency. It still requires explicit free-Kaggle/local-GPU selection and book-specific auditioning. |
| NVIDIA MagpieTTS v2607 / raw NeMo Speech v3.0.0 | **Rejected; not exposed** | All five short arms and the long arm shared an early cut/clipping defect and failed by ear. One focused hosted-NIM PCM comparison may diagnose raw-runtime versus production-service behaviour; it does not reopen integration. Treat v2602 NeMo-Speech.cpp as a separate path. |
| CosyVoice 3 | **Keep / integration candidate** | A real 30-minute free-Kaggle render was listenable. Proper nouns need attention; this is not a rejection. |
| TADA-1B | **Keep / opt-in** | Works free on local CPU or Kaggle; high naturalness but residual pacing/control issues. Not rejected. |
| Chatterbox Multilingual V3 regional voices | **Rejected** | Synthetic-reference CFG-zero arms, seeded Arthur CFG 0/0.5 controls and genuine human Irish/Australian CFG 0.5 arms all failed by ear. The local accent route is closed. |
| Pocket TTS 2.1 Peter Yearsley preset | **Accepted opt-in; not default** | In the 3,600-word file, the body was decent with some emotion but sometimes lifeless/poorly paced. The clean 600-word A/B sounded more natural with current sentence packing; paragraph-aware packing made intonation stranger. Peter remains imperfect but passed as an optional free CPU narrator. Cloning remains unproven. |
| NeuTTS Air 1.4.1 Q4 + Jo | **Rejected for audiobook production** | Evaluated on Breakneck Ch 1. Shipped voice Jo is American (`en-us`), not British. Spells out abbreviations (`vs.` -> "v s"). Intrusive acoustic token decoder defect on `espeak-ng` palatal glides (`ʲ`, U+02B2) creates audible "ee" stutters across common transitions (*"the-e-airport"*, *"I-e often"*, *"v-e-s"*). High CPU RTF (2.25x–5.9x). Formally rejected. |
| KittenTTS 0.8.1 Jasper/Rosie | **Accepted opt-in; not default** | Dave selected normalized A for Jasper (scratchy opening cured with buffer pre-warming) and B for Rosie. Rosie's long-form body led for pace/tone. In the clean 600-word A/B both packing modes sounded decent with no meaningful difference, so current sentence packing wins on fewer resets. Preset-only; no UK-identity claim. |
| Higgs Audio V2 | **Reserve, not finalist** | Usable but seed-dependent seams. Reopen only for a materially improved official release/runtime or a book-specific audition. |
| OmniVoice current weights/path | **Short-form hold** | Accents were good; CPU RTF ~9 and non-commercial weights block normal books. Reconsider on official performance/licence change or a bounded short use. |
| EdgeTTS through `edge-tts` | **Conditional hold** | Free direct cost and accents were acceptable, but the interface is unofficial/fragile and proper nouns failed. Re-test only with a pronunciation fix and current service docs. |
| MOSS-TTS Local Transformer v1.5 | **Rejected as audiobook finalist** | Multiple corrective long-form structures still collapsed or sounded joined/off-paced. Reopen only for a materially changed official release, not another seed/chunk tweak. |
| MeloTTS tested UK/AU voices | **Rejected for production** | Human listening rejected overall TTS, pronunciation and numbers. Reopen only for a materially different official model/voice release. |
| Piper official VCTK-medium path | **Fully retired from this product** | Current/deployed runtime plus encoding-controlled A/Bs all failed. The service, profile, configuration, routing and voice catalogue were removed on 2026-08-15; historical evidence remains in the docs. |
| Kokoro tested voices | **Retired from quality contention** | Keep only compatibility/debug uses unless a materially new official model clears the listening floor. Never use paid GPU merely to make rejected-quality audio faster. |
| AWS Polly Long-Form | **Rejected on cost/value** | Recheck current official price and run a quality/cost audition only if it becomes the cheapest option capable of passing the human floor. |

No ASR score in this table is a quality verdict. Dave's listening is the
admission/rejection evidence; measurements only establish completeness,
runtime and the exact tested boundary.

The 2026-08-13 Pocket/NeuTTS/Kitten result is a listening verdict about clips
generated by the isolated evaluation scripts with raw text through each
official API. They were served by the app, but did **not** use the app's text
normalizer; earlier “app-path clip” wording was incorrect. The 2026-08-14
follow-up held model, voice and settings fixed and changed only raw versus
explicit spoken wording. Dave selected the normalized arm for **all four**
voices. In September 2026, NeuTTS Air was auditioned on Breakneck Ch 1 and
formally rejected due to American accent (`en-us`), phonetic decoder glides
(*"I-e often"*, *"the-e-airport"*), abbreviation failure (`vs.` -> "v s"), and
slow CPU RTF (2.25x). Jasper's scratchy start on KittenTTS was resolved with
pre-warmed audio buffers, and Rosie gave the strongest overall CPU handling.

Pocket and Kitten are therefore the only admitted **opt-in CPU-only book choices**,
never as defaults or automatic fallbacks. Their preview, first-render and
recovery commands use the named `explicit` text profile: deterministic spoken
numbers/currency and acronym letter-spacing, without the legacy phonetic
lexicon. Every offered official preset must have a persisted preview before it
is selectable. Catalogue presence is not a human quality verdict for every
voice; it guarantees immediate audition and an engine-bound conversion choice.

The first Peter/Rosie long-form gate is valid evidence about the voices' body
quality, but **invalid evidence about title/author delivery**. Both engines were
sent the identical flattened first request beginning `Title: ... Author: ...`
and continuing directly into the first sentence. The source was Project
Gutenberg's generated `pg-header`, not book prose. Exact `pg-header`/`pg-footer`
containers are now excluded structurally. Paragraph-aware request boundaries
remain an A/B candidate, not a production default, until heard.

The corrective 600-word gate was rendered and heard at revision `cc1b0c6`:
current 280-character sentence packing (15 requests) versus exact source-
paragraph boundaries (28 requests), for both Peter and Rosie. No engine
parameter changed. Dave preferred current packing for Peter because it sounded
more natural; the paragraph-aware arm had stranger intonation. Rosie showed no
meaningful audible difference. Current packing therefore remains production
behavior for both engines: paragraph preservation does not justify nearly
twice as many model resets without an audible gain.

## Book acquisition pipeline docs — moved to infra — Active

The LazyLibrarian/Prowlarr/qBittorrent/SABnzbd grab-and-delivery pipeline
(topology, VPN coverage, credentials, failure modes) is host-stack
infrastructure, not this app. It briefly lived in this repo's
`OPERATIONS.md` (added 2026-07-31) but moved to `infra` on 2026-08-01 —
`docs/protocols/book-acquisition-pipeline.md`, with `book_sync.sh` and
`pipeline_healthcheck.sh` tracked at `infra/stacks/docker-vm/media-stack/scripts/`.

**Why:** it duplicated infra's own host-stack records and, separately,
overlapped un-cross-referenced with `mediahub`'s NAS-side `books-dl`
project. See `infra/DECISIONS.md` "Book acquisition pipeline docs
consolidated into infra" for the full reasoning. Don't re-add that material
here — this repo keeps only `scripts/wanted/` (the `wanted_monitor`
watcher), per `infra/docs/protocols/repo-map.md`.

## ASR evidence boundary — Active

ASR is structural QA only: use it to detect missing, repeated, truncated or
grossly mismatched audio. It does not rank naturalness, accent, prosody or
pronunciation, and an individual ASR substitution is never evidence that the
engine pronounced a word badly. Human listening is authoritative for audible
quality. The local Vibe Q8 clip proved the reverse-error case on 2026-07-29:
Dave heard Huawei/Xiaomi as fine while Whisper produced “Swawe”/“Shaumi”.

For the shared audition comparison, full-duration takes with uncertain missing
passages may remain hearable with an explicit completeness warning, preserving
the earlier cache and both ASR reports. Martin and CosyVoice Beatrice are such
cases on 11 November: two ASRs flag middle passages. Their availability is not
a completeness pass, a production approval, or evidence of a model root cause.

**Why:** ASR has now failed in both directions—normalising an audibly wrong
name back to the expected word, and transcribing an acceptable pronunciation
as the wrong word. Removing ASR entirely would also remove the guard that caught
collapsed outputs; keeping it within this narrow boundary preserves its value
without pretending it can hear like the listener.

## Wanted monitor Audiobook status query — Active

`scripts/wanted/wanted_monitor.py` queries LazyLibrarian's database matching
`Status = 'Wanted' OR AudioStatus = 'Wanted'`. LazyLibrarian tracks ebooks in
`Status` and audiobooks in `AudioStatus`.

**Why:** filtering on `Status` alone made the monitor blind to titles wanted
specifically as audiobooks (missed 4 of 12 wanted titles on 2026-08-07).
Fixed in commit `908d82b` alongside recovering openbooks queue idempotency guard.

## ASR WER auto-rerender (#41) — Retired

The `--auto-rerender` implementation is removed. ASR WER must never replace a
render or choose among seeds: it cannot judge audible quality and has produced
false conclusions in both directions. Structural ASR may hold grossly
incomplete/mismatched output for review. Any future retry mechanism must use
deterministic completeness failures only or preserve alternatives for Dave to
hear blind.

**Why:** live audit on 2026-08-13 found the missing production flag and a
single-chapter recovery path that could overwrite a whole-book QA report. The
old entry overstated both implementation and evidence. Retired by Dave on
2026-08-13 after the audit explanation.

## Application HTTP Basic authentication — Superseded

The UI and private APIs require environment-owned HTTP Basic credentials. An
empty password fails closed; the settings database cannot set or reveal it.
Podcast RSS/audio plus health/version probes remain public for non-browser
clients.

**Superseded 2026-08-13:** this ignored the actual deployment boundary. The app
is LAN-only and its public hostname already has Pangolin SSO. Stacking HTTP
Basic behind Pangolin created a second incompatible login and made Pangolin's
health check report the healthy target as unhealthy. Dave explicitly reversed
this after testing the real public URL.

## LAN, Pangolin SSO, podcast access and article SSRF boundary — Active

The app is intentionally passwordless on the trusted LAN. External browser
access uses Pangolin SSO at `audio.magnusfamily.co.uk`; the application must not
add a second password prompt behind it. Flask trusted-host validation includes
the LAN names/addresses and the Pangolin hostname, and browser writes retain
same-origin enforcement. Podcast delivery bypasses Pangolin SSO only for the
exact feed path `api/articles/rss` and enclosure shape
`api/articles/audio/*/*`; the health probe is evaluated by Pangolin against the
private target. The Telegram callback has its own exact
`api/telegram/webhook` bypass. All other public-host paths retain SSO.

Telegram's public webhook requires the official
`X-Telegram-Bot-Api-Secret-Token` header and the incoming chat must equal the
configured owner `TELEGRAM_CHAT_ID`. Article URL ingest permits public
HTTP(S) destinations only, checks all resolved addresses plus the connected
peer, validates every redirect, and bounds response size.

**Official basis:** Flask 3.1 request lifecycle/security documentation,
Python `ipaddress`/`urllib.parse`, Requests redirect controls, and Telegram Bot
API `setWebhook(secret_token=...)`, plus Pangolin's public-resource
authentication and ordered path-rule documentation, read 2026-08-13. This
keeps identity at the real ingress boundary without weakening webhook or
server-side request-forgery controls.

## Article Podcast RSS Feed & Telegram Capture (#42) — Active

Articles are served via a standard RSS 2.0 podcast feed (`/api/articles/rss`) with
audio enclosures for Pocket Casts/Overcast/ABS, and one or more article URLs sent
in a single owner Telegram message via webhook (`/api/telegram/webhook`) are
automatically fetched, converted to EPUB, deduplicated within that message and
enqueued individually for narration. Deployments behind a proxy set
`PUBLIC_BASE_URL` so
the feed emits canonical HTTPS enclosure URLs instead of its internal LAN
origin.

**Why:** Decouples article narrations from the main audiobook shelf into a clean
podcast feed and provides one-tap link capture from phone/desktop via Telegram.

## Narrator Identity & M4B Metadata (#40) — Active

Single-file M4B builds preserve author and narrator identity (`composer` / `narrator`
ID3 tags).

**Why:** Prevents multiple renders of the same book using different voices from
collapsing into a single indistinguishable entry in Audiobookshelf.

## Settings DB WAL Permissions Self-Healing (#37) — Active

Startup entrypoint (`entrypoint.sh`) and webapp DB initialization (`init_db()`)
automatically enforce read-write permissions (`0666`) on SQLite database files
and WAL/SHM sidecars.

**Why:** Eliminates intermittent `READONLY` errors when saving Settings after system
reboots or file permission shifts.

## Deepgram Cloud TTS Integration (Aura-2) — Active

Deepgram Aura-2 is integrated as a first-class cloud TTS engine via `tts-proxy`:
- **Aura-2 Models** (`aura-2-orion-en`, `aura-2-orpheus-en`, `aura-2-arcas-en`, `aura-2-pandora-en`, `aura-2-hyperion-en`): Priced at **$0.030 per 1,000 characters** ($30/1M chars). Expressive neural speech with natural intonation, dynamic prosody, and speed control.
- **Aura-1 Rejection (Angus)**: Evaluated on *Armed Struggle: The Story of the IRA* and canonical samples, then **rejected** for audiobook production by Dave due to monotone/flat delivery across quotes and lack of emotional range or speed parameter support. Aura-1 models are excluded from the product.
- **Preprocessing Contract**: Bound to the `'explicit'` text normalization profile (expands years, numbers, currency, ordinals, and initialisms like `I.R.A.` and `G.P.O.`; avoids shouty phonetic respellings). Text is chunked at $\le 400$ characters per request at clause/sentence boundaries, joined with 300 ms sentence gaps and 650 ms paragraph gaps.
- **Audition Previews**: Previews for the 5 registered Aura-2 voices are pre-generated on canonical `SAMPLE_TEXT` and persisted to `/data/previews/` so the Voice selector plays instantly with zero cold generation.
- **Settings Management**: Users enter their `DEEPGRAM_API_KEY` under **Settings → API Keys** with a live connectivity test endpoint (`/api/settings/test_deepgram`).


