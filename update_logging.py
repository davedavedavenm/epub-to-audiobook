with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

import re
old_block = """            # Stage 2: EPUB3 with SMIL (Read-Along)
            try:
                from epub_generator import package_epub3_with_audio
                input_filename = job.get('input_filename', '')
                if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
                    epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
                    epub_out = output_path / f"{job['book_name']}.epub"
                    chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
                    if chunks_log.exists():
                        package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
            except Exception as e:
                app.logger.error(f"Stage 2 (EPUB3) failed: {e}")"""

new_block = """            # Stage 2: EPUB3 with SMIL (Read-Along)
            try:
                from epub_generator import package_epub3_with_audio
                input_filename = job.get('input_filename', '')
                app.logger.info(f"EPUB3 Debug: input_filename={input_filename}")
                if input_filename.endswith('.epub') or (job.get('is_pdf') and os.path.exists(UPLOAD_DIR / input_filename.rsplit('.', 1)[0] + '.epub')):
                    epub_in = UPLOAD_DIR / (input_filename if not job.get('is_pdf') else input_filename.rsplit('.', 1)[0] + '.epub')
                    epub_out = output_path / f"{job['book_name']}.epub"
                    chunks_log = Path(f"/data/transcripts/{job_id}/chunks.jsonl")
                    app.logger.info(f"EPUB3 Debug: chunks_log={chunks_log}, exists={chunks_log.exists()}")
                    if chunks_log.exists():
                        package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
                else:
                    app.logger.warning(f"EPUB3 Debug: Condition false for {input_filename}")
            except Exception as e:
                app.logger.error(f"Stage 2 (EPUB3) failed: {e}")"""

content = content.replace(old_block, new_block)

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)