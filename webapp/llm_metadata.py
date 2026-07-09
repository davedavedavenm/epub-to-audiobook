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


# Deterministic floor: known-hard names every book of this kind trips on.
# Merged into every profile so the pipeline never regresses below this even
# when no LLM is available (mirrors convert_book.SEED_PRONUNCIATION).
SEED_RULES = {
    "Cupertino": "Coo-per-TEE-no", "Beijing": "Bay-JING", "McDonald's": "Mick-DON-uld-z",
    "Huawei": "HWAH-way", "Xiaomi": "SHOW-mee", "Nguyen": "Nwin", "Qualcomm": "KWAL-com",
    "Foxconn": "FOX-con", "Shenzhen": "SHUN-jen", "Guangzhou": "GWANG-joe",
    # TADA tokenizer quirks caught by ear/QA (2026-07-08): "iPhones" -> "if owns"
    "iPhone": "eye-phone", "iPhones": "eye-phones", "iPad": "eye-pad",
    "iPods": "eye-pods", "iPod": "eye-pod", "iOS": "eye-O-S",
}


def _seed_profile(reason: str) -> dict:
    return {'domain': 'general', 'form': 'nonfiction', 'is_fiction': False,
            'rules': dict(SEED_RULES), 'notes': [f'seed-only ({reason})']}


def _fallback_settings():
    """Optional secondary LLM provider (env LLM_FALLBACK_API_BASE_URL /
    LLM_FALLBACK_API_KEY / LLM_FALLBACK_MODEL_NAME). Used only when the primary
    errors. Returns None if not configured. Env-only by design — the backup
    should not depend on the same DB the primary reads."""
    key = os.environ.get('LLM_FALLBACK_API_KEY')
    if not key:
        return None
    return {
        'LLM_API_BASE_URL': os.environ.get('LLM_FALLBACK_API_BASE_URL', 'https://api.openai.com/v1'),
        'LLM_API_KEY': key,
        'LLM_MODEL_NAME': os.environ.get('LLM_FALLBACK_MODEL_NAME', 'gpt-4o-mini'),
    }


def _call_llm_json_chain(prompt: str, temperature: float = 0.1):
    """Try the primary LLM provider, then the optional fallback, each with a
    retry. Returns (parsed_obj, tier) or (None, None) if all fail. This is the
    'nothing silently gives up' path — the caller then degrades to seed rules."""
    attempts = []
    primary = _get_llm_settings()
    if primary.get('LLM_API_KEY'):
        attempts.append(('primary', primary))
    fb = _fallback_settings()
    if fb:
        attempts.append(('fallback', fb))
    for tier, s in attempts:
        for retry in range(2):
            try:
                obj = _call_llm_json(prompt, s, temperature=temperature)
                if retry or tier != 'primary':
                    logging.info(f"LLM narration profile served by {tier} (retry {retry}).")
                return obj, tier
            except Exception as e:
                logging.warning(f"LLM {tier} attempt {retry + 1} failed: {e}")
    return None, None


def _call_llm_json(prompt: str, settings: dict, temperature: float = 0.1):
    """POST a prompt expecting a strict-JSON reply; returns parsed obj or None."""
    headers = {"Authorization": f"Bearer {settings['LLM_API_KEY']}",
               "Content-Type": "application/json"}
    payload = {
        "model": settings['LLM_MODEL_NAME'],
        "messages": [
            {"role": "system", "content": "You output strictly valid JSON with no markdown wrapping."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    endpoint = f"{settings['LLM_API_BASE_URL'].rstrip('/')}/chat/completions"
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    content = resp.json()['choices'][0]['message']['content'].strip()
    for fence in ("```json", "```"):
        if content.startswith(fence):
            content = content[len(fence):]
    if content.endswith("```"):
        content = content[:-3]
    return json.loads(content.strip())


# Sample the book more widely than just the opening — pull excerpts across the
# spine so the profile reflects the whole book, not only chapter 1.
def extract_spread_sample(epub_path: Path, max_chars=24000) -> str:
    try:
        full = extract_sample_text(epub_path, max_chars=200000)
    except Exception:
        return extract_sample_text(epub_path, max_chars=max_chars)
    if len(full) <= max_chars:
        return full
    # take 4 evenly spaced windows
    n = 4
    win = max_chars // n
    step = (len(full) - win) // (n - 1)
    return "\n\n[...]\n\n".join(full[i * step:i * step + win] for i in range(n))


def generate_narration_profile(epub_path: Path) -> dict:
    """QA Layer 1 (pre-flight): analyse the book and return an adaptive
    narration profile — NOT hardcoded, generated per book by the LLM.

    Returns {"domain": str, "rules": {search: replace}, "notes": [str]}.
    `rules` are whole-word replacements merged into the TTS lexicon so the
    engine says things correctly (e.g. "US" -> "U S", odd names phonetically,
    ambiguous numbers spelled out). Degrades to {} if no LLM configured.
    """
    settings = _get_llm_settings()
    if not settings['LLM_API_KEY'] and not _fallback_settings():
        logging.info("No LLM configured. Using seed narration profile floor.")
        return _seed_profile('no LLM configured')
    sample = extract_spread_sample(epub_path)
    if not sample:
        return _seed_profile('no sample text extracted')

    prompt = f"""You are a text-to-speech narration engineer preparing a book for audiobook conversion.
Read the sample and (a) classify the book, then (b) find every token a TTS engine is likely to MISREAD.

First decide "form": is this FICTION (novel/short stories — narrative prose with characters and dialogue)
or NON-FICTION (history, business, biography, science, self-help — expository prose)?
This changes what to hunt for:
- FICTION: prioritise CHARACTER names, invented/fantasy names, foreign place names, and words in
  dialogue. Dialogue-heavy prose leans on quotation marks and dashes for pacing — flag anything that
  would break that flow. Numbers are rare; don't invent number rules.
- NON-FICTION: prioritise ACRONYMS/initialisms, COMPANY/BRAND names, place names, technical terms,
  and genuinely ambiguous figures/units. These books are dense with them.

Cover ALL of these categories (weighted by the form above):
- Acronyms/initialisms read letter-by-letter (US -> "U S", UK -> "U K", CEO -> "C E O", IPO -> "I P O", FBI -> "F B I"). Only letters that are genuinely spelled out; leave true words (NASA, NATO) alone.
- Proper nouns, surnames, place names, and BRAND/COMPANY names needing phonetic spelling — INCLUDING well-known ones a TTS still fumbles: e.g. "Cupertino" -> "Coo-per-TEE-no", "Beijing" -> "Bay-JING", "McDonald's" -> "Mick-DON-uld-z", "Nguyen" -> "Nwin", "Huawei" -> "HWAH-way", "Xiaomi" -> "SHOW-mee". Be generous: any name a general audiobook narrator might mispronounce.
- Foreign or invented words.
- Numbers/dates/units that would be misread ONLY where context makes them ambiguous (a modern engine reads plain years and numbers correctly on its own — do NOT add rules just to spell numbers out).
Err toward INCLUDING a name rather than skipping it.

Return ONLY a JSON object:
{{"form": "fiction" | "nonfiction",
  "domain": "<one short phrase, e.g. 'US politics nonfiction' or 'epic fantasy'>",
  "rules": {{"<original text>": "<spoken replacement>"}},
  "notes": ["<short note>"]}}
Keep rules high-precision (only clear wins). Empty rules {{}} if none.

BOOK SAMPLE:
{sample}
"""
    obj, tier = _call_llm_json_chain(prompt, temperature=0.1)
    if obj is None:
        logging.warning("All LLM providers failed for narration profile — using seed rules.")
        return _seed_profile('LLM providers failed')
    try:
        rules = obj.get('rules', {}) if isinstance(obj, dict) else {}
        # sanitize: keep only str->str, drop empties
        rules = {str(k): str(v) for k, v in rules.items() if k and v and str(k) != str(v)}
        # merge the deterministic floor so the profile never regresses below the
        # known-hard names (LLM rules win on conflict).
        for k, v in SEED_RULES.items():
            rules.setdefault(k, v)
        form = (obj.get('form') if isinstance(obj, dict) else '') or ''
        form = str(form).strip().lower()
        is_fiction = form.startswith('fic')
        profile = {
            'domain': (obj.get('domain') if isinstance(obj, dict) else '') or 'general',
            'form': 'fiction' if is_fiction else 'nonfiction',
            'is_fiction': is_fiction,
            'rules': rules,
            'notes': obj.get('notes', []) if isinstance(obj, dict) else [],
            'provider_tier': tier,
        }
        logging.info(f"Narration profile: form={profile['form']} domain={profile['domain']} rules={len(rules)} via {tier}")
        return profile
    except Exception as e:
        logging.error(f"Narration profile parse failed: {e}")
        return _seed_profile('LLM parse failed')


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
