import sqlite3
conn = sqlite3.connect("/data/jobs.db")
conn.execute("DELETE FROM jobs WHERE voice='af_bella'")
conn.commit()
conn.close()