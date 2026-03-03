with open('webapp/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if 'init_db()' in line and 'def init_db():' not in line:
        continue
    out.append(line)

with open('webapp/app.py', 'w', encoding='utf-8') as f:
    f.writelines(out)

with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
