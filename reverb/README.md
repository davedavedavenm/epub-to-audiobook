# Reverb stock narrator service

The internal HTTP service uses port 8080. `/health` and `/v1/audio/voices`
return HTTP 503 until the stock model and preset load. `/v1/audio/speech`
accepts `reverb_en_male_narrator_audition` and returns WAV or MP3. Send at most
6,000 characters per request at speed 1.0. When the CPU is busy, retry after
the interval indicated by the HTTP 503 response.

Give the container read-only access to the populated Hugging Face `hub`
directory at `/data/hf/hub`. Include the full cache root so its snapshot
symlinks resolve. The adapter uses Reverb-TTS v1.0.0 revision
`72be799c8fb6d56a206d260b425c48bf3bd5943d`, the upstream runtime 1.0.0 at
`ba46de8d0473bf7281ce3f5bbdfdadad691d7398`, and the runtime's Higgs Audio v2
codec pin `0e3a9177c2991016b8e5e17d23aa474ee665bef2`. Inference runs
on CPU and loads the INT8 checkpoint as float32, using two threads by default.
The runtime applies English Verbalis, sentence chunking, and seed 42 with
consecutive seeds per chunk. The adapter keeps the supplied text intact.

To prepare the cache on an internet-connected host, install
`huggingface_hub==2.4.0` in a Python environment and run the exact downloads
below. Pass the same absolute cache path to Compose as `REVERB_HUB_CACHE`.
Copy the entire Hub cache if preparing it on a different machine. [Hugging Face CLI documentation](https://huggingface.co/docs/huggingface_hub/guides/cli).

```bash
cache="${REVERB_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
hf download software-mansion/Reverb-TTS \
  model/safetensors/int8/config.json model/safetensors/int8/model.safetensors \
  model/tokenizer.json model/tokenizer_config.json model/chat_template.jinja \
  voices/en_male_narrator_1.json \
  --revision 72be799c8fb6d56a206d260b425c48bf3bd5943d --cache-dir "$cache"
hf download eustlb/higgs-audio-v2-tokenizer config.json model.safetensors \
  --revision 0e3a9177c2991016b8e5e17d23aa474ee665bef2 --cache-dir "$cache"
```

Software Mansion publishes 16 stock presets covering seven languages. The
upstream API supports zero-shot cloning using clean single-speaker audio and
an exact transcript. The usage guide recommends 3–10 seconds of audio. This
service is configured for the stock English male narrator 1. Obtain consent
from any speaker whose voice is cloned and disclose synthetic speech. The
code uses Apache-2.0 and model weights use CC BY-NC 4.0. Audio carries
Software Mansion AI Labs attribution. [Model card](https://huggingface.co/software-mansion/Reverb-TTS)
and [pinned usage guide](https://github.com/software-mansion-labs/Reverb-TTS/blob/ba46de8d0473bf7281ce3f5bbdfdadad691d7398/docs/usage.md).
