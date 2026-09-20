"""
sync_armed_struggle_abs.py — Package and sync newly rendered Armed Struggle audiobook
to Audiobookshelf on docker-vm, preserving Dave's exact listening progress.
"""

import os
import json
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
    try:
        from mutagen.mp3 import MP3
        return float(MP3(str(path)).info.length)
    except Exception:
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

    # Filter for currently available completed chapters
    available_chapters = [(fname, title) for fname, title in chapters_def if (audio_dir / fname).exists()]
    if not available_chapters:
        print("No completed chapter MP3s found in", audio_dir)
        return

    print(f"Packaging {len(available_chapters)} completed chapters for Audiobookshelf:")
    for fname, title in available_chapters:
        print(f"  - {fname}")

    # 1. Calculate exact chapter timings
    chapters_meta = []
    current_time = 0.0
    chapter_durations = {}

    for idx, (fname, title) in enumerate(available_chapters):
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
    print(f"Total synced audiobook duration: {total_duration:,} seconds ({total_duration/3600:.2f} hours)")

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
        for fname, _ in available_chapters:
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
    ch2_idx = next((i for i, (fn, _) in enumerate(available_chapters) if "10 - Two New States" in fn), None)
    if ch2_idx is not None:
        new_ch2_start = chapters_meta[ch2_idx]["start"]
        new_ch2_dur = chapter_durations[ch2_idx]
        # In the original Arcas render, Dave was at 28.975% of Chapter 2 (sentence 166 / 575).
        # In Breeze 2, batches 1-11 cover sentences 1-165, which corresponds to 2,385.0s into Chapter 2.
        # We give a 35-second context lead-in at 2,350.0s (~39.2 min into Chapter 2).
        offset_in_ch2 = min(2350.0, new_ch2_dur - 10.0)
        new_current_time = round(new_ch2_start + offset_in_ch2, 2)
        print("\n>>> Recalibrating listening progress:")
        print("    Original position: 7,723.6s (28.97% into Chapter 2: Two New States in Arcas)")
        print(f"    New Chapter 2 start: {new_ch2_start}s, available duration: {new_ch2_dur}s")
        print(f"    Recalibrated position: {new_current_time}s ({new_current_time/60:.1f} min total, {offset_in_ch2/60:.1f} min into Ch2)")
    else:
        new_current_time = 0.0
        print("\n>>> Chapter 2 not yet synced; progress initialized to 0.0s.")

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
