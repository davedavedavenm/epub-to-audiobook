import subprocess

# 1. Clear the queue on Zorin
# We use a script inside the container to ensure we have access to the DB
clear_db = "import sqlite3; conn=sqlite3.connect('/data/jobs.db'); conn.execute('DELETE FROM jobs WHERE status NOT IN (\"completed\", \"failed\")'); conn.commit(); conn.close()"
remote_clear = f"docker exec epub-to-audiobook-ui python3 -c {subprocess.list2cmdline([clear_db])}"

# 2. Fix the index.html encoding on Zorin (Remove BOM and ensure clean UTF-8)
fix_html = "p='/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'; b=open(p,'rb').read(); b=b.replace(b'\\xff\\xfe', b''); b=b.replace(b'\\xef\\xbb\\xbf', b''); open(p,'wb').write(b)"
remote_fix = f"python3 -c {subprocess.list2cmdline([fix_html])}"

# 3. Restart to apply
remote_restart = "cd /home/dave/ai/lab/stacks/epub-to-audiobook && docker compose restart webapp"

full_cmd = f"{remote_clear} && {remote_fix} && {remote_restart}"
subprocess.run(["ssh", "zorin", full_cmd])