import sqlite3
conn = sqlite3.connect("/data/jobs.db")
c = conn.cursor()
c.execute("UPDATE jobs SET status = 'queued', container_name = NULL, retry_count = 0 WHERE id IN ('job-modest', 'job-jekyll')")
conn.commit()
conn.close()