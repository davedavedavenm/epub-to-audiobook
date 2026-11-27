# ZONOS3-Mini on CPU

The container serves Zyphra's Imogen preset at `http://zonos3:8080`. It uses
ZONOS3-Mini's quantized backbone and `keep2_plain` decoder, the publisher's
pre-encoded reference codes, UK English and the native text normalizer.
Sampling retains the vendor defaults with seed 42. The stock preset and the
optional custom-reference route run on the local service.

- [MIT native runtime, pinned revision](https://github.com/Zyphra/ZONOS3-Mini/tree/a50e14117d99181ba7f28047b451ba03ba1a09a9)
- [Apache-2.0 weights, pinned revision](https://huggingface.co/Zyphra/ZONOS3-Mini/tree/2921b8821772b0bd10a04456863d21abf9d2f283)
- [Native GGML build, model and reference options](https://github.com/Zyphra/ZONOS3-Mini/blob/a50e14117d99181ba7f28047b451ba03ba1a09a9/servers/ggml/README.md)

`POST /v1/audio/speech` accepts `input`, a stock or enrolled `voice`, and
`response_format: mp3` or `wav`. The stock ID is `zonos3_imogen_audition`.
The default is MP3 at 128 kbit/s. Both
outputs are mono at 44.1 kHz. The input limit is 4,096 characters. The
bridge splits larger inputs into bounded native requests and adds 250 ms
at joins. Keep conversion requests near 600 characters to preserve pacing
and allow an end-to-end client timeout above the bridge's 360-second
synthesis deadline. Concurrent requests receive HTTP 429 with
`Retry-After: 5`.

The native service listens on loopback only. The public container listener
opens after the pinned decoder and speaker have successfully synthesized
a short probe. Use `GET /v1/audio/voices` or `GET /health` for readiness.
The model and preset are verified by SHA-256 at image build time.
The container needs roughly 3 GiB of RAM and four CPU threads. No runtime
model downloads, GPU devices or host port publication are needed.

## Enroll a custom narrator in Studio

Enable the `zonos3` profile and open **Voices → Clone a voice**. Select
**ZONOS3-Mini (local)**, give the voice a name and upload an 8–45 second
PCM WAV at 16–48 kHz. Use clean speech from one speaker. After the status reads
**ready**, refresh Voices, play the cached shared-test recording and use the
same voice in the local book picker. Studio uses the native English text
frontend for previews, books and recovery. This path derives a speaker
embedding and leaves the accent unclassified.

The webapp needs the local faster-whisper `base` cache under
`WHISPER_MODEL_DIR` (default `/data/models/whisper`). Set
`ZONOS3_PREVIEW_ASR_MODEL` to use a different installed model. On a fresh
install, populate the cache once from the stack checkout. The command fetches
model weights and takes no audio. [faster-whisper 1.1.1 model downloader](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.1.1/faster_whisper/utils.py).

```sh
docker compose exec -T webapp python -c 'import os; from faster_whisper.utils import download_model; download_model(os.getenv("ZONOS3_PREVIEW_ASR_MODEL", "base"), cache_dir=os.getenv("WHISPER_MODEL_DIR", "/data/models/whisper"))'
```

Studio checks
that the preview decodes and uses unprompted ASR to flag missing spans and the
ending. If the preview omits part of the passage, Studio retries once with
smaller chunks. The voice ID records the successful chunk profile and the
same profile is used for books and recovery. ASR checks text completeness.

The bridge produces a 192-float `.npy` once with the upstream `spk-encoder-cli`.
The pinned encoder from the weights revision above is `spk-encoder.gguf`,
SHA-256 `9539f340b70be246005403b9c254732e180e85e0b3c57fb1973f0d6bc6c59bdc`.
Studio persists the embedding and reference/preview hashes under
`data/voices/zonos3`. The source WAV is temporary. The service reads the
embedding through a read-only mount and verifies its digest against the voice
ID before passing it to native generation. A failed replacement leaves the
previous ready voice available. A successful replacement changes future
selections once its preview is ready. Existing jobs retain their exact
embedding for normal conversion and recovery. Removing a voice removes it
from the picker and removes artifacts without saved jobs.
