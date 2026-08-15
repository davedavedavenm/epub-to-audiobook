# NVIDIA Magpie hosted-NIM diagnostic

This is a one-request root-cause check, not a production engine. Dave rejected
the raw NeMo v2607 outputs after all five short arms and the long arm shared an
early cut/clipping defect. NVIDIA's hosted Magpie service uses its Riva/NIM path,
so one direct WAV comparison can tell us whether that defect belongs to the raw
runtime or survives the production service.

## Free-use boundary

NVIDIA Developer Program members currently get free hosted NIM endpoint access
for prototyping, with account and shared-traffic rate limits. NVIDIA does not
publish a guaranteed audiobook-size allowance. Production or end-user NIM use
requires NVIDIA AI Enterprise; current official starting pricing is USD4,500
per GPU/year or about USD1/GPU-hour in cloud deployments. Therefore:

- use the hosted endpoint for this single focused diagnostic only;
- do not submit a book, add automatic retry, or connect it to the queue;
- do not treat “unlimited prototyping” as permission for production audiobooks.

Official sources checked 2026-08-15:
[NIM FAQ](https://docs.api.nvidia.com/nim/docs/product),
[NIM for Developers](https://developer.nvidia.com/nim), and the
[Magpie HTTP API](https://build.nvidia.com/nvidia/magpie-tts-multilingual/api).

## Obtain and use the key

1. Sign in at the official [Magpie NIM page](https://build.nvidia.com/nvidia/magpie-tts-multilingual).
2. Join the free NVIDIA Developer Program if prompted, then select **Get API Key**.
3. Store the key only in the current shell as `NVIDIA_API_KEY`; never add it to
   `.env`, a command argument, source control, screenshots, logs, or chat.
4. From the repository root, run exactly once:

   ```powershell
   python scripts/nvidia_nim_magpie_control.py --confirm-single-free-prototype-request
   ```

The client sends the fixed two-sentence Aria control from the failed passage,
uses NVIDIA's documented HTTP endpoint and 44.1 kHz `LINEAR_PCM`, has no retry
loop, refuses to overwrite a prior result, and validates mono 16-bit WAV before
keeping it under ignored `scratch/`.
