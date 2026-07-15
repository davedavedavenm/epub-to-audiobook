import pytest
from pathlib import Path
import tempfile
import re

# Copy definitions of find_missing_chapters and get_mp3_duration to avoid ebooklib dependency during local Windows testing
def find_missing_chapters(output_dir: Path, total_chapters: int,
                          start_chapter: int | None = None,
                          end_chapter: int | None = None) -> list[int]:
    existing = set()
    if output_dir.exists():
        for f in output_dir.glob('*.mp3'):
            m = re.match(r'^(\d{3,4})(?:[_\-\.\s]|$)', f.name)
            if m:
                existing.add(int(m.group(1)))

    first = start_chapter or 1
    last = end_chapter or total_chapters
    return [ch for ch in range(first, last + 1) if ch not in existing]

def get_mp3_duration(path: Path) -> float:
    try:
        import subprocess
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', str(path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0

def test_find_missing_chapters_3_digit():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create some mock 3-digit MP3 files
        (tmp_path / "001.mp3").write_bytes(b"dummy audio")
        (tmp_path / "002_Chapter_2.mp3").write_bytes(b"dummy audio")
        (tmp_path / "004.mp3").write_bytes(b"dummy audio")
        
        # total 4 chapters, start=1, end=4
        missing = find_missing_chapters(tmp_path, total_chapters=4, start_chapter=1, end_chapter=4)
        assert missing == [3]  # Only chapter 3 is missing

def test_find_missing_chapters_4_digit():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Create some mock 4-digit MP3 files (p0n1 style)
        (tmp_path / "0001_intro.mp3").write_bytes(b"dummy audio")
        (tmp_path / "0003_story.mp3").write_bytes(b"dummy audio")
        
        # total 3 chapters
        missing = find_missing_chapters(tmp_path, total_chapters=3)
        assert missing == [2]  # Only chapter 2 is missing

def test_find_missing_chapters_mixed():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Mix of formats
        (tmp_path / "001.mp3").write_bytes(b"dummy audio")
        (tmp_path / "0002_chapter.mp3").write_bytes(b"dummy audio")
        (tmp_path / "004_chapter.mp3").write_bytes(b"dummy audio")
        
        missing = find_missing_chapters(tmp_path, total_chapters=4)
        assert missing == [3]  # Only chapter 3 is missing

def test_get_mp3_duration_non_existent():
    assert get_mp3_duration(Path("/nonexistent/file.mp3")) == 0.0
