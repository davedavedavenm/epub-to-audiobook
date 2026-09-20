"""
build_and_sync.py — Rebuild Armed Struggle.m4b and sync to Audiobookshelf.
"""

import os
import json
import subprocess
from pathlib import Path
from mutagen.mp3 import MP3

root = Path(__file__).resolve().parents[1]
audio_dir = root / "output" / "armed_struggle_cillian"

chapters_def = [
    ("08 - Preface.mp3", "Preface"),
    ("09 - One The Irish Revolution Nineteen Sixteen 23.mp3", "One The Irish Revolution Nineteen Sixteen 23"),
    ("10 - Two New States Nineteen Twenty Three 63.mp3", "Two New States Nineteen Twenty Three 63"),
]

print("1. Calculating chapter timings...")
available_chapters = [(fn, t) for fn, t in chapters_def if (audio_dir / fn).exists()]
chapters_meta = []
current_time = 0.0
chapter_durations = {}

for idx, (fname, title) in enumerate(available_chapters):
    fpath = audio_dir / fname
    dur = float(MP3(str(fpath)).info.length)
    chapter_durations[idx] = dur
    end_time = current_time + dur
    chapters_meta.append({
        "start": round(current_time, 3),
        "end": round(end_time, 3),
        "title": title,
        "id": idx
    })
    current_time = end_time

total_duration = round(current_time, 3)
print(f"Total audio duration: {total_duration:.1f}s ({total_duration/3600:.2f} hours)")

# Build metadata.json
metadata = {
    "tags": [],
    "chapters": chapters_meta,
    "title": "Armed Struggle",
    "subtitle": "Armed Struggle- The Story of the IRA_5bd54041",
    "authors": ["Richard English"],
    "narrators": ["Cillian Murphy (Breeze 2 Studio Irish Clone)"],
    "series": [],
    "genres": ["Audiobook", "History", "Irish History"],
    "publishedYear": "2008",
    "publishedDate": None,
    "publisher": None,
    "description": "Richard English's definitive history of the IRA, narrated in authentic studio Irish by Cillian Murphy (Breeze TTS 2).",
    "isbn": None,
    "asin": None,
    "language": "eng",
    "explicit": False,
    "abridged": False
}
meta_file = audio_dir / "metadata.json"
meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

# Build ffmpeg metadata & concat file
concat_list = audio_dir / "concat_list.txt"
with open(concat_list, "w", encoding="utf-8") as f:
    for fname, _ in available_chapters:
        p = (audio_dir / fname).resolve()
        f.write(f"file '{str(p).replace(chr(92), '/')}'\n")

meta_txt = audio_dir / "ffmetadata.txt"
with open(meta_txt, "w", encoding="utf-8") as f:
    f.write(";FFMETADATA1\n")
    f.write("title=Armed Struggle: The Story of the IRA\n")
    f.write("artist=Richard English\n")
    f.write("album=Armed Struggle\n")
    f.write("composer=Cillian Murphy (Breeze 2)\n")
    for ch in chapters_meta:
        f.write("[CHAPTER]\nTIMEBASE=1/1000\n")
        f.write(f"START={int(ch['start'] * 1000)}\n")
        f.write(f"END={int(ch['end'] * 1000)}\n")
        f.write(f"title={ch['title']}\n")

m4b_path = audio_dir / "Armed Struggle.m4b"
print("2. Building Armed Struggle.m4b...")
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", str(concat_list),
    "-i", str(meta_txt),
    "-map_metadata", "1",
    "-codec:a", "aac", "-b:a", "128k",
    str(m4b_path)
]
subprocess.run(ffmpeg_cmd, check=True)
print(f"✓ Armed Struggle.m4b built: {m4b_path.stat().st_size:,} bytes")

print("3. Syncing files to docker-vm...")
remote_dir = "/opt/stacks/audiobookshelf/audiobooks/Richard English - Armed Struggle- The Story of the IRA_5bd54041"
files_to_sync = [str(m4b_path), str(meta_file)]
for fname, _ in available_chapters:
    files_to_sync.append(str(audio_dir / fname))

subprocess.run(["scp"] + files_to_sync + [f"docker-vm:{remote_dir}/"], check=True)
print("✓ Files synced via scp!")

print("4. Updating Audiobookshelf progress database...")
new_ch2_start = chapters_meta[2]["start"]
new_ch2_dur = chapter_durations[2]
offset_in_ch2 = min(2350.0, new_ch2_dur - 10.0)
new_current_time = round(new_ch2_start + offset_in_ch2, 2)
print(f"   Recalibrated position: {new_current_time}s ({new_current_time/60:.1f} min total, {offset_in_ch2/60:.1f} min into Ch2)")

sql_cmd = f"UPDATE mediaProgresses SET currentTime = {new_current_time}, duration = {total_duration}, updatedAt = datetime('now') WHERE mediaItemId = '7039379c-0265-4597-9fd8-d083da521f03';"
pipe_cmd = f'echo "{sql_cmd}" | ssh docker-vm "sudo sqlite3 /opt/stacks/audiobookshelf/config/absdatabase.sqlite"'
subprocess.run(pipe_cmd, shell=True, check=True)
print("✓ Database progress updated!")

print("5. Triggering ABS library scan...")
scan_curl = 'curl -s -X POST -H "Authorization: Bearer $(grep ABS_API_TOKEN /home/dave/ai/lab/stacks/epub-to-audiobook/.env | cut -d= -f2)" http://localhost:13378/api/libraries/items/a1726d71-36d8-4b16-a9b8-d03106fdd781/scan'
subprocess.run(["ssh", "docker-vm", scan_curl], check=False)
print("✓ Scan triggered! All done!")
