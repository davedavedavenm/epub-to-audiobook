import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from neutts import NeuTTS

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish
from numeric_ab import selected_text, source_hash

torch.set_num_threads(4)
out = Path('/output')
out.mkdir(parents=True, exist_ok=True)
started = time.perf_counter()
tts = NeuTTS(
    backbone_repo='neuphonic/neutts-air-q4-gguf',
    backbone_device='cpu',
    codec_repo='neuphonic/neucodec-onnx-decoder',
    codec_device='cpu',
    seed=42,
)
ref_codes = torch.load('/upstream/samples/jo.pt', map_location='cpu')
ref_text = Path('/upstream/samples/jo.txt').read_text().strip()
render_text, input_name, arm = selected_text()
chunks = [part.strip() for part in re.split(r'(?<=[.!?])\s+', render_text) if part.strip()]
rendered = []
chunk_durations = []
for index, chunk in enumerate(chunks, 1):
    audio = np.asarray(tts.infer(chunk, ref_codes, ref_text, temperature=1.0, top_k=50))
    duration = len(audio) / 24000
    if duration < 1.0:
        raise RuntimeError(f'NeuTTS chunk {index}/{len(chunks)} truncated to {duration:.2f}s')
    rendered.append(audio)
    chunk_durations.append(round(duration, 3))
audio = np.concatenate([
    part
    for index, rendered_audio in enumerate(rendered)
    for part in ((np.zeros(6000, dtype=rendered_audio.dtype), rendered_audio)
                 if index else (rendered_audio,))
])
stem = 'cpu_neutts_jo' if not arm else f'numeric_neutts_jo_{arm}'
wav = out / f'{stem}.wav'
sf.write(wav, audio, 24000)
finish('NeuTTS Air Q4', '1.4.1 / upstream ac69851', started, wav,
       out / f'{stem}.mp3', {
           'voice': 'official Jo pre-encoded reference',
           'reference_boundary': 'Arthur exact transcript unavailable; identity comparison not valid',
           'backbone': 'neuphonic/neutts-air-q4-gguf',
           'codec': 'neuphonic/neucodec-onnx-decoder',
           'seed': 42,
           'chunking': 'sentence boundary; 250 ms joins',
           'chunks': len(chunks),
           'chunk_durations_seconds': chunk_durations,
           'ab_arm': arm or None,
           'raw_source_sha256': source_hash() if arm else None,
       }, input_text=render_text, input_name=input_name)
