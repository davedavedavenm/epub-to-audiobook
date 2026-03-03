with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

import re

# 1. CLEANUP PREVIOUS BROKEN INJECTIONS
# Remove all the try/except Stage 2 blocks we might have injected
content = re.sub(r'# Stage 2: EPUB3 with SMIL \(Read-Along\).*?# Stage 2 \(EPUB3\) failed: \{e\}\)\n', '', content, flags=re.DOTALL)
# Remove all the try block fragments
content = re.sub(r'try:\s+input_filename = job.get.*?# Stage 2 \(EPUB3\) failed: \{e\}\)\n', '', content, flags=re.DOTALL)

# 2. PROPER INJECTION
# EPUB3 logic
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
        print(f"Stage 2 (EPUB3) failed: {e}")
"""

# Find WHERE to inject. In finalize_completed_job, after rename_output_files
pattern = r"(rename_output_files\(output_path, job\['book_name'\]\))"
# Only replace the first occurrence which is in finalize_completed_job usually
content = re.sub(pattern, r"\1" + epub_logic, content, count=1)

# 3. SSH Fix - Copy key to /tmp
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
content = re.sub(r'(def copy_to_audiobookshelf\(.*?\):)', r'\1' + ssh_prep, content)
content = content.replace("'/root/.ssh/id_ed25519'", "ssh_key_tmp")

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)