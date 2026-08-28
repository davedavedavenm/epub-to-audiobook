FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ffmpeg git time \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --recurse-submodules https://github.com/Zyphra/zonos2.cpp.git /upstream \
    && git -C /upstream checkout 39a4d01558db86dca1219273992c77ebc8e03991 \
    && git -C /upstream submodule update --init --recursive \
    && cmake -S /upstream -B /upstream/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /upstream/build --target zonos2-cli -j4
RUN pip install --no-cache-dir huggingface_hub==0.34.4 num2words==0.5.14
CMD ["python", "/repo/evaluations/new-engines/render_zonos2.py"]
