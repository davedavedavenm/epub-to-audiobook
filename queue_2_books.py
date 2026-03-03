import subprocess
import os
import sqlite3
import datetime

remote_cmd = """cd /home/dave/ai/lab/stacks/epub-to-audiobook/data/uploads && \
wget -qO modest_proposal.epub https://www.gutenberg.org/ebooks/1080.epub.noimages && \
wget -qO jekyll_hyde.epub https://www.gutenberg.org/ebooks/43.epub.noimages && \
docker exec epub-to-audiobook-ui python3 -c \"import sqlite3, datetime; conn = sqlite3.connect('/data/jobs.db'); c = conn.cursor(); c.execute(\\\"INSERT OR REPLACE INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at) VALUES ('job-modest', 'A Modest Proposal', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'modest_proposal.epub', 'ModestProposal', datetime('now'))\\\"); c.execute(\\\"INSERT OR REPLACE INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at) VALUES ('job-jekyll', 'Dr Jekyll and Mr Hyde', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'jekyll_hyde.epub', 'JekyllHyde', datetime('now'))\\\"); conn.commit(); conn.close()\" && \
docker logs --tail 20 epub-to-audiobook-worker"""

subprocess.run(["ssh", "zorin", remote_cmd])