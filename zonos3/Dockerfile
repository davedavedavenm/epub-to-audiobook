FROM ubuntu:24.04 AS native

ARG RUNTIME_REV=a50e14117d99181ba7f28047b451ba03ba1a09a9
ENV CARGO_HOME=/opt/cargo RUSTUP_HOME=/opt/rustup CARGO_BUILD_JOBS=2
ENV PATH=/opt/cargo/bin:${PATH}
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake curl git ninja-build \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --silent --show-error --location https://sh.rustup.rs -o /tmp/rustup.sh \
    && sh /tmp/rustup.sh -y --profile minimal --default-toolchain 1.100.0 --no-modify-path \
    && rm /tmp/rustup.sh
WORKDIR /src
RUN git init . \
    && git remote add origin https://github.com/Zyphra/ZONOS3-Mini.git \
    && git fetch --depth 1 origin "$RUNTIME_REV" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$RUNTIME_REV" \
    && git submodule update --init --depth 1 servers/ggml/ggml third_party/zyphra-textnorm
RUN cmake -S servers/ggml -B /build -G Ninja -DCMAKE_BUILD_TYPE=Release \
         -DBUILD_TESTING=OFF -DGGML_NATIVE=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF \
    && cmake --build /build --parallel 2 --target zonos3-server \
    && mkdir /runtime \
    && cp /build/zonos3-server /runtime/ \
    && cp -a /build/ggml/src/libggml*.so* /runtime/ \
    && cp LICENSE /runtime/LICENSE

FROM ubuntu:24.04 AS weights
ARG WEIGHTS_REV=2921b8821772b0bd10a04456863d21abf9d2f283
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /models
COPY models.sha256 .
RUN set -eu; \
    base="https://huggingface.co/Zyphra/ZONOS3-Mini/resolve/${WEIGHTS_REV}"; \
    while read -r sha path; do \
        mkdir -p "$(dirname "$path")"; \
        curl --fail --silent --show-error --location --retry 3 --max-time 600 "$base/gguf/$path" -o "$path"; \
    done < models.sha256; \
    sha256sum --check models.sha256; \
    curl --fail --silent --show-error --location --retry 3 "$base/README.md" -o MODEL_CARD.md

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home zonos
ENV LD_LIBRARY_PATH=/opt/zonos3
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 OMP_THREAD_LIMIT=4 ZAC_THREADS=4
COPY --from=native /runtime/ /opt/zonos3/
COPY --from=weights /models/ /models/
COPY server.py /app/server.py
USER zonos
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python3", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/v1/audio/voices', timeout=3).close()"]
CMD ["python3", "/app/server.py"]
