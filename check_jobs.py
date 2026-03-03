import subprocess

py_script = """import sqlite3
conn = sqlite3.connect('/data/jobs.db')
c = conn.cursor()
res = c.execute("SELECT status, progress_percent, error, sync_status, sync_error FROM jobs WHERE id IN ('job-modest', 'job-jekyll')").fetchall()
for r in res:
    print(r)
conn.close()
"""
remote_cmd = f"docker exec epub-to-audiobook-ui python3 -c \"{py_script}\""
subprocess.run(["ssh", "zorin", remote_cmd])