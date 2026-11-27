import io
from unittest.mock import Mock

import app as web


def test_zonos3_reference_is_held_until_preview_and_replaces_by_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(web, 'CUSTOM_VOICES_DIR', tmp_path / 'references')
    monkeypatch.setattr(web, 'PREVIEWS_DIR', tmp_path / 'previews')
    monkeypatch.setattr(web, '_zonos3_upload_state', {})
    monkeypatch.setattr(web.subprocess, 'run', Mock())
    checks = Mock(side_effect=[True, False, True])
    monkeypatch.setattr(web, '_zonos3_preview_complete', checks)
    responses = iter([
        Mock(content=b'\x93NUMPYembedding one'), Mock(content=b'a' * 6000, headers={'Content-Type': 'audio/mpeg'}),
        Mock(content=b'\x93NUMPYembedding two'), Mock(content=b'b' * 6000, headers={'Content-Type': 'audio/mpeg'}),
        Mock(content=b'c' * 6000, headers={'Content-Type': 'audio/mpeg'}),
    ])

    def post(url, **kwargs):
        if url.endswith('/audio/speech'):
            assert kwargs['json']['input'] == web._preview_text_for('zonos3')
            assert kwargs['json']['voice'] not in web.all_voices()
        return next(responses)

    monkeypatch.setattr(web.requests, 'post', post)
    monkeypatch.setattr(web.requests, 'get', Mock())
    client = web.app.test_client()

    def run_thread(*, target, args, daemon):
        class Thread:
            def start(self):
                tasks.append((target, args))
        return Thread()

    tasks = []
    monkeypatch.setattr(web.threading, 'Thread', run_thread)

    def upload(source):
        return client.post('/api/voices/custom', data={
            'engine': 'zonos3', 'voice_id': 'Example', 'file': (io.BytesIO(source), 'reference.wav'),
        })

    assert upload(b'RIFF\0\0\0\0WAVEfirst').status_code == 202
    assert upload(b'RIFF\0\0\0\0WAVElater').status_code == 409
    assert client.get('/api/voices/custom').json['voices'][0]['state'] == 'preparing'
    target, args = tasks.pop()
    target(*args)
    ready = client.get('/api/voices/custom').json['voices'][0]
    voice_id = ready['voice_id']
    assert ready['state'] == 'ready'
    assert web.all_voices()[voice_id]['engine'] == 'zonos3'
    assert web.all_voices()[voice_id]['accent'] == 'Unclassified'
    assert client.get(f'/api/preview/{voice_id}').status_code == 200

    assert upload(b'RIFF\0\0\0\0WAVEsecond').status_code == 202
    assert voice_id in web.all_voices()
    target, args = tasks.pop()
    target(*args)
    next_voice = client.get('/api/voices/custom').json['voices'][0]['voice_id']
    assert '_compact_' in next_voice and voice_id not in web.all_voices()
    assert checks.call_count == 3
    assert (web._zonos3_references() / f'{voice_id}.npy').exists()
    monkeypatch.setattr(web, 'get_all_jobs', lambda: [{'voice': voice_id}])
    assert client.delete('/api/voices/custom/example?engine=zonos3').status_code == 200
    assert next_voice not in web.all_voices()
    assert (web._zonos3_references() / f'{voice_id}.npy').exists()
    assert not (web._zonos3_references() / f'{next_voice}.npy').exists()


def test_absent_zonos3_reference_never_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(web, 'CUSTOM_VOICES_DIR', tmp_path)
    monkeypatch.setattr(web, 'check_engines_health', lambda: {'kokoro': True, 'zonos3': False})
    voice_id = 'zonos3_custom_missing_' + 'a' * 64
    assert web.pick_engine_with_fallback('zonos3', voice_id) == ('zonos3', voice_id, None)
    client = web.app.test_client()
    response = client.post('/api/library/convert', json={'voice': voice_id, 'path': 'some.epub'})
    assert response.status_code == 400
    assert 'ZONOS3 reference' in response.json['error']


def test_failed_enrollment_never_publishes_and_can_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(web, 'CUSTOM_VOICES_DIR', tmp_path / 'references')
    monkeypatch.setattr(web, 'PREVIEWS_DIR', tmp_path / 'previews')
    monkeypatch.setattr(web, '_zonos3_upload_state', {})
    enrol = Mock(content=b'\x93NUMPYexample')
    failed = Mock()
    failed.raise_for_status.side_effect = web.requests.HTTPError('Unavailable')
    monkeypatch.setattr(web.requests, 'post', Mock(side_effect=[enrol, failed]))
    web._prepare_zonos3_reference('failed', b'fake source')
    assert web._zonos3_upload_state == {'failed': 'failed'}
    assert not list(web._zonos3_references().glob('*.npy'))
    assert not list(web._zonos3_references().glob('*.json'))


def test_unavailable_backend_refuses_upload_before_starting_preparation(monkeypatch):
    monkeypatch.setattr(web, '_zonos3_upload_state', {})
    monkeypatch.setattr(web.requests, 'get', Mock(side_effect=web.requests.ConnectionError()))
    response = web.app.test_client().post('/api/voices/custom', data={
        'engine': 'zonos3', 'voice_id': 'test', 'file': (io.BytesIO(b'RIFF\0\0\0\0WAVEtest'), 'test.wav'),
    })
    assert response.status_code == 503
    assert 'offline or starting' in response.json['error']
    assert not web._zonos3_upload_state


def test_completeness_gate_catches_clipped_tail_and_tolerates_isolated_name_variants(monkeypatch, tmp_path):
    import qa_asr

    prepared = web._preview_text_for('zonos3')
    audio = tmp_path / 'preview.mp3'
    monkeypatch.setattr(qa_asr, 'transcribe', lambda *args, **kwargs: ' '.join(prepared.split()[:-48]))
    assert not web._zonos3_preview_complete(audio, prepared)
    monkeypatch.setattr(qa_asr, 'transcribe', lambda *args, **kwargs: prepared.replace('Huawei', 'Wahway'))
    assert web._zonos3_preview_complete(audio, prepared)
