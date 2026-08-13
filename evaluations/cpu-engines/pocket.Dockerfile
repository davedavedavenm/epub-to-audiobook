FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pocket-tts==2.1.0 scipy==1.16.1 soundfile==0.13.1
COPY evaluations/cpu-engines/render_pocket.py /render.py
CMD ["python", "/render.py"]
