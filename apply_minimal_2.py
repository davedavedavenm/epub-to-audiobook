with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Force global setting
content = content.replace("MIN_CHAPTER_SIZE_KB = int(os.environ.get('MIN_CHAPTER_SIZE_KB', '500'))", "MIN_CHAPTER_SIZE_KB = 0")
# Force default param
content = content.replace("min_size_kb: int = 500", "min_size_kb: int = 0")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)