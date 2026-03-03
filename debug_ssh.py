import re
with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

debug_ssh = """def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    app.logger.info("DEBUG: Starting copy_to_audiobookshelf")
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    if os.path.exists(ssh_key_src):
        app.logger.info(f"DEBUG: Found source key {ssh_key_src}")
        import subprocess
        subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
        subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
        app.logger.info(f"DEBUG: Prepared temp key {ssh_key_tmp}")
    else:
        app.logger.warning(f"DEBUG: Source key {ssh_key_src} NOT FOUND")"""

start_marker = "def copy_to_audiobookshelf("
start_pos = content.find(start_marker)
# Find the end of our previous injection or the original function start
next_target = content.find('target = f"', start_pos)
new_content = content[:start_pos] + debug_ssh + "\n\n    " + content[next_target:]

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(new_content)