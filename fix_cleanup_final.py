import re
with open('webapp/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_func = """def cleanup_small_files(output_dir: Path, min_size_kb: int = 0) -> int:
    '''Remove MP3 files smaller than min_size_kb.

    These are typically photo captions, part dividers, or other noise
    that the EPUB converter produced from non-textual content.
    Returns the count of files removed.
    '''
    removed = 0
    if min_size_kb <= 0:
        return 0

    min_bytes = min_size_kb * 1024
    for mp3_file in sorted(output_dir.glob("*.mp3")):
        if mp3_file.stat().st_size < min_bytes:
            print(f"Removing small file ({mp3_file.stat().st_size} bytes): {mp3_file.name}")
            mp3_file.unlink()
            removed += 1
    if removed:
        # Renumber remaining files sequentially
        remaining = sorted(output_dir.glob("*.mp3"))
        for idx, mp3_file in enumerate(remaining, 1):
            # Extract name after the track number prefix
            match = re.match(r"^\d+\s*-\s*(.*)$", mp3_file.stem)
            chapter_name = match.group(1) if match else mp3_file.stem
            new_name = f"{idx:02d} - {chapter_name}.mp3"
            new_path = output_dir / new_name
            if new_path != mp3_file:
                mp3_file.rename(new_path)
    return removed
"""

start_marker = "def cleanup_small_files("
end_marker = "\n    return removed\n"

start_pos = content.find(start_marker)
end_pos = content.find(end_marker, start_pos)

if start_pos != -1 and end_pos != -1:
    full_end = end_pos + len(end_marker)
    new_content = content[:start_pos] + new_func + content[full_end:]
    with open('webapp/app.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print("Successfully replaced cleanup_small_files")
else:
    print(f"Could not find markers: {start_pos}, {end_pos}")