import os
p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
with open(p, 'rb') as f:
    raw = f.read()

# Remove BOMs if any
raw = raw.replace(b'\xef\xbb\xbf', b'')
raw = raw.replace(b'\xff\xfe', b'')

# Convert to string, replacing all non-ASCII with space or safe equivalent
text = raw.decode('utf-8', errors='ignore')

# Use a safe ASCII-only map for specific symbols if possible, 
# but for now let's just strip non-ASCII to be 100% sure the UI is clean.
clean_text = "".join([i if ord(i) < 128 else " " for i in text])

with open(p, 'w', encoding='utf-8') as f:
    f.write(clean_text)