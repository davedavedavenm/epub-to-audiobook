import re
import os

with open('webapp/app.py', 'rb') as f:
    raw = f.read(2)

if raw == b'\xff\xfe':
    with open('webapp/app.py', 'rb') as f:
        content = f.read().decode('utf-16')
else:
    with open('webapp/app.py', 'r', encoding='utf-8') as f:
        content = f.read()

# Surigical fixes
if "init_db()" not in content:
    content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

content = content.replace("MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))", "MIN_CHAPTER_SIZE_KB = 0")
content = content.replace("min_size_kb: int = 500", "min_size_kb: int = 0")
content = re.sub(r"min_total_mb = 0\.1 if .*? else 1\.0", "min_total_mb = 0.01", content)

content = content.replace("elif tts_engine == 'edge':\n            # EdgeTTS (direct)\n            tts_base_url = 'not-needed'", 
                          "elif tts_engine == 'edge':\n            # EdgeTTS via Proxy\n            tts_base_url = f\"{TTS_PROXY_URL}/j/{job_id}/v1\" if TTS_PROXY_URL else f\"http://tts-proxy:8882/j/{job_id}/v1\"")

content = content.replace("'--tts', 'edge' if tts_engine == 'edge' else 'openai'", "'--tts', 'openai'")

ssh_logic = """
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            import subprocess
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except: pass
"""
content = content.replace("dest_path = f\"{AUDIOBOOKSHELF_DIR}/{dest_folder}\"", "dest_path = f\"{AUDIOBOOKSHELF_DIR}/{dest_folder}\"\n" + ssh_logic)
content = content.replace("'-i', '/root/.ssh/id_ed25519',", "'-i', '/tmp/id_ed25519_tmp',")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)