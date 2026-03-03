import subprocess
remote_cmd = """python3 -c "
with open('/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/app.py', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'Stage 2: EPUB3 with SMIL' in line:
        print(f'Line {i}: {line.strip()}')
        # print 5 lines before
        for j in range(i-5, i):
            print(f'  {lines[j].strip()}')
"
"""
subprocess.run(["ssh", "zorin", remote_cmd])