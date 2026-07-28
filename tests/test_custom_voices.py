"""Uploaded reference voices must behave like any other voice.

Chatterbox is a cloning engine — the stock "human-cloned" narrators are just
reference WAVs in a directory. Uploading one should therefore need no rebuild
and no special-casing downstream; the only real work is making every
"is this a known voice" check aware of the uploaded ones.
"""

import re
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / 'webapp' / 'app.py').read_text(encoding='utf-8')
SERVER = (Path(__file__).resolve().parents[1] / 'chatterbox' / 'server.py').read_text(encoding='utf-8')
COMPOSE = (Path(__file__).resolve().parents[1] / 'docker-compose.yml').read_text(encoding='utf-8')


class TestEngineSeesUploads:
    def test_server_scans_the_custom_subdir(self):
        assert "'custom'" in SERVER or '"custom"' in SERVER, \
            'the engine must scan the bind-mounted custom voices directory'

    def test_custom_overrides_builtin(self):
        """Scanned second, so a custom voice with a stock name wins."""
        load = SERVER[SERVER.index('def _load_voices'):]
        builtin = load.index('VOICES_DIR, "*.wav"')
        custom = load.index('"custom"')
        assert custom > builtin, 'custom voices must be scanned after built-ins'

    def test_all_chatterbox_services_mount_it(self):
        """One WAV should reach Turbo, Nano and Multilingual V3."""
        assert COMPOSE.count('/app/voices/custom') == 3, \
            'Turbo, Nano and Multilingual V3 all need the custom voices mount'


class TestWebappSeesUploads:
    def test_all_voices_helper_exists(self):
        assert 'def all_voices(' in APP

    def test_uploads_offered_on_both_engines(self):
        fn = APP[APP.index('def all_voices('):]
        fn = fn[:fn.index('\n@app.route')]
        assert "'chatterbox_nano'" in fn and "'chatterbox'" in fn

    def test_validation_checks_are_lookups_not_static(self):
        """A custom voice must not be rejected as unknown at queue time."""
        for check in ('if voice not in VOICES:', 'if voice_id not in VOICES:'):
            assert check not in APP, \
                f'"{check}" would reject uploaded voices — use all_voices()'

    def test_upload_is_atomic(self):
        fn = APP[APP.index('def upload_custom_voice('):]
        fn = fn[:fn.index('\n@app.route')]
        assert 'os.replace(' in fn, 'a half-written reference must never be visible'

    def test_upload_rejects_non_wav(self):
        fn = APP[APP.index('def upload_custom_voice('):]
        fn = fn[:fn.index('\n@app.route')]
        assert '_probe_wav' in fn, 'an mp3 renamed .wav must be caught at upload'

    def test_voice_id_is_sanitised(self):
        fn = APP[APP.index('def upload_custom_voice('):]
        fn = fn[:fn.index('\n@app.route')]
        assert re.search(r"re\.sub\(r?['\"]\[\^a-z0-9_\]", fn), \
            'voice ids become filenames; they must be sanitised'
