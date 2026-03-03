import subprocess

# Reset and queue script
job_script = """import sqlite3, datetime
conn = sqlite3.connect('/data/jobs.db')
conn.execute("DELETE FROM jobs")
conn.execute("INSERT INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at, start_chapter, end_chapter) VALUES ('final-e2e', 'A Modest Proposal', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'modest_proposal.epub', 'ModestProposal_Final', ?, 1, 3)", (datetime.datetime.now().isoformat(),))
conn.commit()
conn.close()
"""
with open("final_queue.py", "w") as f:
    f.write(job_script)

subprocess.run(["scp", "final_queue.py", "zorin:/home/dave/ai/lab/stacks/epub-to-audiobook/final_queue.py"])

remote_cmds = """cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker cp final_queue.py epub-to-audiobook-ui:/app/final_queue.py && \
docker exec epub-to-audiobook-ui python3 /app/final_queue.py && \
sleep 15 && \
docker logs --tail 20 epub-to-audiobook-worker"""

subprocess.run(["ssh", "zorin", remote_cmds])