# Hume TADA-1B — OpenAI-compatible server. CPU by default; CUDA if the host
# provides a GPU. First run downloads ~5GB of models into the HF cache volume.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Explicit CUDA torch first (PyPI default can resolve CPU-only); GPU-capable
# build falls back to CPU cleanly, so one image serves both.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124  && pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY voices/ /app/voices/
ENV VOICES_DIR=/app/voices
ENV HF_HOME=/data/hf
# Trigger NVIDIA container-runtime driver injection on GPU hosts (Vast etc.)
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
EXPOSE 8005
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:8005/health || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8005"]
