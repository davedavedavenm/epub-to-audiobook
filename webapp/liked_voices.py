"""Dave's heard November shortlist; model versions are part of voice identity.

These are ordinary-narration Likes, not pronunciation or full-book approvals.
The later 416-word Maybe for Isabella supersedes her earlier short-take Like.
"""

CPU_VOICES = {
    'pocket4_bill_boerst': ('Bill Boerst', 'Pocket 4 / October 100M', 'pocket', 'bill_boerst'),
    'pocket4_caro_davy': ('Caro Davy', 'Pocket 4 / October 100M', 'pocket', 'caro_davy'),
    'pocket4_stuart_bell': ('Stuart Bell', 'Pocket 4 / October 100M', 'pocket', 'stuart_bell'),
    'pocket4_peter_yearsley': ('Peter Yearsley', 'Pocket 4 / October 100M', 'pocket', 'peter_yearsley'),
    'phonon_edwin': ('Edwin', 'Phonon 31M', 'phonon', 'Edwin'),
    'phonon_hugh': ('Hugh', 'Phonon 31M', 'phonon', 'Hugh'),
    'phonon_freya': ('Freya', 'Phonon 31M', 'phonon', 'Freya'),
    'phonon_imogen': ('Imogen', 'Phonon 31M', 'phonon', 'Imogen'),
    'klein_arthur': ('Arthur', 'Klein X1.5-Pro', 'klein', 'Arthur'),
    'silencio2_peter': ('Peter Yearsley', 'Silencio 2', 'silencio', 'Peter'),
    'kitten2_rosie': ('Rosie', 'KittenTTS 2', 'kitten', 'Rosie'),
}

LIKED_VOICES = {
    key: {'name': f'{name} ({model})', 'accent': 'English',
          'gender': 'Unspecified', 'engine': 'cpu_narrators', 'liked': True,
          'rating_date': '2026-11-10'}
    for key, (name, model, _family, _speaker) in CPU_VOICES.items()
}
for _name in ('jack', 'colin', 'rufus', 'conor', 'sean'):
    LIKED_VOICES[f'deepgram_flux_{_name}'] = {
        'name': f'{_name.title()} (Deepgram Flux)', 'accent': 'British',
        'gender': 'Male', 'engine': 'deepgram', 'liked': True,
        'rating_date': '2026-11-10',
    }

# Keep heard GPU takes available to audition without implying that a new
# full-book lane has passed preflight/recovery or authorizing GPU work at boot.
for _id, _name, _accent in (
    ('maya2_siddhant', 'Siddhant (Maya 2 Native)', 'Indian English'),
    ('maya2_nivedita', 'Nivedita (Maya 2 Native)', 'Indian English'),
    ('voxcpm2_peter', 'Peter Yearsley (VoxCPM2)', 'British reference'),
):
    LIKED_VOICES[_id] = {
        'name': _name, 'accent': _accent, 'gender': 'Unspecified',
        'engine': 'audition', 'liked': True, 'audition_only': True,
        'rating_date': '2026-11-10',
        'note': ('Liked short take; not suitable for Badawi' if _id.startswith('maya')
                 else 'Liked GPU audition; full-book integration pending'),
    }

MODELS = {
    'phonon': ('gradium/phonon-31m-en', '92741c5b07d085ff840e26fea8ce43110b87852f'),
    'klein': ('klein-ml/Klein-TTS-X1.5-Pro', '25e0e73bebba71e5985bc369628ebdcb81bf7116'),
    'silencio': ('BlueRoseLabs/Silencio-2', '20930f5f6a6bb564f2a8207152fd5c5d8eecff03'),
    'kitten': ('KittenML/kitten-tts-2', 'c93cb7c271baa51d9ae8204d5277988906f235a2'),
}
PHONON_CATALOG = 'hf://gradium/phonon-voices@0ee17205f254b5abc43b266c8a0f215565c352f7'
