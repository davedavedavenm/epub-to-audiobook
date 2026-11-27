import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tts_proxy'))

from liked_voices import CPU_VOICES, LIKED_VOICES
from app import all_voices, get_engine_url, text_profile_for_engine
import proxy


def test_shortlist_respects_newer_verdicts_and_exact_models():
    assert len(LIKED_VOICES) == 19
    assert len(CPU_VOICES) == 11
    assert sum(1 for v in LIKED_VOICES.values() if v['liked']) == 18
    assert not any('isabella' in key or 'harriet' in key or 'edmund' in key
                   for key in LIKED_VOICES)
    assert CPU_VOICES['phonon_edwin'][2:] == ('phonon', 'Edwin')
    assert CPU_VOICES['pocket4_bill_boerst'][1] == 'Pocket 4 / October 100M'
    assert LIKED_VOICES['maya2_siddhant']['audition_only']
    assert all_voices()['kitten2_rosie']['liked'] is True
    assert all_voices()['kitten2_rosie']['catalogue_status'] == 'Keep'
    assert LIKED_VOICES['silencio2_peter']['liked'] is False
    assert LIKED_VOICES['silencio2_peter']['catalogue_status'] == 'disliked'
    assert 'pocket4_peter_yearsley' in LIKED_VOICES


def test_round_one_verdicts_are_bound_to_exact_voice_ids_and_sample():
    voices = all_voices()
    expected = {
        'klein_arthur': ('Retire vote · refinement pending', 'Chinese pronunciation'),
        'uk_female_samuel_nano': ('Keep', '21 of April'),
        'phonon_edwin': ('Keep', 'hua way way'),
        'pocket4_caro_davy': ('Keep', 'unsure about the final April date'),
    }
    for key, (verdict, finding) in expected.items():
        assert voices[key]['catalogue_status'] == verdict
        assert voices[key]['rating_date'] == '2026-11-27'
        assert voices[key]['rated_sample_id'] == 'narrator-standard-v1'
        assert finding in voices[key]['note']
        assert not voices[key].get('audition_only')
    assert voices['klein_arthur']['engine'] == 'cpu_narrators'
    assert 'klein_arthur' in CPU_VOICES
    assert not voices['uk_male_minter_nano'].get('catalogue_status')


def test_round_two_verdicts_are_bound_to_exact_audio(monkeypatch, tmp_path):
    import app as web

    monkeypatch.setattr(web, 'CUSTOM_VOICES_DIR', tmp_path)
    (tmp_path / 'accent_australian_female.wav').touch()
    voices = all_voices()
    expected = {
        'pocket4_stuart_bell': '3352272559db45f5f1cceb72cd3f560fc53a74f5c185b4a5b394b17c4789cd26',
        'accent_australian_female_nano': 'f2ef35c1cb033e367e727a397109ebeb44f0aa41cded5d4a5314c43b65e4434b',
        'kitten2_rosie': '69ef4181e27abb364e4448971b46e51f72bd91267873fddbb939c749b6c279bc',
        'phonon_hugh': '50a48b5f543eb78e830ae513ccd26aff18ea4a4eb7969c272ddc9c954aad80cc',
    }
    for voice_id, audio_hash in expected.items():
        assert voices[voice_id]['catalogue_status'] == 'Keep'
        assert voices[voice_id]['rated_sample_id'] == 'narrator-standard-v1'
        assert voices[voice_id]['rated_audio_sha256'] == audio_hash
        assert not voices[voice_id].get('audition_only')
    assert 'no Australian accent' in voices['accent_australian_female_nano']['note']


def test_voice_catalogue_has_compact_groups_and_shared_sample_details():
    template_path = Path(__file__).resolve().parents[1] / 'webapp' / 'templates' / 'index.html'
    template = template_path.read_text(encoding='utf-8')
    assert 'Liked voices' not in template
    assert 'Voices by model' in template
    assert 'representative_id' in Path(__file__).resolve().parents[1].joinpath('webapp', 'voice_catalogue.py').read_text(encoding='utf-8')
    assert 'Other voices in this model' in template
    assert 'deepgram_flux_jack' not in template  # Representative selection comes from metadata, not duplicated markup.
    assert 'filterModelCatalogue' in template
    assert 'Shared test passage' in template and 'preview_sample_label' in template
    assert 'voiceSample.text' in template and 'escapeHtml(voiceSample.text)' in template
    assert 'preview_sample_current' in template
    assert 'playVoicePreview' in template and 'v.preview_cached === true' in template
    assert 'modelCatalogue' in template and 'engineUnconfigured[group.engine]' in template
    assert 'v.rated_sample_id === v.preview_sample_id' in template
    assert 'v.rated_audio_sha256 === v.preview_audio_sha256' in template
    assert "'Listening verdict' : 'Previous verdict'" in template
    assert 'verdictLabel(v)' in template and 'verdictLabel(other)' in template


def test_new_cpu_paths_do_not_fall_back_to_legacy_engine():
    url, model = get_engine_url('cpu_narrators', 'test')
    assert url == os.environ.get('CPU_NARRATORS_URL', 'http://cpu-narrators:8016/v1')
    assert model == 'tts-1'
    assert text_profile_for_engine('cpu_narrators') == 'explicit'
    import pytest
    with pytest.raises(ValueError, match='cached audition'):
        get_engine_url('audition', 'test')


def test_flux_uses_v2_and_auditioned_expression(monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return type('Reply', (), {'status_code': 200, 'content': b'audio'})()

    monkeypatch.setattr(proxy.httpx, 'AsyncClient', Client)
    assert asyncio.run(proxy._deepgram_chunk('Example.', 'flux-jack-en', 'test')) == b'audio'
    assert '/v2/speak?' in calls[0][0]
    assert 'model=flux-jack-en' in calls[0][0]
    assert 'expressivity=0&speed=1' in calls[0][0]
    asyncio.run(proxy._deepgram_chunk('Example.', 'aura-2-orion-en', 'test'))
    assert '/v1/speak?' in calls[1][0]


def test_unknown_deepgram_voice_never_becomes_orion(monkeypatch):
    import pytest
    monkeypatch.setattr(proxy, 'get_setting', lambda key: 'test-key')
    with pytest.raises(ValueError, match='substitution'):
        asyncio.run(proxy.get_deepgram_audio('Example.', 'deepgram_typo'))


def test_flux_preview_uses_proxy_not_kokoro(monkeypatch, tmp_path):
    import app as web
    calls = []

    class Reply:
        content = b'test-audio' * 1000

        def raise_for_status(self):
            pass

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Reply()

    monkeypatch.setattr(web, 'PREVIEWS_DIR', tmp_path)
    monkeypatch.setattr(web.requests, 'post', post)
    result = web.get_voice_preview('deepgram_flux_jack')
    assert result and result.read_bytes() == Reply.content
    assert '/j/preview/v1/audio/speech' in calls[0][0]
    assert calls[0][1]['json']['voice'] == 'deepgram_flux_jack'
    assert calls[0][1]['json']['model'] == 'deepgram'
