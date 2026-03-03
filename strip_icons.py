import re
p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Replace emoji icons with plain text labels or remove them
c = re.sub(r'<i>≡ƒôÜ</i>', '<span>📚</span>', c) # Open Book
c = re.sub(r'<i>≡ƒô¥</i>', '<span>📥</span>', c) # Tray
c = re.sub(r'<i>ΓÅ│</i>', '<span>⏳</span>', c) # Hourglass
c = re.sub(r'<i>≡ƒùú∩╕Å</i>', '<span>🗣️</span>', c) # Speaking head
c = re.sub(r'<i>≡ƒôÃ</i>', '<span>📜</span>', c) # History
c = re.sub(r'<i>ΓÜâ∩╕Å</i>', '<span>⚙️</span>', c) # Gear

# Let's just be aggressive and remove the <i>...</i> tags inside .nav-tab if they contain anything weird
c = re.sub(r'<button class="nav-tab.*?><i>.*?</i>', lambda m: m.group(0).split('<i>')[0] + '<i>', c)

# Actually, the safest way is to just use clean emoji or plain text if emojis are failing.
# I will replace them with simple ASCII placeholders for now to PROVE it works.
replacements = {
    'Library': 'LIB',
    'Upload': 'UP',
    'Queue': 'QUE',
    'Voices': 'VOX',
    'History': 'HIS',
    'Config': 'CFG'
}

# Restore clean template first
import subprocess
subprocess.run(['git', 'checkout', p])

with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Replace the <i> tags content with something safe
c = re.sub(r'<i>.*?</i>', '<i></i>', c)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)