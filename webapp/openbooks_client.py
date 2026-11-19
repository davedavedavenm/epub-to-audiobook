import logging
import os
from pathlib import Path
import re
import threading
import time

import requests

logger = logging.getLogger(__name__)

BOOK_FINDER_URL = os.getenv("BOOK_FINDER_URL", "http://192.168.1.113:8095").rstrip("/")
ALLOWED_EXTS = {".epub", ".azw3", ".mobi", ".pdf"}


def _safe_upload_dest(upload_dir, raw_filename: str) -> Path:
    root = Path(upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    base = Path(str(raw_filename or "").replace("\x00", "")).name
    base = re.sub(r"[^A-Za-z0-9._ \-()\[\]]+", "_", base).strip(" .")
    if not base or base in {".", ".."}:
        base = "book.epub"
    suffix = Path(base).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        stem = Path(base).stem or "book"
        base = f"{stem}.epub"
    dest = (root / base).resolve()
    if not dest.is_relative_to(root) or dest == root:
        raise ValueError(f"Unsafe upload filename: {raw_filename!r}")
    return dest


def search_books(query: str, timeout: float = 95.0):
    """Proxy Book Finder search over LAN HTTP to docker-vm's unified cwa-book-bot service."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    resp = requests.get(
        f"{BOOK_FINDER_URL}/api/bookfinder/search",
        params={"q": clean_query},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results") or []


def _bg_sync_to_uploads(
    book_id=None,
    filename=None,
    upload_dir=None,
    wait_s: float = 90.0,
    poll_s: float = 4.0,
) -> bool:
    """Pull a grabbed book from docker-vm:8095/api/bookfinder/file into local UPLOAD_DIR."""
    target_dir = upload_dir or os.getenv("UPLOAD_DIR", "/data/uploads")
    fallback_name = filename or (f"calibre_{book_id}.epub" if book_id is not None else "book.epub")
    dest = _safe_upload_dest(target_dir, fallback_name)
    if dest.exists() and dest.stat().st_size > 0:
        return True

    params = {"book_id": int(book_id)} if book_id is not None else {"filename": Path(str(filename)).name}
    deadline = time.monotonic() + max(0.0, float(wait_s))
    while True:
        try:
            resp = requests.get(
                f"{BOOK_FINDER_URL}/api/bookfinder/file",
                params=params,
                stream=True,
                timeout=60,
            )
            if resp.status_code == 200:
                tmp = dest.with_name(f".{dest.name}.tmp")
                with tmp.open("wb") as out:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            out.write(chunk)
                if tmp.stat().st_size > 0:
                    tmp.replace(dest)
                    logger.info("Synced grabbed book to %s", dest)
                    return True
                tmp.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Background fetch for %s failed: %s", fallback_name, exc)
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)
    logger.warning("Could not fetch %s from %s into %s", fallback_name, BOOK_FINDER_URL, target_dir)
    return False


def grab_and_import_book(command: str, title: str = "", author: str = "", timeout: float = 190.0):
    """Trigger grab on docker-vm Book Finder (into Calibre) and fetch a studio upload copy."""
    clean_cmd = (command or "").strip()
    if not clean_cmd:
        raise ValueError("No download command specified")

    resp = requests.post(
        f"{BOOK_FINDER_URL}/api/bookfinder/grab",
        json={"command": clean_cmd, "title": title, "author": author},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(data.get("error") or data.get("message") or "Book Finder grab failed")

    filename = data.get("filename") or ""
    calibre_id = data.get("calibre_id")
    if calibre_id is not None or filename:
        sync_thread = threading.Thread(
            target=_bg_sync_to_uploads,
            kwargs={"book_id": calibre_id, "filename": filename or f"{title or 'book'}.epub"},
            daemon=True,
        )
        sync_thread.start()

    return {
        "status": "success",
        "filename": filename or title,
        "title": data.get("title") or title or filename,
        "author": data.get("author") or author or "Unknown",
        "calibre_id": calibre_id,
        "ingested": bool(data.get("ingested")),
        "library_url": data.get("library_url"),
        "message": data.get("message") or f"Successfully grabbed '{filename or title}' into Calibre.",
    }
