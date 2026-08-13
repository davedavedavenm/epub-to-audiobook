import json
import resource
import subprocess
from pathlib import Path

import soundfile as sf


def finish(engine, version, started, wav_path, mp3_path, extra=None):
    wav_path, mp3_path = Path(wav_path), Path(mp3_path)
    subprocess.run([
        'ffmpeg', '-y', '-v', 'error', '-i', str(wav_path),
        '-codec:a', 'libmp3lame', '-b:a', '128k', str(mp3_path),
    ], check=True)
    audio, rate = sf.read(wav_path)
    duration = len(audio) / rate
    wall = __import__('time').perf_counter() - started
    report = {
        'engine': engine,
        'version': version,
        'input': 'webapp.voice_sample.SAMPLE_TEXT',
        'input_characters': len(_sample_text()),
        'duration_seconds': round(duration, 3),
        'wall_seconds': round(wall, 3),
        'rtf': round(wall / duration, 3),
        'peak_rss_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        'wav_bytes': wav_path.stat().st_size,
        'mp3_bytes': mp3_path.stat().st_size,
    }
    report.update(extra or {})
    mp3_path.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


def _sample_text():
    import sys
    sys.path.insert(0, '/repo/webapp')
    from voice_sample import SAMPLE_TEXT
    return SAMPLE_TEXT


def sample_text():
    return _sample_text()
