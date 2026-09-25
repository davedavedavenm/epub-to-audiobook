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

### 24–25 September 2026 — Prep-bug audit + headless Colab pipeline stood up — **L4 rendering in flight; harvest loop mandatory**
- Dave's "18xx read as 1,800" report exposed a prep-bug class: year expansion covered only 1900–2099. Audit found more (decades "1920s", times "8.45 p.m.", ".45" calibers, "£10,000" butchery, compound ordinals "twenty-onest"). All fixed in canonical **`scripts/as_prep.py`** with hard unit tests; payloads regenerated — **zero stray digits book-wide** (MI6/M60 acronyms excepted by design). Consequence: the 23 Sep Kaggle Preface/Ch1 renders are **superseded** (predate the fixes).
- **Pipeline:** official `google-colab-cli` on khpi5 (Linux-only — the Pi is the control plane; Windows unsupported). L4 provisioned (~197 compute units, **1.54 units/h measured** → 100+ GPU-h; book needs ~40–55). Gotchas fixed and recorded: CLI 0.7.2 needs `jupyter-kernel-client` 1.0.2 + `KernelClient→JupyterKernelClient` shim in `colab_cli/runtime.py`; **Python 3.10 venv mandatory** (fish-speech pins `datasets==2.18.0`, no 3.12/3.13 wheels; uv backtracks to a Rust tokenizers build) — runner self-bootstraps and re-execs.
- **Auth:** OAuth device flow approved once on the AI Pro account (authuser=2); token persists on khpi5. Colab-mcp browser-bridge installed/approved but **superseded by the CLI** (no tab babysitting, account pinned).
- **Resilience lesson:** first L4 session reclaimed 40 min into the Preface — nothing had left the VM → total loss. The **harvest loop** (`/tmp/harvest.sh` on khpi5, 4-min cycle → `/tmp/harvest/`) is now load-bearing: a chapter counts only once downloaded and gated. Runner state `/content/as_state.json` makes re-provision restart-within-chapter cheap.
- **Lanes status:** Kaggle weekly 30 h cap hit 23 Sep (fallback kernels staged; auto-retry loop left running); **Lightning free tier could not start GPUs without a linked payment method** (400 PermissionDenied verified 24 Sep; T4_X_2 also silently fell back to CPU) — excluded then, **but reversed 24 Sep ~20:00: Dave linked a payment method + added balance, GPU start verified working (real Tesla T4 via `switch_machine(T4)`, then stopped)**. Modal remains vetoed (zero credits). Lightning key retained: `.secrets/lightning_api_key` (used with `LIGHTNING_USERNAME=david-mep9n`).
- Ops note: local Windows shell tooling was removed mid-session; repo/doc/git work now runs through the federated win-desktop-commander / khpi5 desktop-commander over mcpproxy. Deepgram/Flux verdicts from the same day recorded in DECISIONS (Rufus/Colin = general-novel candidates).
- **Preface gate PASSED 2026-09-24 17:2x:** harvested 17:06 → landed in `evaluations/new-engines/output/` + served; waveform 12.3 min, RMS 0.0969, 0 saturated/quiet; ASR SRC 1920 vs 1876 words (0.977), content coverage 95.5%, first/last lines verbatim. Chapter 1 rendering (ETA ~3.2 h); note the runner self-caps at 10 h — if it exits with "10h budget", re-run `colab exec -s render -f /tmp/launch.py` on the same VM to continue from state.
- **Gate automation (2026-09-24 22:35):** `scripts/gate_book_chapter.py` is now THE delivery gate for book chapters — streaming waveform health (RMS band 0.02–0.30, mean|diff| > 0.002, no ≥2 s full-scale plateau, no dead 30 s window) + faster-whisper `base` ASR against the exact prepped payload (`scratch/as_book/<slug>.json`), thresholds word-ratio ≥0.93 and coverage ≥0.90, report persisted to `<name>.gate.json`. **Validated by reproducing the preface's recorded waveform exactly** (12.3 min, RMS 0.0969); its ASR re-check: SRC 1,912 vs 1,900 (**0.994**), coverage 96.5%, boundary 1.0/1.0 — PASS. (Re-check numbers run slightly above the original 0.977/95.5% record; both clear thresholds.)
- **ch1 gate PASSED 2026-09-24 22:4x** (ONE — The Irish Revolution 1916–23): 742/742 sents — banked count **exactly matches** the source payload (no truncation/misplacement), 103.6 min, waveform RMS 0.0988, mean|diff| 0.00653, 0 plateau, 0 quiet windows; ASR SRC 16,254 vs 16,163 words (**0.994**), coverage **94.7%**, WER 0.061, boundary first 0.933 / last 1.0. Superseded 23 Sep ch1 (641-sent pre-fix payload) renamed `…_SUPERSEDED_20260923` so it cannot enter the M4B.
- **Harvest-loop wedge (incident → fixed 22:26):** `harvest.sh`'s un-timeboxed `colab exec` probe hung **2 h 19 m** on `render2` from ~20:05, freezing the loop — ch1 (rendered 21:47) was never pulled. Killed the wedge, added `timeout 90` on probes + `timeout 300` on downloads, restarted; proof-pull of ch1 succeeded immediately (149,206,509 B). A local arm now auto-pulls + auto-gates every remaining chapter (5 min cycle, atomic `.part` → rename). ch4 already rendered and entered the pipeline at 22:35. Total spend to date: **$0**.
- **ch4 gate PASSED 2026-09-25:** 687/687 sents, 89.6 min, waveform RMS 0.0977, ASR 0.993 word ratio / 95.1% coverage.
- **ch2 gate PASSED 2026-09-25 (New States 1923–63 — Dave's chapter):** 652/652 sents, 96.2 min, waveform RMS 0.0975, ASR 0.990 word ratio / 93.4% coverage. Harvested 02:14, gated by `scripts/pull_and_gate_book.py`.
- **ch5 gate PASSED 2026-09-25:** 742/742 sents, 103.0 min, waveform RMS 0.0979, ASR 0.991 word ratio / 94.8% coverage. Harvested 03:16.
- **Delivery-arm restart (2026-09-25 ~06:39):** the original ad-hoc pull+gate loop died silently with an agent session restart, leaving ch2/ch5 ungated in the harvest for ~4 h. Replaced by the committed `scripts/pull_and_gate_book.py` (atomic `.part`→rename pulls with remote size check, idempotent — gated sections are never re-pulled or re-gated — ALLDONE summary, rc 0 all-PASS / 2 any-FAIL).
- **Lane crash incident (2026-09-25 ~13:30, fixed):** both lanes crashed after their clean prefixes with `FileNotFoundError: payloads/ch4\n.json` / `conclusion\n.json`. Root cause was double: the launch had **mistyped render's scope** (`ch1,ch2,ch3,ch4` — ch8 was never in any lane's scope; the crash is the only reason ch4 wasn't rendered twice) and the running parser had **no strip**, so each file's final entry carried a `\n`. No work was lost — `as_state.json` held every banked chapter and per-sentence WAVs are banked per slug. Both lanes were re-scoped (`render`→`ch8`, `render2`→`conclusion`) and relaunched **on the warm VMs** (weights still resident — no cold start) at 13:45. The repo parser was fixed to strip-then-filter (the intermediate filter-only form silently dropped the polluted entry = a book missing a chapter, no error) with a pinning test (`f2433e9d`/`f243e9d`).
- **Running total gated: preface ✅ ch1 ✅ ch2 ✅ ch3 ✅ ch4 ✅ ch5 ✅ ch6 ✅ ch7 ✅ (8/10, all PASS)**; ch8 + conclusion rendering since 13:45, ETA ≈ 16:00–16:20.
- **Gate-source verification (measured 2026-09-25, not assumed):** the production bundle was downloaded from khpi5 (`/tmp/as_bundle.zip`) and diffed against `scratch/as_book/*.json` — **all 10 payloads byte-identical**, so every gate has compared ASR against exactly the text the lane rendered. The bundle has **no `manifest.json`** (and carries an extra `cillian_irish_dry.wav`), so `fish_colab_runner.py` falls back to its hardcoded `BOOK_TAG=armed_struggle` + `ORDER=[preface,ch1..ch8,conclusion]` — that is why production slugs are unpadded (`ch1`, not `ch01`).
- **Discrepancy found — `scripts/fish_bundle.py` cannot reproduce this book's bundle.** It derives slugs as `f"ch{idx:02d}"` from `chapters.list_renderable_chapters()`, which returns **24** sections for `fixtures/armed_struggle.epub`, versus the 10 sections `scripts/regenerate_as_book.py` maps by `index_split_*.html`. A bundle built by the repo script would therefore carry `ch01..ch24` slugs, a manifest that overrides the runner's ORDER, and payloads that no gate source exists for. **Do not queue *The Armed Struggle* through the webapp lane path until the chapter mapping is reconciled**; the in-flight render is unaffected (bundle already built, running on the hardcoded path). Affects future webapp-driven renders only.

### 23 September 2026 — BOOK PRODUCTION underway — **Preface ✅ + Chapter ONE ✅ (both gated); Chapter TWO rendering** — *SUPERSEDED 2026-09-25: renders predate the year/decade/time/ordinal prep fixes; Colab re-render in flight (see entry above)*
- **Preface**: 78/78 sentences, RTF 2.82, 0 failures, 12.2 min, ASR-complete. Re-rendered once after prep fix.
- **Chapter ONE (Irish Revolution 1916–23)**: **641/641 sentences, RTF 2.78, 0 failures, no re-rolls needed, 102.2 min**, waveform gate clean, ASR content coverage **94.7%** after year-digit normalization (remainder = ASR mishearing proper nouns + digit-form normalization; no systematic drops). First/last passages match source.
- **Chapter TWO (New States 1923–63 — Dave's chapter) rendering now.** Remaining: ch3 (1,152 sents — largest, ~8h), ch4–8, conclusion. All banked/resumable.
- Recipe held at production scale with zero manual intervention. Total spend: $0.
- **Incident note:** Windows temp cleanup wiped `%TEMP%\opencode` (served audition files + analysis venv). Book renders were safe in `evaluations/new-engines/output/` (durable-copies discipline paid off); lab clips remain re-downloadable from their Kaggle kernels; venv rebuilt. Serve dir recreated with book files.
- After all 10 sections: build chaptered M4B, replace audio in ABS item `7039379c`, rescan, remap Dave's position (39.9% fraction into "New States 1923–63").

### 23 September 2026 — BOOK PRODUCTION launched — Preface rendered; Chapter ONE next
- Dave approved the locked recipe ("perfect... this is the answer for this book") and ordered the **whole book from the Preface**, replacing his existing ABS copy while preserving his exact progress. Tánaiste respelling corrected ("Tawnashta") per his stress-test catch.
- Method codified in **`CILLIAN-RECIPE.md`**; book-wide payloads in `scratch/as_book/*.json` (10 sections, 152,359 words, zero digit-years); production renderer `scripts/prepare_kaggle_fish_as_book_chapter.py <slug>`.
- Year-less ordinal dates fixed in prep ("9 October" → "the ninth of October") after the first Preface render surfaced it.
- Plan: sequential chapter kernels (~53 GPU-h total ≈ ~2 weeks free quota); ABS swap + progress remap at the end.

### 22 September 2026 — LOCKED-RECIPE stress test — **PASS: dual-ref routing, dates/ordinals/numbers/currency all spoken correctly; 0 failures**
- Made-up 2-paragraph stress text (ordinals "12 July 1921", year ranges, "4,500", "55,000", "£15 million", em-dashes, curly apostrophes, dramatic quote mid-flow, deliberately-unrespelled killer Gaelic names: Caoimhghín Ó Caoláin, Glounthaune, Cnoc na Gaoithe).
- Kernel `fish-stress-lab` v3: **RTF 2.78x, 0/8 failures** (auto re-roll armed but unneeded), final waveform gate pass. ASR completeness: **every sentence present in order**; "the twelfth of July nineteen twenty-one" ✓, "nineteen twenty-three" ✓, "four thousand five hundred" ✓, "fifteen million pounds" ✓, "the tenth of August nineteen twenty-seven" ✓; quote delivered complete via expressive-tail ref.
- Known limits (by design): unrespelled raw Gaelic names mangle (lexicon is the fix — that's its job); "Dawl Air-inn" heard as "Dol Ehrin" once (ASR weakness or mild drift — Dave's ear decides on the chapter).
- **Recipe now locked for chapter production**: narration = full 28s ref @ t0.85; quotes = expressive-tail crop @ t0.85; curly apostrophes; years/ordinals/numbers/currency→words; orphan merge; per-sentence banking + health gate + auto re-roll (seed 43/44); silence-trim + 0.18s/0.50s natural gaps; mastering chain; ASR completeness check before delivery.
- Next: Dave hears the stress clip; on approval, chapter re-render of "New States 1923–63" with the full recipe, then paced book production.

### 22 September 2026 — Drama round 2 verdict + expressive-reference lab — **crops of the 28s clip as emotion anchors; verdict pending**
- Round-2 pace verdicts: atempo 0.85 "still too fast", 0.88 "not quite right" (note: arm-level generation variance confounded the comparison — raw lengths differed before tempo), period surgery "nice but still flat or run on". Root complaint: **the quote is emotive and none of the takes convey it** — Fish anchors emotion on the reference, and both refs are flat interview cuts. Fish has no emotion control parameter.
- Fix hypothesis: **emotionally-charged reference crops**. Silence-mapped the 28s Cillian clip; cut three expressive crops (`crop_emotional_list` 8.4s, `crop_power_of_art` 3.8s emphatic ending, `crop_expressive_tail` 9.9s) into the private refs dataset (v2) with transcripts.
- Lab `fish-emoref-lab` rendered 4 arms (D quote, temp 0.85, refs: emotional-list / power-of-art / power-of-art@t1.0 / expressive-tail) — all ok, served. **Verdict pending.** If one conveys emotion without breaking the accent, production rule = narration uses the full-ref recipe; dramatic quotes use the chosen expressive crop.
- Fallback if all still flat: Deepgram Rufus/Colin for quote-heavy passages (paid, ~$3/book for quote fraction) — Dave's call; or accept restrained delivery.

### 22 September 2026 — Verdicts: Rufus/Colin "very good" (general-novel list); drama arms all too fast → pace arms v2 served
- Deepgram Flux **Rufus and Colin (expressivity=1): "both very good"** — recorded as top general-novel candidates (preset voices; cannot be Cillian; paid per character).
- Drama line, full ref, round 1 (t0.7 / t1.0 / atempo 0.93 / no-comma): **all too fast** — the 28s ref's interview pace transfers, and 7% slowdown was insufficient. Round 2 served: **atempo 0.85**, **atempo 0.88**, **comma→period surgery** (short declarative sentences force the model to breathe), and **periods + atempo 0.9**. Verdict pending.
- Recipe state: narration LOCKED (Cillian, full 28s ref, temp 0.85, curly apostrophes, silence-trim + natural gaps). Open: dramatic-line pace, plus queued prep fixes (ordinal dates, orphan merge, per-sentence re-roll).

### 22 September 2026 — Lab verdicts round 2 + Deepgram assessed for Cillian — **curly kept; ordinal-date + dropped-word bugs logged; Deepgram = no cloning, presets only**
- Apostrophe lab verdicts: S1 all four arms identical, **the chapter's weird pause did NOT reproduce** (stochastic per-sentence render variance, not the apostrophe — curly stays, book default). S2 curly fine; straight mispronounced Dáil Éireann in one arm (stochastic again); comma-smoothing "a little bit off".
- v2.1 chapter verdicts: solid voice, **lacking emotion, quotes flat** (drama lab arms served separately); two completeness defects logged for the prep/queue: **ordinal dates read cardinally** ("Sunday 10 July" must become "the tenth of July") and **a dropped word** ("a" before "volunteer went"). Per-sentence re-roll for stochastic defects (dropped words, stray pauses) is now a production-queue requirement since banking makes it cheap.
- Drama-lab arms (D × full ref: t0.7 / t1.0 / atempo 0.93 / no-comma) rendered and served — verdict pending.
- **Deepgram assessed for the Cillian voice: not possible.** Official developer docs checked 2026-09-22 (full index + TTS/Flux/voices pages): no voice-cloning or custom-voice product exists on the platform; all voices are presets. Irish coverage: Aura-1 `angus` (already rejected by ear 2026-07), Flux `maeve` (female only). What Deepgram DOES add: Flux TTS `/v2/speak` with `expressivity` (-2..2, beta, calm↔animated) and `speed` (0.5–1.5), Aura-2 per-word pronunciation overrides. Book cost at documented Aura-2 pricing ($0.030/1k chars): ~900k chars ≈ **$27 — violates the zero-cost rule**; sample clips of draco/arcas (Aura-2) and rufus/colin (Flux, expressivity=1) rendered for reference (~$0.03 actual).
- **General-novel applicability (Dave's standing note):** findings failing the Irish bar stay on record for books where accent/lexicon don't matter — Deepgram Flux (expressivity+speed, paid), Supertonic-3 (free CPU presets), Higgs 3 (needs H100-class), Gemini Achernar (free quota-paced) remain candidate narrators for generic novels.

### 22 September 2026 — Emotion lab — **10 arms rendered (temp x reference); Dave's picks pending**
- Dave asked for emotion in the narration. Lab matrix: dramatic sentence (killer's quote, D) + neutral narrative (N) x temperature {0.7, 0.85, 1.0} on the dry ref; then 0.85 with the unused **28s full Cillian clip** (transcript captured via offline Whisper) and with **both refs as multi-reference** (`generate_long` accepts prompt lists).
- All 10 arms rendered + gated + served (`lab_{D,N}_t{07,085,10}_dry`, `lab_{D,N}_t085_full`, `lab_{D,N}_t085_both`).
- Infra note: kernel source size limit (~1 MB) forces reference audio through a **private Kaggle dataset** (`davedavedavedavenm/cillian-refs` + refs.json transcripts, mounted at /kaggle/input) — the established pattern for future kernels.
- Pending Dave's picks: temperature sweet spot, ref choice, then production recipe = winning punctuation style + winning temp/ref + orphan-merge + trim/natural-gap assembly. Chapter re-render only after that.

### 22 September 2026 — Dave v2 verdict + sentence-lab turn — **accent still somewhat American; pauses robotic ("by his death......Kevin...O'Higgins"); NO whole-chapter renders until recipe locked**
- Dave's verdicts: v2 accent "just a bit too American still"; weird pauses, "doesn't sound like natural flowing speech"; specific defect at the Kevin O'Higgins sentence. Also directed: iterate at sentence level, not per-chapter.
- Prime suspect identified: **all apostrophes in the source are curly Unicode (O’Higgins ×10, IRA’s, didn’t…)** — never tested (tough-Irish audition had no apostrophes); plus long comma-rich sentences inviting mechanical pauses.
- Sentence lab `fish-ohiggins-lab` (8 arms, all rendered ok): S1/S2/S3 × curly vs straight vs spaced apostrophe vs comma-stripped, temp 0.7, per-arm mastered mp3s served for Dave's per-sentence picks.
- Pacing-only fix built from existing v2 banked audio (no re-render): **v2.1** — per-sentence silence-trim + natural gaps (0.18s sentence / 0.50s paragraph) replacing mechanical 0.35/0.65s; 92.2 min, gate pass, served.
- Accent lever queued behind lab results: **multi-reference anchoring** (cillian_irish.wav = 28s longer cut of the same Cillian source, transcript captured; generate_long accepts prompt_text/prompt_tokens lists) alongside the winning punctuation variant.

### 22 September 2026 — AS ch2 v1 verdict + v2 fixes — **voice drift/pacing/years flagged by Dave; v2 rendered + spliced; A/B awaiting ear verdict**
- Dave's verdict on v1: voice sometimes goes American; pacing sometimes poor/running on; year ranges ("1911-1921") read digit-wise instead of "nineteen eleven to nineteen twenty-one".
- v2 fixes (kernel `fish-as-newstates-cillian-v2`, ~4h15m, $0): (1) full year expansion — ASR confirms spoken-word years ("March nineteen thirty-four General Army Convention" transcribed as "March 1934"); zero digit-years in payload; (2) paragraph-aware assembly gaps (0.65s paragraphs / 0.35s sentences) + abbreviation-safe splitting (615 sentences vs 504); (3) **temperature 1.0 → 0.7** to anchor accent/prosody — the change that needs Dave's A/B ear.
- One orphan fragment failed in v2 ("At the", a broken-paragraph split inside "At the army's March 1934…"): rendered via candidate kernel ("At the" / "At the," — both passed) and spliced; first splice silently skipped the failed index (checked `ok` before the fix branch) — re-spliced and ASR-verified: "…working-class basis at the Army's March 1934 General Army Convention…".
- **Structural fix queued for the production builder: merge orphan fragments (<4 words, no terminal punctuation) into the following sentence during text prep** — this class (v1: "F.", v2: "At the") then cannot occur.
- Final v2: 94.8 min, RTF 2.6, waveform gate pass. A/B links: v1 `armed_struggle_ch2_newstates_cillian.mp3`, v2 `armed_struggle_ch2_newstates_cillian_v2.mp3`.

### 22 September 2026 — Armed Struggle ch2 "New States 1923-63" overnight render — **COMPLETE + spliced fix; awaiting Dave's listening verdict**
- The actual chapter Dave is listening to (39.9% in; 95.6 min professional audio). 14,583 words from his own calibre EPUB, repo lexicon + chapter glossary (Fianna Fáil→"Fee-na Fawl", standalone Dáil/Éireann, Sean→"Shawn", Eamon→"Aymun", **IRA→"I-R-A"** letter-reading). Kernel `fish-as-newstates-cillian`, ~4h10m wall on free Kaggle T4×2, $0.
- **RTF 2.56x** (503/504 sentences passed; one bare initial "F." of *F. L. Green* produced no audio — fixed by a candidate-letter kernel ("Ef."/"Eff."/"F."/"F" — all rendered; "Ef." spliced in) and local re-master. ASR spot-check at the splice confirms "F-L. Green's 1945 novel, Odd Man Out" with correct flow.
- Waveform gate on final: 93.3 min, RMS 0.096, zero saturation. Files landed in `evaluations/new-engines/output/` and served locally.
- Measured basis for full-book production: **~42 GPU-h for 16 audio-hours (RTF ~2.6)** ≈ 1.5 weeks of free quota paced per chapter; a 95-min chapter ≈ 4.2 h.

### 21 September 2026 — Fish S2 Pro full-chapter PILOT (optimized harness) — **COMPLETE; measured RTF 2.62x; 0/200 sentence failures; Dave's listening verdict pending**
- Chapter: Sophie's World Ch 6 "Fate" (the chapter Dave is listening to; 15.5 min rendered vs 16.4 min professional narration; 2,851 source words). Kernel `fish-sophies-fate-cillian` v2, free Kaggle T4×2, $0.
- **Measured RTF 2.62x** — 5.7x faster than the audition harness (15.03x): the single-process driver (AR + caches + codec loaded once, codec split to cuda:1) removed the per-sentence reload that dominated the audition number.
- Gates: all 200 sentences passed in-kernel waveform checks; independent local re-check of the master (RMS 0.093, zero saturation, 928.9s); faster-whisper ASR = 2,853 words vs 2,851 source — word-complete, correct order.
- **Whole-book math (measured basis):** 16-h book ≈ 42 GPU-h at RTF 2.62 single-AR-GPU (~1.5 weeks of ~30 h/wk free quota); 2-GPU sentence sharding (not yet built) would roughly halve wall time. A 95-min Armed Struggle chapter ≈ 4.2 GPU-h.
- Pilot builder: `scripts/prepare_kaggle_fish_sophies_fate.py`. Gotchas baked in: install runtime BEFORE importing torch (torchaudio ABI), codec-patch touches 4 call sites, `PYTHONUTF8=1` for kernel push with unicode text.
- **Dave's ear verdict pending — if it passes, the Armed Struggle production path is settled (Fish S2 Pro + Cillian + lexicon, chapters paced across free Kaggle quota).**

### 20 September 2026 — Fish S2 Pro bounded retry (flat Cillian ref) — **rendered on free Kaggle T4×2; VOICE PASSES by ear; pronunciation is the open issue**
- **Dave's listening verdict (2026-09-20): "Fish S2 Pro retry voice is perfect"** — the flat-Cillian hypothesis is confirmed: the 2026-09-18 rejection was theatrical prompt prosody transfer, not the engine. The voice/timbre gate is now passed on the toughest test we have.
- **Open issue: pronunciation of hard Irish terms** (Dáil Éireann, Taoiseach, Tánaiste, etc. as-spelled). ASR heard "Padreik Paris", "deal era", "Toshak" — consistent with the engine reading anglo spelling literally.
- Plan of attack (in flight): deterministic proper-noun respelling lexicon applied at preprocessing (only exact watch-list tokens, engine-agnostic), A/B auditioned on the same kernel/text. Note: the repo's old respelling ban originated from a misdiagnosed formatting artefact (AGENTS rule 7 context) — this bounded audition re-tests that boundary with Dave's ear as judge. Fine-tuning is not viable (9.5s of reference audio); a longer reference does not teach out-of-distribution words.
- **Respelled A/B take rendered 2026-09-21** (`fixtures/irish_pronunciation_lexicon.json`, kernel `fish-s2pro-tough-irish-respelled`, same voice/seed/chain, health-gated: 52.3s, RMS 0.094, no saturation, ASR-complete). ASR shows the intended shift on most terms ("Dawl Air-inn"→"doll air in", "Doon Leery"→"Dune Leery", "Portleesh"→"Port Leish", "Teeshock"→"T-Shock", "Shin Fayn"→"Sinn Fein"); uncertain: "Pawdrig Peerse"→"Podrick Pierson", "Cahal Brooah", "Preev Aira". **Dave's ear verdict on the lexicon pending — per-term tuning is data, not code.**
- The 2026-09-18 rejection named its own remedy (flat, non-theatrical studio prompt). Retry used `cillian_irish_dry.wav` + transcript on the tough-Irish paragraph, seed 42, per the rejection-boundary rule.
- Result: **all 6 sentences passed waveform health gates** (kernel-side AND independent local re-check: 54.1s, RMS 0.095, zero saturation) and a faster-whisper-base ASR completeness pass (full passage, correct order, no truncation). Kernel `fish-s2pro-tough-irish-cillian` v9, RTF **15.03x** on free T4 — viable for auditions, slow for books.
- Runtime notes that made T4 possible: S2 Pro stack needs >16 GB so the **DAC codec was split onto the second T4** (patched `inference.py`: `CODEC_DEVICE` env, 4 call sites); `--half` (current main replaced `--precision`); apt `portaudio19-dev` before `pip install -e`; weights via `snapshot_download`. Builder: `scripts/prepare_kaggle_fish_s2pro.py`.

### 20 September 2026 — Chatterbox CPU Cillian voices (Nano dry/full, Turbo) — **tested on Tough Irish Words; rejected by ear**
- Dave's verdict on all three arms: *"all those nano ones are shit"*.
- Arms: `chatterbox-nano_dry`, `chatterbox-nano_full` (Zorin :8006, RTF 0.77–0.80), `chatterbox-turbo_full` (:8004, RTF 1.95), human `cillian_irish_dry` reference, seeded, mastered chain.
- Consequence: the Chatterbox-family CPU route to Cillian+Irish is **closed**, consistent with the earlier regional-accent-closure decision; local CPU default narrator remains Beatrice/Nano for UK content only. The CPU-Cillian ladder now runs: Higgs TTS 3 (Kaggle, Cillian clone, RTF 1.67, awaiting Dave's listening verdict) → Breeze 2 (current production winner).
- First-party: rendered via the deployed Zorin services; no engine/voice changes made.

### 20 September 2026 — Live landscape sweep vs the July review: 4 new open-weight candidates + 3 reconsideration triggers — **test/watch; listening in progress Sept 2026**
Sources: vendor model cards, checked 2026-09-20. **All benchmark numbers below are vendor-reported and unverified by our listening gate.**

- **Higgs TTS 3 (`bosonai/higgs-tts-3-4b`, ~4B, released early Sep 2026) — TEST, top priority.** *→ CLOSED 2026-09-20: booted on free T4 but output numerically invalid; H100-class hardware required (see Tested note).*
  - Vendor SeedTTS WER 1.11 (vs Fish S2-Pro 1.31, OmniVoice 1.21, Qwen3-TTS-1.7B 1.30); top emergent-TTS win-rate vs Fish/Qwen/IndexTTS-2/MOSS/OmniVoice. Zero-shot cloning, 100+ languages (Irish in the WER 5–10 "usable" tier, US/UK/AU English in the polished tier), inline `<|emotion|>/<|prosody:pause|>/<|prosody:speed|>` control tokens, 24 kHz.
  - This release **satisfies the recorded Higgs V2 boundary in `DECISIONS.md`** ("reopen only for a materially improved official release").
  - Licence: Boson Higgs TTS 3 Research & Non-Commercial + Creator Use Grant explicitly covering audiobooks with attribution; personal listening use is inside the non-commercial grant (same class as BreezeBlue already in production).
  - Serving: SGLang-Omni or vLLM-Omni OpenAI-compatible `/v1/audio/speech`; weights gated on HF (licence acceptance + token required). Card hardware claim is H100; T4/L4 fit unverified — first-run risk is runtime, not licence.
  - First-party links: [model card](https://huggingface.co/bosonai/higgs-tts-3-4b), [blog](https://www.boson.ai/blog/higgs-audio-v3-tts), [SGLang cookbook](https://sgl-project.github.io/sglang-omni/cookbook/higgs_tts.html).
  - **Tested on free Kaggle T4 2026-09-20** (`scripts/prepare_kaggle_higgs3.py`, kernel `davedavedavedavenm/higgs3-tough-irish-cillian` v7): tough-Irish paragraph, Cillian dry-ref zero-shot clone, seed 42, nominal RTF 1.67 free — **OUTPUT INVALID: waveform is saturated DC plateau (RMS 0.98, mean sample delta ~0); Dave heard clicking only.** The engine "ran" on T4 but numerically collapsed; vendor hardware-support section lists **1×H100 only**. Higgs TTS 3 is **not runnable on free hardware** (T4 fp16 collapses; fp32 exceeds 16 GB; no free Ampere+ exists). Reopen only when free Ampere/Hopper compute or vendor adds validated consumer/Turing support.
  - Runtime findings preserved for any future attempt: runnable on T4 needed vllm 0.29 + vLLM-Omni **git main** (registry missing from all pypi releases), deploy-yaml `attention_backend FLASHINFER→TRITON_ATTN` (T4 sm_75) and stage0 `max_model_len 8192→4096` (KV fit) — it boots and "synthesises" but see validity note above. Serving schema is `ref_audio` base64 data-URL + `ref_text` (vendor vLLM client), not the `references[]` shape in the model card (that is SGLang's).
  - **Process lesson applied by this failure: every audition file must pass a waveform health gate before delivery** (RMS in speech band ~0.02–0.3, mean|diff| > 0.002, no >2s full-scale plateau), duration AND a spot ASR/completeness check. Length/size alone proved nothing again — repo Rule 1, re-paid.
- **Mistral Voxtral-4B-TTS-2603 (Mar 2026) — TEST.**
  - Frontier open weights, 20 curated studio preset voices (no cloning needed — avoids the prompt-prosody contamination mode recorded for Fish S2 Pro), 9 languages incl. EN/NL/FR/DE with dialect claims, streaming, RTF 0.103 (vendor, H200, concurrency 1), ≥16 GB VRAM.
  - Licence CC BY-NC 4.0 — personal non-commercial listening use permitted; commercial use is not.
  - First-party links: [model card](https://huggingface.co/mistralai/Voxtral-4B-TTS-2603), [blog](https://mistral.ai/news/voxtral-tts), [paper](https://arxiv.org/abs/2603.25551).
- **Supertone Supertonic-3 (May 2026, 99M ONNX) — TEST, cheapest first.**
  - Runs fast on **CPU** (vendor: beats larger baselines measured on A100; card shows an audiobook sample), 31 languages, `<laugh>/<breath>/<sigh>` tags, OpenRAIL-M.
  - Boundary: open-weight voices are fixed presets; zero-shot custom-voice styles route through a **paid** Voice Builder. If a preset clears the floor by ear it displaces Nano/Beatrice as free-local default for the whole back-catalogue with zero cloud quota; if not, closed.
  - First-party links: [model card](https://huggingface.co/Supertone/supertonic-3), [GitHub](https://github.com/supertone-inc/supertonic), [audio demo](https://supertonic3.github.io/).
- **Maya Research maya1 (3B, Apache-2.0, Nov 2025) — SKIP for now.** Voice-design + 20 emotion tags, English-only, 16 GB VRAM; card carries no reproducible benchmarks and heavy self-claims. Lower priority than the three above. [Card](https://huggingface.co/maya-research/maya1).

- **Reconsideration triggers recorded (no verdicts changed here):**
  1. **Fish S2 Pro bounded retry** — the Sep-2026 rejection names its own remedy ("perfectly flat, clean, non-theatrical studio prompt"); `chatterbox/voices/cillian_irish_dry.wav` is now that prompt. Under the rejection-boundary rule this is a materially different controlled hypothesis.
  2. **CosyVoice 3 path inconsistency** — `DECISIONS.md` keeps the official Kaggle runtime as "keep / integration candidate" ("30-minute render listenable") while the Sep-19 **Modal wrapper** (wetext/vllm build) rendered "garbled". A wrapper failure is not an engine verdict; one official-runtime Kaggle arm would close the thread.
  3. **Zero-cost economics** — Modal's $30/month free credit exceeds the ~$24 measured full-book Breeze cost, and the render already banks completed chapters, so pacing across the monthly reset is a true $0 path; separately the recorded Breeze T4 Kaggle figure (RTF 7.86) is explicitly "without FlashAttention" and has never been re-measured with it.

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
