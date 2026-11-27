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
    'breeze', 'cosyvoice', 'f5tts', 'polly', 'inworld',
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
    payload_hash = hashlib.sha256(sample_text_for('cpu_narrators').encode()).hexdigest()
    info = sample_info(audio, payload_hash)
    assert info['preview_sample_current']
    assert info['preview_audio_sha256'] == hashlib.sha256(b'old recording').hexdigest()
    assert not sample_info(audio, 'different-preparation')['preview_sample_current']
    audio.write_bytes(b'a different recording')
    assert not sample_info(audio)['preview_sample_current']
    assert 'preview_audio_sha256' not in sample_info(audio)


def test_preparation_failure_never_silently_sends_raw_numbers(monkeypatch):
    import tts_preprocess

    def broken(*args, **kwargs):
        raise ValueError('broken dependency')

    monkeypatch.setattr(tts_preprocess, 'normalize_text_for_tts', broken)
    with pytest.raises(RuntimeError, match='Could not prepare shared sample'):
        sample_text_for('cpu_narrators')


def test_missing_number_dependency_cannot_silently_change_shared_payload(monkeypatch):
    import tts_preprocess

    monkeypatch.setattr(tts_preprocess, 'HAS_NUM2WORDS', False)
    for engine in ('cosyvoice', 'vibevoice', 'cpu_narrators'):
        with pytest.raises(RuntimeError, match='num2words is required'):
            sample_text_for(engine)
    # Native raw-input auditions are an explicit contract, not a failure fallback.
    for engine in ('maya2', 'voxmel', 'kale'):
        assert sample_text_for(engine) == SAMPLE_TEXT


@pytest.mark.parametrize('voice_id, engine', [
    ('maya2_siddhant', 'maya2'), ('maya2_nivedita', 'maya2'),
    ('voxcpm2_peter', 'voxcpm2'),
    ('higgs3_default_audition', 'higgs3'),
])
def test_native_audition_payload_is_explicit_without_claiming_a_book_route(voice_id, engine):
    from app import all_voices

    voice = all_voices()[voice_id]
    assert voice['audition_only'] is True
    assert voice['preview_text_engine'] == engine
    assert sample_text_for(engine) == SAMPLE_TEXT
    # The exception is restricted to named native audition contracts.
    assert sample_text_for('audition') != SAMPLE_TEXT


@pytest.mark.parametrize('voice_id, engine, profile', [
    ('tontaube_marcus_audition', 'tontaube', 'explicit'),
    ('zonos3_imogen_audition', 'zonos3', 'native'),
    ('reverb_en_male_narrator_audition', 'reverb', 'native'),
])
def test_promoted_voice_keeps_its_preview_and_routes_books(voice_id, engine, profile):
    import os
    from app import all_voices, get_engine_url

    voice = all_voices()[voice_id]
    assert not voice.get('audition_only')
    assert voice['engine'] == voice['preview_text_engine'] == engine
    expected_url = os.environ.get(f'{engine.upper()}_URL', f'http://{engine}:8080/v1')
    assert get_engine_url(engine, 'test')[0] == expected_url.rstrip('/')
    assert text_profile_for_engine(engine) == profile
    expected = SAMPLE_TEXT if profile == 'native' else sample_text_for('cpu_narrators')
    assert sample_text_for(engine) == expected


def test_native_book_frontend_keeps_numbers_and_names_through_both_stages(tmp_path, monkeypatch):
    from zipfile import ZipFile
    from scripts import convert_book
    from tts_preprocess import preprocess_epub

    original = tmp_path / 'source.epub'
    with ZipFile(original, 'w') as book:
        book.writestr('chapter.xhtml', '<html><body><p>In 1916 Huawei spent £24.60.</p></body></html>')
    prepared, _ = preprocess_epub(original, native_text=True)
    monkeypatch.setattr(convert_book, '_TEXT_PROFILE', 'native')
    monkeypatch.setattr(convert_book, '_LEXICON', {'Huawei': 'replacement'})
    with ZipFile(prepared) as book:
        assert convert_book.chapter_text(book, 'chapter.xhtml') == 'In 1916 Huawei spent £24.60.'


def test_long_sentence_stays_complete_inside_book_request_limit():
    from scripts.convert_book import chunk

    source = ' '.join(['a very long sentence'] * 180)
    chunks = chunk(source, 600, pack_paragraphs=True)
    assert max(map(len, chunks)) <= 600
    assert ' '.join(chunks) == source


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


@pytest.mark.parametrize(('voice', 'retry', 'calls'), [
    ('tontaube_marcus_audition', '1', 2),
    ('zonos3_imogen_audition', '', 1),
    ('reverb_en_male_narrator_audition', 'unavailable', 1),
    ('existing_voice', '1', 1),
])
def test_busy_speech_retries_only_for_stock_backend_with_delay(monkeypatch, voice, retry, calls):
    from unittest.mock import Mock
    from scripts import convert_book

    busy = Mock(status_code=503, headers={'Retry-After': retry})
    ready = Mock(status_code=200)
    post = Mock(side_effect=[busy, ready])
    monkeypatch.setattr(convert_book.requests, 'post', post)
    monkeypatch.setattr(convert_book.time, 'sleep', Mock())
    response = convert_book._post_speech('http://engine/audio/speech', {'voice': voice}, 10)
    assert response is (ready if calls == 2 else busy)
    assert post.call_count == calls
