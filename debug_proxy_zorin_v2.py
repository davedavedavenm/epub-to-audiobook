import subprocess

py_script = """import sys, re
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

remote_cmd = f"""python3 -c '{py_script}' && \
cd /home/dave/ai/lab/stacks/epub-to-audiobook && \
docker compose restart tts-proxy && \
docker exec epub-to-audiobook-ui python3 -c \"import sqlite3; conn = sqlite3.connect('/data/jobs.db'); c = conn.cursor(); c.execute(\\\"UPDATE jobs SET status = 'queued', container_name = NULL, retry_count = 0 WHERE id = 'test-ryan'\\\"); conn.commit(); conn.close()\" && \
sleep 20 && \
docker logs --tail 50 tts-proxy"""

cmd = ['ssh', 'zorin', remote_cmd]
subprocess.run(cmd)