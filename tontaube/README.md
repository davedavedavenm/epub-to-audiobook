# Marcus private CPU backend

This service exposes the bundled Marcus reference through the internal OpenAI-style speech API. The engine listens on container port 8080. The native Tontaube server listens on loopback in the same container. Keep the engine off published ports and allow only the owner to submit synthesis through the Studio.

The adapter uses [Tontaube lite v1.1.0](https://github.com/craitech/tontaube/tree/ef254ca3d7dcbf536e83b04fd38798aea6b5e759) and the [pinned V1.1 INT4 weights](https://huggingface.co/TontaubeAI/TontaubeV1.1-int4/tree/2cff8331a357cdd50b05c823f5172eaa3ac6c121). It uses the official native CPU pipeline, the upstream lock for the CPU path, and same-version [official PyTorch 2.9.1 CPU wheels](https://pytorch.org/get-started/previous-versions/#v291). The container installs no CUDA or vLLM runtime. It needs Linux amd64 with AVX2, FMA and F16C.

The [Tontaube Community Model License 1.0](https://huggingface.co/TontaubeAI/TontaubeV1.1-int4/blob/2cff8331a357cdd50b05c823f5172eaa3ac6c121/LICENSE) permits personal noncommercial use under Section 2. Infrastructure operated solely for the licensee falls outside the speech-generation service definition. Giving anyone else hosted generation access requires a separate written licence under Section 3a. The included stock reference is MIT-licensed with the rest of the [bundled voice catalogue](https://github.com/craitech/tontaube/tree/v1.1.0/voices).

Bind the private cache in read-write mode at `/data/cache` as container UID 1000. The container starts offline, so pre-seed the exact Hugging Face snapshots under `huggingface/hub/` and the prepared VibeVoice runtime cache under `tontaube/vibevoice-acoustic-tokenizer/`. The preflight pins DualCodec `a4243540cfb149e38c82dc80dfa5c83d5e0af2a9`, W2V-BERT `da985ba0987f70aaeb84a80f2851cfac8c697a7b` and VibeVoice `c00898d257e6b46004e3e2866a47534085fb685a` through the upstream release. The native kernels compile on their first start on the target host. The image itself includes the stock Marcus reference and verifies its SHA-256 `806822d41ebe37b1bf3c19e8ccd5d0e71f1d4807d763e69486bdb5dd9bbc64d2` at build time. Keep that cache private and retain the upstream notices alongside the weights.

To prepare a new private cache from the upstream releases, run the pinned
preflight with temporary network access. Create a mode-0700 host directory
owned by UID/GID 1000. The running container uses the same owner.

```bash
install -d -m 0700 /path/to/private/cache
docker run --rm \
  --mount type=bind,source=/path/to/private/cache,target=/data/cache \
  -e HF_HUB_OFFLINE=0 -e TTS_BACKEND=lite -e LITE_DEVICE=cpu \
  -e TTS_MODEL_REPO_ID=TontaubeAI/TontaubeV1.1-int4 \
  -e TTS_MODEL_REVISION=2cff8331a357cdd50b05c823f5172eaa3ac6c121 \
  epub-to-audiobook-tontaube python -m app.cli preflight
```

- `GET /v1/audio/voices` responds with `tontaube_marcus_audition` once all native models load. While loading or after a failure it responds with HTTP 503.
- `POST /v1/audio/speech` accepts the stock voice ID, English input prepared by the Studio, `response_format` of `mp3` or `wav`, and stock speed `1.0`. Synthesis uses the audition's audiobook style and seed 42 with the verbalizer disabled.
- The adapter permits one active synthesis request. Keep caller request timeouts at 900 seconds for bounded Studio chunks and the approved preview.
