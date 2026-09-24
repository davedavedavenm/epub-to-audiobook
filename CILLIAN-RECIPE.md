# Cillian Recipe — Fish S2 Pro Production Method (LOCKED 2026-09-22)

This is the locked, proven production method for **The Armed Struggle: The Story of
the IRA** narrated by the **Cillian Murphy** voice, and the baseline recipe for any
book narrated with this voice. Every element below was adopted through Dave's
listening verdicts across 2026-09-20/22 (see `DECISIONS.md` and
`TTS-WATCH-FINDINGS.md` for the full evidence trail).

## Engine & voice

| Component | Value |
|---|---|
| Engine | Fish Speech **S2 Pro** (`fishaudio/s2-pro`, 4.4B Dual-AR + DAC codec) |
| Hardware | **Primary: headless Colab L4 via `google-colab-cli` on khpi5** (~197 compute units ≈ 100+ GPU-h at 1.54 units/h measured). Fallback: Kaggle T4×2 (30 h weekly cap). NEVER Modal (zero credit, standing veto) or Lightning free GPU (payment-method wall, verified 2026-09-24) |
| Narration reference | `chatterbox/voices/cillian_irish.wav` (28s clip) — Dave: "perfect" |
| Quote/dramatic reference | expressive crop `crop_expressive_tail.wav` (last 9.9s of the same clip) — Dave: "probably the best" |
| Precision | L4/Ampere+: `torch.bfloat16` auto; T4 fallback: fp16 `--half` (no bf16 on sm_75) |
| Temperature | **0.85** (narration AND quotes; 0.7 = flat, 1.0 = drifts American) |
| Sampling | top_p 0.9, top_k 30, iterative_prompt, chunk_length 300, seed 42 (re-rolls 43/44) |
| Licence | Boson-class non-commercial personal use; Fish licence terms per DECISIONS 2026-09-18 entry |

## Text preparation (in order)

**Canonical implementation: `scripts/as_prep.py`** (unit-tested — run it directly;
it asserts every rule). Chapter payloads are generated via
`scripts/regenerate_as_book.py`. The prep pipeline, in order:

1. **Irish lexicon** (`fixtures/irish_pronunciation_lexicon.json`), longest-first exact
   replacement. Includes Dáil Éireann→"Dawl Air-inn", Taoiseach→"Teeshock",
   Tánaiste→"Tawnashta" (corrected 2026-09-22), Dún Laoghaire→"Doon Leery",
   Portlaoise→"Portleesh", Sinn Féin→"Shin Fayn", IRA→"I-R-A", Fianna Fáil→"Fee-na
   Fawl", person names, etc. **Books carry their own glossary additions** (data, not code).
2. **Dates → words**: "12 July 1921" → "the twelfth of July nineteen twenty-one";
   year-less dates ("9 October") and month-first forms too (Dave verdict: cardinals are wrong).
3. **Decades**: "1920s"/"late-1920s" → "nineteen twenties".
4. **Year ranges** ("1923–63" → "nineteen twenty-three to sixty-three"; also
   "1763–98" with expanded first year) and **standalone years 1000–2099** → words
   ("1848" → "eighteen forty-eight", "1798" → "seventeen ninety-eight",
   "1014" → "ten fourteen"). Zero digit-years may remain in the payload (checked).
5. **Short-form quote years**: ’98 → "ninety-eight".
6. **Money/weights**: "£15 million" → "fifteen million pounds" (comma amounts safe);
   "250lb" → "two hundred and fifty pound".
7. **Numbers → words**: 3+-digit and comma-group integers, then 2-digit, then
   1-digit ("World War 1" → "World War one").
8. **Times/calibers**: "8.45 p.m." → "eight forty-five p.m."; ".45" → "forty-five".
9. **Mixed decade ranges**: "forties–80s" → "forties to eighties".
10. **Orphan merge**: fragments without terminal punctuation (<3 words) merge into
    the following sentence (kills the "F." / "At the" defect class).
11. **Quote detection**: sentences containing an opening ‘ are flagged; the flag
    propagates to sentences containing a non-letter-apostrophe ’ (regex
    `(?<![A-Za-z])’`). Quote sentences use the expressive ref.
12. Curly apostrophes are **kept** (verdict: all apostrophe variants sounded the same;
    book default is fine).

Hard rule validated by the 2026-09-22 incidents: **any digit surviving prep will be
read wrongly** — the payload scan must show zero digit runs before pushing a kernel.
(MI6/MI5/M60/M62-style acronyms are the only intended exceptions.)

## Synthesis (per sentence)

- Single process: model + caches load **once** (RTF 2.6–2.8; the per-sentence
  subprocess harness measured 15x — never use it for books).
- Single-GPU L4 (24 GB): whole stack on `cuda:0`, no split needed. On the 16 GB
  T4 fallback, split the DAC codec to `cuda:1` (S2 Pro stack >16 GB): patch
  `inference.py` with a module-top `CODEC_DEVICE` env read + 4 call-site swaps,
  set `FISH_CODEC_DEVICE=cuda:1`. The runner carries the patch either way
  (harmless when unset).
- Install order: apt `portaudio19-dev libsox-dev libsndfile1 ffmpeg` BEFORE
  `pip install -e`; **import torch only after pip** (torchaudio ABI mismatch otherwise).
- Weights: `snapshot_download('fishaudio/s2-pro')`.
- **Per-sentence banking** to `/content/wavs/CHAPTER/NNNN.wav` + `/content/as_state.json`
  (resumable; harvest loop copies finished chapters off the VM every 4 min — a
  chapter does NOT count until harvested. On the Kaggle fallback lane:
  `/kaggle/working/out/wavs/`).
- **Health gate per sentence** (RMS 0.005–0.5, mean|diff|>0.001, peak>0.05);
  **auto re-roll on failure with seed 43, then 44**.
- Payloads + references ship as one **`as_bundle.zip`** (2.3 MB: payloads, refs,
  transcripts) via `colab upload`; the Kaggle fallback lane uses the private
  dataset `davedavedavedavenm/cillian-refs` instead (kernel scripts must stay
  under 1 MB).
- **Python 3.10 venv is mandatory on Colab images**: fish-speech pins
  `datasets==2.18.0`, which has no 3.12/3.13 wheels — uv then backtracks to
  tokenizers 0.10.3 (Rust source build → fails). The runner detects this and
  self-bootstraps `uv venv /content/fishenv --python 3.10`, seeding
  numpy/soundfile, then re-execs into it.

## Assembly

- Silence-trim each banked sentence (−44 dB threshold, 80 ms pads).
- Gaps: **0.18s** between sentences, **0.50s** between paragraphs (mechanical
  0.35/0.65 uniform gaps were rejected: "robotic / run-on").
- Mastering: `equalizer=f=220:width_type=o:width=1.2:g=1.0,
  highshelf=f=7500:gain=-2.0:width=1.0, loudnorm=I=-20:TP=-2:LRA=11`, 192k MP3.
- Final waveform gate + **ASR completeness check** (faster-whisper on the
  `epub-to-audiobook-ui` container) against the source text before delivery.
  No file reaches Dave ungated.

## Measured basis

- RTF **2.56–2.78x** on Kaggle T4×2 (single-AR-GPU; codec mostly idle → 2-GPU sentence
  sharding could ~halve wall time, not yet built).
- **Colab L4 (2026-09-24/25): Preface DONE** — 83/83, 0 failures, 12.3 min audio
  in 34 min (RTF ≈ 2.8); harvested + waveform-clean + ASR 95.5% coverage.
  ch1 pace ~15 s/sentence (RTF ≈ 1.8–2). Compute cost **1.54 units/hour** →
  197-unit balance ≈ 100–128 L4 GPU-hours.
- Stress test (2026-09-22): 8/8 sentences, 0 failures, all dates/numbers verified by ASR.
- Whole book (152,359 words, 10 sections ≈ 17–20h audio): **40–55 GPU-hours** —
  inside a single AI-Pro credit balance; earlier estimate of "~2 weeks of Kaggle
  quota" obsoleted by the Colab lane.

## Production orchestration — headless Colab (khpi5)

**One-time setup (done 2026-09-24):**
- `uv tool install google-colab-cli` on khpi5 (v0.7.2, Linux-only → the Pi is
  the control plane; Windows is not supported).
- CLI 0.7.2 breaks against current `jupyter-kernel-client`: install 1.0.2 into
  the tool env AND shim `KernelClient = JupyterKernelClient` in
  `colab_cli/runtime.py` (every `colab exec` otherwise dies with AttributeError).
- Auth: run any colab command; it prints an OAuth device URL — approve **on the
  AI Pro Google account** and paste the code back. Token persists in
  `~/.config/colab-cli`. (The `colab-mcp` browser-bridge server also works but
  the CLI supersedes it — no browser tab to babysit, and the account is fixed
  rather than "whichever tab is open".)

**Two-lane parallel split (since 2026-09-24 18:27, halves wall-clock):**
the AI Pro account accepts a second concurrent L4 session, so the book runs on
two lanes with **disjoint chapter scopes**. The runner reads
`/content/as_chapters.txt` (comma-separated slugs; absent = full ORDER) —
without it both runners would render the same chapters.
- **lane 1 `render`** (`gpu-l4-s-kkb-ass1a1-...`): `ch1,ch2,ch3,ch8` (3,611 sents)
- **lane 2 `render2`** (`gpu-l4-s-kkb-ass1b0-...`): `ch4,ch5,ch6,ch7,conclusion` (3,479 sents)

**Per-lane render loop (all on khpi5, `/tmp/` assets):**
```
colab new -s render2 --gpu L4                    # second lane
colab upload -s LANE /tmp/as_bundle.zip /content/as_bundle.zip
colab upload -s LANE /tmp/fish_colab_runner.py /content/runner.py
colab upload -s LANE /tmp/laneN.txt /content/as_chapters.txt   # scope!
colab exec -s LANE -f /tmp/launch.py       # detached runner; /content/render.log
colab exec -s LANE -f /tmp/poll2.py        # progress markers
```
**The harvest loop must be running** (`nohup bash /tmp/colab_harvest.sh` — v2
polls BOTH sessions): every 4 min it reads each lane's `/content/as_state.json`
and `colab download`s completed chapters to
`/tmp/harvest/armed_struggle_CHAPTER_cillian.mp3` (log: `/tmp/harvest.log`).
Lane scopes are disjoint so filenames never collide. A VM reclaim then costs at
most the in-progress chapter — proven by the first session, lost 40 min into
the Preface.

**Watchdog** (`scripts/colab_watchdog.py`, v2, khpi5 `/tmp/`): covers BOTH
lanes — re-adopt pruned registry entries, respawn keep-alive, refresh proxy
tokens <15 min to expiry, probe `ALIVE|DEAD <remain>` and relaunch a dead
runner while its lane scope is unfinished. **Always start it with the CLI venv
python** (`/home/dave/.local/share/uv/tools/google-colab-cli/bin/python`) —
system python3 dies on `pydantic_core`. It never auto-provisions: a reclaimed
VM logs `manual re-provision required`.

**Windows-side pull (per harvest):** `scp khpi5:/tmp/harvest/* ` →
`evaluations/new-engines/output/`; a local arm polls every 5 min, pulls
atomically (`.part` → rename) and gates each chapter, reporting `ALLDONE` with
a verdict table when all 10 `.gate.json` files exist.

## Gate — the only definition of "done"

```bash
python scripts/gate_book_chapter.py evaluations/new-engines/output/armed_struggle_ch1_cillian.mp3
# → writes <name>.gate.json, exit 0 = PASS / 1 = FAIL
```

Compares ASR (`faster-whisper base`, `WHISPER_MODEL_DIR` =
`evaluations/new-engines/output/.whisper`) against the **exact payload the lane
rendered** (`scratch/as_book/<slug>.json`), plus streaming waveform stats.
Thresholds: word ratio ≥ 0.93, coverage ≥ 0.90, RMS 0.02–0.30, mean|diff| >
0.002, plateau < 2 s, quiet-30 s windows = 0. The gate tool itself was
validated by reproducing the already-gated Preface exactly before it was
trusted on new chapters.

Verdicts so far (2026-09-25):

| section | sents | length | RMS | word ratio | coverage | verdict |
|---|---|---|---|---|---|---|
| preface | 83/83 | 12.3 min | 0.0969 | 0.9937 | 0.965 | **PASS** |
| ch1 | 742/742 | 103.6 min | 0.0988 | 0.9944 | 0.9465 | **PASS** |
| ch4 | 687/687 | 89.6 min | 0.0977 | 0.9940 | 0.9506 | **PASS** |

A gate PASS is a *completeness and health* claim only. Whether the chapter
**sounds** right stays Dave's ear — never promote a PASS to a listening verdict.

## Running a lane from the webapp

The same job can be driven through the app instead of the manual loop above:

1. **Settings → Render Lanes** → set `COLAB_SSH_HOST` / `COLAB_SSH_USER`
   (khpi5) and optionally `FISH_LANE` (`auto` = free lanes only; name
   `lightning` explicitly to spend money).
2. Convert screen → engine **Fish S2 Pro** → pick a lane → Convert. A paid lane
   is refused **at POST** with the reason if its credentials are absent, so a
   doomed job never enters the queue.
3. The app SSHes to `~/as-lane/lane_ctl.sh` on khpi5
   (`status / submit / progress / fetch / log / done / stop`) to create the
   session, upload `as_bundle.zip` + `runner.py`, poll `as_state.json` and pull
   finished chapters into the job's `out/` dir.

**Safety guard:** `submit` refuses while `LANE_COLAB_MAX_SESSIONS` (default 2)
Colab sessions are already up. Colab reclaims VMs to stay inside its limits, so
letting a webapp job start a third session could kill a running render —
including this book. The refusal is loud and actionable, never a silent kill.

**Not yet runnable for this book:** `scripts/fish_bundle.py` derives slugs as
`ch{idx:02d}` from `chapters.list_renderable_chapters()`, which returns 24
sections for `fixtures/armed_struggle.epub`, while the production payloads are
the 10 sections `scripts/regenerate_as_book.py` maps. Queueing *The Armed
Struggle* through the webapp would therefore render a different chapter split.
Reconcile the chapter mapping first — see TTS-WATCH-FINDINGS.md 2026-09-25.

**Finish line:** all 10 sections → chaptered M4B → replace audio of ABS item
`7039379c` → ABS rescan → progress remap (Dave is 39.9% into "New States 1923–63").

**Economics / lanes:** L4 ≈ 1.54 units/h; book ≈ 40–55 GPU-h ≈ 60–90 units of
the ~197 balance. Kaggle fallback lane kernels:
`scripts/prepare_kaggle_fish_as_book_chapter.py` (weekly 30 h cap applies).
Lightning AI: GPU required a linked payment method on free tier (verified
400 PermissionDenied) — **reversed 2026-09-24 ~20:00: Dave added a payment
method + balance; GPU start verified working (real Tesla T4, then stopped)**.
Key in `.secrets/lightning_api_key` + `LIGHTNING_USERNAME=david-mep9n`.
Official rates (lightning.ai/pricing, checked 2026-09-24): T4 $0.55/h,
L4 $0.79/h, L40S $2.14/h.

## Known limits

- Unrespelled raw Gaelic names mangle — the lexicon is the fix (by design).
- Occasional stochastic per-sentence defects (dropped small words, stray pauses) —
  caught by ASR completeness + re-roll; never ship ungated.
- Flat delivery on dramatic lines was solved by the expressive ref crop, not by
  temperature (0.7 flat, 1.0 drifts).
