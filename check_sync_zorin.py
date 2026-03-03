import subprocess
py_script = """import sqlite3
conn = sqlite3.connect('/data/jobs.db')
c = conn.cursor()
res = c.execute("SELECT sync_status, sync_error FROM jobs WHERE id = 'test-ryan'").fetchone()
print(f"Status: {res[0]} | Error: {res[1]}")
conn.close()
"""
remote_cmd = f"docker exec epub-to-audiobook-ui python3 -c \"{py_script}\""
subprocess.run(["ssh", "zorin", remote_cmd])