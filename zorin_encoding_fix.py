import os
def fix_encoding(root_dir):
    for r, d, files in os.walk(root_dir):
        if '.git' in r: continue
        for f in files:
            if f.endswith(('.html', '.py', '.sh', '.txt')):
                p = os.path.join(r, f)
                try:
                    with open(p, 'rb') as fin:
                        raw = fin.read(2)
                    if raw == b'\xff\xfe' or raw == b'\xfe\xff':
                        encoding = 'utf-16' if raw == b'\xff\xfe' else 'utf-16-be'
                        print(f"Fixing encoding for {p} ({encoding})")
                        with open(p, 'rb') as fin:
                            text = fin.read().decode(encoding)
                        with open(p, 'w', encoding='utf-8', newline='\n') as fout:
                            fout.write(text)
                except Exception as e:
                    print(f"Error processing {p}: {e}")

fix_encoding('.')