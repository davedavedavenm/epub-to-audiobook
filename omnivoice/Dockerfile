# CPU-only OmniVoice service for the Zorin host. Model weights are cached in
# a named volume and are not baked into the image or repository.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg git libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir \
      torch==2.8.0 torchaudio==2.8.0 \
      --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY server.py .

RUN useradd -r -s /bin/false appuser \
    && mkdir -p /data/hf \
    && chown -R appuser:appuser /app /data
USER appuser

ENV HF_HOME=/data/hf
ENV OMNIVOICE_DEVICE=cpu
ENV OMNIVOICE_DTYPE=float32
EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8008/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8008"]

