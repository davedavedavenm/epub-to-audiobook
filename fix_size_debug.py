with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
content = re.sub(r"min_total_mb = 0\.1 if .*? else 1\.0", "min_total_mb = 0.001", content)

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)