import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import app as appmod  # noqa: E402
from app import app, get_db, get_job, init_db, save_job  # noqa: E402
from qa_report import merge_qa_reports  # noqa: E402


def test_lan_ui_and_api_are_intentionally_passwordless():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/jobs').status_code == 200
        assert client.get('/api/health').status_code in (200, 503)


def test_cross_origin_write_is_refused():
    app.config.update(TESTING=True)
    headers = {'Origin': 'https://attacker.example'}
    with app.test_client() as client:
        response = client.post('/api/queue/pause', headers=headers)
        assert response.status_code == 403


def test_telegram_webhook_requires_official_secret_header(monkeypatch):
    monkeypatch.setattr(appmod, 'TELEGRAM_WEBHOOK_SECRET', 'telegram-secret')
    with app.test_client() as client:
        assert client.post('/api/telegram/webhook', json={}).status_code == 401
        response = client.post(
            '/api/telegram/webhook', json={},
            headers={'X-Telegram-Bot-Api-Secret-Token': 'telegram-secret'})
        assert response.status_code == 200
        assert response.get_json()['status'] == 'ignored'


def test_recovery_qa_merge_preserves_all_chapters():
    current = {'chapters': [
        {'chapter': 1, 'wer': 0.01, 'flagged': False},
        {'chapter': 2, 'wer': 0.03, 'flagged': False},
    ], 'lexicon_suggestions': {'old': 'OLD'}}
    recovered = {'chapters': [
        {'chapter': 2, 'wer': 0.2, 'flagged': True},
    ], 'lexicon_suggestions': {'new': 'NEW'}}
    merged = merge_qa_reports(current, recovered)
    assert [chapter['chapter'] for chapter in merged['chapters']] == [1, 2]
    assert merged['chapters'][1]['wer'] == 0.2
    assert merged['flagged_chapters'] == [2]
    assert merged['lexicon_suggestions'] == {'old': 'OLD', 'new': 'NEW'}


def test_rss_enclosure_is_a_served_article_audio_route(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, 'OUTPUT_DIR', tmp_path)
    monkeypatch.setattr(appmod, 'PUBLIC_BASE_URL', 'https://audio.example')
    job_id = 'rss-audio-test'
    outdir = tmp_path / 'podcast_test'
    outdir.mkdir()
    audio = outdir / 'article.mp3'
    audio.write_bytes(b'ID3' + b'x' * 2048)
    save_job({
        'id': job_id, 'book_name': 'Article', 'voice': 'v',
        'status': 'completed', 'created_at': '2026-08-13T00:00:00',
        'input_filename': 'article.epub', 'output_dirname': outdir.name,
        'source_kind': 'article', 'source_url': 'https://example.com/a',
        'source_site': 'Example',
    })
    try:
        with app.test_client() as client:
            feed = client.get('/api/articles/rss')
            assert feed.status_code == 200
            enclosure = f'/api/articles/audio/{job_id}/article.mp3'
            assert f'https://audio.example{enclosure}' in feed.get_data(as_text=True)
            streamed = client.get(enclosure)
            assert streamed.status_code == 200
            assert streamed.mimetype == 'audio/mpeg'
    finally:
        with get_db() as conn:
            conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
            conn.commit()


def _completed_job_fixture(tmp_path, monkeypatch, *, job_id='history-test', kind='book', files=1):
    upload = tmp_path / 'uploads'
    output = tmp_path / 'output'
    for path in (upload, output):
        path.mkdir(exist_ok=True)
    monkeypatch.setattr(appmod, 'DB_PATH', tmp_path / 'jobs.db')
    monkeypatch.setattr(appmod, 'UPLOAD_DIR', upload)
    monkeypatch.setattr(appmod, 'OUTPUT_DIR', output)
    monkeypatch.setattr(appmod, 'LOG_DIR', tmp_path / 'logs')
    init_db()
    outdir = output / f'Example_{job_id}'
    outdir.mkdir()
    for index in range(1, files + 1):
        (outdir / f'{index:02d}.mp3').write_bytes(b'ID3' + bytes([index]) * 2048)
    input_name = f'{job_id}_Example.epub'
    (upload / input_name).write_bytes(b'epub')
    save_job({
        'id': job_id, 'book_name': 'Example', 'voice': 'voice',
        'voice_name': 'Narrator', 'tts_engine': 'chatterbox_nano',
        'status': 'completed', 'created_at': '2026-08-14T10:00:00',
        'completed_at': '2026-08-14T11:00:00', 'input_filename': input_name,
        'output_dirname': outdir.name, 'file_count': files, 'source_kind': kind,
    })
    return outdir


def test_single_mp3_download_is_not_wrapped_in_zip(tmp_path, monkeypatch):
    _completed_job_fixture(tmp_path, monkeypatch, kind='article', files=1)
    with app.test_client() as client:
        response = client.get('/api/jobs/history-test/download')
    assert response.status_code == 200
    assert response.mimetype == 'audio/mpeg'
    assert response.headers['Content-Disposition'].endswith('filename=Example.mp3')


def test_multi_chapter_mp3_download_remains_one_zip(tmp_path, monkeypatch):
    _completed_job_fixture(tmp_path, monkeypatch, files=2)
    with app.test_client() as client:
        response = client.get('/api/jobs/history-test/download')
    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    archive = tmp_path / 'download.zip'
    archive.write_bytes(response.data)
    with ZipFile(archive) as zipped:
        assert zipped.namelist() == ['01.mp3', '02.mp3']


def test_delete_conversion_removes_owned_local_files_only(tmp_path, monkeypatch):
    outdir = _completed_job_fixture(tmp_path, monkeypatch)
    upload_root = appmod.UPLOAD_DIR
    tts_copy = upload_root / 'history-test_Example_tts.epub'
    tts_copy.write_bytes(b'preprocessed epub')
    with app.test_client() as client:
        response = client.delete('/api/jobs/history-test/delete', json={'remove_from_abs': False})
    assert response.status_code == 200
    assert not outdir.exists()
    assert not tts_copy.exists()
    assert upload_root.exists(), 'an empty filename must never resolve to and remove the upload root'
    assert get_job('history-test') is None


def test_delete_everywhere_stops_when_exact_abs_removal_fails(tmp_path, monkeypatch):
    outdir = _completed_job_fixture(tmp_path, monkeypatch)
    appmod.update_job('history-test', synced_to_abs=True)
    monkeypatch.setattr(appmod, '_delete_synced_copy', lambda _job: (False, 'unsafe path'))
    with app.test_client() as client:
        response = client.delete('/api/jobs/history-test/delete', json={'remove_from_abs': True})
    assert response.status_code == 409
    assert response.get_json()['error'] == 'unsafe path'
    assert outdir.exists()
    assert get_job('history-test') is not None


def test_new_article_episode_filename_is_unique_to_job():
    name = appmod._episode_filename(
        {'id': 'abc12345', 'source_date': '2026-08-14'}, 'Same title')
    assert name == '2026-08-14 - Same title [abc12345].mp3'


def _article_capture_fixture(tmp_path, monkeypatch):
    upload = tmp_path / 'uploads'
    output = tmp_path / 'output'
    articles = tmp_path / 'articles'
    for path in (upload, output, articles):
        path.mkdir()
    monkeypatch.setattr(appmod, 'DB_PATH', tmp_path / 'jobs.db')
    monkeypatch.setattr(appmod, 'UPLOAD_DIR', upload)
    monkeypatch.setattr(appmod, 'OUTPUT_DIR', output)
    monkeypatch.setattr(appmod, 'ARTICLES_DIR', articles)
    monkeypatch.setattr(appmod, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(appmod, 'check_engines_health',
                        lambda: {'chatterbox_nano': True})
    monkeypatch.setattr(appmod, 'maybe_start_next_queued_job', lambda: None)
    init_db()
    return {
        'url': 'https://example.com/story',
        'title': 'A Proper Article Title',
        'author': 'Writer',
        'site': 'Example',
        'date': '2026-08-13',
        'image': '',
        'text': 'A complete sentence for narration. ' * 110,
        'word_count': 550,
        'estimated_minutes': 4,
    }


def test_url_article_capture_uses_default_local_engine(tmp_path, monkeypatch):
    meta = _article_capture_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr('article.fetch_article', lambda _url: meta)
    with app.test_client() as client:
        response = client.post('/api/articles/narrate_url', json={'url': meta['url']})
    assert response.status_code == 200
    job = get_job(response.get_json()['job_id'])
    assert job['voice'] == appmod.DEFAULT_VOICE
    assert job['tts_engine'] == 'chatterbox_nano'
    assert job['render_target'] == 'local'
    assert job['output_format'] == 'mp3'
    assert job['source_kind'] == 'article'
    assert job['source_site'] == 'Example'


def test_telegram_article_capture_is_owner_only_and_uses_same_defaults(tmp_path, monkeypatch):
    meta = _article_capture_fixture(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr('article.fetch_article', lambda url: calls.append(url) or meta)
    monkeypatch.setattr(appmod, 'TELEGRAM_WEBHOOK_SECRET', 'telegram-secret')
    monkeypatch.setattr(appmod, 'TELEGRAM_CHAT_ID', '12345')
    monkeypatch.setattr(appmod, 'TELEGRAM_BOT_TOKEN', '')
    headers = {'X-Telegram-Bot-Api-Secret-Token': 'telegram-secret'}

    with app.test_client() as client:
        refused = client.post('/api/telegram/webhook', headers=headers, json={
            'message': {'chat': {'id': 999}, 'text': meta['url']}})
        accepted = client.post('/api/telegram/webhook', headers=headers, json={
            'message': {'chat': {'id': 12345}, 'text': f'Read this: {meta["url"]}'}})

    assert refused.status_code == 200
    assert refused.get_json()['status'] == 'ignored_chat'
    assert calls == [meta['url']]
    assert accepted.status_code == 200
    job = get_job(accepted.get_json()['job_id'])
    assert job['voice'] == appmod.DEFAULT_VOICE
    assert job['tts_engine'] == 'chatterbox_nano'
    assert job['render_target'] == 'local'
    assert job['notify_telegram'] == 1


def test_telegram_article_capture_queues_all_distinct_urls(tmp_path, monkeypatch):
    meta = _article_capture_fixture(tmp_path, monkeypatch)
    first = 'https://example.com/first'
    second = 'https://example.com/second'
    calls = []

    def fetch(url):
        calls.append(url)
        return {**meta, 'url': url, 'title': f'Article {len(calls)}'}

    monkeypatch.setattr('article.fetch_article', fetch)
    monkeypatch.setattr(appmod, 'TELEGRAM_WEBHOOK_SECRET', 'telegram-secret')
    monkeypatch.setattr(appmod, 'TELEGRAM_CHAT_ID', '12345')
    monkeypatch.setattr(appmod, 'TELEGRAM_BOT_TOKEN', '')
    headers = {'X-Telegram-Bot-Api-Secret-Token': 'telegram-secret'}

    with app.test_client() as client:
        response = client.post('/api/telegram/webhook', headers=headers, json={
            'message': {
                'chat': {'id': 12345},
                'text': f'{first}\n{second}.\nDuplicate: {first}',
            },
        })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'enqueued'
    assert payload['enqueued_count'] == 2
    assert payload['failed_count'] == 0
    assert calls == [first, second]
    assert len(payload['jobs']) == 2
    for item in payload['jobs']:
        job = get_job(item['job_id'])
        assert job['source_url'] == item['url']
        assert job['render_target'] == 'local'
        assert job['notify_telegram'] == 1


def test_telegram_article_failure_is_acknowledged_without_retry(tmp_path, monkeypatch):
    _article_capture_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr('article.fetch_article',
                        lambda _url: (_ for _ in ()).throw(RuntimeError('paywall')))
    monkeypatch.setattr(appmod, 'TELEGRAM_WEBHOOK_SECRET', 'telegram-secret')
    monkeypatch.setattr(appmod, 'TELEGRAM_CHAT_ID', '12345')
    monkeypatch.setattr(appmod, 'TELEGRAM_BOT_TOKEN', '')

    with app.test_client() as client:
        response = client.post('/api/telegram/webhook', headers={
            'X-Telegram-Bot-Api-Secret-Token': 'telegram-secret'}, json={
                'message': {'chat': {'id': 12345},
                            'text': 'https://example.com/paywall'},
            })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'processed_with_errors'
    assert payload['enqueued_count'] == 0
    assert payload['failed_count'] == 1


def test_generated_epub_uses_real_media_duration(tmp_path, monkeypatch):
    from ebooklib import epub
    import epub_generator as generator

    source = tmp_path / 'source.epub'
    book = epub.EpubBook()
    book.set_identifier('timing-test')
    book.set_title('Timing Test')
    book.set_language('en')
    front = epub.EpubHtml(title='Front', file_name='front.xhtml')
    front.content = '<html><body><p>short front matter</p></body></html>'
    body = epub.EpubHtml(title='Body', file_name='body.xhtml')
    body.content = '<html><body><h1>Body</h1><p>' + ('word ' * 150) + '</p></body></html>'
    book.add_item(front); book.add_item(body)
    book.add_item(epub.EpubNav()); book.add_item(epub.EpubNcx())
    book.spine = ['nav', front, body]
    epub.write_epub(source, book)

    audio_dir = tmp_path / 'audio'; audio_dir.mkdir()
    (audio_dir / '001.mp3').write_bytes(b'not-decoded-in-this-test')
    chunks = tmp_path / 'chunks.jsonl'; chunks.write_text('')
    monkeypatch.setattr(generator, '_audio_duration', lambda _path: 12.345)

    output = tmp_path / 'readalong.epub'
    generator.package_epub3_with_audio(source, output, audio_dir, chunks)
    with ZipFile(output) as archive:
        smil_name = next(name for name in archive.namelist() if name.endswith('chapter_1.smil'))
        smil = archive.read(smil_name).decode()
        assert 'clipEnd="00:00:12.345"' in smil
        assert 'front.xhtml#s' not in smil
