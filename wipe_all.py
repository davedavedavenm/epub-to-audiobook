import sqlite3
conn = sqlite3.connect("/data/jobs.db")
conn.execute("DELETE FROM jobs")
conn.commit()
conn.close()