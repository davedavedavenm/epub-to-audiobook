import subprocess

# 1. Update Proxy Script (Runs on Zorin)
proxy_update = """import sys, re
with open('/home/dave/ai/lab/stacks/epub-to-audiobook/tts_proxy/proxy.py', 'r') as f:
    c = f.read()

debug_log = '''    except Exception as e:
        print(f"Exception parsing JSON: {e}")
        try:
            body = await request.body()
            print(f"Raw body: {body}")
        except: pass
        raise HTTPException(status_code=400, detail="Invalid JSON")'''

c = re.sub(r'    except Exception:.*?\n.*?raise HTTPException\(status_code=400, detail="Invalid JSON"\)', debug_log, c, flags=re.DOTALL)

with open('/home/dave/ai/lab/stacks/epub-to-audiobook/tts_proxy/proxy.py', 'w') as f:
    f.write(c)
"""
with open("update_proxy_zorin.py", "w") as f:
    f.write(proxy_update)

subprocess.run(["scp", "update_proxy_zorin.py", "zorin:/home/dave/ai/lab/stacks/epub-to-audiobook/update_proxy_zorin.py"])

# 2. Reset Job Script (Runs inside webapp container on Zorin)
job_reset = """import sqlite3
conn = sqlite3.connect('/data/jobs.db')
c = conn.cursor()
c.execute("UPDATE jobs SET status = 'queued', container_name = NULL, retry_count = 0 WHERE id = 'test-ryan'")
conn.commit()
conn.close()
"""
with open("reset_job.py", "w") as f:
    f.write(job_reset)

subprocess.run(["scp", "reset_job.py", "zorin:/home/dave/ai/lab/stacks/epub-to-audiobook/reset_job.py"])

# 3. Execute all commands on Zorin
remote_cmds = """cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
python3 update_proxy_zorin.py && \
docker compose restart tts-proxy && \
docker cp reset_job.py epub-to-audiobook-ui:/app/reset_job.py && \
docker exec epub-to-audiobook-ui python3 /app/reset_job.py && \
sleep 20 && \
docker logs --tail 50 tts-proxy"""

subprocess.run(["ssh", "zorin", remote_cmds])