import aiohttp
import asyncio
import json
import logging
import os
import subprocess
import threading

logger = logging.getLogger(__name__)

OPENBOOKS_WS_URL = os.getenv("OPENBOOKS_WS_URL", "ws://192.168.1.113:6082/ws")
OPENBOOKS_SSH_HOST = os.getenv("OPENBOOKS_SSH_HOST", "docker-vm")
OPENBOOKS_SSH_USER = os.getenv("OPENBOOKS_SSH_USER", "dave")
OPENBOOKS_BOOKS_DIR = os.getenv("OPENBOOKS_BOOKS_DIR", "/home/dave/docker-apps/calibre-web-automated/book-ingest")

_ws_lock = threading.Lock()

async def _do_search(clean_query: str, timeout: float = 20.0):
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
                            msg = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 15.0))
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

async def search_openbooks_async(query: str, timeout: float = 20.0):
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    logger.info(f"Searching OpenBooks for '{clean_query}' via {OPENBOOKS_WS_URL}")

    with _ws_lock:
        return await _do_search(clean_query, timeout=timeout)

async def _do_grab(command: str, timeout: float = 35.0):
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
                            msg = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 25.0))
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
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

async def grab_openbooks_async(command: str, timeout: float = 35.0):
    if not command:
        raise ValueError("No download command specified")

    logger.info(f"Sending grab request to OpenBooks: {command}")

    with _ws_lock:
        filename = await _do_grab(command, timeout=timeout)

    if not filename:
        raise RuntimeError("Download timed out or book was not sent by IRC server.")

    return filename

def _bg_sync_to_studio(filename: str):
    """Background helper to sync grabbed book from docker-vm to Audiobook Studio uploads."""
    local_upload_dir = os.getenv("UPLOAD_DIR", "/data/uploads")
    os.makedirs(local_upload_dir, exist_ok=True)
    local_dest = os.path.join(local_upload_dir, filename)

    if os.path.exists(local_dest):
        return

    remote_src = f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}:{OPENBOOKS_BOOKS_DIR}/{filename}"
    logger.info(f"Background syncing {filename} from {remote_src} to {local_dest}...")
    try:
        cmd = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=no", remote_src, local_dest]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            remote_calibre_dir = "/home/dave/docker-apps/calibre-web-automated/calibre-library"
            find_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=no", f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}", f"find '{remote_calibre_dir}' -name '{filename}'"]
            find_res = subprocess.run(find_cmd, capture_output=True, text=True, timeout=8)
            if find_res.returncode == 0 and find_res.stdout.strip():
                remote_file = find_res.stdout.strip().splitlines()[0]
                subprocess.run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=no", f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}:{remote_file}", local_dest], timeout=10)
    except Exception as e:
        logger.warning(f"Background SCP skipped or timed out (book safely ingested into Calibre-Web): {e}")

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
