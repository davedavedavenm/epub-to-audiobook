import os

# 1. Update .env to point to the live mount
with open('.env', 'r', encoding='utf-8') as f:
    lines = f.readlines()
with open('.env', 'w', encoding='utf-8', newline='\n') as f:
    for line in lines:
        if line.startswith('LIBRARY_DIR='):
            f.write('LIBRARY_DIR=/mnt/openbooks\n')
        else:
            f.write(line)

# 2. Update docker-compose.yml to use the live mount
with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for line in lines:
    if '/data/library:/data/library' in line:
        # Switch back to host mount
        out.append(line.replace('/data/library:/data/library', '/mnt/openbooks:/mnt/openbooks:ro'))
    elif 'LIBRARY_DIR=${LIBRARY_DIR' in line:
        # Switch back to /mnt/openbooks default
        out.append(line.replace(':-/data/library}', ':-/mnt/openbooks}'))
    else:
        out.append(line)

with open('docker-compose.yml', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(out)