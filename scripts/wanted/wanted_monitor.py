#!/usr/bin/env python3
"""Wanted books monitor.

Legal-first behavior:
- Reads LazyLibrarian wanted list (local LL sqlite DB).
- Checks whether each wanted title already exists in the OpenBooks library folder.
- Optionally triggers a provider-specific request hook (disabled by default).
- Sends notifications when a wanted book is detected in the library folder.

This script is intentionally provider-agnostic. It does not implement acquisition of
copyrighted works from unauthorized sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests


DEFAULT_LL_DB = '/home/dave/docker-apps/lazylibrarian/config/lazylibrarian.db'
DEFAULT_STATE_DB = '/home/dave/scripts/wanted_state.db'
DEFAULT_LIBRARY_DIR = '/mnt/openbooks'
DEFAULT_LOG = '/home/dave/scripts/wanted_monitor.log'
DEFAULT_REQUEST_ALLOWLIST = '/home/dave/scripts/wanted_allowlist.txt'


def now_ts() -> int:
    return int(time.time())


def log(msg: str, log_path: Path | None):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    if log_path:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open('a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass


def normalize(s: str) -> str:
    s = (s or '').lower().strip()
    s = s.replace('&', ' and ')
    s = re.sub(r"[^a-z0-9\s]+", ' ', s)
    s = re.sub(r"\s+", ' ', s).strip()
    return s


def token_set(s: str) -> set[str]:
    return set(normalize(s).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def containment(needles: set[str], haystack: set[str]) -> float:
    """How much of `needles` is contained in `haystack` (0..1)."""
    if not needles:
        return 0.0
    return len(needles & haystack) / len(needles)


@dataclass(frozen=True)
class Wanted:
    author: str
    title: str

    @property
    def key(self) -> str:
        h = hashlib.sha1(f"{normalize(self.author)}|{normalize(self.title)}".encode('utf-8')).hexdigest()
        return h


class StateDB:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS wanted_state (
                key TEXT PRIMARY KEY,
                author TEXT,
                title TEXT,
                found INTEGER DEFAULT 0,
                found_path TEXT,
                last_checked_ts INTEGER,
                next_check_ts INTEGER,
                attempt_count INTEGER DEFAULT 0,
                last_request_ts INTEGER,
                created_ts INTEGER
            )
        ''')
        # Request queue for OpenBooks (monitor enqueues; separate worker dequeues).
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS openbooks_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT,
                author TEXT,
                title TEXT,
                query TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',  -- queued, sent, failed
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_ts INTEGER,
                updated_ts INTEGER
            )
        ''')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_openbooks_queue_status ON openbooks_queue(status)')
        self.conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_openbooks_queue_key_status ON openbooks_queue(key, status)')
        self.conn.commit()

    def upsert(self, w: Wanted):
        self.conn.execute('''
            INSERT INTO wanted_state (key, author, title, created_ts)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET author=excluded.author, title=excluded.title
        ''', (w.key, w.author, w.title, now_ts()))
        self.conn.commit()

    def mark_checked(self, key: str, next_check_ts: int, increment_attempt: bool):
        if increment_attempt:
            self.conn.execute('''
                UPDATE wanted_state
                SET last_checked_ts=?, next_check_ts=?, attempt_count=attempt_count+1
                WHERE key=?
            ''', (now_ts(), next_check_ts, key))
        else:
            self.conn.execute('''
                UPDATE wanted_state
                SET last_checked_ts=?, next_check_ts=?
                WHERE key=?
            ''', (now_ts(), next_check_ts, key))
        self.conn.commit()

    def mark_found(self, key: str, path: str):
        self.conn.execute('''
            UPDATE wanted_state
            SET found=1, found_path=?, next_check_ts=NULL
            WHERE key=?
        ''', (path, key))
        self.conn.commit()

    def mark_requested(self, key: str):
        self.conn.execute('''
            UPDATE wanted_state
            SET last_request_ts=?
            WHERE key=?
        ''', (now_ts(), key))
        self.conn.commit()

    def enqueue_openbooks(self, w: Wanted, query: str) -> bool:
        """Enqueue an OpenBooks request. Returns True if enqueued or already queued."""
        t = now_ts()
        try:
            self.conn.execute('''
                INSERT INTO openbooks_queue (key, author, title, query, status, created_ts, updated_ts)
                VALUES (?, ?, ?, ?, 'queued', ?, ?)
            ''', (w.key, w.author, w.title, query, t, t))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return True

    def pick_openbooks_queue(self, limit: int) -> list[sqlite3.Row]:
        rows = self.conn.execute('''
            SELECT * FROM openbooks_queue
            WHERE status='queued'
            ORDER BY created_ts ASC, id ASC
            LIMIT ?
        ''', (limit,)).fetchall()
        return rows

    def mark_openbooks_sent(self, row_id: int):
        self.conn.execute('''
            UPDATE openbooks_queue
            SET status='sent', updated_ts=?, attempt_count=attempt_count+1, last_error=NULL
            WHERE id=?
        ''', (now_ts(), row_id))
        self.conn.commit()

    def mark_openbooks_failed(self, row_id: int, err: str):
        self.conn.execute('''
            UPDATE openbooks_queue
            SET status='failed', updated_ts=?, attempt_count=attempt_count+1, last_error=?
            WHERE id=?
        ''', (now_ts(), (err or '')[:500], row_id))
        self.conn.commit()

    def pick_due(self, limit: int) -> list[sqlite3.Row]:
        t = now_ts()
        rows = self.conn.execute('''
            SELECT * FROM wanted_state
            WHERE found=0 AND (next_check_ts IS NULL OR next_check_ts <= ?)
            ORDER BY
                COALESCE(next_check_ts, 0) ASC,
                CASE WHEN last_checked_ts IS NULL THEN 0 ELSE 1 END ASC,
                COALESCE(last_checked_ts, 0) ASC,
                created_ts DESC
            LIMIT ?
        ''', (t, limit)).fetchall()
        return rows

    def pick_any_unfound(self, limit: int) -> list[sqlite3.Row]:
        """Pick unfound items ignoring schedule (for testing/manual runs)."""
        rows = self.conn.execute('''
            SELECT * FROM wanted_state
            WHERE found=0
            ORDER BY
                CASE WHEN last_checked_ts IS NULL THEN 0 ELSE 1 END ASC,
                COALESCE(last_checked_ts, 0) ASC,
                created_ts DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        return rows

    def close(self):
        self.conn.close()


def read_ll_wanted(ll_db: Path) -> list[Wanted]:
    # LazyLibrarian DB can be busy/locked; copy to /tmp before reading.
    tmp = Path(f"/tmp/ll_wanted_{os.getpid()}.db")
    try:
        tmp.write_bytes(ll_db.read_bytes())
    except Exception:
        # Fallback to direct read if copy fails.
        tmp = ll_db

    conn = sqlite3.connect(str(tmp))
    cur = conn.cursor()
    cur.execute('''
        SELECT authors.AuthorName, books.BookName
        FROM books
        JOIN authors ON books.AuthorID = authors.AuthorID
        WHERE books.Status = 'Wanted'
    ''')
    rows = cur.fetchall()
    conn.close()
    if tmp != ll_db:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    return [Wanted(author=a or '', title=t or '') for (a, t) in rows]


def iter_library_files(library_dir: Path) -> Iterable[Path]:
    if not library_dir.exists():
        return []
    exts = {'.epub', '.pdf', '.mobi', '.azw3', '.fb2'}
    for p in library_dir.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def find_match(w: Wanted, library_dir: Path, min_score: float) -> tuple[float, Path] | None:
    wt = token_set(w.title)
    wa = token_set(w.author)
    best: tuple[float, Path] | None = None

    for f in iter_library_files(library_dir):
        name = f.stem
        ft = token_set(name)
        title_c = containment(wt, ft)
        author_c = containment(wa, ft)
        # Avoid single-token false positives by requiring some author overlap when title is tiny.
        if len(wt) < 2 and author_c == 0:
            continue
        score = 0.8 * title_c + 0.2 * author_c
        if best is None or score > best[0]:
            best = (score, f)

    if best and best[0] >= min_score:
        return best
    return None


def find_match_via_api(w: Wanted, library_api: str, min_score: float) -> tuple[float, str] | None:
    """Match against the webapp library API (preferred when mounts differ)."""
    try:
        data = requests.get(library_api, timeout=20).json()
    except Exception:
        return None
    if not isinstance(data, list):
        return None

    wt = token_set(w.title)
    wa = token_set(w.author)
    best: tuple[float, str] | None = None
    for b in data:
        title = (b or {}).get('title') or ''
        if not title:
            continue
        ft = token_set(title)
        title_c = containment(wt, ft)
        author_c = containment(wa, ft)
        if len(wt) < 2 and author_c == 0:
            continue
        score = 0.8 * title_c + 0.2 * author_c
        if best is None or score > best[0]:
            best = (score, title)

    if best and best[0] >= min_score:
        return best
    return None


def telegram_notify(token: str, chat_id: str, text: str, log_path: Path | None):
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={'chat_id': chat_id, 'text': text}, timeout=10)
        ok = resp.status_code == 200
        if not ok:
            log(f"Telegram notify failed: {resp.status_code} {resp.text[:200]}", log_path)
        else:
            log("Telegram notify ok", log_path)
        return ok
    except Exception as e:
        log(f"Telegram notify exception: {e}", log_path)
        return False


def whatsapp_notify(evo_url: str, evo_key: str, to_number: str, text: str, log_path: Path | None) -> bool:
    """Send a WhatsApp message via Evolution API (if configured)."""
    if not evo_url or not evo_key or not to_number:
        return False
    try:
        url = evo_url.rstrip('/') + '/message/sendText'
        # Evolution instances vary slightly; keep payload minimal.
        payload = {
            'number': to_number,
            'text': text,
        }
        headers = {
            'apikey': evo_key,
            'Content-Type': 'application/json',
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        ok = 200 <= resp.status_code < 300
        if not ok:
            log(f"WhatsApp notify failed: {resp.status_code} {resp.text[:200]}", log_path)
        return ok
    except Exception as e:
        log(f"WhatsApp notify exception: {e}", log_path)
        return False


def backoff_seconds(attempt: int, base: int, max_s: int) -> int:
    # 1 -> base, 2 -> 2*base, 3 -> 4*base ... capped
    d = base * (2 ** max(0, attempt - 1))
    return int(min(d, max_s))


def openbooks_send_via_bridge(bridge_path: str, query: str, log_path: Path | None, timeout_s: int) -> bool:
    """Send an OpenBooks request via a local bridge script (worker path).

    The wanted monitor should only enqueue requests; the worker sends them so the
    monitor never blocks on slow or down OpenBooks infrastructure.
    """
    if not bridge_path:
        return False
    p = Path(bridge_path)
    if not p.exists():
        log(f"OpenBooks bridge not found: {bridge_path}", log_path)
        return False
    try:
        r = subprocess.run(
            [sys.executable, str(p), query],
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_s)),
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or '').strip().replace('\n', ' ')[:200]
            log(f"OpenBooks bridge failed (rc={r.returncode}): {err}", log_path)
            return False
        return True
    except subprocess.TimeoutExpired:
        log(f"OpenBooks bridge timeout after {timeout_s}s", log_path)
        return False
    except Exception as e:
        log(f"OpenBooks bridge exception: {e}", log_path)
        return False


def load_allowlist_patterns(path: Path, log_path: Path | None) -> list[re.Pattern] | None:
    """Load allowlist patterns for OpenBooks requests.

    File format (one per line):
    - Blank lines and lines starting with '#' are ignored
    - 're:<regex>' for advanced patterns
    - Otherwise treated as a token rule: all tokens must appear in "<title> <author>"
      Example: "frankenstein|shelley"
    """
    if not path:
        return None
    if not path.exists():
        log(f"Allowlist file not found (requests disabled): {path}", log_path)
        return None

    pats: list[re.Pattern] = []
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('re:'):
            rx = line[3:].strip()
            if not rx:
                continue
            try:
                pats.append(re.compile(rx, flags=re.IGNORECASE))
            except re.error:
                log(f"Invalid allowlist regex (skipped): {line}", log_path)
            continue

        # Token rule: split by common separators and require all tokens to match.
        tokens = [t.strip() for t in re.split(r"[|,;/]+", line) if t.strip()]
        if not tokens:
            continue
        lookaheads = ''.join(f"(?=.*{re.escape(normalize(t))})" for t in tokens)
        pats.append(re.compile(lookaheads + r".*", flags=re.IGNORECASE))

    if not pats:
        log(f"Allowlist loaded but empty (requests disabled): {path}", log_path)
        return None
    return pats


def is_allowlisted(w: Wanted, pats: list[re.Pattern] | None) -> bool:
    if not pats:
        return False
    hay = normalize(f"{w.title} {w.author}")
    for p in pats:
        try:
            if p.search(hay):
                return True
        except Exception:
            continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ll-db', default=DEFAULT_LL_DB)
    ap.add_argument('--state-db', default=DEFAULT_STATE_DB)
    ap.add_argument('--library-dir', default=DEFAULT_LIBRARY_DIR)
    ap.add_argument('--log', default=DEFAULT_LOG)
    ap.add_argument('--limit', type=int, default=5)
    ap.add_argument('--min-score', type=float, default=0.72)
    ap.add_argument('--backoff-base-s', type=int, default=6 * 60 * 60)  # 6 hours
    ap.add_argument('--backoff-max-s', type=int, default=7 * 24 * 60 * 60)  # 7 days
    ap.add_argument('--notify-telegram', action='store_true')
    ap.add_argument('--notify-whatsapp', action='store_true')
    ap.add_argument('--whatsapp-number', default='')
    ap.add_argument('--notification-mode', choices=['summary', 'per-title'], default='summary')
    ap.add_argument('--max-notifications', type=int, default=1, help='Hard cap on messages sent per run (all channels).')
    ap.add_argument('--library-api', default='')  # e.g. http://192.168.1.88:8881/api/library
    ap.add_argument('--force', action='store_true', help='Ignore scheduling and check unfound items now (testing/manual)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--request-openbooks', action='store_true', help='Trigger OpenBooks requests for unfound items (rate-limited).')
    ap.add_argument('--openbooks-bridge', default='/home/dave/scripts/openbooks_bridge.py')
    ap.add_argument('--request-policy', choices=['all', 'allowlist'], default='all',
                    help="When requesting OpenBooks: 'all' requests for any unfound LL Wanted item; "
                         "'allowlist' requires a match in --request-allowlist-file.")
    ap.add_argument('--request-allowlist-file', default=DEFAULT_REQUEST_ALLOWLIST,
                    help='Allowlist file used only when --request-policy allowlist is selected.')
    ap.add_argument('--max-requests-per-run', type=int, default=1)
    ap.add_argument('--request-cooldown-s', type=int, default=12 * 60 * 60)  # 12h per title
    ap.add_argument('--post-request-check-s', type=int, default=60 * 60)  # 1h
    ap.add_argument('--request-sleep-s', type=int, default=2)
    ap.add_argument('--process-openbooks-queue', action='store_true',
                    help='Dequeue and send OpenBooks requests (does not check LL wanted).')
    ap.add_argument('--max-queue-sends', type=int, default=2)
    ap.add_argument('--bridge-timeout-s', type=int, default=60)
    args = ap.parse_args()

    ll_db = Path(args.ll_db)
    state_db = Path(args.state_db)
    library_dir = Path(args.library_dir)
    log_path = Path(args.log) if args.log else None
    library_api = (args.library_api or '').strip()

    if not ll_db.exists():
        log(f"LazyLibrarian DB not found: {ll_db}", log_path)
        return 2

    wanted = read_ll_wanted(ll_db)
    log(f"Wanted count (LL): {len(wanted)}", log_path)

    st = StateDB(state_db)
    try:
        if args.process_openbooks_queue:
            rows = st.pick_openbooks_queue(max(0, int(args.max_queue_sends or 0)))
            if not rows:
                log("OpenBooks queue: nothing to send", log_path)
                return 0
            for row in rows:
                q = (row['query'] or '').strip()
                if not q:
                    st.mark_openbooks_failed(int(row['id']), "empty query")
                    continue
                log(f"OpenBooks queue send: {q}", log_path)
                ok = openbooks_send_via_bridge(args.openbooks_bridge, q, log_path, int(args.bridge_timeout_s or 60))
                if ok:
                    st.mark_openbooks_sent(int(row['id']))
                    log("OpenBooks queue send ok", log_path)
                else:
                    st.mark_openbooks_failed(int(row['id']), "bridge failed/timeout")
            return 0

        for w in wanted:
            st.upsert(w)

        due = st.pick_any_unfound(args.limit) if args.force else st.pick_due(args.limit)
        if not due:
            log("No due wanted items", log_path)
            return 0

        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        evo_url = os.environ.get('EVOLUTION_API_URL', '')
        evo_key = os.environ.get('EVOLUTION_API_KEY', '')
        default_wa = os.environ.get('DEFAULT_WHATSAPP_NUMBER', '')
        wa_to = (args.whatsapp_number or default_wa).strip()

        telegram_enabled = bool(args.notify_telegram and token and chat_id)
        whatsapp_enabled = bool(args.notify_whatsapp and evo_url and evo_key and wa_to)
        if args.notify_telegram and not telegram_enabled:
            log("Telegram notify enabled but TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID missing; disabling for this run", log_path)
        if args.notify_whatsapp and not whatsapp_enabled:
            log("WhatsApp notify enabled but EVOLUTION_API_URL/EVOLUTION_API_KEY/DEFAULT_WHATSAPP_NUMBER missing; disabling for this run", log_path)

        found_now: list[tuple[Wanted, str, float]] = []
        notifications_sent = 0
        requests_sent = 0
        requested_now: list[Wanted] = []
        allow_pats = None
        if args.request_openbooks and args.request_policy == 'allowlist':
            allow_pats = load_allowlist_patterns(Path(args.request_allowlist_file), log_path)

        for i, row in enumerate(due, start=1):
            w = Wanted(author=row['author'] or '', title=row['title'] or '')
            log(f"[{i}/{len(due)}] Check: {w.title} | {w.author}", log_path)

            found = None
            if library_api:
                found = find_match_via_api(w, library_api, args.min_score)
                if found:
                    score, title = found
                    msg = f"FOUND: {w.title} ({w.author})\nLibrary: {title}\nScore: {score:.2f}"
                    found_path = title
                else:
                    msg = ''
            else:
                m = find_match(w, library_dir, args.min_score)
                if m:
                    score, path = m
                    msg = f"FOUND: {w.title} ({w.author})\nFile: {path.name}\nScore: {score:.2f}"
                    found_path = str(path)
                else:
                    msg = ''

            if msg:
                log(msg, log_path)
                if not args.dry_run:
                    st.mark_found(w.key, str(found_path))
                    found_now.append((w, str(found_path), float(score)))

                    if args.notification_mode == 'per-title' and notifications_sent < max(0, int(args.max_notifications or 0)):
                        if telegram_enabled:
                            telegram_notify(token, chat_id, msg, log_path)
                            notifications_sent += 1
                        if whatsapp_enabled and notifications_sent < max(0, int(args.max_notifications or 0)):
                            whatsapp_notify(evo_url, evo_key, wa_to, msg, log_path)
                            notifications_sent += 1
                continue

            # not found; schedule next check with backoff
            request_ok = False
            if args.request_openbooks:
                if args.request_policy == 'all':
                    request_ok = True
                elif args.request_policy == 'allowlist':
                    request_ok = bool(allow_pats and is_allowlisted(w, allow_pats))

            if (request_ok
                and requests_sent < max(0, int(args.max_requests_per_run or 0))
                and not args.dry_run):
                last_req = int(row['last_request_ts'] or 0)
                if (now_ts() - last_req) >= int(args.request_cooldown_s or 0):
                    query = f"{w.title} {w.author}".strip()
                    if st.enqueue_openbooks(w, query):
                        st.mark_requested(w.key)
                        requests_sent += 1
                        requested_now.append(w)
                        log(f"OpenBooks enqueued: {query}", log_path)
                        # After requesting, re-check sooner than the exponential backoff.
                        st.mark_checked(w.key, now_ts() + int(args.post_request_check_s or 0), increment_attempt=True)
                        if args.request_sleep_s:
                            time.sleep(float(args.request_sleep_s))
                        continue

            attempt = int(row['attempt_count'] or 0) + 1
            delay = backoff_seconds(attempt, args.backoff_base_s, args.backoff_max_s)
            st.mark_checked(w.key, now_ts() + delay, increment_attempt=True)

        # Send a single summary message (default) to avoid Telegram spam.
        if args.notification_mode == 'summary' and (found_now or requested_now) and not args.dry_run:
            if notifications_sent < max(0, int(args.max_notifications or 0)):
                lines = [f"Wanted monitor run: checked {len(due)} item(s)"]
                if requested_now:
                    lines.append("")
                    lines.append(f"Queued OpenBooks request(s): {len(requested_now)}")
                    for w in requested_now[:10]:
                        lines.append(f"- {w.title} ({w.author})")
                    if len(requested_now) > 10:
                        lines.append(f"...and {len(requested_now) - 10} more")
                if found_now:
                    lines.append("")
                    lines.append("Searched and found in library:")
                for w, _found_path, s in found_now[:10]:
                    lines.append(f"- {w.title} ({w.author}) [score {s:.2f}]")
                if len(found_now) > 10:
                    lines.append(f"...and {len(found_now) - 10} more")
                text = "\n".join(lines)
                if telegram_enabled:
                    telegram_notify(token, chat_id, text, log_path)
                    notifications_sent += 1
                if whatsapp_enabled and notifications_sent < max(0, int(args.max_notifications or 0)):
                    whatsapp_notify(evo_url, evo_key, wa_to, text, log_path)
                    notifications_sent += 1

        return 0
    finally:
        st.close()


if __name__ == '__main__':
    raise SystemExit(main())
