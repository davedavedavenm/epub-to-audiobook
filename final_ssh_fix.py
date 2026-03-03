with open("webapp/app.py", "r", encoding="utf-8") as f:
    content = f.read()

import re
pattern = r'def copy_to_audiobookshelf\(.*?\):'
replacement = """def copy_to_audiobookshelf(output_dir: Path, book_name: str, job_id: str | None = None) -> bool:
    # Advanced fix for SSH permissions on Windows/NTFS mounts
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            import subprocess
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except Exception as e:
        app.logger.warning(f"Failed to prepare temp SSH key: {e}")"""

# Clean up the previous broken injection first
content = content.replace("ssh_key_tmp = \"/tmp/id_ed25519_tmp\"", "# BROKEN")
content = re.sub(r'# BROKEN.*?try:.*?except: pass', '', content, flags=re.DOTALL)

# Re-inject properly
content = re.sub(pattern, replacement, content)

with open("webapp/app.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)