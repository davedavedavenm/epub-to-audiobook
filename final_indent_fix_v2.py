with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# Find the over-indented block and fix it
broken_block = """            # Stage 2: EPUB3 with SMIL (Read-Along)
            try:
                input_filename = job.get('input_filename', '')
                if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
                    epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
                    epub_out = output_path / f"{job['book_name']}.epub"
                    chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
                    if chunks_log.exists():
                        package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
            except Exception as e:
                print(f"Stage 2 (EPUB3) failed: {e}")"""

fixed_block = """    # Stage 2: EPUB3 with SMIL (Read-Along)
    try:
        input_filename = job.get('input_filename', '')
        if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
            epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
            epub_out = output_path / f"{job['book_name']}.epub"
            chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
            if chunks_log.exists():
                package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
    except Exception as e:
        print(f"Stage 2 (EPUB3) failed: {e}")"""

content = content.replace(broken_block, fixed_block)

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)