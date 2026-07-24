# Chatterbox Turbo TTS — OpenAI-compatible server.
# CPU by default (works on any machine, incl. friends without a GPU).
# On first run it downloads the ~700MB Turbo model into the HF cache volume.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# chatterbox-tts pins torch==2.6.0 — preinstall the CUDA build of exactly that
# version so pip keeps it (GPU-capable, falls back to CPU cleanly).
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124  && pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY voices/ /app/voices/

RUN useradd -r -s /bin/false appuser \
    && mkdir -p /data/hf \
    && chown -R appuser:appuser /app /data
USER appuser

ENV VOICES_DIR=/app/voices
ENV HF_HOME=/data/hf
# librosa (pulled by chatterbox master) JIT-compiles via numba at load; appuser
# has no writable default cache dir, so numba raises "cannot cache function
# '__o_fold': no locator available". Point it at a writable path.
ENV NUMBA_CACHE_DIR=/tmp/numba
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
EXPOSE 8004

HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8004/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8004"]
