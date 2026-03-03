with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Advanced fix for SSH permissions on Windows/NTFS mounts
pattern = r'def copy_to_audiobookshelf\(.*?\):'
replacement = """def copy_to_audiobookshelf(output_dir, book_name, job_id=None):
    # Copy key to a location where we can set 600 permissions (avoids NTFS mount issues)
    ssh_key_src = "/root/.ssh/id_ed25519"
    ssh_key_tmp = "/tmp/id_ed25519_tmp"
    try:
        if os.path.exists(ssh_key_src):
            subprocess.run(["cp", ssh_key_src, ssh_key_tmp], capture_output=True)
            subprocess.run(["chmod", "600", ssh_key_tmp], capture_output=True)
    except: pass"""

content = re.sub(pattern, replacement, content)

# Now replace the usages of the key in the same function
content = content.replace("'-i', '/root/.ssh/id_ed25519',", "'-i', ssh_key_tmp,")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)