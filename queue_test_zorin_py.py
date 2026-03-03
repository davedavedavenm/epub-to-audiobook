import subprocess

py_script = """import sqlite3, datetime
conn = sqlite3.connect("/data/jobs.db")
c = conn.cursor()
c.execute("INSERT OR REPLACE INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at) VALUES ('test-ryan', 'NLP Pacing Test', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'nlp_test.epub', 'nlp_test_ryan', ?)", (datetime.datetime.now().isoformat(),))
conn.commit()
conn.close()
"""

remote_cmd = f"""cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker exec epub-to-audiobook-ui python3 -c {subprocess.list2cmdline([py_script])} && \
docker logs --tail 20 epub-to-audiobook-worker"""

cmd = ['ssh', 'zorin', remote_cmd]
subprocess.run(cmd)