FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

ARG VIBEVOICE_RUNTIME_SHA=07cb79feadd2d3fd7f47530d4c964a12857936a0
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg git git-lfs && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/vibevoice-community/VibeVoice.git /opt/VibeVoice \
    && git -C /opt/VibeVoice checkout --detach "$VIBEVOICE_RUNTIME_SHA" \
    && test "$(git -C /opt/VibeVoice rev-parse HEAD)" = "$VIBEVOICE_RUNTIME_SHA"
RUN pip install --no-cache-dir numpy==1.26.4 \
    && pip install --no-cache-dir -e /opt/VibeVoice \
    && pip install --no-cache-dir fastapi uvicorn soundfile

WORKDIR /app
COPY vibevoice/server.py /app/server.py
COPY chatterbox/voices/ /app/voices/
RUN python -c "import hashlib,pathlib; p=pathlib.Path('/app/voices/uk_male_minter.wav'); b=p.read_bytes(); assert b[:4] == b'RIFF' and len(b) == 864182 and hashlib.sha256(b).hexdigest() == '8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252', 'Arthur voice is missing/corrupt (run git lfs pull)'"
RUN useradd -r -m -s /bin/false appuser && mkdir -p /data/hf /app/voices/custom \
    && chown -R appuser:appuser /app /data /home/appuser
USER appuser
ENV HF_HOME=/data/hf VIBEVOICE_DTYPE=float16 NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility
EXPOSE 8010
HEALTHCHECK --interval=60s --timeout=10s --start-period=300s --retries=5 \
    CMD curl -f http://localhost:8010/health || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]
