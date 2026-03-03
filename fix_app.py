import re
with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\n*init_db\(\)  # Initialize database\n*', '\n', content)
content = content.replace("if __name__ == '__main__':", "init_db()  # Initialize database\n\nif __name__ == '__main__':")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
