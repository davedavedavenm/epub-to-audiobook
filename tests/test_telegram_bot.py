"""Tests for enhanced Telegram notifications, commands, and callbacks in webapp."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "webapp"))
import app as appmod  # noqa: E402


def test_tail_error_extractor_and_quiet_hours():
    tb = 'Traceback (most recent call last):\n  File "/app/worker.py", line 42, in run\nRuntimeError: Kokoro OOM <bad>'
    assert appmod._extract_tail_error(tb) == "RuntimeError: Kokoro OOM <bad>"
    assert appmod._is_london_quiet_hours(datetime(2026, 11, 22, 23, 30, tzinfo=ZoneInfo("Europe/London"))) is True
    assert appmod._is_london_quiet_hours(datetime(2026, 11, 22, 12, 0, tzinfo=ZoneInfo("Europe/London"))) is False


def test_send_telegram_notification_html_and_buttons(monkeypatch):
    posted = []
    monkeypatch.setattr(appmod, "TELEGRAM_BOT_TOKEN", "bot-tok")
    monkeypatch.setattr(appmod, "TELEGRAM_CHAT_ID", "7967413811")
    monkeypatch.setattr(appmod, "PUBLIC_BASE_URL", "https://audio.example.com")
    monkeypatch.setattr(appmod, "_is_london_quiet_hours", lambda: True)
    monkeypatch.setattr(appmod.requests, "post", lambda url, json=None, timeout=10: posted.append((url, json)))

    appmod.send_telegram_notification(
        {"id": "j1", "book_name": "Dune <1>", "voice_name": "uk", "error": "Trace\nValueError: bad <tag>"},
        False,
    )
    assert len(posted) == 1
    body = posted[0][1]
    assert body["parse_mode"] == "HTML"
    assert body["disable_web_page_preview"] is True
    assert body["disable_notification"] is True
    assert "Dune &lt;1&gt;" in body["text"]
    assert "ValueError: bad &lt;tag&gt;" in body["text"]
    assert body["reply_markup"]["inline_keyboard"][0][0]["url"] == "https://audio.example.com/#job-j1"


def test_telegram_commands_and_callbacks(monkeypatch):
    sent = []
    monkeypatch.setattr(appmod._TG_BOOK_WORKER, 'submit', lambda fn, *args: fn(*args))

    class FakeResp:
        def __init__(self, payload, ok=True, status=200):
            self._p = payload
            self.ok = ok
            self.status_code = status
            self.headers = {"content-type": "application/json"}
            self.text = "ok"

        def json(self):
            return self._p

        def raise_for_status(self):
            assert self.ok

    monkeypatch.setattr(appmod, "TELEGRAM_BOT_TOKEN", "bot-tok")
    monkeypatch.setattr(appmod, "TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(appmod, "TELEGRAM_WEBHOOK_SECRET", "sec")
    monkeypatch.setattr(appmod, "_tg_api", lambda method, payload, timeout=10: sent.append((method, payload)))
    monkeypatch.setattr(appmod.requests, "get", lambda url, **kw: FakeResp({"results": [{"title": "Project Hail Mary", "author": "Andy Weir", "format": "epub", "command": "!dl1"}]}))
    monkeypatch.setattr(appmod.requests, "post", lambda url, **kw: FakeResp({"status": "success"}))

    client = appmod.app.test_client()
    hdrs = {"X-Telegram-Bot-Api-Secret-Token": "sec"}

    r_find = client.post("/api/telegram/webhook", headers=hdrs, json={
        "message": {"chat": {"id": 12345}, "text": "/find Hail Mary"},
    })
    assert r_find.status_code == 200 and r_find.json["command"] == "/find"
    kb = sent[-1][1]["reply_markup"]["inline_keyboard"][0]
    grab_cb = kb[0]["callback_data"]
    assert grab_cb.startswith("bk:grab:")

    # Stranger callback rejected without calling bookfinder
    r_bad = client.post("/api/telegram/webhook", headers=hdrs, json={
        "callback_query": {"id": "c0", "from": {"id": 999}, "message": {"chat": {"id": 999}}, "data": grab_cb},
    })
    assert r_bad.status_code == 200 and r_bad.json["status"] == "ignored_chat"

    # Owner callback grabs and edits message
    r_ok = client.post("/api/telegram/webhook", headers=hdrs, json={
        "callback_query": {"id": "c1", "from": {"id": 12345}, "message": {"chat": {"id": 12345}, "message_id": 88}, "data": grab_cb},
    })
    assert r_ok.status_code == 200 and r_ok.json["action"] == "grab"
    assert any(m == "editMessageText" and "Grabbed:" in p["text"] for m, p in sent)

    r_help = client.post("/api/telegram/webhook", headers=hdrs, json={
        "message": {"chat": {"id": 12345}, "text": "/help"},
    })
    assert r_help.status_code == 200 and r_help.json["command"] == "/help"


def test_wanted_searches_series_gap_before_requesting_specific_title(monkeypatch):
    tg = Mock()
    post = Mock()
    get = Mock(side_effect=[
        Mock(ok=True, json=lambda: [{'series': 'A & Z', 'missing_volume': 2,
                                     'search_query': 'A & Z 2 Writer', 'author': 'Writer'}]),
        Mock(ok=True, json=lambda: {'results': [{'title': 'The Second Book', 'author': 'Writer'}]}),
    ])
    monkeypatch.setattr(appmod, '_tg_api', tg)
    monkeypatch.setattr(appmod.requests, 'get', get)
    monkeypatch.setattr(appmod.requests, 'post', post)
    monkeypatch.setattr(appmod, '_TG_FIND_CACHE', {})
    submit = Mock()
    monkeypatch.setattr(appmod._TG_BOOK_WORKER, 'submit', submit)

    appmod._handle_book_command(123, '/wanted')
    message = tg.call_args.args[1]
    assert 'A &amp; Z, volume 2' in message['text']
    find_button = message['reply_markup']['inline_keyboard'][0][0]['callback_data']
    callback = {'id': '1', 'message': {'chat': {'id': 123}, 'message_id': 42}, 'data': find_button}
    appmod._handle_book_callback(callback, '123')
    # The webhook returns while the upstream search is still pending.
    assert get.call_count == 1
    work, *args = submit.call_args.args
    work(*args)
    assert get.call_args.kwargs['params'] == {'q': 'A & Z 2 Writer'}
    assert get.call_args.kwargs['timeout'] > 90
    post.assert_not_called()
    audio_button = tg.call_args.args[1]['reply_markup']['inline_keyboard'][0][0]['callback_data']
    appmod._handle_book_callback(dict(callback, data=audio_button), '123')
    assert post.call_args.kwargs['json'] == {'title': 'The Second Book', 'author': 'Writer'}

    appmod._TG_FIND_CACHE.clear()
    post.reset_mock()
    get.reset_mock()
    for expired in (audio_button, find_button):
        response, status = appmod._handle_book_callback(dict(callback, data=expired), '123')
        assert (response['status'], status) == ('expired_token', 200)
        assert tg.call_args.args[0] == 'answerCallbackQuery'
    post.assert_not_called()
    get.assert_not_called()


@pytest.mark.parametrize(('author', 'code', 'error', 'expected'), [
    ('A. Writer', 409, 'Several matches for A < Z', 'Several matches for A &lt; Z'),
    ('Unknown Author', 404, 'Add the ebook first', 'Add the ebook first'),
    ('', 404, None, 'HTTP 404'),
])
def test_recent_book_audio_preserves_known_author_and_explains_failure(monkeypatch, author, code, error, expected):
    tg = Mock()
    get = Mock(side_effect=[
        Mock(ok=True, json=lambda: []),
        Mock(ok=True, json=lambda: {'books': [{'title': 'The Book', 'author': author}]}),
    ])
    result = Mock(ok=False, status_code=code)
    if error:
        result.json.return_value = {'error': error}
    else:
        result.json.side_effect = appmod.requests.exceptions.JSONDecodeError('Not JSON', '<html>', 0)
    post = Mock(return_value=result)
    monkeypatch.setattr(appmod, '_tg_api', tg)
    monkeypatch.setattr(appmod.requests, 'get', get)
    monkeypatch.setattr(appmod.requests, 'post', post)
    monkeypatch.setattr(appmod, '_TG_FIND_CACHE', {})

    appmod._handle_book_command(123, '/wanted')
    message = tg.call_args.args[1]
    assert 'Recent Library Books' in message['text']
    button = message['reply_markup']['inline_keyboard'][0][0]['callback_data']
    callback = {'id': '1', 'message': {'chat': {'id': 123}, 'message_id': 42}, 'data': button}
    appmod._handle_book_callback(callback, '123')

    payload = {'title': 'The Book'}
    if author == 'A. Writer':
        payload['author'] = author
    assert post.call_args.kwargs['json'] == payload
    assert tg.call_args.args[0] == 'editMessageText'
    assert tg.call_args.args[1]['text'].endswith(expected)
