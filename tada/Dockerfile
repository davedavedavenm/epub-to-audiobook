# Hume TADA-1B — OpenAI-compatible server. CPU by default; CUDA if the host
# provides a GPU. First run downloads ~5GB of models into the HF cache volume.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# Pin the FULL CUDA torch stack (torch + torchaudio + torchvision) BEFORE
# installing hume-tada. hume-tada requires torch>=2.7 and pulls torchaudio/
# torchvision unpinned; if torch isn't already satisfied, `pip install -r
# requirements.txt` re-resolves the whole stack from PyPI to the DEFAULT CUDA
# build (currently cu130 / torch 2.12). cu130 needs an R580+ driver, which
# most GPU hosts lack, so torch silently falls back to CPU (incident
# 2026-07-08d: Vast TADA ran on CPU, cuda_available=false). Preinstalling the
# exact pinned cu126 stack means hume-tada finds torch/torchaudio/torchvision
# already satisfied and touches none of them. cu126 needs only an R560+ driver
# (broad host coverage) and satisfies hume-tada's torch<3,>=2.7. Do NOT drop
# the version pins or the torchaudio/torchvision pins — either one lets the
# requirements install drag the cu130 stack back in.
RUN pip install --no-cache-dir \
        torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
        --index-url https://download.pytorch.org/whl/cu126 \
 && pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY voices/ /app/voices/
RUN useradd -r -s /bin/false appuser \
    && mkdir -p /data/hf \
    && chown -R appuser:appuser /app /data
USER appuser
ENV VOICES_DIR=/app/voices
ENV HF_HOME=/data/hf
# Trigger NVIDIA container-runtime driver injection on GPU hosts (Vast etc.)
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
EXPOSE 8005
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:8005/health || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8005"]
