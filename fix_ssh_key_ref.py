with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the specific line in copy_to_audiobookshelf
content = content.replace("'-i', '/root/.ssh/id_ed25519',", "'-i', ssh_key_tmp,")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)