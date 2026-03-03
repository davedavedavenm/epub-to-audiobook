import subprocess
remote_cmd = "python3 -c \"with open('/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html', 'rb') as f: print(f.read(50))\""
subprocess.run(["ssh", "zorin", remote_cmd])