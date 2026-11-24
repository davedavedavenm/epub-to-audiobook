# Pinned upstream Tontaube lite CPU and OpenAI-compatible private adapter.
FROM ghcr.io/astral-sh/uv:0.11.14@sha256:1025398289b62de8269e70c45b91ffa37c373f38118d7da036fb8bb8efc85d97 AS uv
FROM ubuntu:24.04@sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never PATH="/opt/tontaube/.venv/bin:/usr/local/bin:/usr/bin:/bin"
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg g++ git libgomp1 libopus0 ninja-build python3 python3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /opt/tontaube
RUN git init -q && git remote add origin https://github.com/craitech/tontaube.git \
    && git fetch --depth 1 origin ef254ca3d7dcbf536e83b04fd38798aea6b5e759 \
    && git checkout --detach FETCH_HEAD \
    && echo '7835b63889fcca6f5d0b7342f8a5fd407191af896f91376e294bb13ef9807d9c  uv.lock' | sha256sum -c - \
    && echo '806822d41ebe37b1bf3c19e8ccd5d0e71f1d4807d763e69486bdb5dd9bbc64d2  voices/samples/Marcus.mp3' | sha256sum -c - \
    && rm -rf .git
COPY lite_requirements.py /opt/private/lite_requirements.py
RUN uv venv --python /usr/bin/python3 \
    && uv export --frozen --no-dev --no-emit-project --format requirements-txt > /tmp/upstream.lock \
    && python /opt/private/lite_requirements.py /tmp/upstream.lock > /tmp/lite.lock \
    && uv --no-config pip install --no-deps --require-hashes -r /tmp/lite.lock \
    && uv --no-config pip install --no-deps --index-url https://download.pytorch.org/whl/cpu \
        torch==2.9.1+cpu torchaudio==2.9.1+cpu torchvision==0.24.1+cpu \
    && python -c "import torch, torchaudio; assert torch.version.cuda is None" \
    && rm /tmp/upstream.lock /tmp/lite.lock

COPY --chmod=0644 server.py /opt/private/server.py
RUN install -d -o 1000 -g 1000 -m 0700 /data/cache
USER 1000:1000
ENV HF_HOME=/data/cache/huggingface XDG_CACHE_HOME=/data/cache \
    TONTAUBE_CACHE_DIR=/data/cache/tontaube HF_HUB_OFFLINE=1 \
    LITE_CPU_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MAX_JOBS=2
EXPOSE 8080
CMD ["uvicorn", "server:app", "--app-dir", "/opt/private", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
