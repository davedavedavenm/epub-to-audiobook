import os

with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for line in lines:
    if 'LIBRARY_DIR=${LIBRARY_DIR:-/mnt/openbooks}' in line:
        # Uncomment and fix
        out.append(line.replace('#       - ', '      - ').replace(':-/data/library}', ':-/mnt/openbooks}'))
    else:
        out.append(line)

with open('docker-compose.yml', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(out)