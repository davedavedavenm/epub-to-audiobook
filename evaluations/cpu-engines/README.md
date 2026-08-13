# Isolated CPU-engine screen

This directory evaluates new upstream engines without registering them in the
application, starting a background service, or giving an ordinary book job a
new route. The containers are one-shot processes with four CPU cores, explicit
memory limits, no GPU devices and no paid/cloud fallback.

Official upstreams pinned for the 2026-08-13 screen:

| Engine | Pin | Licence / boundary |
|---|---|---|
| Pocket TTS | PyPI `2.1.0`; upstream HEAD `7fc13c7` recorded | MIT; Arthur reference clone |
| NeuTTS Air | PyPI `1.4.1`; upstream HEAD `ac69851` recorded | Apache-2.0 Air Q4 GGUF; official `jo.pt` + exact `jo.txt`, because Arthur's exact reference transcript is not in this repo |
| KittenTTS | official v0.8.1 wheel; upstream HEAD `9f3e0d8` recorded | Apache-2.0 developer preview; preset voices only |

All engines receive the byte-identical canonical text from
`webapp/voice_sample.py`. Outputs and JSON measurements go to `output/`, which
is ignored by git. A successful short render is only a listening candidate; it
does not admit an engine to long-form or production use.

Run one candidate at a time on Zorin:

```bash
docker compose -f evaluations/cpu-engines/compose.yaml run --rm pocket
docker compose -f evaluations/cpu-engines/compose.yaml run --rm neutts
docker compose -f evaluations/cpu-engines/compose.yaml run --rm kitten
```

Copy approved clips to `/data/previews/cpu_*.mp3` only after checking that the
JSON reports a non-zero, full output. Dave's listening verdict is the quality
gate; ASR is not used to rank these clips.
