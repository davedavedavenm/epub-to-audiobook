import subprocess

py_script = """import sqlite3
conn = sqlite3.connect("/data/jobs.db")
c = conn.cursor()
c.execute("UPDATE jobs SET status = 'queued', container_name = NULL, retry_count = 0 WHERE id = 'test-ryan'")
conn.commit()
conn.close()
"""

remote_cmd = f"""cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker exec epub-to-audiobook-ui python3 -c {subprocess.list2cmdline([py_script])} && \
sleep 15 && \
docker logs audiobook-test-ryan"""

cmd = ['ssh', 'zorin', remote_cmd]
subprocess.run(cmd)