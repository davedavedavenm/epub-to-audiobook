with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("def cleanup_small_files(output_dir: Path, min_size_kb: int = 500) -> int:",
                          "def cleanup_small_files(output_dir: Path, min_size_kb: int = 0) -> int:")

with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)