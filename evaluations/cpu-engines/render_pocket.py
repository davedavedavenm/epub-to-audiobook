import sys
import time
from pathlib import Path

import scipy.io.wavfile
import torch
from pocket_tts import TTSModel

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish
from numeric_ab import selected_text, source_hash

torch.set_num_threads(4)
out = Path('/output')
out.mkdir(parents=True, exist_ok=True)
started = time.perf_counter()
model = TTSModel.load_model()
# Cloning weights are gated by Kyutai's Hugging Face model terms. The official
# Peter Yearsley catalogue voice gives us a legitimate UK audiobook screen
# without bypassing that access decision or smuggling a token into the image.
voice = model.get_state_for_audio_prompt('peter_yearsley')
render_text, input_name, arm = selected_text()
audio = model.generate_audio(voice, render_text)
stem = 'cpu_pocket_peter_yearsley' if not arm else f'numeric_pocket_peter_{arm}'
wav = out / f'{stem}.wav'
scipy.io.wavfile.write(wav, model.sample_rate, audio.detach().cpu().numpy())
finish('Pocket TTS', '2.1.0 / upstream 7fc13c7', started, wav,
       out / f'{stem}.mp3', {
           'voice': 'official peter_yearsley preset',
           'cloning_boundary': 'requires accepted Kyutai Hugging Face model terms',
           'ab_arm': arm or None,
           'raw_source_sha256': source_hash() if arm else None,
       }, input_text=render_text, input_name=input_name)
