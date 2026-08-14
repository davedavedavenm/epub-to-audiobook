import sys
import time
from pathlib import Path

import soundfile as sf
from kittentts import KittenTTS

sys.path.insert(0, '/repo/evaluations/cpu-engines')
from metrics import finish
from numeric_ab import selected_text, source_hash

out = Path('/output')
out.mkdir(parents=True, exist_ok=True)
model = KittenTTS('KittenML/kitten-tts-mini-0.8')
render_text, input_name, arm = selected_text()
for voice in ('Jasper', 'Rosie'):
    started = time.perf_counter()
    audio = model.generate(render_text, voice=voice, speed=1.0, clean_text=False)
    stem = (f'cpu_kitten_{voice.lower()}' if not arm
            else f'numeric_kitten_{voice.lower()}_{arm}')
    wav = out / f'{stem}.wav'
    sf.write(wav, audio, 24000)
    finish('KittenTTS mini', '0.8.1 / upstream 9f3e0d8', started, wav,
           out / f'{stem}.mp3', {
               'voice': voice,
               'clean_text': False,
               'ab_arm': arm or None,
               'raw_source_sha256': source_hash() if arm else None,
           }, input_text=render_text, input_name=input_name)
