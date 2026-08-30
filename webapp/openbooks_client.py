import asyncio
import json
import logging
import os
import subprocess
import websockets

logger = logging.getLogger(__name__)

OPENBOOKS_WS_URL = os.getenv("OPENBOOKS_WS_URL", "ws://192.168.1.248:6081/ws")
OPENBOOKS_SSH_HOST = os.getenv("OPENBOOKS_SSH_HOST", "192.168.1.248")
OPENBOOKS_SSH_USER = os.getenv("OPENBOOKS_SSH_USER", "dave")
OPENBOOKS_BOOKS_DIR = os.getenv("OPENBOOKS_BOOKS_DIR", "/home/dave/Downloads/openbooks/books")

async def search_openbooks_async(query: str, timeout: float = 12.0):
    if not query or not query.strip():
        return []
    
    clean_query = query.strip()
    logger.info(f"Searching OpenBooks for '{clean_query}' via {OPENBOOKS_WS_URL}")
    
    try:
        async with websockets.connect(OPENBOOKS_WS_URL, open_timeout=5.0) as ws:
            # Handshake
            await ws.send(json.dumps({"type": 1, "payload": {}}))
            # Search query
            await ws.send(json.dumps({"type": 2, "payload": {"query": clean_query}}))
            
            start_time = asyncio.get_event_loop().time()
            while True:
                remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    data = json.loads(msg)
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
                        return results
                except asyncio.TimeoutError:
                    break
    except Exception as e:
        logger.error(f"OpenBooks WebSocket search failed: {e}")
        
    return []

async def grab_openbooks_async(command: str, timeout: float = 30.0):
    if not command:
        raise ValueError("No download command specified")
        
    logger.info(f"Sending grab request to OpenBooks: {command}")
    filename = None
    
    try:
        async with websockets.connect(OPENBOOKS_WS_URL, open_timeout=5.0) as ws:
            # Handshake
            await ws.send(json.dumps({"type": 1, "payload": {}}))
            # Send download command
            await ws.send(json.dumps({"type": 3, "payload": {"book": command}}))
            
            start_time = asyncio.get_event_loop().time()
            while True:
                remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                if remaining <= 0:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    data = json.loads(msg)
                    if data.get("type") == 3:  # Book file received
                        filename = data.get("detail")
                        logger.info(f"OpenBooks downloaded: {filename}")
                        break
                except asyncio.TimeoutError:
                    break
    except Exception as e:
        logger.error(f"OpenBooks WebSocket grab failed: {e}")
        raise RuntimeError(f"Could not download book: {e}")
        
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
