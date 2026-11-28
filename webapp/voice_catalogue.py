"""Model/version grouping for the Voices audition catalogue.

Groups are presentation metadata only. They do not create voice IDs, infer a
shared speaker from a model label, or imply that a preview-enabled engine has a
book conversion route.
"""
from __future__ import annotations

from voice_customization import voice_customization_for


# These are explicit regional listening results, not general narration votes.
# They describe the cited earlier auditions, regardless of the current preview.
HEARD_ACCENTS = {
    # VOICES.md: the September Breeze auditions on Irish history passages.
    'breeze_cillian_irish': ('Irish', 'Earlier Breeze audition; no verified Studio book route.'),
    # VOICES.md: the October opening and Say Nothing chapter 4.
    'higgs_cillian_irish': ('Irish', 'Dave praised the accent in the Armed Struggle opening and liked the Say Nothing chapter 4 preview. Studio book route uses a GPU lane.'),
    'fish_cillian_irish': ('Irish', 'Dave called the flat-reference Cillian retry “perfect”. This recipe narrated the delivered Armed Struggle audiobook.'),
}

# Verdicts apply to the identified recordings. William was never on the desk.
REGIONAL_LISTENING_NOTES = {
    'en-AU-NatashaNeural': 'Dave rejected the Australian accent on the November regional desk.',
    'en-AU-WilliamNeural': 'Earlier audition met a basic quality floor. High-quality Australian narration remains unverified.',
    'accent_australian_female_nano': 'Keep for general narration. Dave heard no Australian accent.',
    'zonos3_custom_female_reference_nov27_standard_d49e1465b6c60b73da0aaea6ecffeb7e453f9778f282c2925ee98a6f0d81413b': 'Dave rejected the regional desk recordings as accent performances.',
    'zonos3_custom_vctk_p374_standard_010de87012bfd138d1ba8eda1fd93aaf1337cb2ca968a1d4f20e544bf1f382d4': 'This take used an Australian speaker as the reference. Dave rejected the desk recordings as accent performances.',
}

REFERENCE_ENGINES = {'chatterbox', 'chatterbox_nano', 'tada', 'cosyvoice', 'breeze', 'vibevoice', 'fish'}


def accent_evidence_for(voice_id: str, info: dict) -> dict:
    """Report what the accent label describes without reclassifying the voice."""
    label = info.get('accent') or 'Unspecified'
    reference = info.get('reference_accent')
    engine = info.get('engine')
    if reference or label.endswith(' reference'):
        source = 'reference'
        label = (reference or label).removesuffix(' reference')
    elif label.endswith((' requested', ' (prompted)')):
        source = 'target'
        label = label.removesuffix(' requested').removesuffix(' (prompted)')
    elif label in ('English', 'Unspecified', 'Unclassified', 'Custom', 'Prompt-controlled', 'Character'):
        source = 'unspecified'
    elif engine in REFERENCE_ENGINES or (engine == 'qwen3' and voice_id == 'uk_male_minter_qwen3') or voice_id == 'silencio2_peter':
        source = 'reference'
    else:
        source = 'listed'

    evidence = {'accent_source': source, 'accent_label': label.removesuffix(' English')}
    if voice_id in HEARD_ACCENTS:
        evidence['heard_accent'], evidence['heard_accent_note'] = HEARD_ACCENTS[voice_id]
    elif voice_id in REGIONAL_LISTENING_NOTES:
        evidence['heard_accent_note'] = REGIONAL_LISTENING_NOTES[voice_id]
    return evidence


MODEL_GROUPS = (
    {
        'key': 'tontaube', 'title': 'Tontaube', 'model': 'V1.1 INT4 · audiobook style',
        'engine': 'tontaube', 'preferred': ('tontaube_marcus_audition',),
        'model_note': 'Listen around 0:42 for Huawei. Whisper heard “hallway” and reached the final date.',
        'book_route': 'Local CPU · private personal use.',
    },
    {
        'key': 'zonos3', 'title': 'ZONOS3-Mini', 'model': '800M · 100M active',
        'engine': 'zonos3', 'preferred': ('zonos3_imogen_audition',),
        'model_note': 'Dave liked Imogen on the Badawi excerpt. She read 1916 as a cardinal number in Irish history. '
                      'The two Australian-reference voices on the November desk failed the accent test.',
        'book_route': 'Local CPU · Imogen preset and enrolled references.',
    },
    {
        'key': 'kale_base', 'title': 'Kale TTS', 'model': '1 Base',
        'engine': 'audition', 'preferred': ('kale_base_amy',),
        'book_route': 'No integrated book route.',
    },
    {
        'key': 'voxmel_06b', 'title': 'VoxMel', 'model': '0.6B',
        'engine': 'voxmel', 'preferred': (),
        'model_note': 'Shared Test v1 listening verdict: Zira sounded robotic and the dry Cillian reference sounded rough and warbly.',
        'book_route': 'Excluded after listening review.',
        'verdict_only': True,
    },
    {
        'key': 'reverb', 'title': 'Reverb-TTS', 'model': 'v1.0.0 · 297M',
        'engine': 'reverb', 'preferred': ('reverb_en_male_narrator_audition',),
        'model_note': 'Generated with Reverb-TTS by Software Mansion AI Labs (CC BY-NC 4.0 weights). Whisper recovered the full passage, including both prices.',
        'book_route': 'Local CPU · noncommercial narration.',
    },
    {
        'key': 'deepgram_flux', 'title': 'Deepgram Flux', 'model': 'Flux speech model',
        'engine': 'deepgram', 'preferred': ('deepgram_flux_jack',),
        'book_route': 'Integrated; Deepgram credentials and billing apply.',
    },
    {
        'key': 'chatterbox_turbo', 'title': 'Chatterbox Turbo', 'model': 'Turbo · 350M',
        'engine': 'chatterbox', 'preferred': ('uk_male_minter',),
        'book_route': 'Integrated; profile is opt-in.',
    },
    {
        'key': 'chatterbox_nano', 'title': 'Chatterbox Nano', 'model': 'Nano · 110M',
        'engine': 'chatterbox_nano', 'preferred': ('uk_male_minter_nano',),
        'book_route': 'Integrated; local CPU route.',
    },
    {
        'key': 'phonon_31m', 'title': 'Phonon', 'model': 'English · 31M · ptts 0.5.0',
        'engine': 'cpu_narrators', 'preferred': ('phonon_edwin', 'phonon_hugh'),
        'book_route': 'Integrated; local CPU route.',
    },
    {
        'key': 'pocket4', 'title': 'Pocket TTS 4', 'model': 'October · 100M',
        'engine': 'cpu_narrators', 'preferred': ('pocket4_bill_boerst', 'pocket4_caro_davy'),
        'book_route': 'Integrated; local CPU route.',
    },
    {
        'key': 'klein_x15', 'title': 'Klein TTS', 'model': 'X1.5-Pro',
        'engine': 'cpu_narrators', 'preferred': ('klein_arthur',),
        'book_route': 'Integrated; local CPU route.',
    },
    {
        'key': 'silencio2', 'title': 'Silencio', 'model': 'Silencio 2',
        'engine': 'cpu_narrators', 'preferred': ('silencio2_peter',),
        'book_route': 'Integrated; local CPU route.',
    },
    {
        'key': 'kitten2', 'title': 'KittenTTS', 'model': 'KittenTTS 2',
        'engine': 'cpu_narrators',
        'preferred': ('kitten2_john_kani_audition', 'kitten2_rosie'),
        'book_route': 'Integrated for registered CPU presets; custom audition voices need a registered, approved route.',
    },
    {
        'key': 'deepgram_aura2', 'title': 'Deepgram Aura-2', 'model': 'English voice catalogue',
        'engine': 'deepgram', 'preferred': ('deepgram_orion', 'deepgram_pandora'),
        'book_route': 'Integrated; Deepgram credentials and billing apply.',
    },
    {
        'key': 'pocket21', 'title': 'Pocket TTS', 'model': '2.1',
        'engine': 'pocket', 'preferred': ('pocket_bill_boerst',),
        'book_route': 'Integrated; profile is opt-in.',
    },
    {
        'key': 'kitten081', 'title': 'KittenTTS', 'model': '0.8.1',
        'engine': 'kitten', 'preferred': ('kitten_jasper', 'kitten_bella'),
        'book_route': 'Integrated; profile is opt-in.',
    },
    {
        'key': 'tada', 'title': 'TADA', 'model': 'TADA-1B · v8',
        'engine': 'tada', 'preferred': ('uk_male_minter_tada',),
        'model_note': 'The historical runtime uses a community tokenizer; equivalence to the official tokenizer is unverified. Refreshing the official path awaits upstream file access.',
        'book_route': 'Integrated; profile is opt-in.',
    },
    {
        'key': 'cosyvoice3', 'title': 'CosyVoice', 'model': 'Fun-CosyVoice3 · 0.5B · 2512',
        'engine': 'cosyvoice', 'preferred': ('uk_male_minter_cosyvoice',),
        'book_route': 'Direct conversion is fail-closed; GPU lane support is not verified.',
    },
    {
        'key': 'breeze2', 'title': 'Breeze', 'model': 'Breeze 2 · 3.5B',
        'engine': 'breeze', 'preferred': ('breeze_arthur', 'breeze_cillian_irish'),
        'model_note': 'New named-reference tests require verified speaker permission under the current model terms. Earlier auditions are retained.',
        'book_route': 'Direct conversion is fail-closed; GPU lane support is not verified.',
    },
    {
        'key': 'qwen3_customvoice', 'title': 'Qwen3-TTS', 'model': '1.7B CustomVoice',
        'engine': 'qwen3', 'preferred': ('qwen3_aiden',),
        'book_route': 'The integrated route selects Qwen3 Base; CustomVoice book support is not verified.',
    },
    {
        'key': 'qwen3_base', 'title': 'Qwen3-TTS', 'model': '1.7B base/reference voice',
        'engine': 'qwen3', 'preferred': ('uk_male_minter_qwen3',),
        'model_note': 'Dave liked the native John Kani take. A separate November Vulkan trial read 1,410 words '
                      'with the same reference. Dave rejected the accent on the regional desk.',
        'book_route': 'Integrated; profile is opt-in.',
    },
    {
        'key': 'vibevoice15b', 'title': 'VibeVoice', 'model': '1.5B',
        'engine': 'vibevoice', 'preferred': ('uk_male_minter_vibevoice',),
        'book_route': 'Integrated; opt-in profile or free GPU lane.',
    },
    {
        'key': 'fish_s2pro', 'title': 'Fish Speech', 'model': '2.0 · S2 Pro · 4.4B',
        'engine': 'fish', 'preferred': ('fish_cillian_irish',),
        'book_route': 'Integrated through the locked GPU lane recipe.',
    },
    {
        'key': 'fish_drama3', 'title': 'Fish Drama 3', 'model': 'Drama 3 · native auditions',
        'engine': 'fish_drama3', 'preferred': (), 'verdict_only': True,
        'model_note': ('Dave liked the six-paragraph Peter reading and the 29-second Cillian take. '
                       'The repaired short Peter take also passed listening. Other takes dropped '
                       'words, and the rebuilt 14.6-minute Cillian take awaits a listening verdict.'),
        'book_route': 'No Studio book route.',
    },
    {
        'key': 'ming3_05b', 'title': 'Ming TTS', 'model': '3.0 · 0.5B',
        'engine': 'ming3', 'preferred': (), 'verdict_only': True,
        'model_note': ('Dave liked the instruction-guided storytelling apart from Irish pronunciation. '
                       'The Peter reference clone sounded tinny with some artefacts.'),
        'book_route': 'No Studio book route.',
    },
    {
        'key': 'higgs3', 'title': 'Higgs TTS', 'model': '3',
        'engine': 'fish', 'preferred': ('higgs_cillian_irish',),
        'model_note': 'New named-reference tests require verified speaker permission under the current model terms. Earlier auditions are retained.',
        'book_route': 'Integrated through the shared GPU lane.',
    },
    {
        'key': 'maya2', 'title': 'Maya 2', 'model': 'Native voices',
        'engine': 'audition', 'preferred': ('maya2_siddhant', 'maya2_nivedita'),
        'model_note': 'Shared test: native text normalization changes pence to cents in the pound amounts. Judge the voice separately from this known wording error.',
        'book_route': 'Audition only; book conversion is not integrated.',
    },
    {
        'key': 'voxcpm2', 'title': 'VoxCPM2', 'model': 'Peter Yearsley reference audition',
        'engine': 'audition', 'preferred': ('voxcpm2_peter',),
        'model_note': 'A separate November GPU trial reused one text-designed narrator for a chapter. '
                      'It dropped part of a sentence, including on two retries. Hold that configuration for unattended books.',
        'book_route': 'Audition only; book conversion is not integrated.',
    },
    {
        'key': 'gemini31', 'title': 'Gemini TTS', 'model': '3.1 Flash',
        'engine': 'gemini', 'preferred': ('gemini_achernar', 'gemini_zephyr'),
        'model_note': 'Shared-test refreshes follow the free daily quota. Older previews remain available until refreshed.',
        'book_route': 'Integrated; free-tier credentials and quota apply.',
    },
    {
        'key': 'inworld15', 'title': 'Inworld TTS', 'model': '1.5 Mini',
        'engine': 'inworld', 'preferred': ('inworld_Graham',),
        'book_route': 'Integrated; credentials and pricing apply.',
    },
    {
        'key': 'kokoro', 'title': 'Kokoro', 'model': '82M · compatibility/debug',
        'engine': 'kokoro', 'preferred': ('bm_george', 'am_michael'),
        'book_route': 'Integrated compatibility route; retired from quality contention.',
    },
    {
        'key': 'edge', 'title': 'Microsoft Edge TTS', 'model': 'Neural voice catalogue',
        'engine': 'edge', 'preferred': ('en-GB-RyanNeural', 'en-GB-LibbyNeural'),
        'book_route': 'Integrated network route; voice service availability may vary.',
    },
    {
        'key': 'polly', 'title': 'Amazon Polly', 'model': 'Registered voice catalogue',
        'engine': 'polly', 'preferred': ('polly_ruth', 'polly_danielle'),
        'book_route': 'Integrated; AWS credentials and pricing apply.',
    },
    {
        'key': 'f5tts', 'title': 'F5-TTS', 'model': '300M',
        'engine': 'f5tts', 'preferred': (),
        'book_route': 'No registered voice or book conversion route.',
        'model_note': 'Engine entry is retained; no voice ID or cached preview is registered.',
    },
)

_GROUP_BY_KEY = {group['key']: group for group in MODEL_GROUPS}
_ENGINE_GROUP = {
    'zonos3': 'zonos3',
    'chatterbox': 'chatterbox_turbo',
    'chatterbox_nano': 'chatterbox_nano',
    'cosyvoice': 'cosyvoice3',
    'pocket': 'pocket21',
    'kitten': 'kitten081',
    'tada': 'tada',
    'breeze': 'breeze2',
    'vibevoice': 'vibevoice15b',
    'fish': 'fish_s2pro',
    'gemini': 'gemini31',
    'inworld': 'inworld15',
    'kokoro': 'kokoro',
    'edge': 'edge',
    'polly': 'polly',
    'f5tts': 'f5tts',
}
_PREFIX_GROUP = (
    ('deepgram_flux_', 'deepgram_flux'),
    ('deepgram_', 'deepgram_aura2'),
    ('pocket4_', 'pocket4'),
    ('phonon_', 'phonon_31m'),
    ('klein_', 'klein_x15'),
    ('silencio2_', 'silencio2'),
    ('kitten2_', 'kitten2'),
    ('maya2_', 'maya2'),
    ('voxcpm2_', 'voxcpm2'),
    ('higgs_', 'higgs3'),
    ('qwen3_aiden', 'qwen3_customvoice'),
    ('uk_male_minter_qwen3', 'qwen3_base'),
)

_REPRESENTATIVE_IDS = {
    group['key']: group['preferred'] for group in MODEL_GROUPS
}


def model_key_for_voice(voice_id: str, voice: dict) -> str:
    """Resolve a voice to an exact model/version group without guessing speakers."""
    override = voice.get('catalogue_model')
    if override:
        if override not in _GROUP_BY_KEY:
            raise ValueError(f"Unknown catalogue_model {override!r} on {voice_id}")
        return override

    for prefix, key in _PREFIX_GROUP:
        if voice_id.startswith(prefix):
            return key
    engine = voice.get('engine', '')
    if engine == 'qwen3':
        return 'qwen3_base'
    try:
        return _ENGINE_GROUP[engine]
    except KeyError:
        # Preserve an unknown entry without putting unrelated voices under a
        # made-up shared model/version. Each gets a visible identity-unknown
        # card until explicit model metadata is added.
        return f'unclassified:{engine or "unknown"}:{voice_id}'


def _representative(group: dict, members: list[tuple[str, dict]]) -> str | None:
    by_id = dict(members)
    preferred = [voice_id for voice_id in group['preferred'] if voice_id in by_id]

    def current(voice_id: str) -> bool:
        info = by_id[voice_id]
        return info.get('preview_cached') is True and info.get('preview_sample_current') is True

    def cached(voice_id: str) -> bool:
        return by_id[voice_id].get('preview_cached') is True

    # Prefer the shared passage across the whole model before falling back to
    # an older preferred voice. Preferences break ties within each readiness tier.
    for predicate in (current, cached):
        for candidates in (preferred, [voice_id for voice_id, _ in members]):
            match = next((voice_id for voice_id in candidates if predicate(voice_id)), None)
            if match:
                return match
    return (preferred or [voice_id for voice_id, _ in members] or [None])[0]


def build_voice_catalogue(voices: dict[str, dict], engine_registry: dict | None = None) -> list[dict]:
    """Build model cards for every registered voice, including unconfigured ones.

    `engine_registry` contributes a display name for future/unclassified groups;
    it never filters voices out. Preview and route readiness are separate fields.
    """
    grouped: dict[str, list[tuple[str, dict]]] = {}
    for voice_id, info in voices.items():
        key = model_key_for_voice(voice_id, info)
        grouped.setdefault(key, []).append((voice_id, info))

    # Keep a model card for verdict-only models and registered engines
    # with no registered voice (currently F5-TTS).
    for group in MODEL_GROUPS:
        if group.get('verdict_only') or group['engine'] in (engine_registry or {}):
            grouped.setdefault(group['key'], [])

    ordered = [group for group in MODEL_GROUPS if group['key'] in grouped]
    extra_keys = sorted(key for key in grouped if key not in _GROUP_BY_KEY)
    for key in extra_keys:
        _, engine, voice_id = (key.split(':', 2) + ['', '', ''])[:3]
        registry = (engine_registry or {}).get(engine, {})
        ordered.append({
            'key': key,
            'title': f"{registry.get('name') or (engine or 'Unknown engine').upper()} · {voice_id}",
            'model': 'Version or model identity not recorded',
            'engine': engine,
            'preferred': (),
            'book_route': 'Review engine integration metadata.',
            'model_note': 'Voice is retained in the catalogue; exact model/version grouping needs metadata.',
        })

    result = []
    for spec in ordered:
        members = sorted(grouped[spec['key']], key=lambda item: (item[1].get('name', '').casefold(), item[0]))
        representative_id = _representative(spec, members)
        representative = dict(voices[representative_id]) if representative_id else None
        cached_count = sum(info.get('preview_cached') is True for _, info in members)
        current_count = sum(
            info.get('preview_cached') is True and info.get('preview_sample_current') is True
            for _, info in members
        )
        result.append({
            'key': spec['key'],
            'title': spec['title'],
            'model': spec['model'],
            'engine': spec['engine'],
            'book_route': spec['book_route'],
            **voice_customization_for(spec['key']),
            'model_note': spec.get('model_note', ''),
            'verdict_only': spec.get('verdict_only', False),
            'voice_count': len(members),
            'cached_count': cached_count,
            'current_count': current_count,
            'earlier_count': cached_count - current_count,
            'pending_count': len(members) - cached_count,
            'representative_id': representative_id,
            'representative': representative,
            'other_voice_ids': [voice_id for voice_id, _ in members if voice_id != representative_id],
            'engine_registry_name': (engine_registry or {}).get(spec['engine'], {}).get('name', ''),
        })
    return result

