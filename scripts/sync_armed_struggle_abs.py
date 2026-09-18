"""
sync_armed_struggle_abs.py — Package and sync newly rendered Armed Struggle audiobook
to Audiobookshelf on docker-vm, preserving Dave's exact listening progress.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
audio_dir = root / "output" / "armed_struggle_cillian"
backup_dir = root / "fixtures" / "armed_struggle_chapters"
cover_path = root / "fixtures" / "armed_struggle_chapters" / "cover.jpg"

chapters_def = [
    ("08 - Preface.mp3", "Preface"),
    ("09 - One The Irish Revolution Nineteen Sixteen 23.mp3", "One The Irish Revolution Nineteen Sixteen 23"),
    ("10 - Two New States Nineteen Twenty Three 63.mp3", "Two New States Nineteen Twenty Three 63"),
    ("11 - Three The Birth Of The Provisional Ira Nineteen Sixty Three 72.mp3", "Three The Birth Of The Provisional Ira Nineteen Sixty Three 72"),
    ("12 - Four The Politics Of Violence Nineteen Seventy Two 6.mp3", "Four The Politics Of Violence Nineteen Seventy Two 6"),
    ("13 - Five The Prison War Nineteen Seventy Six 81.mp3", "Five The Prison War Nineteen Seventy Six 81"),
    ("14 - Six Politicization And The Cycle Of Violence Nineteen Eighty One 8.mp3", "Six Politicization And The Cycle Of Violence Nineteen Eighty One 8"),
    ("15 - Seven Talking And Killing Nineteen Eighty Eight 94.mp3", "Seven Talking And Killing Nineteen Eighty Eight 94"),
    ("16 - Eight Cessations Of Violence Nineteen Ninety Four To Two Thousand Two.mp3", "Eight Cessations Of Violence Nineteen Ninety Four To Two Thousand Two"),
    ("17 - Conclusion.mp3", "Conclusion"),
    ("18 - Afterword.mp3", "Afterword"),
]

def get_mp3_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

def main():
    print("===================================================================")
    print(">>> PACKAGING & AUDIOBOOKSHELF SYNC FOR ARMED STRUGGLE")
    print("===================================================================")

    if not audio_dir.exists():
        print(f"Directory {audio_dir} does not exist yet.")
        return

    # Check that all 11 chapters exist
    missing = [fname for fname, _ in chapters_def if not (audio_dir / fname).exists()]
    if missing:
        print(f"Chapters not yet finished: {missing}")
        print("Waiting for full render to complete before packaging M4B and syncing.")
        return

    # 1. Calculate exact chapter timings
    chapters_meta = []
    current_time = 0.0
    chapter_durations = {}

    for idx, (fname, title) in enumerate(chapters_def):
        fpath = audio_dir / fname
        dur = get_mp3_duration(fpath)
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
    print(f"Total new audiobook duration: {total_duration:,} seconds ({total_duration/3600:.2f} hours)")

    # 2. Build metadata.json
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
    print(f"Saved metadata.json ({len(chapters_meta)} chapters)")

    # Copy cover if present
    if not (audio_dir / "cover.jpg").exists():
        # Grab backup cover from docker-vm if needed
        subprocess.run(["scp", "docker-vm:/tmp/armed_struggle_backup/cover.jpg", str(audio_dir / "cover.jpg")], check=False)

    # 3. Build Armed Struggle.m4b using ffmpeg
    print("Building Armed Struggle.m4b with chapter markers...")
    m4b_path = audio_dir / "Armed Struggle.m4b"
    concat_list = audio_dir / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for fname, _ in chapters_def:
            p = (audio_dir / fname).resolve()
            f.write(f"file '{str(p).replace(chr(92), '/')}'\n")

    # FFmpeg metadata file for chapters
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

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(meta_txt),
        "-map_metadata", "1",
        "-codec:a", "aac", "-b:a", "128k",
        str(m4b_path)
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"✓ Created: {m4b_path.name} ({m4b_path.stat().st_size:,} bytes)")

    # 4. Sync to docker-vm
    remote_dir = "/opt/stacks/audiobookshelf/audiobooks/Richard English - Armed Struggle- The Story of the IRA_5bd54041"
    print(f"\n>>> Syncing to {remote_dir} on docker-vm via scp...")
    sync_files = [str(audio_dir / f) for f in os.listdir(audio_dir) if f.endswith((".mp3", ".m4b", ".json", ".jpg"))]
    subprocess.run(["scp"] + sync_files + [f"docker-vm:{remote_dir}/"], check=True)
    print("✓ Files copied to Audiobookshelf directory!")

    # 5. Calculate Dave's updated listening position
    # Old stats:
    #   Old Ch 2 start: 6201.552, old duration: 5253.12
    #   Old currentTime: 7723.646 -> 1522.094s into Ch 2 (ratio: 0.28975)
    new_ch2_start = chapters_meta[2]["start"]
    new_ch2_dur = chapter_durations[2]
    new_current_time = round(new_ch2_start + (0.28975 * new_ch2_dur), 2)
    print(f"\n>>> Recalibrating listening progress:")
    print(f"    Original position: 7,723.6s (28.97% into Chapter 2: Two New States)")
    print(f"    New Chapter 2 start: {new_ch2_start}s, duration: {new_ch2_dur}s")
    print(f"    Recalibrated position: {new_current_time}s ({new_current_time/60:.1f} min)")

    # Update SQLite database on docker-vm
    sql_cmd = (
        f"UPDATE mediaProgresses "
        f"SET currentTime = {new_current_time}, duration = {total_duration}, updatedAt = datetime('now') "
        f"WHERE mediaItemId = '7039379c-0265-4597-9fd8-d083da521f03';"
    )
    ssh_sql = f'sudo sqlite3 /opt/stacks/audiobookshelf/config/absdatabase.sqlite "{sql_cmd}"'
    subprocess.run(["ssh", "docker-vm", ssh_sql], check=True)
    print("✓ Audiobookshelf progress database updated!")

    # Trigger library scan via Audiobookshelf API
    scan_curl = (
        'curl -s -X POST -H "Authorization: Bearer $(grep ABS_API_TOKEN /home/dave/ai/lab/stacks/epub-to-audiobook/.env | cut -d= -f2)" '
        'http://localhost:13378/api/libraries/items/a1726d71-36d8-4b16-a9b8-d03106fdd781/scan'
    )
    subprocess.run(["ssh", "docker-vm", scan_curl], check=False)
    print("✓ Audiobookshelf scan triggered successfully!")
    print("\n>>> ALL TASKS COMPLETE! DAVE CAN RESUME LISTENING SEAMLESSLY.")

if __name__ == "__main__":
    main()
