import sys
import time
from pathlib import Path

import soundfile as sf
from kittentts import KittenTTS

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish, sample_text

out = Path('/output')
out.mkdir(parents=True, exist_ok=True)
model = KittenTTS('KittenML/kitten-tts-mini-0.8')
for voice in ('Jasper', 'Rosie'):
    started = time.perf_counter()
    audio = model.generate(sample_text(), voice=voice, speed=1.0, clean_text=False)
    stem = f'cpu_kitten_{voice.lower()}'
    wav = out / f'{stem}.wav'
    sf.write(wav, audio, 24000)
    finish('KittenTTS mini', '0.8.1 / upstream 9f3e0d8', started, wav,
           out / f'{stem}.mp3', {'voice': voice, 'clean_text': False})
