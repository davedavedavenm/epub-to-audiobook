FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none https://github.com/Audio8-AI/Audio8_TTS.git /upstream \
    && git -C /upstream checkout 421f71559848572431bd6229af3e1a73f25986a7
RUN pip install --no-cache-dir \
    -r /upstream/onnx_runtime/requirements.txt \
    'huggingface_hub[cli]==0.34.4' tokenizers==0.22.2 num2words==0.5.14
ENV PYTHONPATH=/upstream/onnx_runtime
CMD ["python", "/repo/evaluations/new-engines/render_audio8.py"]
