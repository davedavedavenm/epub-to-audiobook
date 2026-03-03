import re
import os

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    \"\"\"Copy completed audiobook to Audiobookshelf library via SSH.\"\"\"
    if not AUDIOBOOKSHELF_DIR or not AUDIOBOOKSHELF_HOST:
        return False

    # Advanced fix for SSH permissions on Windows/NTFS mounts
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
        # Ensure destination exists
        import shlex
        remote_mkdir = ' '.join(shlex.quote(x) for x in ['mkdir', '-p', '--', dest_path])
        mkdir_cmd = ['ssh', *ssh_args, target, remote_mkdir]
        mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=30)
        if mkdir_result.returncode != 0:
            err = (mkdir_result.stderr or mkdir_result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync mkdir failed: {err}")
            app.logger.error(f"Audiobookshelf mkdir failed: {err}")
            return False

        # Rsync to target
        cmd = ['rsync', '-av', '-s', '-e', rsync_ssh, f'{output_dir}/', f"{target}:{dest_path}/"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            if job_id:
                update_job(job_id, sync_status='failed', sync_error=err)
                append_job_log(job_id, f"Sync failed: {err}")
            app.logger.error(f"Failed to copy to Audiobookshelf: {err}")
            return False

        # Count files at destination
        remote_count = f"find -- {shlex.quote(dest_path)} -type f | wc -l"
        count_cmd = ['ssh', *ssh_args, target, remote_count]
        count_result = subprocess.run(count_cmd, capture_output=True, text=True, timeout=30)
        file_count = 0
        if count_result.returncode == 0:
            try:
                file_count = int(count_result.stdout.strip())
            except Exception:
                file_count = 0

        if job_id:
            update_job(job_id,
                sync_status='ok',
                sync_file_count=file_count,
                sync_error='',
                sync_timestamp=datetime.now().isoformat()
            )
            append_job_log(job_id, f"Sync ok: {file_count} files")

        app.logger.info(f"Copied {book_name} to Audiobookshelf")
        _trigger_abs_rescan(job_id)
        return True

    except Exception as e:
        if job_id:
            update_job(job_id, sync_status='failed', sync_error=str(e))
            append_job_log(job_id, f"Sync exception: {e}")
        app.logger.error(f"Sync error: {e}")
        return False
"""

start_pos = content.find('def copy_to_audiobookshelf(')
next_def = re.search(r'\\ndef ', content[start_pos+1:])
if next_def:
    end_pos = start_pos + 1 + next_def.start()
else:
    end_pos = len(content)

new_content = content[:start_pos] + new_func + content[end_pos:]
with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)