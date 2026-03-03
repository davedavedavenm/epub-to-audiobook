with open("webapp/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

out = []
skip = False
for line in lines:
    if "Stage 2: EPUB3 with SMIL" in line:
        skip = True
        continue
    if skip and "Stage 2 (EPUB3) failed" in line:
        skip = False
        continue
    if skip:
        continue
    out.append(line)

content = "".join(out)
import re
# Find the FIRST rename_output_files call which is inside convert_book
pattern = r"(            rename_output_files\(output_path, job\['book_name'\]\))"
epub_logic = """
            # Stage 2: EPUB3 with SMIL (Read-Along)
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
                app.logger.error(f"Stage 2 (EPUB3) failed: {e}")
"""
content = re.sub(pattern, r"\1" + epub_logic, content, count=1)

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)