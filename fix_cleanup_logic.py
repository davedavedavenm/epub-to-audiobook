with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("min_bytes = min_size_kb * 1024", 
                          "if min_size_kb <= 0: return 0\n      min_bytes = min_size_kb * 1024")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)