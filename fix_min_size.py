with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("min_total_mb = 0.1 if (start_chapter and end_chapter and end_chapter - start_chapter < 3) else 1.0",
                          "min_total_mb = 0.01")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)