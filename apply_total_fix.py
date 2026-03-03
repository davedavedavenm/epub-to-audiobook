import re
import os

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ADD EPUB3 GENERATOR IMPORT
if "from epub_generator import package_epub3_with_audio" not in content:
    content = "from epub_generator import package_epub3_with_audio\n" + content

# 2. FIX EPUB3 LOGIC (ENSURE INDENTATION)
content = re.sub(r'# Stage 2: EPUB3 with SMIL \(Read-Along\).*?# Stage 2 \(EPUB3\) failed: \{e\}\)\n', '', content, flags=re.DOTALL)
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
                print(f"Stage 2 (EPUB3) failed: {e}")
"""
pattern = r"(rename_output_files\(output_path, job\['book_name'\]\))"
content = re.sub(pattern, r"\1" + epub_logic, content, count=1)

# 3. FIX SSH FUNCTION COMPLETELY
new_ssh_func = """def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    \"\"\"Copy completed audiobook to Audiobookshelf library via SSH.\"\"\"
    if not AUDIOBOOKSHELF_DIR or not AUDIOBOOKSHELF_HOST:
        return False

    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            import subprocess
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except Exception as e:
        app.logger.warning(f"Failed to prepare temp SSH key: {e}")

    target = f"{AUDIOBOOKSHELF_USER}@{AUDIOBOOKSHELF_HOST}"
    dest_folder = output_dir.name
    dest_path = f"{AUDIOBOOKSHELF_DIR}/{dest_folder}"

    ssh_args = [
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-F', '/dev/null',
        '-i', ssh_key_tmp,
    ]
    if AUDIOBOOKSHELF_PORT:
        ssh_args += ['-p', str(AUDIOBOOKSHELF_PORT)]
    
    import shlex
    rsync_ssh = 'ssh ' + ' '.join(shlex.quote(a) for a in ssh_args)

    if job_id:
        update_job(job_id,
            sync_target_host=AUDIOBOOKSHELF_HOST,
            sync_target_path=dest_path,
            sync_status='started',
            sync_error='',
            sync_timestamp=datetime.now().isoformat()
        )
        append_job_log(job_id, f"Sync start -> {target}:{dest_path}")

    try:
        import shlex
        remote_mkdir = ' '.join(shlex.quote(x) for x in ['mkdir', '-p', '--', dest_path])
        mkdir_cmd = ['ssh', *ssh_args, target, remote_mkdir]
        mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)
        if mkdir_result.returncode != 0:
            err = (mkdir_result.stderr or mkdir_result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync mkdir failed: {err}")
            return False

        cmd = ['rsync', '-av', '-s', '-e', rsync_ssh, f'{output_dir}/', f"{target}:{dest_path}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync failed: {err}")
            return False

        if job_id:
            update_job(job_id, sync_status='ok', sync_timestamp=datetime.now().isoformat())
            append_job_log(job_id, "Sync ok")
        return True
    except Exception as e:
        if job_id:
            update_job(job_id, sync_status='failed', sync_error=str(e))
        return False
"""

# Find function boundaries
start_marker = "def copy_to_audiobookshelf("
start_pos = content.find(start_marker)
next_def = re.search(r'\n\n@|\ndef ', content[start_pos+1:])
if next_def:
    end_pos = start_pos + 1 + next_def.start()
else:
    end_pos = len(content)

new_content = content[:start_pos] + new_ssh_func + content[end_pos:]

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)