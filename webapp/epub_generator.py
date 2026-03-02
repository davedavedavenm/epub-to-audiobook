import os
import json
import re
import shutil
from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def _get_audio_files(audio_dir):
    """Get mapping of chapter_num -> mp3_path."""
    audio_dir = Path(audio_dir)
    files = {}
    for p in audio_dir.glob("*.mp3"):
        m = re.match(r"^(\d{4})_", p.name)
        if m:
            files[int(m.group(1))] = p
    return files

def _read_chunks(chunks_jsonl_path):
    """Read proxy chunks."""
    chunks = []
    p = Path(chunks_jsonl_path)
    if not p.exists(): return []
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip(): continue
            try:
                chunks.append(json.loads(line))
            except: continue
    return chunks

def package_epub3_with_audio(input_epub_path, output_epub_path, audio_dir, chunks_jsonl_path):
    """Main entry point for Stage 2 EPUB3 generation."""
    print(f"Packaging EPUB3: {input_epub_path} -> {output_epub_path}")
    try:
        shutil.copy(input_epub_path, output_epub_path)
        print("Successfully created EPUB3 skeleton")
    except Exception as e:
        print(f"Error generating EPUB3: {e}")
        raise e