import base64
import sys
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webapp'))

import app as appmod  # noqa: E402
from app import app, get_db, save_job  # noqa: E402
from qa_report import merge_qa_reports  # noqa: E402


def _basic(username='dave', password='correct-horse'):
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return {'Authorization': f'Basic {token}'}


def test_private_api_requires_environment_auth(monkeypatch):
    monkeypatch.setattr(appmod, 'APP_AUTH_USERNAME', 'dave')
    monkeypatch.setattr(appmod, 'APP_AUTH_PASSWORD', 'correct-horse')
    app.config.update(TESTING=True, AUTH_BYPASS_FOR_TESTS=False)
    with app.test_client() as client:
        denied = client.get('/api/jobs')
        assert denied.status_code == 401
        assert denied.headers['WWW-Authenticate'].startswith('Basic ')
        assert client.get('/api/jobs', headers=_basic()).status_code == 200
        assert client.get('/api/health').status_code in (200, 503)
    app.config['AUTH_BYPASS_FOR_TESTS'] = True


def test_cross_origin_write_is_refused(monkeypatch):
    monkeypatch.setattr(appmod, 'APP_AUTH_PASSWORD', 'correct-horse')
    app.config.update(TESTING=True, AUTH_BYPASS_FOR_TESTS=False)
    headers = {**_basic(), 'Origin': 'https://attacker.example'}
    with app.test_client() as client:
        response = client.post('/api/queue/pause', headers=headers)
        assert response.status_code == 403
    app.config['AUTH_BYPASS_FOR_TESTS'] = True


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
            assert enclosure in feed.get_data(as_text=True)
            streamed = client.get(enclosure)
            assert streamed.status_code == 200
            assert streamed.mimetype == 'audio/mpeg'
    finally:
        with get_db() as conn:
            conn.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
            conn.commit()


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
