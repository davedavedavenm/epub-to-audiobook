import subprocess
import shlex

remote_cmd = """cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker cp create_test_epub.py epub-to-audiobook-ui:/app/create_test_epub.py && \
docker exec epub-to-audiobook-ui python3 /app/create_test_epub.py && \
sqlite3 data/jobs.db "INSERT OR REPLACE INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at) VALUES ('test-ryan', 'NLP Pacing Test', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'nlp_test.epub', 'nlp_test_ryan', datetime('now'));" && \
docker logs --tail 20 epub-to-audiobook-worker"""

cmd = ['ssh', 'zorin', remote_cmd]
subprocess.run(cmd)