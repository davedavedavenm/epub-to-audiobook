import sqlite3
conn = sqlite3.connect('/data/jobs.db')
c = conn.cursor()
res = c.execute("SELECT sync_status, sync_error FROM jobs WHERE id = 'test-ryan'").fetchone()
if res:
    print(f"Status: {res[0]}\nError: {res[1]}")
else:
    print("Job not found")
conn.close()