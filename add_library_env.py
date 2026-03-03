import sys

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for line in lines:
    out.append(line)
    if 'UPLOAD_DIR=/data/uploads' in line:
        indent = line[:line.find('UPLOAD_DIR')]
        out.append(f"{indent}LIBRARY_DIR=${{LIBRARY_DIR:-/data/uploads}}\n")

with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.writelines(out)