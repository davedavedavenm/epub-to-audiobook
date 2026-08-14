FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

RUN useradd -r -m -s /bin/false appuser \
    && mkdir -p /data/hf \
    && chown -R appuser:appuser /app /data /home/appuser
USER appuser

ENV HF_HOME=/data/hf
ENV CUDA_VISIBLE_DEVICES=
EXPOSE 8012

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8012/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8012"]

