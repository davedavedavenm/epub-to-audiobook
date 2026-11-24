"""Local OpenAI-compatible adapter for the pinned Reverb stock narrator."""

from contextlib import asynccontextmanager
import io
import logging
import os
from pathlib import Path
import subprocess
from threading import Lock

from fastapi import FastAPI, HTTPException, Response
import numpy as np
from pydantic import BaseModel, Field
import soundfile as sf

MODEL = 'software-mansion/Reverb-TTS'
REVISION = '72be799c8fb6d56a206d260b425c48bf3bd5943d'
VOICE_ID = 'reverb_en_male_narrator_audition'
PRESET = 'en_male_narrator_1'
VARIANT = 'int8'
MAX_INPUT_CHARS = 6000
ATTRIBUTION = 'Synthetic audio generated using Reverb-TTS by Software Mansion AI Labs (noncommercial use)'
_synthesis = Lock()
_log = logging.getLogger(__name__)


def load_model():
    from huggingface_hub import snapshot_download
    from reverb_tts import TTS
    import torch

    torch.set_num_threads(int(os.environ.get('REVERB_THREADS', '2')))
    torch.set_num_interop_threads(1)
    snapshot = Path(snapshot_download(MODEL, revision=REVISION, local_files_only=True))
    model = TTS.from_pretrained(snapshot, variant=VARIANT, device='cpu', dtype=torch.float32)
    voice = model.preset_voice(PRESET)
    return model, voice


@asynccontextmanager
async def lifespan(app):
    app.state.narrator = None
    try:
        app.state.narrator = load_model()
    except Exception:
        _log.exception('Pinned Reverb model or stock voice could not be loaded')
    yield
    app.state.narrator = None


app = FastAPI(lifespan=lifespan)


class SpeechRequest(BaseModel):
    model: str = 'tts-1'
    input: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    voice: str
    response_format: str = 'mp3'
    speed: float = 1.0


def _narrator():
    narrator = getattr(app.state, 'narrator', None)
    if narrator is None:
        raise HTTPException(status_code=503, detail='Reverb stock narrator is unavailable')
    return narrator


@app.get('/health')
def health():
    _narrator()
    return {'status': 'ok', 'model': MODEL, 'revision': REVISION, 'variant': VARIANT, 'device': 'cpu'}


@app.get('/v1/audio/voices')
def voices():
    _narrator()
    return {'voices': [{'id': VOICE_ID, 'name': 'English male narrator 1'}]}


def _audio_response(audio, sample_rate, output_format):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all() or not np.any(audio):
        raise HTTPException(status_code=500, detail='Reverb generated invalid audio')
    output = io.BytesIO()
    with sf.SoundFile(output, mode='w', samplerate=sample_rate, channels=1, format='WAV', subtype='PCM_16') as wav:
        wav.comment = ATTRIBUTION
        wav.write(audio)
    if output_format == 'wav':
        return Response(output.getvalue(), media_type='audio/wav')

    result = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', 'pipe:0', '-c:a', 'libmp3lame', '-q:a', '2',
         '-metadata', f'comment={ATTRIBUTION}', '-f', 'mp3', 'pipe:1'],
        input=output.getvalue(), capture_output=True, timeout=60, check=True,
    )
    return Response(result.stdout, media_type='audio/mpeg')


@app.post('/v1/audio/speech')
def speech(req: SpeechRequest):
    if req.voice != VOICE_ID:
        raise HTTPException(status_code=400, detail='Unknown Reverb stock voice')
    if req.response_format not in ('wav', 'mp3'):
        raise HTTPException(status_code=400, detail='response_format must be wav or mp3')
    if not req.input.strip():
        raise HTTPException(status_code=400, detail='input must contain text')
    if req.speed != 1.0:
        raise HTTPException(status_code=400, detail='Reverb stock narration supports speed 1.0')
    model, voice = _narrator()
    if not _synthesis.acquire(blocking=False):
        raise HTTPException(status_code=503, detail='Reverb is serving another request', headers={'Retry-After': '5'})
    try:
        audio = model.generate(req.input, voice, language='en', seed=42)
        return _audio_response(audio, model.sample_rate, req.response_format)
    finally:
        _synthesis.release()
