import os
import re

def sanitize_file(path):
    if not os.path.exists(path):
        return
    print(f"Sanitizing {path}")
    with open(path, 'rb') as f:
        raw = f.read()
    
    # Remove BOMs
    raw = raw.replace(b'\xef\xbb\xbf', b'')
    raw = raw.replace(b'\xff\xfe', b'')
    
    # Convert to string, ignore errors to drop mangled multi-byte sequences
    text = raw.decode('utf-8', errors='ignore')
    
    # Replace common mangled separators with ASCII
    text = text.replace('┬╖', ' - ')
    text = text.replace('→', ' -> ')
    text = text.replace('✅', '[OK]')
    
    # Strip all remaining non-ASCII
    clean_text = "".join([i if ord(i) < 128 else " " for i in text])
    
    # Specifically empty out the <i> tags which are often sources of mangled emojis
    clean_text = re.sub(r'<i>.*?</i>', '<i></i>', clean_text)
    
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(clean_text)

base = '/home/dave/ai/lab/stacks/epub-to-audiobook'
sanitize_file(os.path.join(base, 'webapp/app.py'))
sanitize_file(os.path.join(base, 'webapp/templates/index.html'))