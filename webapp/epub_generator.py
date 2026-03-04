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
    nltk.download('punkt', quiet=True)

def _get_audio_files(audio_dir):
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

class ChunkIterator:
    def __init__(self, chunks):
        total_chars = sum(len(c.get('text', '').strip()) for c in chunks)
        total_dur = sum(c.get('duration_s', 0.0) for c in chunks)
        self.sec_per_char = (total_dur / total_chars) if total_chars > 0 else 0.06

    def next_duration(self, text):
        return len(text) * self.sec_per_char

def format_smil_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def split_html_into_words(html_str):
    import re
    # Match tags or non-whitespace characters, plus trailing whitespace
    pattern = r'(?:<[^>]+>|[^<\s]+)+\s*'
    parts = re.findall(pattern, html_str)
    return [p for p in parts if p.strip() or '<' in p]

def instrument_html(html_content, chunk_iterator):
    if isinstance(html_content, bytes):
        html_content = html_content.decode('utf-8')
    soup = BeautifulSoup(html_content, 'lxml')
    counter = 1
    durations = []
    
    for tag in soup.find_all(['p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = tag.get_text().strip()
        if not text: continue
        
        inner_html = tag.decode_contents()
        html_words = split_html_into_words(inner_html)
        
        if not html_words: continue
        
        tag.clear()
        for html_word in html_words:
            span = soup.new_tag("span", id=f"s{counter}")
            part_soup = BeautifulSoup(html_word, 'html.parser')
            # Extract plain text to calculate duration
            part_text = part_soup.get_text()
            
            span.extend(part_soup.contents)
            tag.append(span)
            
            # Duration based on characters in this word/segment
            durations.append(chunk_iterator.next_duration(part_text))
            counter += 1
            
    # Ensure html tag has epub namespace
    html_tag = soup.find('html')
    if html_tag and not html_tag.has_attr('xmlns:epub'):
        html_tag['xmlns:epub'] = "http://www.idpf.org/2007/ops"
        
    return str(soup), durations

def generate_smil(html_file_name, audio_file_name, durations):
    smil = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">',
        '  <body>',
        f'    <seq id="id1" epub:textref="../{html_file_name}">',
    ]
    current_time = 0.0
    for i, dur in enumerate(durations, start=1):
        end_time = current_time + dur
        begin_str = format_smil_time(current_time)
        end_str = format_smil_time(end_time)
        
        smil.append(f'      <par id="par{i}">')
        smil.append(f'        <text src="../{html_file_name}#s{i}"/>')
        smil.append(f'        <audio src="../Audio/{audio_file_name}" clipBegin="{begin_str}" clipEnd="{end_str}"/>')
        smil.append('      </par>')
        current_time = end_time
        
    smil.extend(['    </seq>', '  </body>', '</smil>'])
    return "\n".join(smil), current_time

def _fix_uids(book):
    import uuid
    for i, itm in enumerate(book.get_items()):
        if not getattr(itm, 'id', None):
            itm.id = f"gen_id_{i}_{str(uuid.uuid4())[:8]}"
        itm.uid = str(itm.id)

    def _fix_toc(toc, counter=1):
        new_toc = []
        for item in toc:
            if isinstance(item, (tuple, list)):
                section, sub_toc = item
                if not getattr(section, 'uid', None):
                    section.uid = f"gen_nav_{counter}_{str(uuid.uuid4())[:8]}"
                    counter += 1
                new_sub_toc, counter = _fix_toc(sub_toc, counter)
                new_toc.append((section, new_sub_toc))
            else:
                if isinstance(item, epub.EpubHtml):
                    # Link objects are safer in TOC for NCX generation
                    item = epub.Link(item.file_name, item.title, item.id)
                if not getattr(item, 'uid', None):
                    item.uid = f"gen_nav_{counter}_{str(uuid.uuid4())[:8]}"
                    counter += 1
                new_toc.append(item)
        return new_toc, counter

    book.toc, _ = _fix_toc(book.toc)
    
    # Also check book.spine
    for i, item_ref in enumerate(book.spine):
        if isinstance(item_ref, tuple):
            iid = item_ref[0]
        else:
            iid = item_ref
        item = book.get_item_with_id(iid)
        if item and not getattr(item, 'uid', None):
            item.uid = str(item.id)

def package_epub3_with_audio(input_epub_path, output_epub_path, audio_dir, chunks_jsonl_path):
    print(f"Packaging EPUB3: {input_epub_path} -> {output_epub_path}")
    try:
        book = epub.read_epub(input_epub_path)
        audio_files = _get_audio_files(audio_dir)
        book.version = 3.0
        _fix_uids(book)
        
        chunks = _read_chunks(chunks_jsonl_path)
        chunk_iter = ChunkIterator(chunks)
        
        audio_items = {}
        for ch_idx, mp3_path in audio_files.items():
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
        total_book_duration = 0.0
        
        for idx, html_item in enumerate(html_items):
            ch_idx = idx + 1
            if ch_idx in audio_items:
                audio_item = audio_items[ch_idx]
                
                new_html, durations = instrument_html(html_item.content, chunk_iter)
                html_item.content = new_html.encode('utf-8')
                
                smil_content, chap_duration = generate_smil(html_item.file_name, audio_item.file_name, durations)
                total_book_duration += chap_duration
                
                smil_item = epub.EpubItem(f"smil_{ch_idx}", f"SMIL/chapter_{ch_idx}.smil", "application/smil+xml", smil_content.encode('utf-8'))
                book.add_item(smil_item)
                smil_items.append(smil_item)

        _fix_uids(book)
        epub.write_epub(output_epub_path, book)
        _post_process_opf(output_epub_path, html_items, smil_items, total_book_duration)
        print("Successfully created EPUB3 with Instrumented Read-Along")
    except Exception as e:
        print(f"Error generating EPUB3: {e}")
        traceback.print_exc()
        if not os.path.exists(output_epub_path):
            shutil.copy(input_epub_path, output_epub_path)

def _post_process_opf(epub_path, html_items, smil_items, total_duration):
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
                hid = getattr(html, 'id', None)
                if not hid: continue
                if any(getattr(s, 'id', None) == smil_id for s in smil_items):
                    content = content.replace(f'id="{hid}"', f'id="{hid}" media-overlay="{smil_id}"')
                    
            formatted_duration = format_smil_time(total_duration)
            content = content.replace('</metadata>', f'    <meta property="media:duration">{formatted_duration}</meta>\n    <meta property="media:active-class">-epub-media-overlay-active</meta>\n  </metadata>')
            
            with open(opf_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        fp = os.path.join(root, file)
                        zip_ref.write(fp, os.path.relpath(fp, temp_dir))
    finally:
        shutil.rmtree(temp_dir)
