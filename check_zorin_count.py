import subprocess
check_db = "import sqlite3; conn=sqlite3.connect('/data/jobs.db'); print(conn.execute('SELECT COUNT(id) FROM jobs').fetchone()[0]); conn.close()"
subprocess.run(["ssh", "zorin", f"docker exec epub-to-audiobook-ui python3 -c {subprocess.list2cmdline([check_db])}"])