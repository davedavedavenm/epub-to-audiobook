FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git time \
    && rm -rf /var/lib/apt/lists/*
# sopro 2.0.5 is the published release matching runtime commit
# cb2b2a1949cd70cca469d689416906a6d181fa22.
RUN pip install --no-cache-dir \
    "sopro==2.0.5" \
    soundfile==0.13.1 num2words==0.5.14
CMD ["python", "/repo/evaluations/new-engines/render_sopro.py"]
