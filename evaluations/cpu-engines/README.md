# Isolated CPU-engine screen

This directory evaluates new upstream engines without registering them in the
application, starting a background service, or giving an ordinary book job a
new route. The containers are one-shot processes with four CPU cores, explicit
memory limits, no GPU devices and no paid/cloud fallback.

Official upstreams pinned for the 2026-08-13 screen:

| Engine | Pin and official instructions checked 2026-08-14 | Licence / boundary |
|---|---|---|
| Pocket TTS | PyPI `2.1.0`; [official README at `7fc13c7`](https://github.com/kyutai-labs/pocket-tts/blob/7fc13c7/README.md) uses `TTSModel.load_model()`, `get_state_for_audio_prompt()` and `generate_audio()` | MIT code; official `peter_yearsley` preset. Voice cloning weights require accepting Kyutai's Hugging Face model terms and authenticated download; never bypass that gate. |
| NeuTTS Air | PyPI `1.4.1`; [official README at `ac69851`](https://github.com/neuphonic/neutts/blob/ac69851f28fc63a487917e7c2e27f0d75c759cba/README.md) uses `NeuTTS(...).infer(input_text, ref_codes, ref_text)`; official CPU wheels `torch==2.8.0`, `torchaudio==2.8.0`, `torchao==0.12.0` | Apache-2.0 Air Q4 GGUF; official `jo.pt` + exact `jo.txt`, because Arthur's exact reference transcript is not in this repo |
| KittenTTS | [official v0.8.1 README](https://github.com/KittenML/KittenTTS/blob/0.8.1/README.md) uses `KittenTTS(...).generate(text, voice=...)`; release wheel and upstream HEAD `9f3e0d8` recorded | Apache-2.0 developer preview; preset voices only |

All engines receive the byte-identical canonical text from
`webapp/voice_sample.py`. Outputs and JSON measurements go to `output/`, which
is ignored by git. A successful short render is only a listening candidate; it
does not admit an engine to long-form or production use.

Measured on the i5-12400 Zorin host (four-core caps):

| Clip | Audio | Wall | RTF | Peak RSS | Important boundary |
|---|---:|---:|---:|---:|---|
| Pocket Peter Yearsley | 64.080 s | 66.220 s | 1.033 | 1307.6 MiB | official preset; one >50-token warning; cloning gated |
| NeuTTS Jo | 72.610 s | 357.875 s | 4.929 | 2842.4 MiB | ten sentence chunks; whole passage truncated; phonemizer warnings |
| Kitten Jasper | 72.317 s | 166.590 s | 2.304 | 1047.9 MiB | preset, not a clone |
| Kitten Rosie | 80.267 s | 141.368 s | 1.761 | 1090.4 MiB | preset, not a clone |

NeuCodec's package metadata permits new incompatible TorchAO releases. The
screen therefore pins the oldest officially permitted Torch/TorchAudio/TorchAO
CPU combination. Do not loosen those pins without re-running the import and
full-duration checks.

Run one candidate at a time on Zorin:

```bash
docker compose -f evaluations/cpu-engines/compose.yaml run --rm pocket
docker compose -f evaluations/cpu-engines/compose.yaml run --rm neutts
docker compose -f evaluations/cpu-engines/compose.yaml run --rm kitten
```

## Pinned numbers-and-currency A/B

Dave judged Peter, Jo, Jasper and Rosie decent/good, but heard poor number and
currency handling in all four original clips. Those clips used the official
APIs above but, contrary to the earlier “app-path” description, passed raw text
straight to the models. `numeric_ab.py` now pins a focused corpus and its source
hash. It provides two controlled inputs while keeping model, voice and settings
fixed:

- `raw`: byte-identical symbols/digits sent through the official API.
- `normalized`: the repo's deterministic unclassified-engine preprocessing,
  including spoken years, ordinals, percentages, large numbers and currencies.
  Every image pins the app's `num2words==0.5.14`; the harness fails rather than
  silently returning digits if that dependency is missing.

Run one engine and one arm at a time so the product remains responsive:

```bash
NUMERIC_AB_ARM=raw docker compose -f evaluations/cpu-engines/compose.yaml run --rm pocket
NUMERIC_AB_ARM=normalized docker compose -f evaluations/cpu-engines/compose.yaml run --rm pocket
```

Repeat for `neutts` and `kitten`. Reports record both the raw-source hash and
the exact rendered-input hash. During an unresolved test, blind-copy the
resulting MP3s into the preview cache and keep the assignment out of the
browser labels.

**Verdict (2026-08-14):** Peter A, Jo A, Jasper A and Rosie B were the
normalized arms. Dave selected all four. The original shared numeric failure
was raw evaluation input, not a demonstrated engine limitation. Peter had no
reported residual issue; Jo produced “the e order” around “the order”; Jasper
started slightly scratchy; Rosie gave perhaps the strongest handling.

## Official voice inventory

- Pocket TTS English catalogue: `alba`, `anna`, `azelma`, `bill_boerst`,
  `caro_davy`, `charles`, `cosette`, `eponine`, `eve`, `fantine`, `george`,
  `jane`, `jean`, `javert`, `marius`, `mary`, `michael`, `paul`,
  `peter_yearsley`, `stuart_bell`, `vera`. Other languages: `giovanni` (it),
  `lola` (es), `juergen` (de), `rafael` (pt), `estelle` (fr). A supplied WAV
  is also supported, subject to the legitimate model-access gate.
- NeuTTS references: `dave`, `jo`, `emily`, `paul`, `sophie`, `steven` (en),
  `mateo` (es), `greta` (de), `juliette` (fr). Custom references use a clean
  3–15 second mono WAV plus exact transcript.
- KittenTTS presets: `Bella`, `Jasper`, `Luna`, `Bruno`, `Rosie`, `Hugo`,
  `Kiki`, `Leo`; no official cloning path is documented.

The exact official source links are in the table at the top of this file.

Copy approved clips to `/data/previews/cpu_*.mp3` only after checking that the
JSON reports a non-zero, full output. Dave's listening verdict is the quality
gate; ASR is not used to rank these clips.
