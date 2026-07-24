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
