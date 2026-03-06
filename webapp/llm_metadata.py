import os
import json
import logging
from pathlib import Path
import requests
import xml.etree.ElementTree as ET
import zipfile
from bs4 import BeautifulSoup

def _get_llm_settings():
    # We need to import get_setting from app.py, but to avoid circular imports, 
    # we can just read from the DB or let the caller pass the settings.
    # Alternatively, we can use the same approach as in app.py
    import sqlite3
    db_path = Path(os.environ.get("DB_PATH", "/data/jobs.db"))
    settings = {
        'LLM_API_BASE_URL': os.environ.get('LLM_API_BASE_URL', 'https://api.openai.com/v1'),
        'LLM_API_KEY': os.environ.get('LLM_API_KEY', ''),
        'LLM_MODEL_NAME': os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    }
    
    try:
        if db_path.exists():
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                for key in settings.keys():
                    row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
                    if row and row['value']:
                        settings[key] = row['value']
    except Exception as e:
        logging.error(f"Failed to load LLM settings: {e}")
        
    return settings

def extract_sample_text(epub_path: Path, max_chars=15000) -> str:
    """Extract a sample of text from the beginning of the EPUB."""
    try:
        with zipfile.ZipFile(epub_path, 'r') as zf:
            # 1. Find OPF
            container_xml = zf.read('META-INF/container.xml').decode('utf-8')
            root = ET.fromstring(container_xml)
            opf_path = next(rf.get('full-path') for rf in root.iter() if rf.tag.endswith('rootfile'))
            
            # 2. Parse OPF to get reading order (spine)
            opf_content = zf.read(opf_path).decode('utf-8')
            opf_root = ET.fromstring(opf_content)
            
            ns = {'opf': 'http://www.idpf.org/2007/opf'}
            manifest = {item.get('id'): item.get('href') for item in opf_root.findall('.//opf:item', ns)}
            spine = [itemref.get('idref') for itemref in opf_root.findall('.//opf:itemref', ns)]
            
            opf_dir = Path(opf_path).parent
            
            sample_text = ""
            for item_id in spine:
                if len(sample_text) > max_chars:
                    break
                if item_id in manifest:
                    href = manifest[item_id]
                    file_path = str(opf_dir / href) if str(opf_dir) != '.' else href
                    try:
                        html_content = zf.read(file_path).decode('utf-8')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        text = soup.get_text(separator=' ', strip=True)
                        sample_text += text + "\n\n"
                    except:
                        continue
            return sample_text[:max_chars]
    except Exception as e:
        logging.error(f"Error extracting sample text for LLM: {e}")
        return ""

def generate_metadata(epub_path: Path) -> dict:
    """Use configured LLM to generate metadata based on EPUB content."""
    settings = _get_llm_settings()
    
    if not settings['LLM_API_KEY']:
        logging.info("LLM_API_KEY not set. Skipping automated metadata generation.")
        return {}
        
    sample_text = extract_sample_text(epub_path)
    if not sample_text:
        return {}

    prompt = f"""
You are an expert librarian and metadata extractor. I will provide you with the first few chapters/pages of a book.
Your task is to analyze the text and extract the following metadata:
1. "title": The title of the book (cleaned up, no weird formatting).
2. "author": The author's name.
3. "description": A compelling summary/description of the book based on the text. Write a 1-2 paragraph professional blurb.
4. "tags": An array of 3-5 relevant genre or thematic tags (e.g., ["Science Fiction", "Space Opera", "Classic"]).

Return ONLY a valid JSON object. Do not include markdown formatting like ```json or any other text. 
Here is the book sample:

{sample_text}
"""

    headers = {
        "Authorization": f"Bearer {settings['LLM_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings['LLM_MODEL_NAME'],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that outputs strictly valid JSON without any markdown wrapping."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        endpoint = f"{settings['LLM_API_BASE_URL'].rstrip('/')}/chat/completions"
        logging.info(f"Requesting LLM metadata from {endpoint} using model {settings['LLM_MODEL_NAME']}...")
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        
        # Strip potential markdown formatting if the model ignored instructions
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        metadata = json.loads(content.strip())
        logging.info(f"Successfully generated metadata: {metadata.get('title')}")
        return metadata
    except Exception as e:
        logging.error(f"LLM Metadata generation failed: {e}")
        return {}


def generate_lexicon(epub_path: Path) -> dict:
    """Use configured LLM to generate a pronunciation lexicon for complex names in the EPUB."""
    settings = _get_llm_settings()
    
    if not settings['LLM_API_KEY']:
        logging.info("LLM_API_KEY not set. Skipping automated lexicon generation.")
        return {}
        
    sample_text = extract_sample_text(epub_path, max_chars=30000)
    if not sample_text:
        return {}

    prompt = f"""
You are an expert linguist and text-to-speech engineer. I will provide you with a sample from a book.
Your task is to identify any complex Sci-Fi, Fantasy, non-English, or made-up names and terms that a standard text-to-speech engine might mispronounce.
For each term, provide a simple English phonetic spelling to help the TTS engine pronounce it correctly (e.g., "Daenerys": "Duh-nair-iss").

Return ONLY a valid JSON object where keys are the original words and values are the phonetic spellings. Do not include markdown formatting like ```json or any other text. 
If you find no such words, return an empty JSON object {{}}.

Here is the book sample:

{sample_text}
"""

    headers = {
        "Authorization": f"Bearer {settings['LLM_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings['LLM_MODEL_NAME'],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that outputs strictly valid JSON without any markdown wrapping."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }
    
    try:
        endpoint = f"{settings['LLM_API_BASE_URL'].rstrip('/')}/chat/completions"
        logging.info(f"Requesting LLM lexicon from {endpoint} using model {settings['LLM_MODEL_NAME']}...")
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        lexicon = json.loads(content.strip())
        logging.info(f"Successfully generated lexicon with {len(lexicon)} entries.")
        return lexicon
    except Exception as e:
        logging.error(f"LLM Lexicon generation failed: {e}")
        return {}
