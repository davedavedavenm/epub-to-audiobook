# Kaggle free-GPU conversion runbook

Runs the repo's TADA engine + the full fixed preprocessing pipeline on Kaggle's
free GPU (T4, 30 h/week). Faithful test path: it starts the real
`tada/server.py` and runs `scripts/convert_book.py` — no bespoke code.

## One-time prerequisites
1. **Phone-verify the Kaggle account** at <https://www.kaggle.com/settings>
   ("Phone Verification"). Without this, kernels get **no internet** and every
   `pip`/`git`/HuggingFace call fails with "Temporary failure in name
   resolution" — regardless of `enable_internet: true`. (Incident 2026-07-08.)
2. Install + auth the CLI (newer `KGAT_` token, no username needed):
   ```bash
   pip install kaggle
   printf '%s' 'KGAT_xxxxxxxx' > ~/.kaggle/access_token   # from kaggle.com/settings > API
   ```
   On Windows the CLI has a temp-dir bug on upload — pre-create the mangled path
   it wants, e.g. `mkdir -p "$LOCALAPPDATA/Temp/.kaggle/uploads/C_"`.

## Run
```bash
# 1. epub dataset (once per book; edit dataset-metadata.json id/title)
cp your_book.epub apple_in_china.epub
kaggle datasets create -p .            # or `datasets version -p .` to update

# 2. push + run the kernel (edit START/END/VOICE at the top of run.py)
kaggle kernels push -p .
kaggle kernels status  davedavedavedavenm/apple-china-tada-ch1-2
kaggle kernels output  davedavedavedavenm/apple-china-tada-ch1-2 -p ./out
```
Outputs are `NNN.mp3` per chapter in the kernel output. `run.py` refuses to
proceed if the GPU isn't actually visible (`cuda_available` gate).

## NVIDIA MagpieTTS v2607 stateful long-form gate

`build_magpie_longform_gate.py` stages one private free-T4 job under
`scratch/magpie_longform/kernel`. It pins the official v2607 model revision and
SHA-256 plus the official NeMo Speech v3.0.0 source commit. It refuses CPU,
non-T4 and paid fallback. T4 is not in NVIDIA's documented supported-GPU list,
so this is explicitly a capacity experiment rather than a supported deployment.

```bash
python scripts/kaggle/build_magpie_longform_gate.py
python -m kaggle kernels push -p scratch/magpie_longform/kernel
python -m kaggle kernels status davedavedavedavenm/nvidia-magpie-v2607-longform-gate
python -m kaggle kernels output davedavedavedavenm/nvidia-magpie-v2607-longform-gate \
  -p scratch/magpie_longform/output
python scripts/kaggle/validate_magpie_longform_gate.py \
  scratch/magpie_longform/output/out
```

One model load renders the five official English presets (`Aria`, `Jason`,
`John`, `Leo`, `Sofia`) on the same 202-word prepared hard text, then gives
John a 1,470-word stateful continuity arm. The manifest records source,
model/runtime, long-form chunk, audio, memory and RTF evidence. Every output is
fully decoded; no ASR is used. A successful job proves only capacity and file
integrity. Dave's listening verdict is required before any app integration,
voice exposure or long-form quality claim.

## VibeVoice same-speaker-turn listening gate

`build_vibe_turn_reset_kernel.py` stages two independent private kernels under
`scratch/vibe_turn_reset/kernel_A` and `kernel_B`. This evaluates the exact
community runtime's documented remedy for speech that becomes too fast:
multiple newline-delimited `Speaker 1:` turns inside one model generation. It
is not ordinary converter chunking and does not alter `vibevoice/server.py` or
production defaults.

```bash
python scripts/kaggle/build_vibe_turn_reset_kernel.py
python -m kaggle kernels push -p scratch/vibe_turn_reset/kernel_A
# Push B only after A proves the environment and completes.
python -m kaggle kernels push -p scratch/vibe_turn_reset/kernel_B
```

The builder pins source/reference/script hashes, official weights, community
runtime commit, cfg 2.0, DDPM 10, seed, FP16 and SDPA. Each job gets a fresh
model process. It reconstructs all 1,998 source words from the labelled turns,
decodes the generated MP3 and runs ASR only as a completeness guard. Voice
quality and pacing remain a human listening decision.

## IndexTTS-2.5 sentence-boundary Arthur follow-up

`build_indextts25_gate.py` stages one private, explicitly free-T4 job under
`scratch/indextts25_boundary_fix/kernel`. It pins official release commit
`39207d91c30899cad1e7c1b9eb678c241f678e55`, model revision
`c39ce5ba981572cb187443877ff559dfb246ce63`, FP32 and Arthur's exact reference
hash. It refuses P100, CPU fallback and non-T4 GPUs.

```bash
python scripts/kaggle/build_indextts25_gate.py
python -m kaggle kernels push -p scratch/indextts25_boundary_fix/kernel
python -m kaggle kernels status davedavedavedavenm/indextts25-arthur-boundary-fix
python -m kaggle kernels output davedavedavedavenm/indextts25-arthur-boundary-fix \
  -p scratch/indextts25_boundary_fix/output
```

The original two-arm gate garbled speech at its exact 200 ms internal joins.
This follow-up produces one clip only. It byte-pins the corrected explicit text
(`one point five gigawatts`), splits it into nine complete sentences, asserts
that Index's official 120-token splitter cannot subdivide any call, and joins
the resulting PCM with 200 ms sentence gaps. Per-sentence hashes and durations
are included in the manifest.
The kernel validates exact source/reference/weight hashes, WAV/MP3 structure,
full decode, duration, memory and RTF, and writes a manifest. It deliberately
does not run ASR; Dave's listening verdict is the quality gate. Do not run a
long-form follow-up unless this corrected gate passes by ear.

Kaggle's 2026-08 global Python image can contain mutually incompatible NumPy
files. The working gate follows the existing CosyVoice isolation pattern:
`uv`-managed Python 3.10, seeded venv, inherited `PYTHONPATH` and user-site
packages disabled, plus `numpy==1.26.4`, `scipy==1.12.0` and
`scikit-learn==1.4.2`. The SciPy 1.12 pin follows the
[official compatibility table](https://docs.scipy.org/doc/scipy-1.13.0/dev/toolchain.html),
not trial-and-error version selection.

## CosyVoice 3 (`run_cosyvoice3.py`)

Zero-shot English narration cloned from a UK reference clip, on Kaggle's free
T4. Push/run/fetch exactly as above, with `kernel-metadata.json` pointed at
`run_cosyvoice3.py`.

**The pins are not optional.** Runs v4-v16 installed CosyVoice's dependencies
*unpinned* on Kaggle's stock Python 3.12. They completed with no error and
wrote plausible-looking WAVs — but every one was fluent multilingual babble
unrelated to the input text (Whisper detected Mongolian, Hungarian, Arabic and
Chinese on English input). The model weights were complete and the reference
transcript was correct; the dependency skew alone caused it, the repo pinning
`transformers==4.51.3` for its Qwen2 LLM backbone being the prime suspect.

So the driver follows the upstream README literally: Python 3.10 (`uv` supplies
only the interpreter, `pip` resolves), `pip install -r requirements.txt` with
the repo's own pins, `snapshot_download` into
`pretrained_models/Fun-CosyVoice3-0.5B`, and the `inference_zero_shot` prompt
signature from `example.py` (`'You are a helpful assistant.<|endofprompt|>' +
transcript`). Torch is installed before `requirements.txt` because deepspeed's
sdist imports torch at build time.

Two traps worth knowing:
- The model dir must contain the `CosyVoice-BlankEN/` subfolder — the config
  resolves `qwen_pretrain_path` to it. A partial download there gives you a
  randomly-initialised LLM and, again, silent babble.
- A zero-shot prompt transcript that does not match the prompt audio degrades
  output badly. `infer_narration.py` uses an ASR-verified transcript.

**Never trust the WAVs by ear-free inspection.** The kernel ASR-transcribes
every paragraph, prints a word-sequence similarity against the input, and ends
in `VERDICT: PASS/FAIL`; `out/asr_verification.json` carries the same. Big
artefacts go to `/tmp` (`/kaggle/working` has a ~20 GB quota); only audio and
transcripts land in `/kaggle/working/out`.

### Confirmed working (2026-07-24)

`build_chapter_kernel.py` generates a single-file chapter kernel (Kaggle script
kernels take no attachable sources, so the text is embedded at build time) and
narrated The Yellow Wallpaper end to end:

| | |
|---|---|
| audio | 30.3 min, 24 kHz mono |
| generation | 26.4 min on a **Tesla P100** (RTF ~0.87) |
| whole run | 32 min, of which ~9 min install + 4 min model download |
| verification | 105/105 chunks, mean similarity 0.966, min 0.833, none < 0.75 |

The P100 needs no special handling — earlier scripts forced a CPU fallback on
compute capability < 7.0, which was never necessary and only made things slower.
The kernel ASR-checks chunk 0 and aborts before the remaining ~30 min of GPU if
it doesn't match, so a broken engine costs 12 minutes rather than a full run.

Two bugs that cost real time, both in the driver rather than CosyVoice:
`python -c {repr(snippet)}` sends literal `\n` to the shell and dies with a
SyntaxError — write the snippet to a file instead. And when polling
`kaggle kernels status`, match case-insensitively: the terminal state is
`KernelWorkerStatus.ERROR`, so a `*error*` glob silently reports a dead job as
running forever.

## Paid fallback (works today, no phone verification)
`scripts/vast-gpu.sh up tada` → point `convert_book.py` at the printed URL.
~$0.25/hr RTX 3090; a few chapters cost pennies. Always `down` when finished.
