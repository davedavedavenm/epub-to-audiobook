import sys
import time
from pathlib import Path

import scipy.io.wavfile
import torch
from pocket_tts import TTSModel

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish, sample_text

torch.set_num_threads(4)
out = Path('/output')
out.mkdir(parents=True, exist_ok=True)
started = time.perf_counter()
model = TTSModel.load_model()
# Cloning weights are gated by Kyutai's Hugging Face model terms. The official
# Peter Yearsley catalogue voice gives us a legitimate UK audiobook screen
# without bypassing that access decision or smuggling a token into the image.
voice = model.get_state_for_audio_prompt('peter_yearsley')
audio = model.generate_audio(voice, sample_text())
wav = out / 'cpu_pocket_peter_yearsley.wav'
scipy.io.wavfile.write(wav, model.sample_rate, audio.detach().cpu().numpy())
finish('Pocket TTS', '2.1.0 / upstream 7fc13c7', started, wav,
       out / 'cpu_pocket_peter_yearsley.mp3', {
           'voice': 'official peter_yearsley preset',
           'cloning_boundary': 'requires accepted Kyutai Hugging Face model terms',
       })
