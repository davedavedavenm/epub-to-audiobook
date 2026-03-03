import os
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import nltk
import traceback

# Ensure nltk data is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def _get_audio_files(audio_dir):
    """Get mapping of chapter_index (1-based) -> mp3_path."""
    audio_dir = Path(audio_dir)
    files = {}
    for p in sorted(audio_dir.glob("*.mp3")):
        m = re.match(r"^0*(\d+)", p.name)
        if m:
            files[int(m.group(1))] = p
    return files

def _read_chunks(chunks_jsonl_path):
    chunks = []
    p = Path(chunks_jsonl_path)
    if not p.exists(): return []
    with p.open('r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.strip(): continue
            try:
                chunks.append(json.loads(line))
            except: continue
    return chunks

def instrument_html(html_content):
    """Wrap each sentence in a span with a unique ID."""
    if isinstance(html_content, bytes):
        html_content = html_content.decode('utf-8')
    soup = BeautifulSoup(html_content, 'lxml')
    counter = 1
    for tag in soup.find_all(['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = tag.get_text().strip()
        if not text: continue
        sentences = nltk.sent_tokenize(text)
        tag.clear()
        for sent in sentences:
            span = soup.new_tag("span", id=f"s{counter}")
            span.string = sent + " "
            tag.append(span)
            counter += 1
    return str(soup), counter - 1

def generate_smil(html_file_name, audio_file_name, span_count, duration_per_span):
    """Generate a SMIL file mapping spans to audio timing."""
    smil = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">',
        '  <body>',
        f'    <seq id="id1" epub:textref="../{html_file_name}">',
    ]
    current_time = 0.0
    for i in range(1, span_count + 1):
        end_time = current_time + duration_per_span
        smil.append(f'      <par id="par{i}">')
        smil.append(f'        <text src="../{html_file_name}#s{i}"/>')
        smil.append(f'        <audio src="../Audio/{audio_file_name}" clipBegin="{current_time}s" clipEnd="{end_time}s"/>')
        smil.append('      </par>')
        current_time = end_time
    smil.extend(['    </seq>', '  </body>', '</smil>'])
    return "\n".join(smil)

def package_epub3_with_audio(input_epub_path, output_epub_path, audio_dir, chunks_jsonl_path):
    print(f"Packaging EPUB3: {input_epub_path} -> {output_epub_path}")
    try:
        book = epub.read_epub(input_epub_path)
        audio_files = _get_audio_files(audio_dir)
        book.version = 3.0
        
        audio_items = {}
        for ch_idx, mp3_path in audio_files.items():
            # uid is positional or via constructor, stored as .id
            item = epub.EpubItem(f"audio_{ch_idx}", f"Audio/{mp3_path.name}", "audio/mpeg", mp3_path.read_bytes())
            book.add_item(item)
            audio_items[ch_idx] = item

        spine_items = []
        for it in book.spine:
            iid = it[0] if isinstance(it, tuple) else it
            if iid == 'nav': continue
            item = book.get_item_with_id(iid)
            if item: spine_items.append(item)
            
        html_items = [item for item in spine_items if isinstance(item, epub.EpubHtml)]
        smil_items = []
        for idx, html_item in enumerate(html_items):
            ch_idx = idx + 1
            if ch_idx in audio_items:
                audio_item = audio_items[ch_idx]
                new_html, span_count = instrument_html(html_item.content)
                html_item.content = new_html.encode('utf-8')
                try:
                    from mutagen.mp3 import MP3
                    total_duration = MP3(audio_files[ch_idx]).info.length
                except:
                    total_duration = 60.0
                
                duration_per_span = total_duration / max(1, span_count)
                smil_content = generate_smil(html_item.file_name, audio_item.file_name, span_count, duration_per_span)
                smil_item = epub.EpubItem(f"smil_{ch_idx}", f"SMIL/chapter_{ch_idx}.smil", "application/smil+xml", smil_content.encode('utf-8'))
                book.add_item(smil_item)
                smil_items.append(smil_item)

        epub.write_epub(output_epub_path, book)
        _post_process_opf(output_epub_path, html_items, smil_items)
        print("Successfully created EPUB3 with Instrumented Read-Along")
    except Exception as e:
        print(f"Error generating EPUB3: {e}")
        traceback.print_exc()
        if not os.path.exists(output_epub_path):
            shutil.copy(input_epub_path, output_epub_path)

def _post_process_opf(epub_path, html_items, smil_items):
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        opf_path = None
        for root, _, files in os.walk(temp_dir):
            for f in files:
                if f.endswith('.opf'):
                    opf_path = os.path.join(root, f); break
            if opf_path: break
        if opf_path:
            with open(opf_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for idx, html in enumerate(html_items):
                ch_idx = idx + 1
                smil_id = f"smil_{ch_idx}"
                hid = getattr(html, 'id', 'MISSING')
                if any(getattr(s, 'id', 'MISSING') == smil_id for s in smil_items):
                    content = content.replace(f'id="{hid}"', f'id="{hid}" media-overlay="{smil_id}"')
            content = content.replace('</metadata>', '    <meta property="media:duration">00:00:00</meta>\n    <meta property="media:active-class">-epub-media-overlay-active</meta>\n  </metadata>')
            with open(opf_path, 'w', encoding='utf-8') as f:
                f.write(content)
            with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        fp = os.path.join(root, file)
                        zip_ref.write(fp, os.path.relpath(fp, temp_dir))
    finally:
        shutil.rmtree(temp_dir)