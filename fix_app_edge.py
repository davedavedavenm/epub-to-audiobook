import re

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Injection logic to validate chapter range before saving job
injection = """
        # Validate chapter range against actual book content
        try:
            if not file_ext == '.pdf':
                toc = get_epub_toc(file_path)
                max_chapters = len(toc) if toc else 999
                if start_chapter and start_chapter > max_chapters:
                    start_chapter = 1
                if end_chapter and end_chapter > max_chapters:
                    end_chapter = max_chapters
        except: pass
"""

content = re.sub(
    r'(output_dirname = f"\{safe_name\}_\{job_id\}")',
    injection + r'\n        \1',
    content
)

# Fix EdgeTTS model_name to 'edge' instead of 'tts-1' 
# because 'tts-1' triggers the OpenAI provider in the tool which might fail if 
# it expects a specific response format that the proxy doesn't perfectly emulate for Edge.
# Actually, the tool uses --tts openai --model_name tts-1 to talk to the proxy.
# The error in log was: ValueError: Chapter start index 3 is out of range. 
# This confirms the tool is running but failing on range.

with open('webapp/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Applied chapter range validation fix.")
