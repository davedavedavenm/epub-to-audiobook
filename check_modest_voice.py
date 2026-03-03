import sqlite3
conn = sqlite3.connect("/data/jobs.db")
r = conn.execute("SELECT id, voice, status FROM jobs WHERE book_name LIKE '%modest%' ORDER BY created_at DESC LIMIT 1").fetchone()
print(f"ID: {r[0]} | Voice: {r[1]} | Status: {r[2]}")
conn.close()