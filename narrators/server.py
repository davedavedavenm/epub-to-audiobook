"""Serialized CPU adapter for the exact November audition models.

Official model runtimes; this HTTP adapter is project-owned. One model family
resident at a time to bound memory on the shared host. No GPU or cloud fallback.
"""
import gc
import io
import os
import sys
import threading

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('MKL_NUM_THREADS', '4')

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from liked_voices import CPU_VOICES, MODELS, PHONON_CATALOG

app = FastAPI()
_lock = threading.Lock()
_family = None
_model = None
_states = {}


class SpeechRequest(BaseModel):
    model: str = 'tts-1'
    input: str = Field(min_length=1, max_length=20000)
    voice: str
    response_format: str = 'wav'
    speed: float = 1.0


def _load(family):
    global _family, _model, _states
    if _family == family and _model is not None:
        return _model
    _model = None
    _states = {}
    _family = None
    gc.collect()
    from huggingface_hub import snapshot_download
    if family == 'phonon':
        import ptts
        ptts.set_num_threads(int(os.environ.get('NARRATOR_THREADS', '4')))
        repo, rev = MODELS[family]
        model = ptts.TTS(f'hf://{repo}@{rev}', lang='en', device='cpu',
                         quant='f32', voice_catalog=PHONON_CATALOG)
    else:
        import torch
        torch.set_num_threads(int(os.environ.get('NARRATOR_THREADS', '4')))
        if family == 'pocket':
            from pocket_tts import TTSModel
            model = TTSModel.load_model(language='english_2026-10', temp=.3,
                                       sampler_decode_steps=4)
            if not model.has_voice_cloning:
                raise RuntimeError('Expected the auditioned voice-cloning weights')
        else:
            repo, rev = MODELS[family]
            excluded = (['cpp/**', 'lm/model.safetensors', 'lm/model-tl2-emb4.safetensors',
                         'decoders/**'] if family == 'kitten' else None)
            folder = snapshot_download(repo, revision=rev, ignore_patterns=excluded)
            if folder not in sys.path:
                sys.path.insert(0, folder)
            if family == 'klein':
                import modeling_klein_tts as mk
                model = mk.KleinTTS.from_pretrained(folder, device='cpu')
                model.phonemizer = mk.Phonemizer(resource=mk.make_resolver(folder))
            elif family == 'silencio':
                from silencio2 import Silencio2TTS
                model = Silencio2TTS.from_pretrained(folder, device='cpu')
            elif family == 'kitten':
                from functools import partial
                from huggingface_hub import hf_hub_download
                from kittenml import KittenTTS
                from kittenml.kittentts2 import vocoder
                # kittenml 0.9.7 otherwise downloads this auxiliary decoder
                # from main. Pin the official weights used by the audition.
                vocoder.hf_hub_download = partial(
                    hf_hub_download, revision='749d1c1a46eb10492095d68fbcf55691ccf137cd')
                model = KittenTTS(folder, device='cpu', weights='packed')
            else:
                raise ValueError('Unknown family')
    _family, _model = family, model
    return model


def _render(text, family, speaker):
    model = _load(family)
    if family == 'phonon':
        return model.synth(text, voice=speaker, temperature=.45,
                           seed=4242424242424242), model.sample_rate
    import torch
    torch.manual_seed(42)
    if family == 'pocket':
        if speaker not in _states:
            from huggingface_hub import hf_hub_download
            reference = hf_hub_download('kyutai/tts-voices', f'voice-zero/{speaker}.wav',
                                        revision='323332d33f997de8394f24a193e1a76df720e01a')
            _states[speaker] = model.get_state_for_audio_prompt(reference)
        return model.generate_audio(_states[speaker], text), model.sample_rate
    if family == 'klein':
        out = model.tts(text, voice=speaker, speed=1., pause=.18, seed=42)
        return out.waveform, 24000
    if family == 'silencio':
        from huggingface_hub import hf_hub_download
        reference = hf_hub_download('kyutai/tts-voices', 'voice-zero/peter_yearsley.wav',
                                    revision='323332d33f997de8394f24a193e1a76df720e01a')
        return model.generate(text, voice=reference,
                              seed=42, normalize=False), model.sample_rate
    return model.generate(text, voice=speaker, preset='stable',
                          advanced={'seed': 42}, normalize=True), model.sample_rate


@app.get('/health')
def health():
    return {'status': 'ok', 'device': 'cpu', 'loaded_family': _family,
            'voices': list(CPU_VOICES), 'models': MODELS}


@app.get('/v1/audio/voices')
def voices():
    return {'voices': [{'id': voice} for voice in CPU_VOICES]}


@app.post('/v1/audio/speech')
def speech(req: SpeechRequest):
    if req.voice not in CPU_VOICES:
        raise HTTPException(400, 'Unknown CPU narrator; no fallback is permitted')
    if req.response_format not in ('wav', 'mp3'):
        raise HTTPException(400, 'response_format must be wav or mp3')
    if not req.input.strip():
        raise HTTPException(400, 'input must contain text')
    _, _, family, speaker = CPU_VOICES[req.voice]
    with _lock:
        chunks = []
        for paragraph in req.input.split('\n\n'):
            if not paragraph.strip():
                continue
            audio, rate = _render(paragraph.strip(), family, speaker)
            if hasattr(audio, 'detach'):
                audio = audio.detach().cpu().numpy()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not len(audio) or not np.isfinite(audio).all():
                raise HTTPException(500, 'Model returned invalid audio')
            if chunks:
                chunks.append(np.zeros(round(rate * .5), dtype=np.float32))
            chunks.append(audio)
        out = io.BytesIO()
        sf.write(out, np.concatenate(chunks), rate, format='WAV', subtype='PCM_16')
    if req.response_format == 'wav':
        return Response(out.getvalue(), media_type='audio/wav')
    import subprocess
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 'mp3',
                             '-b:a', '192k', 'pipe:1'], input=out.getvalue(),
                            capture_output=True, timeout=120, check=True)
    return Response(result.stdout, media_type='audio/mpeg')
