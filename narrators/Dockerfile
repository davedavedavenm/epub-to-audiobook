FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg libsndfile1 espeak-ng \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
COPY narrators/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY narrators/server.py .
COPY webapp/liked_voices.py .
RUN useradd -r -m -s /bin/false appuser && mkdir -p /data/hf /app/references \
    && chown -R appuser:appuser /data /app /home/appuser
USER appuser
ENV HF_HOME=/data/hf CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
EXPOSE 8016
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8016/health || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8016"]
