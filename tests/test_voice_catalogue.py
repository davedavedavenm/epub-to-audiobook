import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

from app import TTS_ENGINES, all_voices
from voice_catalogue import build_voice_catalogue, model_key_for_voice


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
    group, = build_voice_catalogue(voices)
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
    group, = build_voice_catalogue(voices)
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
    group, = build_voice_catalogue(voices)
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
