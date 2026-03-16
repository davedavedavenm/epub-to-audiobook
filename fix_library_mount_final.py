with open('docker-compose.yml', 'r', encoding='utf-8') as f:
    c = f.read()

# Fix the mount properly
c = c.replace('/data/library:/data/library', '/mnt/openbooks:/mnt/openbooks:ro')
# Fix the env default
c = c.replace('LIBRARY_DIR=${LIBRARY_DIR:-/data/library}', 'LIBRARY_DIR=${LIBRARY_DIR:-/mnt/openbooks}')

with open('docker-compose.yml', 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)