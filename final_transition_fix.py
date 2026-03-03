import re
import os

with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add EPUB3 Generator Import
if "from epub_generator import package_epub3_with_audio" not in content:
    content = "from epub_generator import package_epub3_with_audio\n" + content

# 2. Inject EPUB3 Generation Call in finalize_completed_job
# We'll search for the sync call and inject before it
sync_match = re.search(r"(# Sync to ABS\s+synced = copy_to_audiobookshelf\(output_path, job\['book_name'\], job_id=job_id\))", content)
if sync_match and "package_epub3_with_audio" not in sync_match.group(0):
    epub_logic = """# Stage 2: EPUB3 with SMIL (Read-Along)
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
    content = content.replace(sync_match.group(1), epub_logic + sync_match.group(1))

# 3. Robust SSH Key Fix
ssh_fix_logic = """
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

# Find copy_to_audiobookshelf and inject logic
def_match = re.search(r"def copy_to_audiobookshelf\(.*?\):", content)
if def_match:
    content = content.replace(def_match.group(0), def_match.group(0) + ssh_fix_logic)
    # Redirect all key usages in this function to the temp file
    # We find the end of the function by searching for the next 'def '
    next_def_pos = content.find("\ndef ", def_match.end())
    func_body = content[def_match.end():next_def_pos]
    new_body = func_body.replace("'/root/.ssh/id_ed25519'", "ssh_key_tmp")
    content = content[:def_match.end()] + new_body + content[next_def_pos:]

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)