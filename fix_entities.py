p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
with open(p, 'rb') as f:
    raw = f.read()

# Replace the mangled byte sequences with clean HTML entities
# Library: ≡ƒôÜ
raw = raw.replace(b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc3\x9c', b'&#128214;')
# Upload: ≡ƒô¥
raw = raw.replace(b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc2\xa5', b'&#128229;')
# Queue: ΓÅ│
raw = raw.replace(b'\xce\x93\xc3\x85\xe2\x94\x82', b'&#9203;')
# Voices: ≡ƒùú∩╕Å
raw = raw.replace(b'\xe2\x89\xa1\xc6\x92\xc3\xb9\xc3\xba\xe2\x88\xa9\xe2\x80\xa2\xc3\x85', b'&#128483;')
# History: ≡ƒôÃ
raw = raw.replace(b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc3\x83', b'&#128220;')
# Config: ΓÜâ∩╕Å (or similar)
raw = raw.replace(b'\xce\x93\xc3\x9c\xc3\x96\xe2\x88\xa9\xe2\x80\xa2\xc3\x85', b'&#9881;')

with open(p, 'wb') as f:
    f.write(raw)