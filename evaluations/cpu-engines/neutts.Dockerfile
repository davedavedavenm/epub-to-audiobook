FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ffmpeg git libopenblas-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
ENV CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS"
RUN pip install --no-cache-dir "neutts[llama,onnx]==1.4.1" soundfile==0.13.1
RUN git clone --filter=blob:none --no-checkout https://github.com/neuphonic/neutts.git /upstream \
    && cd /upstream \
    && git checkout ac69851f28fc63a487917e7c2e27f0d75c759cba -- samples/jo.pt samples/jo.txt
COPY evaluations/cpu-engines/render_neutts.py /render.py
CMD ["python", "/render.py"]
