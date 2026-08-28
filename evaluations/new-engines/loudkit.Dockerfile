FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git time \
    && rm -rf /var/lib/apt/lists/*
# loudkit 0.1.0 is the published release of runtime commit
# 58fd4a58de8980b42c1021492728876d67ea2718 (tag v0.1.0).
RUN pip install --no-cache-dir \
    "loudkit[torch,onnx,audio,enroll,hub]==0.1.0" \
    soundfile==0.13.1 num2words==0.5.14
CMD ["python", "/repo/evaluations/new-engines/render_loudkit.py"]
