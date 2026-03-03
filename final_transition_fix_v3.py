with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# 1. EPUB3 Import
if "from epub_generator import package_epub3_with_audio" not in content:
    content = "from epub_generator import package_epub3_with_audio\n" + content

# 2. EPUB3 Logic injection - Find the first instance of rename_output_files and inject AFTER it
# Because rename_output_files prepares the directory
pattern = r"(rename_output_files\(output_path, job\['book_name'\]\))"
epub_logic = """
    # Stage 2: EPUB3 with SMIL (Read-Along)
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
"""
content = re.sub(pattern, r"\1" + epub_logic, content)

# 3. SSH Fix - Brutal string replacement for the key path
content = content.replace("'-i', '/root/.ssh/id_ed25519',", "'-i', '/tmp/id_ed25519_tmp',")

# 4. SSH Logic injection - Find start of copy_to_audiobookshelf and inject temp key prep
ssh_prep = """
    # Fix permissions at runtime for mounted SSH key (NTFS workaround)
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            import subprocess
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except: pass
"""
content = content.replace('def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:',
                          'def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:' + ssh_prep)

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)