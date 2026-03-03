p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
with open(p, 'rb') as f:
    raw = f.read()

# Replace all non-ASCII with empty string
clean = bytes([b for b in raw if b < 128])

with open(p, 'wb') as f:
    f.write(clean)