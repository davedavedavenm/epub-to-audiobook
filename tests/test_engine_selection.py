import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))

os.environ.setdefault('DB_PATH', os.path.join(tempfile.mkdtemp(), 'test.db'))
os.environ.setdefault('UPLOAD_DIR', tempfile.mkdtemp())
os.environ.setdefault('OUTPUT_DIR', tempfile.mkdtemp())
os.environ.setdefault('PREVIEWS_DIR', tempfile.mkdtemp())
os.environ.setdefault('LOG_DIR', tempfile.mkdtemp())
os.environ.setdefault('LIBRARY_DIR', tempfile.mkdtemp())
os.environ.setdefault('TOC_CACHE_DIR', tempfile.mkdtemp())
os.environ.setdefault('TRANSCRIPTS_DIR', tempfile.mkdtemp())
os.environ.setdefault('QUEUE_RUNNER_ENABLED', '0')

import app as appmod
from app import get_engine_url
from tts_preprocess import normalize_text_for_tts

JOB_ID = 'testjob123'


def _proxy_or(fallback):
    return f"{appmod.TTS_PROXY_URL}/j/{JOB_ID}/v1" if appmod.TTS_PROXY_URL else fallback


def test_engine_url_kokoro():
    url, model = get_engine_url('kokoro', JOB_ID)
    assert url == _proxy_or(appmod.KOKORO_URL)
    assert model == 'kokoro'


def test_retired_piper_job_fails_closed():
    with pytest.raises(ValueError, match='Piper is retired'):
        get_engine_url('piper', JOB_ID)


def test_retired_piper_is_not_offered():
    assert 'piper' not in appmod.TTS_ENGINES
    assert not [voice for voice, info in appmod.VOICES.items()
                if info.get('engine') == 'piper']


def test_engine_url_chatterbox():
    url, model = get_engine_url('chatterbox', JOB_ID)
    assert url == appmod.CHATTERBOX_URL
    assert model == 'tts-1'


def test_engine_url_tada():
    url, model = get_engine_url('tada', JOB_ID)
    assert url == appmod.TADA_URL
    assert model == 'tts-1'


def test_engine_url_vibevoice():
    url, model = get_engine_url('vibevoice', JOB_ID)
    assert url == appmod.VIBEVOICE_URL
    assert model == 'microsoft/VibeVoice-1.5B'


def test_engine_url_qwen3():
    url, model = get_engine_url('qwen3', JOB_ID)
    assert url == appmod.QWEN3_URL
    assert model == 'Qwen/Qwen3-TTS-12Hz-1.7B-Base'


def test_engine_url_pocket():
    url, model = get_engine_url('pocket', JOB_ID)
    assert url == appmod.POCKET_URL
    assert model == 'pocket-tts-2.1'


def test_engine_url_kitten():
    url, model = get_engine_url('kitten', JOB_ID)
    assert url == appmod.KITTEN_URL
    assert model == 'KittenML/kitten-tts-mini-0.8'


def test_engine_url_gemini_is_pinned():
    url, model = get_engine_url('gemini', JOB_ID)
    assert url == appmod.GEMINI_TTS_URL
    assert model == 'gemini-3.1-flash-tts-preview'


def test_cpu_candidates_use_measured_explicit_text_profile():
    assert appmod.text_profile_for_engine('pocket') == 'explicit'
    assert appmod.text_profile_for_engine('kitten') == 'explicit'
    assert appmod.text_profile_for_engine('gemini') == 'explicit'
    assert appmod.text_profile_for_engine('chatterbox_nano') == 'modern'
    assert appmod.text_profile_for_engine('kokoro') == 'legacy'


def test_cpu_candidate_catalogues_match_official_lists():
    pocket = [key for key, value in appmod.VOICES.items() if value['engine'] == 'pocket']
    kitten = [key for key, value in appmod.VOICES.items() if value['engine'] == 'kitten']
    neutts = [key for key, value in appmod.VOICES.items() if value['engine'] == 'neutts']
    assert len(pocket) == 21
    assert len(kitten) == 8
    assert 'pocket_peter_yearsley' in pocket
    assert 'neutts_jo' in neutts
    assert {'kitten_bella', 'kitten_jasper', 'kitten_luna', 'kitten_bruno',
            'kitten_rosie', 'kitten_hugo', 'kitten_kiki', 'kitten_leo'} == set(kitten)


def test_gemini_catalogue_contains_all_30_official_presets():
    gemini = [key for key, value in appmod.VOICES.items() if value['engine'] == 'gemini']
    assert len(gemini) == 30
    assert gemini[0] == 'gemini_zephyr'
    assert 'gemini_achernar' in gemini
    assert gemini[-1] == 'gemini_sulafat'
    assert all(appmod.VOICES[key]['gender'] == 'Unspecified' for key in gemini)


def test_explicit_candidate_previews_use_explicit_numeric_profile():
    for engine in ('pocket', 'kitten', 'gemini', 'neutts'):
        out = appmod._preview_text_for(engine)
        assert '$1.2' not in out
        assert 'one point two billion dollars' in out
        assert 'fifty two percent' in out
        assert 'one point five gigawatts' in out


def test_gemini_failure_never_enters_automatic_retry(monkeypatch):
    appmod.init_db()
    job_id = 'gemini-quota-no-retry'
    appmod.save_job({
        'id': job_id,
        'book_name': 'Bounded gate',
        'status': 'converting',
        'tts_engine': 'gemini',
        'voice': 'gemini_achernar',
    })
    monkeypatch.setattr(appmod, 'append_job_log', lambda *args, **kwargs: None)
    assert appmod.handle_job_failure(
        job_id, 'container_died', '429 RESOURCE_EXHAUSTED free quota'
    ) is False
    job = appmod.get_job(job_id)
    assert job['status'] == 'failed'
    assert job['retry_count'] == 0
    assert 'No automatic retry' in job['error']


def test_engine_url_edge():
    url, model = get_engine_url('edge', JOB_ID)
    assert url == _proxy_or(f'http://tts-proxy:8882/j/{JOB_ID}/v1')
    assert model == 'tts-1'


def test_modern_skips_number_spelling_but_keeps_acronym_spacing():
    out = normalize_text_for_tts('The U.S. paid $50 for 5000 units.', modern=True)
    assert 'U S' in out
    assert '$50' in out
    assert 'fifty dollars' not in out
    assert '5000' in out


def test_legacy_spells_numbers_and_expands_abbreviations():
    out = normalize_text_for_tts('Dr. Smith paid $50 in the U.S.', modern=False)
    assert 'Doctor Smith' in out
    assert 'fifty dollars' in out
    assert 'U S' in out


def test_years_spelled_for_both_modern_and_legacy():
    # The separator differs by engine class from 2026-07-27: modern engines read
    # an intra-word hyphen as a pause, so "sixty-two" would come out
    # "sixty ... two". The requirement — spelled, never raw digits — is identical.
    for modern in (True, False):
        out = normalize_text_for_tts('It happened in 1962 and 2003.', modern=modern)
        assert f"nineteen sixty{' ' if modern else '-'}two" in out
        assert '1962' not in out
        assert 'two thousand three' in out
        assert '2003' not in out


def test_candidate_sample_accepts_extensionless_and_mp3_urls():
    with appmod.app.test_client() as client:
        for name in ('me_british', 'vctk_irish_m_p364_native',
                     'cv3_southafrican_male', 'vibe_blind_A',
                     'vibe_blind_B', 'cpu_numeric_pocket_peter_a',
                     'cpu_numeric_pocket_peter_b', 'cpu_numeric_neutts_jo_a',
                     'cpu_numeric_neutts_jo_b', 'cpu_numeric_kitten_jasper_a',
                     'cpu_numeric_kitten_jasper_b', 'cpu_numeric_kitten_rosie_a',
                     'cpu_numeric_kitten_rosie_b'):
            sample = appmod.PREVIEWS_DIR / f'{name}.mp3'
            sample.write_bytes(b'ID3candidate-audio')
            for path in (f'/api/sample/{name}', f'/api/sample/{name}.mp3'):
                response = client.get(path)
                assert response.status_code == 200
                assert response.mimetype == 'audio/mpeg'
                assert response.data == b'ID3candidate-audio'
                assert f'{name}.mp3' in response.headers['Content-Disposition']
