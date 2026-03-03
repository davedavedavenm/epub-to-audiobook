import re
import os

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. init_db()
if 'init_db()' not in content or content.find('init_db()') > content.find('if __name__ =='):
    content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

# 2. noise reduction
content = content.replace("MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))", "MIN_CHAPTER_SIZE_KB = 0")
content = content.replace("min_size_kb: int = 500", "min_size_kb: int = 0")

# 3. min_total_mb
content = re.sub(r"min_total_mb = 0\.1 if .*? else 1\.0", "min_total_mb = 0.01", content)

# 4. Edge TTS via Proxy
content = content.replace("elif tts_engine == 'edge':\n            # EdgeTTS (direct)\n            tts_base_url = 'not-needed'", 
                          "elif tts_engine == 'edge':\n            # EdgeTTS via Proxy\n            tts_base_url = f\"{TTS_PROXY_URL}/j/{job_id}/v1\" if TTS_PROXY_URL else f\"http://tts-proxy:8882/j/{job_id}/v1\"")
content = content.replace("'--tts', 'edge' if tts_engine == 'edge' else 'openai'", "'--tts', 'openai'")

# 5. SSH Key Temp Fix
ssh_fix = """
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            import subprocess
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except: pass
"""
# Find copy_to_audiobookshelf and inject after the first few lines
match = re.search(r'def copy_to_audiobookshelf\(.*?\):', content)
if match:
    pos = content.find('"""', match.end())
    if pos != -1:
        end_doc = content.find('"""', pos + 3)
        if end_doc != -1:
            content = content[:end_doc+3] + ssh_fix + content[end_doc+3:]

# Replace usages of the key
content = content.replace("'-i', '/root/.ssh/id_ed25519',", "'-i', '/tmp/id_ed25519_tmp',")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)