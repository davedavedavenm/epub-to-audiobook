FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required for decoding MP3s via faster-whisper.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY verify_audio_sample.py .
COPY verify_audio_vs_captured.py .
COPY transcribe_candidates.py .

RUN useradd -r -s /bin/false appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "/app/verify_audio_sample.py"]
