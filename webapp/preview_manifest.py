"""Identify the text behind cached previews without deleting earlier auditions."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from voice_sample import SAMPLE_ID, SAMPLE_LABEL, SAMPLE_SHA256


@lru_cache(maxsize=1024)
def _audio_hash(path: str, modified_ns: int, size: int) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(audio_path: Path, prepared_text: str) -> None:
    manifest = {
        'sample_id': SAMPLE_ID,
        'source_sha256': SAMPLE_SHA256,
        'prepared_sha256': hashlib.sha256(prepared_text.encode('utf-8')).hexdigest(),
        'audio_sha256': hashlib.sha256(audio_path.read_bytes()).hexdigest(),
    }
    target = audio_path.with_suffix('.sample.json')
    part = target.with_suffix('.json.part')
    part.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    os.replace(part, target)


def sample_info(audio_path: Path, expected_prepared_sha256: str | None = None) -> dict:
    earlier = {'preview_sample_current': False,
               'preview_sample_label': 'Earlier audition',
               'preview_sample_id': None}
    try:
        manifest = json.loads(audio_path.with_suffix('.sample.json').read_text(encoding='utf-8'))
        stat = audio_path.stat()
        if (manifest.get('sample_id') == SAMPLE_ID
                and manifest.get('source_sha256') == SAMPLE_SHA256
                and (expected_prepared_sha256 is None
                     or manifest.get('prepared_sha256') == expected_prepared_sha256)
                and manifest.get('audio_sha256') == _audio_hash(
                    str(audio_path), stat.st_mtime_ns, stat.st_size)):
            return {'preview_sample_current': True,
                    'preview_sample_label': SAMPLE_LABEL,
                    'preview_sample_id': SAMPLE_ID}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return earlier
