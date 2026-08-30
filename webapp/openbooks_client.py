import aiohttp
import asyncio
import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

OPENBOOKS_WS_URL = os.getenv("OPENBOOKS_WS_URL", "ws://192.168.1.113:6082/ws")
OPENBOOKS_SSH_HOST = os.getenv("OPENBOOKS_SSH_HOST", "docker-vm")
OPENBOOKS_SSH_USER = os.getenv("OPENBOOKS_SSH_USER", "dave")
OPENBOOKS_BOOKS_DIR = os.getenv("OPENBOOKS_BOOKS_DIR", "/home/dave/docker-apps/calibre-web-automated/book-ingest")

async def search_openbooks_async(query: str, timeout: float = 30.0):
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    logger.info(f"Searching OpenBooks for '{clean_query}' via {OPENBOOKS_WS_URL}")

    # Retry up to 3 times in case another client temporarily held the WebSocket
    for attempt in range(1, 4):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(OPENBOOKS_WS_URL, timeout=8.0) as ws:
                    # Handshake
                    await ws.send_str(json.dumps({"type": 1, "payload": {}}))
                    # Search query
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

                                        # Clean author / title if inverted
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
            logger.warning(f"OpenBooks WebSocket attempt {attempt}/3 error: {e}")
            if attempt < 3:
                await asyncio.sleep(1.5)

    return []

async def grab_openbooks_async(command: str, timeout: float = 45.0):
    if not command:
        raise ValueError("No download command specified")

    logger.info(f"Sending grab request to OpenBooks: {command}")
    filename = None

    for attempt in range(1, 4):
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
            logger.warning(f"OpenBooks WebSocket grab attempt {attempt}/3 error: {e}")
            if attempt < 3:
                await asyncio.sleep(2.0)

    if not filename:
        raise RuntimeError("Download timed out or book was not sent by IRC server.")

    return filename

def grab_and_import_book(command: str, title: str = "", author: str = ""):
    """
    Downloads book from OpenBooks, transfers it to local uploads, and triggers library ingest.
    """
    # 1. Trigger download via WebSocket
    filename = asyncio.run(grab_openbooks_async(command))
    if not filename:
        raise RuntimeError("Failed to retrieve downloaded book filename from OpenBooks.")

    # 2. SCP file from OpenBooks host into local /data/uploads/
    remote_path = f"{OPENBOOKS_BOOKS_DIR}/{filename}"
    local_dest = f"/data/uploads/{filename}"
    scp_cmd = [
        "scp",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no",
        f"{OPENBOOKS_SSH_USER}@{OPENBOOKS_SSH_HOST}:{remote_path}",
        local_dest
    ]
    logger.info(f"Transferring {remote_path} to {local_dest}...")
    res = subprocess.run(scp_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"SCP failed: {res.stderr}")
        raise RuntimeError(f"Could not transfer downloaded book to local library: {res.stderr}")

    # 3. Trigger Calibre-Web sync if docker-vm is reachable
    try:
        cwa_cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
            "dave@docker-vm",
            f"docker exec calibre-web-automated calibredb add --with-library /calibre-library --automerge overwrite '{local_dest}' 2>&1 || true"
        ]
        subprocess.run(cwa_cmd, capture_output=True, text=True, timeout=10)
    except Exception as ex:
        logger.warning(f"Calibre-Web immediate add notification failed (will sync on cron): {ex}")

    return {
        "status": "success",
        "title": title or filename,
        "author": author,
        "filename": filename,
        "path": local_dest
    }
