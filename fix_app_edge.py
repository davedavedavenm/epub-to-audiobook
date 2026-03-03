import re

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update tts_base_url for edge engine to use proxy
content = content.replace("elif tts_engine == 'edge':\n            # EdgeTTS (direct)\n            tts_base_url = 'not-needed'", 
                          "elif tts_engine == 'edge':\n            # EdgeTTS via Proxy (for NLP pacing and timing)\n            tts_base_url = f\"{TTS_PROXY_URL}/j/{job_id}/v1\" if TTS_PROXY_URL else f\"http://tts-proxy:8882/j/{job_id}/v1\"")

# Force the conversion container to use the openai provider when engine is edge (so it talks to our proxy)
# Find the line: '--tts', 'edge' if tts_engine == 'edge' else 'openai',
content = content.replace("'--tts', 'edge' if tts_engine == 'edge' else 'openai'",
                          "'--tts', 'openai'")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)