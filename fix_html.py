with open('/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html', 'rb') as f:
    raw = f.read()
if raw.startswith(b'\xff\xfe'):
    text = raw.decode('utf-16')
    with open('/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Converted to UTF-8')
else:
    print('Already UTF-8')