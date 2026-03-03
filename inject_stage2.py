import re

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import
if 'from epub_generator import package_epub3_with_audio' not in content:
    content = 'from epub_generator import package_epub3_with_audio\n' + content

# Find finalize_completed_job and inject Stage 2 call
# We want to inject it BEFORE copy_to_audiobookshelf

pattern = r'(# Sync to ABS\s+synced = copy_to_audiobookshelf\(output_path, job\[\'book_name\'\], job_id=job_id\))'
replacement = r'''# Stage 2: EPUB3 with SMIL (Read-Along)
    try:
        input_filename = job.get('input_filename', '')
        if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
            epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
            epub_out = output_path / f"{job['book_name']}.epub"
            chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
            if chunks_log.exists():
                package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
    except Exception as e:
        app.logger.error(f"Stage 2 (EPUB3) failed: {e}")

    \1'''

if re.search(pattern, content):
    content = re.sub(pattern, replacement, content)
else:
    print("Pattern not found!")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
