import re
with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r"MIN_CHAPTER_SIZE_KB = int\(os\.environ\.get\('MIN_CHAPTER_SIZE_KB', '\d+'\)\)", 
                 "MIN_CHAPTER_SIZE_KB = 0", content)

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)