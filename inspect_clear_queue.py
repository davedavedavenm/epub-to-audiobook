import sqlite3
conn = sqlite3.connect("/data/jobs.db")
c = conn.cursor()
# List current non-finished jobs
res = c.execute("SELECT id, status, book_name, voice FROM jobs WHERE status NOT IN ('completed', 'failed')").fetchall()
print("CURRENT QUEUE:")
for r in res:
    print(r)

# Clear all non-completed/failed jobs if any exist
if res:
    print("\nCLEARING QUEUE...")
    c.execute("DELETE FROM jobs WHERE status NOT IN ('completed', 'failed')")
    conn.commit()
    print("Queue cleared.")

conn.close()