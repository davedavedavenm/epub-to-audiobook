with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# SAFE MINIMAL FIXES ONLY
if "init_db()" not in content:
    content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

content = content.replace("MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))", "MIN_CHAPTER_SIZE_KB = 0")
content = content.replace("min_size_kb: int = 500", "min_size_kb: int = 0")
content = content.replace("elif tts_engine == 'edge':\n            # EdgeTTS (direct)\n            tts_base_url = 'not-needed'", 
                          "elif tts_engine == 'edge':\n            # EdgeTTS via Proxy\n            tts_base_url = f\"{TTS_PROXY_URL}/j/{job_id}/v1\" if TTS_PROXY_URL else f\"http://tts-proxy:8882/j/{job_id}/v1\"")
content = content.replace("'--tts', 'edge' if tts_engine == 'edge' else 'openai'", "'--tts', 'openai'")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)