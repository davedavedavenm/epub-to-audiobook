import os

# 1. Fix .env
with open('.env', 'r', encoding='utf-8') as f:
    lines = f.readlines()
with open('.env', 'w', encoding='utf-8', newline='\n') as f:
    for line in lines:
        if line.startswith('LIBRARY_DIR='):
            f.write('LIBRARY_DIR=/data/library\n')
        else:
            f.write(line)

# 2. Fix docker-compose.yml (Enable library mount)
with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
in_webapp = False
for line in lines:
    # If we find the commented out library mount, uncomment it
    if '# - ${LIBRARY_DIR' in line:
        out.append(line.replace('# - ', '      - ').replace('/mnt/openbooks', '/data/library'))
    # If we find the environment variable, ensure it's correct
    elif 'LIBRARY_DIR=${LIBRARY_DIR' in line:
        out.append(line.replace(':-/data/uploads}', ':-/data/library}'))
    else:
        out.append(line)

with open('docker-compose.yml', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(out)