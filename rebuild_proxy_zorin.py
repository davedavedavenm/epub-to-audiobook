import subprocess

# Rebuild proxy and reset job
remote_cmds = """cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker compose build tts-proxy && \
docker compose up -d tts-proxy && \
docker exec epub-to-audiobook-ui python3 /app/reset_job.py && \
sleep 15 && \
docker logs --tail 50 tts-proxy"""

subprocess.run(["ssh", "zorin", remote_cmds])