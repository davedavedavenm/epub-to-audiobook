# MeloTTS is old enough that its tested Python/transformers stack matters.
# Keep this deliberately boring and CPU-only: Zorin has no discrete GPU.
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ffmpeg git libsndfile1 espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir \
      torch==2.1.2 torchaudio==2.1.2 \
      --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY server.py .

RUN useradd -r -s /bin/false appuser \
    && mkdir -p /data/hf /data/nltk \
    && chown -R appuser:appuser /app /data
USER appuser

ENV HF_HOME=/data/hf
ENV NLTK_DATA=/data/nltk
# librosa JIT-compiles through numba at import time. The installed package is
# read-only to appuser, so give numba an explicit writable cache directory.
ENV NUMBA_CACHE_DIR=/tmp/numba
EXPOSE 8007

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8007/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8007"]
