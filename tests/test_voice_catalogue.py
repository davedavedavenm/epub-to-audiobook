import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from app import TTS_ENGINES, all_voices
from voice_catalogue import MODEL_GROUPS, build_voice_catalogue, model_key_for_voice
from voice_customization import voice_customization_for


def test_every_registered_voice_appears_once_in_its_model_group():
    voices = all_voices()
    groups = build_voice_catalogue(voices, TTS_ENGINES)
    grouped_ids = [voice_id for group in groups
                   for voice_id in ([group['representative_id']] if group['representative_id'] else [])
                   + group['other_voice_ids']]

    assert len(grouped_ids) == len(voices)
    assert set(grouped_ids) == set(voices)
    assert len(grouped_ids) == len(set(grouped_ids))
    assert {'chatterbox_turbo', 'chatterbox_nano', 'phonon_31m', 'pocket4',
            'pocket21', 'kitten2', 'kitten081', 'deepgram_flux',
            'deepgram_aura2', 'qwen3_customvoice', 'qwen3_base'} <= {
                group['key'] for group in groups
            }


def test_preferred_current_voice_represents_group_without_claiming_quality_rank():
    voices = {
        'deepgram_flux_jack': {
            'name': 'Jack', 'engine': 'deepgram', 'preview_cached': True,
            'preview_sample_current': True,
        },
        'deepgram_flux_colin': {
            'name': 'Colin', 'engine': 'deepgram', 'preview_cached': True,
            'preview_sample_current': True,
        },
    }
    group = next(group for group in build_voice_catalogue(voices) if group['key'] == 'deepgram_flux')
    assert group['representative_id'] == 'deepgram_flux_jack'
    assert group['other_voice_ids'] == ['deepgram_flux_colin']


def test_old_cached_preview_is_distinguished_from_pending_and_current():
    voices = {
        'phonon_edwin': {
            'name': 'Edwin', 'engine': 'cpu_narrators', 'preview_cached': True,
            'preview_sample_current': False, 'preview_sample_label': 'Earlier audition',
        },
        'phonon_hugh': {
            'name': 'Hugh', 'engine': 'cpu_narrators', 'preview_cached': True,
            'preview_sample_current': True, 'preview_sample_label': 'Shared test v1',
        },
        'phonon_freya': {
            'name': 'Freya', 'engine': 'cpu_narrators', 'preview_cached': False,
            'preview_sample_current': False, 'preview_sample_label': 'Earlier audition',
        },
    }
    group = next(group for group in build_voice_catalogue(voices) if group['key'] == 'phonon_31m')
    assert group['representative_id'] == 'phonon_hugh'
    assert (group['current_count'], group['earlier_count'], group['pending_count']) == (1, 1, 1)


def test_new_shared_audition_represents_model_before_an_older_preferred_voice():
    voices = {
        'breeze_arthur': {
            'name': 'Arthur', 'engine': 'breeze', 'preview_cached': True,
            'preview_sample_current': False,
        },
        'breeze_fictional_voice_design': {
            'name': 'Fictional narrator', 'engine': 'audition',
            'catalogue_model': 'breeze2', 'audition_only': True,
            'preview_cached': True, 'preview_sample_current': True,
        },
    }
    group = next(group for group in build_voice_catalogue(voices) if group['key'] == 'breeze2')
    assert group['representative_id'] == 'breeze_fictional_voice_design'
    assert group['other_voice_ids'] == ['breeze_arthur']


def test_unknown_and_custom_voice_ids_are_preserved_without_model_guessing():
    voices = {
        'customer_clone_alpha': {'name': 'Alpha', 'engine': 'custom_engine', 'preview_cached': True},
        'customer_clone_beta': {'name': 'Beta', 'engine': 'custom_engine', 'preview_cached': False},
        'kitten2_john_kani_audition': {
            'name': 'John Kani (audition)', 'engine': 'audition',
            'catalogue_model': 'kitten2', 'audition_only': True, 'preview_cached': True,
        },
    }
    groups = build_voice_catalogue(voices, {'custom_engine': {'name': 'Custom engine'}})
    ids = {voice_id for group in groups
           for voice_id in ([group['representative_id']] if group['representative_id'] else [])
           + group['other_voice_ids']}

    assert ids == set(voices)
    assert model_key_for_voice('kitten2_john_kani_audition', voices['kitten2_john_kani_audition']) == 'kitten2'
    unknown_groups = [group for group in groups if group['key'].startswith('unclassified:')]
    assert len(unknown_groups) == 2
    assert {group['model'] for group in unknown_groups} == {'Version or model identity not recorded'}


def test_november_auditions_preserve_imogen_book_voice_and_voxmel_verdict():
    voices = all_voices()
    groups = {group['key']: group for group in build_voice_catalogue(voices, TTS_ENGINES)}
    assert groups['kale_base']['representative_id'] == 'kale_base_amy'
    assert groups['zonos3']['representative_id'] == 'zonos3_imogen_audition'
    assert voices['zonos3_imogen_audition']['engine'] == 'zonos3'
    assert not voices['zonos3_imogen_audition'].get('audition_only')
    assert 'Local CPU' in groups['zonos3']['book_route']
    assert {'zonos3_imogen_gpu_audition', 'zonos3_rupert_audition',
            'zonos3_savannah_audition'} <= set(groups['zonos3']['other_voice_ids'])
    for voice_id in ('kale_base_amy', *groups['zonos3']['other_voice_ids']):
        assert voices[voice_id]['audition_only']
        assert voices[voice_id]['engine'] == 'audition'
    assert groups['voxmel_06b']['verdict_only']
    assert groups['voxmel_06b']['voice_count'] == 0
    assert groups['voxmel_06b']['representative_id'] is None
    assert 'robotic' in groups['voxmel_06b']['model_note']
    assert 'warbly' in groups['voxmel_06b']['model_note']


def test_audition_only_voice_cannot_be_generated_or_queued(monkeypatch, tmp_path):
    import app as web

    monkeypatch.setattr(web, 'PREVIEWS_DIR', tmp_path)
    monkeypatch.setattr(web, 'get_job', lambda job_id: {'voice': web.DEFAULT_VOICE})

    def unexpected_synthesis(*args, **kwargs):
        raise AssertionError('A cached audition cannot trigger synthesis')

    monkeypatch.setattr(web, '_preview_text_for', unexpected_synthesis)
    assert web.get_voice_preview('kale_base_amy') is None
    with web.app.test_client() as client:
        assert client.get('/api/preview/kale_base_amy').status_code == 425
        assert client.post('/api/jobs/job-id/resume',
                           json={'voice': 'kale_base_amy'}).status_code == 400
        assert client.post('/api/jobs/batch-reconvert',
                           json={'job_ids': ['job-id'], 'voice_option': 'kale_base_amy'}).status_code == 400


def test_only_known_custom_reference_ids_receive_regional_tags(monkeypatch, tmp_path):
    import app as web

    monkeypatch.setattr(web, 'CUSTOM_VOICES_DIR', tmp_path)
    for stem in ('accent_irish_male', 'accent_australian_female',
                 'accent_southafrican_male', 'other_irish_clone'):
        (tmp_path / f'{stem}.wav').touch()
    voices = all_voices()
    assert voices['accent_irish_male']['accent'] == 'Irish reference'
    assert voices['accent_irish_male_nano']['accent'] == 'Irish reference'
    assert 'accent retention' in voices['accent_irish_male_nano']['note']
    assert voices['accent_australian_female']['accent'] == 'Australian reference'
    assert voices['accent_southafrican_male_nano']['accent'] == 'South African reference'
    assert voices['other_irish_clone']['accent'] == 'Custom'


def test_customization_filters_distinguish_upstream_features_from_studio_access():
    groups = {group['key']: group for group in build_voice_catalogue(all_voices(), TTS_ENGINES)}
    assert {key for key, group in groups.items() if 'upload' in group['customization_filters']} == {
        'chatterbox_turbo', 'chatterbox_nano',
    }
    assert set(groups['zonos3']['customization_filters']) == {'stock', 'cloning', 'steering'}
    assert groups['zonos3']['customization']['cloning']['studio'] == 'preset_only'
    assert groups['qwen3_base']['customization_filters'] == ['cloning']
    assert groups['qwen3_customvoice']['customization_filters'] == ['stock', 'steering']
    assert groups['gemini31']['customization_filters'] == ['stock', 'steering']
    assert groups['breeze2']['customization']['design']['studio'] == 'sample'
    assert not {'cloning', 'design'} & set(groups['deepgram_aura2']['customization_filters'])
    assert groups['deepgram_aura2']['customization']['cloning']['model_label'] == 'Unsupported'
    assert 'Unverified' in groups['kale_base']['customization']['cloning']['model_label']
    assert voice_customization_for('unclassified:new-model')['customization_filters'] == []


def test_documented_customization_covers_model_registry():
    from voice_customization import _OPTIONS

    assert {group['key'] for group in MODEL_GROUPS} == set(_OPTIONS)


def test_history_cards_preserve_drama3_and_ming3_verdicts_without_offering_voices():
    groups = {group['key']: group for group in build_voice_catalogue(all_voices(), TTS_ENGINES)}
    for key in ('fish_drama3', 'ming3_05b'):
        history = groups[key]
        assert history['verdict_only']
        assert history['voice_count'] == 0
        assert history['representative_id'] is None
        assert history['book_route'] == 'No Studio book route.'
        assert 'cloning' in history['customization_filters']
        assert history['customization']['cloning']['studio'] == 'none'
    assert 'awaits a listening verdict' in groups['fish_drama3']['model_note']
    assert 'dropped words' in groups['fish_drama3']['model_note']
    assert {'design', 'steering'} <= set(groups['fish_drama3']['customization_filters'])
    assert 'tinny' in groups['ming3_05b']['model_note']
    assert {'design', 'steering'} <= set(groups['ming3_05b']['customization_filters'])
