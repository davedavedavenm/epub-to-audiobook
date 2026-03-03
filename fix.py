import re
with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# remove existing init_db() calls
content = re.sub(r'^[ \t]*init_db\(\).*$', '', content, flags=re.MULTILINE)

# append to the end of the file right before if __name__ == '__main__':
content = content.replace("if __name__ == '__main__':", "init_db()\n\nif __name__ == '__main__':")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
