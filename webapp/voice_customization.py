"""Upstream voice options and the narrower paths available in Studio.

Use the exact model variant on each card. Evidence for the pinned runtimes
and listening paths is in ENGINES.md and TUNING-AUDIT-2026-11.md.
"""

# Each row records stock voices, reference cloning, and voice design in
# order. Each pair gives upstream capability followed by Studio access.
_OPTIONS = {
    'tontaube': (('yes', 'preset'), ('audio', 'preset_only'), ('delivery', 'fixed')),
    'zonos3': (('yes', 'preset'), ('audio', 'preset_only'), ('structured', 'none')),
    'kale_base': (('yes', 'sample'), ('unknown', 'none'), ('unknown', 'none')),
    'voxmel_06b': (('unknown', 'none'), ('transcript', 'none'), ('unknown', 'none')),
    'reverb': (('yes', 'preset'), ('transcript', 'preset_only'), ('unknown', 'none')),
    'deepgram_flux': (('yes', 'preset'), ('no', 'none'), ('no', 'none')),
    'chatterbox_turbo': (('default', 'reference'), ('audio', 'upload'), ('unknown', 'none')),
    'chatterbox_nano': (('default', 'reference'), ('audio', 'upload'), ('unknown', 'none')),
    'phonon_31m': (('yes', 'preset'), ('hosted_audio', 'none'), ('hosted_text', 'none')),
    'pocket4': (('yes', 'preset'), ('audio', 'reference'), ('unknown', 'none')),
    'klein_x15': (('yes', 'preset'), ('unknown', 'none'), ('unknown', 'none')),
    'silencio2': (('yes', 'reference'), ('audio', 'reference'), ('delivery', 'none')),
    'kitten2': (('yes', 'preset'), ('audio', 'sample'), ('delivery', 'none')),
    'deepgram_aura2': (('yes', 'preset'), ('no', 'none'), ('no', 'none')),
    'pocket21': (('yes', 'preset'), ('audio', 'preset_only'), ('unknown', 'none')),
    'kitten081': (('yes', 'preset'), ('no', 'none'), ('no', 'none')),
    'tada': (('unknown', 'none'), ('optional_transcript', 'reference'), ('unknown', 'none')),
    'cosyvoice3': (('unknown', 'none'), ('transcript', 'sample'), ('text_dialect', 'none')),
    'breeze2': (('unknown', 'none'), ('transcript', 'sample'), ('text', 'sample')),
    'qwen3_customvoice': (('yes', 'sample'), ('no', 'none'), ('text_style', 'none')),
    'qwen3_base': (('no', 'none'), ('optional_transcript', 'reference'), ('no', 'none')),
    'vibevoice15b': (('unknown', 'none'), ('audio', 'reference'), ('unknown', 'none')),
    'fish_s2pro': (('generated', 'none'), ('transcript', 'reference'), ('text_style', 'fixed')),
    'fish_drama3': (('demo_presets', 'none'), ('transcript', 'none'), ('demo_text', 'none')),
    'ming3_05b': (('yes', 'none'), ('transcript', 'none'), ('text_and_steering', 'none')),
    'higgs3': (('default', 'sample'), ('transcript', 'reference'), ('delivery', 'none')),
    'maya2': (('yes', 'sample'), ('optional_transcript', 'none'), ('delivery', 'none')),
    'voxcpm2': (('unknown', 'none'), ('optional_transcript', 'sample'), ('text', 'none')),
    'gemini31': (('yes', 'preset'), ('no', 'none'), ('text_accent', 'fixed')),
    'inworld15': (('yes', 'preset'), ('hosted_audio', 'none'), ('newer_model', 'none')),
    'kokoro': (('yes', 'preset'), ('no', 'none'), ('blend', 'none')),
    'edge': (('yes', 'preset'), ('no', 'none'), ('no', 'none')),
    'polly': (('yes', 'preset'), ('no', 'none'), ('no', 'none')),
    'f5tts': (('default', 'none'), ('transcript', 'none'), ('unknown', 'none')),
}

_MODEL_LABELS = {
    'yes': 'Vendor catalogue',
    'default': 'Vendor default voice',
    'demo_presets': 'Reference presets in Fish Audio’s demo',
    'generated': 'Random voice without a reference',
    'no': 'Unsupported',
    'unknown': 'Unverified for this model',
    'audio': 'Reference audio',
    'transcript': 'Reference audio + transcript',
    'optional_transcript': 'Reference audio, transcript depends on mode',
    'hosted_audio': 'Provider-hosted cloning',
    'text': 'New voice from a text description',
    'text_and_steering': 'New voices from text and separate delivery instructions',
    'hosted_text': 'Provider-hosted text design',
    'demo_text': 'Text voice design in Fish Audio’s demo and delivery controls',
    'newer_model': 'Text design documented for TTS-2',
    'text_style': 'Text instructions for delivery',
    'text_accent': 'Text instructions for accent and style',
    'text_dialect': 'Text direction for delivery and supported Chinese dialects',
    'structured': 'Voice traits and accent controls',
    'delivery': 'Delivery controls only',
    'blend': 'Blending existing presets',
}
_STUDIO_LABELS = {
    'preset': 'Studio presets',
    'preset_only': 'Studio uses presets',
    'reference': 'Preconfigured references in Studio',
    'upload': 'Upload a WAV',
    'sample': 'Studio auditions only',
    'fixed': 'Fixed settings in Studio',
    'none': 'Unavailable in Studio',
}


def voice_customization_for(model_key: str) -> dict:
    """Return card labels and the filters the documented options qualify for."""
    stock, cloning, design = _OPTIONS.get(model_key, (('unknown', 'none'),) * 3)
    filters = []
    if stock[0] in {'yes', 'default', 'demo_presets'}:
        filters.append('stock')
    if cloning[0] in {'audio', 'transcript', 'optional_transcript', 'hosted_audio'}:
        filters.append('cloning')
    if cloning[1] == 'upload':
        filters.append('upload')
    if design[0] in {'text', 'hosted_text', 'text_and_steering', 'demo_text'}:
        filters.append('design')
    if design[0] in {'structured', 'delivery', 'text_style', 'text_accent',
                     'text_dialect', 'blend', 'text_and_steering', 'demo_text'}:
        filters.append('steering')
    return {
        'customization': {
            kind: {'model_label': _MODEL_LABELS[model], 'studio': studio,
                   'studio_label': _STUDIO_LABELS[studio]}
            for kind, (model, studio) in zip(('stock', 'cloning', 'design'),
                                           (stock, cloning, design), strict=True)
        },
        'customization_filters': filters,
    }
