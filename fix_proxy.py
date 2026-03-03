import re

with open('tts_proxy/proxy.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'import io' not in content:
    content = content.replace('import hashlib', 'import io\nimport hashlib')
if 'from mutagen.mp3 import MP3' not in content:
    content = content.replace('from typing import Any', 'from typing import Any\nfrom mutagen.mp3 import MP3')

# Update audio_speech function
# We need to capture the audio content, get its duration, and THEN log it.
# Currently it logs BEFORE getting audio. I should move logging AFTER or log duration separately.

# 1. Find the logging block
log_block_pattern = r'append_jsonl\([\s\S]*?chunks_path,[\s\S]*?\{[\s\S]*?\}\n\s+\)'
log_block_match = re.search(log_block_pattern, content)

if log_block_match:
    log_block = log_block_match.group(0)
    # Remove it from its current position
    content = content.replace(log_block, '# LOGGING MOVED BELOW')

# 2. Add duration calculation helper
if 'def get_audio_duration' not in content:
    duration_func = """
def get_audio_duration(audio_bytes: bytes) -> float:
    try:
        audio_file = io.BytesIO(audio_bytes)
        mp3 = MP3(audio_file)
        return mp3.info.length
    except Exception as e:
        print(f"Duration error: {e}")
        return 0.0
"""
    content = content.replace('app = FastAPI()', 'app = FastAPI()\n' + duration_func)

# 3. Inject updated logging after audio acquisition
# For Polly:
polly_replacement = """            audio_stream = response['AudioStream'].read()
            duration = get_audio_duration(audio_stream)
            append_jsonl(
                chunks_path,
                {
                    "ts": _now_iso(),
                    "job_id": job_id,
                    "text": text,
                    "text_sha256": sha256_hex(text),
                    "strict": strict,
                    "strict_sha256": sha256_hex(strict),
                    "loose": loose,
                    "loose_sha256": sha256_hex(loose),
                    "model": payload.get("model"),
                    "voice": voice,
                    "duration_s": duration
                }
            )
            return Response(content=audio_stream, status_code=200, media_type='audio/mpeg')"""

content = content.replace("            audio_stream = response['AudioStream'].read()\n            return Response(content=audio_stream, status_code=200, media_type='audio/mpeg')", polly_replacement)

# For Kokoro:
kokoro_replacement = """    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(upstream_url, json=payload)

    audio_content = r.content
    duration = get_audio_duration(audio_content)
    append_jsonl(
        chunks_path,
        {
            "ts": _now_iso(),
            "job_id": job_id,
            "text": text,
            "text_sha256": sha256_hex(text),
            "strict": strict,
            "strict_sha256": sha256_hex(strict),
            "loose": loose,
            "loose_sha256": sha256_hex(loose),
            "model": payload.get("model"),
            "voice": voice,
            "duration_s": duration
        }
    )
    ct = r.headers.get("content-type", "application/octet-stream")
    return Response(content=audio_content, status_code=r.status_code, media_type=ct)"""

content = content.replace("""    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(upstream_url, json=payload)

    ct = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, status_code=r.status_code, media_type=ct)""", kokoro_replacement)

with open('tts_proxy/proxy.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
