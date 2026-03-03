import os, re

files = ['webapp/app.py', 'webapp/worker.py', 'webapp/tts_preprocess.py']
for f_path in files:
    if not os.path.exists(f_path): continue
    with open(f_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        text = raw.decode('utf-16')
        with open(f_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print(f'Converted {f_path} from UTF-16 to UTF-8')
    else:
        text = raw.decode('utf-8', errors='ignore')
        with open(f_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'^[ \t]*init_db\(\).*$', '', content, flags=re.MULTILINE)
content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
