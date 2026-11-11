"""Keep the agreed passage, preparation contract and cache labels trustworthy."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
from voice_sample import (  # noqa: E402
    SAMPLE_ID, SAMPLE_SHA256, SAMPLE_TEXT, ORDINARY_TEXT, CHALLENGE_TEXT,
    sample_text_for, SAMPLE_LEXICON,
)
from preview_manifest import sample_info, write_manifest  # noqa: E402
from app import text_profile_for_engine  # noqa: E402
from tts_preprocess import normalize_text_for_tts, _is_letter_spacing  # noqa: E402


def test_agreed_standard_is_versioned_and_unchanged():
    assert SAMPLE_ID == 'narrator-standard-v1'
    assert SAMPLE_SHA256 == '386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7'
    assert hashlib.sha256(SAMPLE_TEXT.encode('utf-8')).hexdigest() == SAMPLE_SHA256
    assert SAMPLE_TEXT == ORDINARY_TEXT + '\n\n' + CHALLENGE_TEXT
    with pytest.raises(ValueError, match='Unknown audition sample'):
        sample_text_for('cpu_narrators', sample_id='unapproved')


@pytest.mark.parametrize('engine', [
    'cpu_narrators', 'chatterbox', 'chatterbox_nano', 'tada', 'vibevoice',
    'qwen3', 'fish', 'pocket', 'kitten', 'gemini', 'deepgram', 'kokoro', 'edge',
])
def test_preview_preparation_matches_book_contract(engine):
    profile = text_profile_for_engine(engine)
    explicit = profile == 'explicit'
    lexicon = ({k: v for k, v in SAMPLE_LEXICON.items() if _is_letter_spacing(k, v)}
               if explicit else SAMPLE_LEXICON)
    expected = normalize_text_for_tts(
        SAMPLE_TEXT, lexicon=lexicon, modern=profile != 'legacy',
        expand_numbers=True if explicit else None,
    )
    assert sample_text_for(engine) == expected


def test_old_or_replaced_audio_cannot_claim_the_new_passage(tmp_path):
    audio = tmp_path / 'voice.mp3'
    audio.write_bytes(b'old recording')
    assert not sample_info(audio)['preview_sample_current']
    write_manifest(audio, sample_text_for('cpu_narrators'))
    assert sample_info(audio)['preview_sample_current']
    audio.write_bytes(b'a different recording')
    assert not sample_info(audio)['preview_sample_current']


def test_preparation_failure_never_silently_sends_raw_numbers(monkeypatch):
    import tts_preprocess

    def broken(*args, **kwargs):
        raise ValueError('broken dependency')

    monkeypatch.setattr(tts_preprocess, 'normalize_text_for_tts', broken)
    with pytest.raises(RuntimeError, match='Could not prepare shared sample'):
        sample_text_for('cpu_narrators')


def test_general_preview_producers_use_shared_engine_text_and_manifest():
    root = Path(__file__).resolve().parents[1]
    approved = (root / 'evaluations' / 'new-engines' / 'render_approved_previews.py').read_text(encoding='utf-8')
    kokoro = (root / 'scripts' / 'test_kokoro_blends.py').read_text(encoding='utf-8')

    assert 'sample_text_for("breeze")' in approved
    assert 'sample_text_for("qwen3")' in approved
    assert 'write_manifest(' in approved
    assert 'Apple was nine weeks from bankruptcy' not in approved
    assert 'sample_text_for("kokoro")' in kokoro
    assert 'write_manifest(' in kokoro
    assert 'Silicon Valley can be an amazingly drab place' not in kokoro


def test_generated_qwen_preview_kernel_embeds_the_canonical_sample_provenance():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'kaggle'))
    from build_qwen3_customvoice_previews import build_kernel

    kernel = build_kernel()
    assert SAMPLE_ID in kernel
    assert SAMPLE_SHA256 in kernel
    expected_literal = json.dumps(sample_text_for('qwen3'), ensure_ascii=False)
    assert f'TEST_TEXT = {expected_literal}' in kernel
    assert 'write_sample_manifest(mp3_path)' in kernel
    assert 'Silicon Valley can be an amazingly drab place' not in kernel
