FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.15.0+cpu torchaudio==2.11.1+cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip check
COPY server.py .

RUN useradd -r -m -s /bin/false appuser && mkdir -p /data/hf
USER appuser
ENV HF_HOME=/data/hf HF_HUB_OFFLINE=1 CUDA_VISIBLE_DEVICES="" \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).close()"]
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
