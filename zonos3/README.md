# ZONOS3-Mini on CPU

The container serves Zyphra's Imogen preset at `http://zonos3:8080`. It uses
ZONOS3-Mini's quantized backbone and `keep2_plain` decoder, the publisher's
pre-encoded reference codes, UK English and the native text normalizer.
Sampling retains the vendor defaults with seed 42. The bridge does not
accept arbitrary speaker references or start a cloud job.

- [MIT native runtime, pinned revision](https://github.com/Zyphra/ZONOS3-Mini/tree/a50e14117d99181ba7f28047b451ba03ba1a09a9)
- [Apache-2.0 weights, pinned revision](https://huggingface.co/Zyphra/ZONOS3-Mini/tree/2921b8821772b0bd10a04456863d21abf9d2f283)
- [Native GGML build, model and reference options](https://github.com/Zyphra/ZONOS3-Mini/blob/a50e14117d99181ba7f28047b451ba03ba1a09a9/servers/ggml/README.md)

`POST /v1/audio/speech` accepts `input`, `voice: zonos3_imogen_audition` and
`response_format: mp3` or `wav`. The default is MP3 at 128 kbit/s. Both
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
