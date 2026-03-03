import subprocess
remote_cmd = "docker exec epub-to-audiobook-ui python3 -c \"with open('/app/app.py', 'r') as f: lines = f.readlines(); print(''.join(lines[2950:2980]))\""
subprocess.run(["ssh", "zorin", remote_cmd])