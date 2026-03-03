with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("MIN_CHAPTER_SIZE_KB = 150", "MIN_CHAPTER_SIZE_KB = 0")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)