import aiohttp
import asyncio
import json
import logging
import os
import re
import shlex
import time
import subprocess
import threading

logger = logging.getLogger(__name__)

OPENBOOKS_WS_URL = os.getenv("OPENBOOKS_WS_URL", "ws://192.168.1.113:6082/ws")
OPENBOOKS_SSH_HOST = os.getenv("OPENBOOKS_SSH_HOST", "docker-vm")
OPENBOOKS_SSH_USER = os.getenv("OPENBOOKS_SSH_USER", "dave")
OPENBOOKS_BOOKS_DIR = os.getenv("OPENBOOKS_BOOKS_DIR", "/home/dave/docker-apps/calibre-web-automated/book-ingest")

_ws_lock = threading.Lock()

async def _do_search(clean_query: str, timeout: float = 90.0):
    for attempt in range(1, 3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(OPENBOOKS_WS_URL, timeout=6.0) as ws:
                    # 1. Handshake
                    await ws.send_str(json.dumps({"type": 1, "payload": {}}))
                    # 2. Search query
                    await ws.send_str(json.dumps({"type": 2, "payload": {"query": clean_query}}))

                    start_time = asyncio.get_event_loop().time()
                    while True:
                        remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                        if remaining <= 0:
                            logger.warning(f"OpenBooks search timed out after {timeout}s for '{clean_query}'")
                            break
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("type") == 2:  # Search Results
                                    raw_books = data.get("books", [])
                                    results = []
                                    seen = set()
                                    for b in raw_books:
                                        author = (b.get("author") or "").strip()
                                        title = (b.get("title") or "").strip()
                                        fmt = (b.get("format") or "epub").upper()
                                        size = b.get("size") or ""
                                        full_cmd = b.get("full") or ""
                                        server = b.get("server") or ""

                                        if " - " in title and not author:
                                            parts = title.split(" - ", 1)
                                            author, title = parts[0].strip(), parts[1].strip()

                                        key = f"{author.lower()}::{title.lower()}::{fmt.lower()}"
                                        if key in seen or not full_cmd:
                                            continue
                                        seen.add(key)

                                        results.append({
                                            "author": author or "Unknown Author",
                                            "title": title or clean_query,
                                            "format": fmt,
                                            "size": size,
                                            "command": full_cmd,
                                            "server": server
                                        })
                                    logger.info(f"OpenBooks returned {len(results)} clean results for '{clean_query}'")
                                    return results
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                        except asyncio.TimeoutError:
                            break
        except Exception as e:
            logger.warning(f"OpenBooks WebSocket attempt {attempt}/2 error: {e}")
            if attempt < 2:
                await asyncio.sleep(1.0)
    return []

async def search_openbooks_async(query: str, timeout: float = 90.0):
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    logger.info(f"Searching OpenBooks for '{clean_query}' via {OPENBOOKS_WS_URL}")

    with _ws_lock:
        return await _do_search(clean_query, timeout=timeout)

async def _do_grab(command: str, timeout: float = 180.0):
    filename = None
    for attempt in range(1, 3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(OPENBOOKS_WS_URL, timeout=8.0) as ws:
                    # Handshake
                    await ws.send_str(json.dumps({"type": 1, "payload": {}}))
                    # Send download command
                    await ws.send_str(json.dumps({"type": 3, "payload": {"book": command}}))

                    start_time = asyncio.get_event_loop().time()
                    while True:
                        remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                        if remaining <= 0:
                            break
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                if data.get("type") == 0 and data.get("appearance") == 3:
                                    # OpenBooks reported a failed transfer: stop waiting
                                    logger.warning(f"OpenBooks error: {data.get('title')}")
                                    break
                                if data.get("type") == 3:  # Book file received
                                    filename = data.get("detail")
                                    logger.info(f"OpenBooks downloaded: {filename}")
                                    break
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                        except asyncio.TimeoutError:
                            break
            if filename:
                break
        except Exception as e:
            logger.warning(f"OpenBooks WebSocket grab attempt {attempt}/2 error: {e}")
            if attempt < 2:
                await asyncio.sleep(1.0)
    return filename

async def grab_openbooks_async(command: str, timeout: float = 180.0):
    if not command:
        raise ValueError("No download command specified")

    logger.info(f"Sending grab request to OpenBooks: {command}")

    with _ws_lock:
        filename = await _do_grab(command, timeout=timeout)

    if not filename:
        raise RuntimeError("Download timed out or book was not sent by IRC server.")

    return filename

OPENBOOKS_CALIBRE_LIBRARY = os.getenv(
    "OPENBOOKS_CALIBRE_LIBRARY", "/home/dave/docker-apps/calibre-web-automated/calibre-library")
_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no"]


def _library_search_terms(filename: str):
    """(author_last_name, first_long_title_word) from an OpenBooks filename.

    "Patrick Radden Keefe - Say Nothing- A True Story ... (retail) (epub).epub"
    -> ("Keefe", "Nothing"). Calibre-Web-Automated renames/truncates titles on ingest, so
    only these two stable tokens are matched against the library path.
    """
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", stem)
    author, sep, title = stem.partition(" - ")
    if not sep:
        author, title = "", stem
    author_tokens = re.findall(r"[A-Za-z0-9]+", author)
    title_tokens = re.findall(r"[A-Za-z0-9]+", title)
    long_words = [w for w in title_tokens if len(w) > 3] or title_tokens
    return (author_tokens[-1] if author_tokens else ""), (long_words[0] if long_words else "")


def _scp_from_docker_vm(remote_path: str, local_dest: str) -> bool:
    cmd = ["scp"] + _SSH_OPTS + [f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}:{remote_path}", local_dest]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return res.returncode == 0 and os.path.exists(local_dest) and os.path.getsize(local_dest) > 0


def _find_in_calibre_library(filename: str):
    """Newest .epub in the Calibre library whose path matches the book, else None."""
    author_last, title_word = _library_search_terms(filename)
    if not (author_last and title_word):
        return None
    ext = os.path.splitext(filename)[1].lower() or ".epub"
    # shlex.quote: the tokens come from a remote filename
    cmd = (f"find {shlex.quote(OPENBOOKS_CALIBRE_LIBRARY)} -type f -iname {shlex.quote('*' + ext)} "
           f"-ipath {shlex.quote('*' + author_last + '*')} -ipath {shlex.quote('*' + title_word + '*')} "
           "-printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-")
    res = subprocess.run(["ssh"] + _SSH_OPTS + [f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}", cmd],
                         capture_output=True, text=True, timeout=30)
    out = res.stdout.strip()
    return out if res.returncode == 0 and out else None


def _bg_sync_to_studio(filename: str, wait_s: float = 120.0, poll_s: float = 6.0):
    """Copy a grabbed book from docker-vm into the conversion app's uploads.

    OpenBooks saves into <ingest>/books/<file> and Calibre-Web-Automated moves it into its
    library within seconds, so the book is looked for in the drop folder first and then, by
    author/title, in the Calibre library. (The old code looked only for <ingest>/<file>,
    which never exists, so grabbed books never reached the app.)
    """
    local_upload_dir = os.getenv("UPLOAD_DIR", "/data/uploads")
    os.makedirs(local_upload_dir, exist_ok=True)
    local_dest = os.path.join(local_upload_dir, filename)
    if os.path.exists(local_dest):
        return True

    candidates = [f"{OPENBOOKS_BOOKS_DIR}/books/{filename}", f"{OPENBOOKS_BOOKS_DIR}/{filename}"]
    deadline = time.monotonic() + wait_s
    while True:
        try:
            for remote in candidates:
                if _scp_from_docker_vm(remote, local_dest):
                    logger.info(f"Synced {filename} to {local_dest} from the drop folder")
                    return True
            remote = _find_in_calibre_library(filename)
            if remote and _scp_from_docker_vm(remote, local_dest):
                logger.info(f"Synced {filename} to {local_dest} from the Calibre library ({remote})")
                return True
        except Exception as e:
            logger.warning(f"Background sync attempt for {filename} failed: {e}")
        if time.monotonic() >= deadline:
            break
        time.sleep(poll_s)
    logger.warning(f"Could not sync {filename} to uploads (it is safely in Calibre if ingest succeeded)")
    return False


def grab_and_import_book(command: str, title: str = "", author: str = ""):
    """
    Downloads book from OpenBooks directly into book-ingest (auto-indexed by Calibre-Web)
    and asynchronously syncs to local conversion uploads.
    """
    filename = asyncio.run(grab_openbooks_async(command))
    if not filename:
        raise RuntimeError("Failed to receive book from OpenBooks.")

    # Kick off background sync to conversion studio uploads without blocking the HTTP response
    sync_thread = threading.Thread(target=_bg_sync_to_studio, args=(filename,), daemon=True)
    sync_thread.start()

    return {
        "status": "success",
        "filename": filename,
        "title": title or filename,
        "author": author or "Unknown",
        "message": f"Successfully grabbed '{filename}' and imported into library."
    }
