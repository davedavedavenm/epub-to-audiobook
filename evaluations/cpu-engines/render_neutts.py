import sys
import time
from pathlib import Path

import soundfile as sf
import torch
from neutts import NeuTTS

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish, sample_text

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
audio = tts.infer(sample_text(), ref_codes, ref_text, temperature=1.0, top_k=50)
wav = out / 'cpu_neutts_jo.wav'
sf.write(wav, audio, 24000)
finish('NeuTTS Air Q4', '1.4.1 / upstream ac69851', started, wav,
       out / 'cpu_neutts_jo.mp3', {
           'voice': 'official Jo pre-encoded reference',
           'reference_boundary': 'Arthur exact transcript unavailable; identity comparison not valid',
           'backbone': 'neuphonic/neutts-air-q4-gguf',
           'codec': 'neuphonic/neucodec-onnx-decoder',
           'seed': 42,
       })
