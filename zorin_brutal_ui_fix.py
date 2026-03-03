p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
with open(p, 'rb') as f:
    raw = f.read()

# Brutal byte replacement for the specific Mojibake observed in Playwright
replacements = [
    (b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc3\x9c', b''), # Library
    (b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc2\xa5', b''), # Upload
    (b'\xce\x93\xc3\x85\xe2\x94\x82', b''),         # Queue
    (b'\xe2\x89\xa1\xc6\x92\xc3\xb9\xc3\xba\xe2\x88\xa9\xe2\x80\xa2\xc3\x85', b''), # Voices
    (b'\xe2\x89\xa1\xc6\x92\xc3\xb4\xc3\xaf', b''), # History
    (b'\xce\x93\xc3\x9c\xc3\x96\xe2\x88\xa9\xe2\x80\xa2\xc3\x85', b''),             # Config
    (b'\xce\x93\xc3\xbf\xc3\x87\xe2\x88\xa9\xe2\x80\xa2\xc3\x85', b''),             # Voices tab sub-icons
    (b'\xe2\x89\xa1\xc6\x92\xc3\xae\xc3\x96', b'')
]

for old, new in replacements:
    raw = raw.replace(old, new)

# Also strip any remaining non-ASCII just in case
clean = bytes([b for b in raw if b < 128])

with open(p, 'wb') as f:
    f.write(clean)