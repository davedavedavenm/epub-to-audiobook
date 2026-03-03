import subprocess

# 1. Total wipe of the jobs table on Zorin
wipe_db = "import sqlite3; conn=sqlite3.connect('/data/jobs.db'); conn.execute('DELETE FROM jobs'); conn.commit(); conn.close()"
remote_wipe = f"docker exec epub-to-audiobook-ui python3 -c {subprocess.list2cmdline([wipe_db])}"

# 2. Fix the mangled icon in index.html
# We'll replace the entire div containing the mangled bytes with a safe one.
# The mangled sequence was inside: <div style="font-size: 5rem; margin-bottom: 24px;">...</div>
fix_html = """p='/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'; 
import re; 
c = open(p, 'r', encoding='utf-8').read(); 
# Target the specific div with the mangled content. 
# We'll use a broad match for the content between the tags if it looks like garbage.
c = re.sub(r'(<div style="font-size: 5rem; margin-bottom: 24px;">)(.*?)(</div>)', r'\\1\u2601\\3', c); # \u2601 is a cloud icon
open(p, 'w', encoding='utf-8').write(c)"""

remote_fix = f"python3 -c {subprocess.list2cmdline([fix_html])}"

# 3. Restart
remote_restart = "cd /home/dave/ai/lab/stacks/epub-to-audiobook && docker compose restart webapp"

subprocess.run(["ssh", "zorin", f"{remote_wipe} && {remote_fix} && {remote_restart}"])