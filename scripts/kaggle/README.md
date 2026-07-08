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

## Paid fallback (works today, no phone verification)
`scripts/vast-gpu.sh up tada` → point `convert_book.py` at the printed URL.
~$0.25/hr RTX 3090; a few chapters cost pennies. Always `down` when finished.
