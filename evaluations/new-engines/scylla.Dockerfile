FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git time \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none https://github.com/lowkeytea/scyllasband.git /upstream \
    && git -C /upstream checkout ab5d38ad46eec64a8e02a56c38a6e4f3c0cfdeb8
RUN pip install --no-cache-dir -e /upstream \
    numpy==2.3.2 huggingface_hub==0.34.4 onnxruntime==1.22.1 \
    soundfile==0.13.1 num2words==0.5.14
CMD ["python", "/repo/evaluations/new-engines/render_scylla.py"]
