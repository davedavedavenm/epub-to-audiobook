FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

ARG QWEN3_RUNTIME_SHA=022e286b98fbec7e1e916cb940cdf532cd9f488e
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg git git-lfs libsox-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    "qwen-tts @ git+https://github.com/QwenLM/Qwen3-TTS.git@${QWEN3_RUNTIME_SHA}" \
    fastapi uvicorn soundfile

WORKDIR /app
COPY qwen3/server.py /app/server.py
COPY qwen3/ref_transcripts.json /app/ref_transcripts.json
COPY chatterbox/voices/ /app/voices/
RUN python -c "import hashlib,pathlib; p=pathlib.Path('/app/voices/uk_male_minter.wav'); b=p.read_bytes(); assert b[:4] == b'RIFF' and len(b) == 864182 and hashlib.sha256(b).hexdigest() == '8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252', 'Arthur voice is missing/corrupt (run git lfs pull)'"
RUN useradd -r -m -s /bin/false appuser && mkdir -p /data/hf /app/voices/custom \
    && chown -R appuser:appuser /app /data /home/appuser
USER appuser
ENV HF_HOME=/data/hf QWEN3_DTYPE=float16 NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility
EXPOSE 8011
HEALTHCHECK --interval=60s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:8011/health || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8011"]
