import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tts_proxy'))

from liked_voices import CPU_VOICES, LIKED_VOICES
from app import get_engine_url, text_profile_for_engine
import proxy


def test_shortlist_respects_newer_verdicts_and_exact_models():
    assert len(LIKED_VOICES) == 19
    assert len(CPU_VOICES) == 11
    assert sum(1 for v in LIKED_VOICES.values() if v['liked']) == 17
    assert not any('isabella' in key or 'harriet' in key or 'edmund' in key
                   for key in LIKED_VOICES)
    assert CPU_VOICES['phonon_edwin'][2:] == ('phonon', 'Edwin')
    assert CPU_VOICES['pocket4_bill_boerst'][1] == 'Pocket 4 / October 100M'
    assert LIKED_VOICES['maya2_siddhant']['audition_only']
    assert LIKED_VOICES['kitten2_rosie']['liked'] is False
    assert LIKED_VOICES['kitten2_rosie']['catalogue_status'] == 'disliked'
    assert LIKED_VOICES['silencio2_peter']['liked'] is False
    assert LIKED_VOICES['silencio2_peter']['catalogue_status'] == 'disliked'
    assert 'pocket4_peter_yearsley' in LIKED_VOICES


def test_voice_catalogue_has_compact_groups_and_shared_sample_details():
    template_path = Path(__file__).resolve().parents[1] / 'webapp' / 'templates' / 'index.html'
    template = template_path.read_text(encoding='utf-8')
    assert 'Start here' in template and 'deepgram_flux_jack' in template
    assert 'phonon_edwin' in template and 'More local CPU likes' in template
    assert 'Compare Edwin with Jack' in template
    assert 'preferred CPU comparator' not in template
    assert '<summary>GPU auditions' in template
    assert 'Browse engine catalogue' in template
    assert 'Shared test passage' in template and 'preview_sample_label' in template
    assert 'voiceSample.text' in template and 'escapeHtml(voiceSample.text)' in template


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
