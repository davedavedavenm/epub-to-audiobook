import sys

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for line in lines:
    if '${LIBRARY_DIR' in line and not line.strip().startswith('#'):
        out.append('# ' + line)
    else:
        out.append(line)

with open('docker-compose.yml', 'w', encoding='utf-8') as f:
    f.writelines(out)