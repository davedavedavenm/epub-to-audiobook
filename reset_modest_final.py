import sqlite3
conn = sqlite3.connect("/data/jobs.db")
conn.execute("UPDATE jobs SET status = 'queued', container_name = NULL, retry_count = 0 WHERE book_name LIKE '%modest%'")
conn.commit()
conn.close()