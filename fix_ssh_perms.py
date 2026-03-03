with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find copy_to_audiobookshelf and inject chmod 600 for the key
pattern = r'def copy_to_audiobookshelf\(.*?\):'
replacement = 'def copy_to_audiobookshelf(output_dir, book_name, job_id=None):\n    # Fix permissions at runtime for mounted SSH key\n    try:\n        subprocess.run(["chmod", "600", "/root/.ssh/id_ed25519"], capture_output=True)\n    except: pass'

content = re.sub(pattern, replacement, content)

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)