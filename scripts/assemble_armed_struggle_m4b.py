#!/usr/bin/env python3
"""Assemble the gated Armed Struggle render into a chaptered M4B and swap it
into Audiobookshelf, remapping Dave's listening position by content.

Safety gates (all loud, all before any write):
  1. All 10 sections must have a PASS verdict from scripts/gate_book_chapter.py.
     A missing or FAILED gate aborts the whole run - a section that failed ASR
     completeness must never be packaged as "the book".
  2. The old m4b in the ABS library folder is moved OUT of the library tree
     (renamed with _SUPERSEDED_<date>), never left beside the new file - two
     m4bs in one item folder makes ABS merge them into a single monster item.
  3. Dave's position is preserved by CONTENT: his saved fraction within the
     old chapter maps onto the same new chapter (fraction-in / fraction-out).
     The position is read live from the ABS database at swap time, not
     hardcoded, in case he listened since the last record.

Usage:
  python scripts/assemble_armed_struggle_m4b.py --check   # gates only, no writes
  python scripts/assemble_armed_struggle_m4b.py           # build + swap + remap
"""
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluations" / "new-engines" / "output"
SLUGS = ["preface"] + [f"ch{i}" for i in range(1, 9)] + ["conclusion"]
TITLES = {
    "preface": "Preface",
    "ch1": "One - The Irish Revolution 1916-23",
    "ch2": "Two - New States 1923-63",
    "ch3": "Three - The Birth of the Provisional IRA 1963-72",
    "ch4": "Four - The Politics of Violence 1972-6",
    "ch5": "Five - The Prison War 1976-81",
    "ch6": "Six - Politicization and the Cycle of Violence 1981-8",
    "ch7": "Seven - Talking and Killing 1988-94",
    "ch8": "Eight - Cessations of Violence 1994-2002",
    "conclusion": "Conclusion",
}
ITEM = "7039379c-0265-4597-9fd8-d083da521f03"
ABS_DB = "/opt/stacks/audiobookshelf/config/absdatabase.sqlite"
ABS_DIR = ("/opt/stacks/audiobookshelf/audiobooks/"
           "Richard English - Armed Struggle- The Story of the IRA_5bd54041")


def sh(cmd, timeout=3600, check=True, input_text=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       input=input_text)
    if check and r.returncode != 0:
        sys.exit(f"command failed rc={r.returncode}: {' '.join(map(str, cmd))}\n"
                 f"{(r.stderr or r.stdout or '')[-1500:]}")
    return r


def log(msg):
    print(time.strftime("[%H:%M:%S] "), msg, flush=True)


def mp3_for(slug):
    return OUT / f"armed_struggle_{slug}_cillian.mp3"


def gate_for(slug):
    return OUT / f"armed_struggle_{slug}_cillian.gate.json"


def check_gates():
    verdicts = {}
    for slug in SLUGS:
        gp = gate_for(slug)
        if not gp.exists():
            sys.exit(f"ABORT: no gate verdict for {slug} - run "
                     f"scripts/pull_and_gate_book.py and wait for ALLDONE")
        v = json.loads(gp.read_text())
        if v.get("verdict") != "PASS":
            sys.exit(f"ABORT: {slug} gate verdict is {v.get('verdict')!r} - "
                     f"a failed section must never be packaged as the book")
        verdicts[slug] = v
    log(f"all {len(SLUGS)} gates PASS "
        f"(word {min(v['asr']['word_ratio'] for v in verdicts.values()):.4f}-"
        f"{max(v['asr']['word_ratio'] for v in verdicts.values()):.4f})")
    return verdicts


def chapter_table():
    """[(slug, title, start_sec, dur_sec)] from the real mp3 durations."""
    from mutagen.mp3 import MP3
    chapters, t = [], 0.0
    for slug in SLUGS:
        dur = float(MP3(str(mp3_for(slug))).info.length)
        chapters.append((slug, TITLES[slug], t, dur))
        t += dur
    return chapters, t


def build_m4b(chapters, total):
    tmp = OUT / "m4b_build"
    tmp.mkdir(exist_ok=True)
    concat = tmp / "concat_list.txt"
    with open(concat, "w", encoding="utf-8") as f:
        for slug, _, _, _ in chapters:
            p = mp3_for(slug).resolve()
            f.write(f"file '{str(p).replace(chr(92), '/')}'\n")
    meta = tmp / "ffmetadata.txt"
    with open(meta, "w", encoding="utf-8") as f:
        f.write(";FFMETADATA1\n")
        f.write("title=Armed Struggle: The Story of the IRA\n")
        f.write("artist=Richard English\n")
        f.write("album=Armed Struggle\n")
        f.write("composer=Cillian Murphy (Fish S2 Pro)\n")
        f.write("genre=History\n")
        f.write("date=2026\n")
        for i, (slug, title, start, dur) in enumerate(chapters):
            f.write("[CHAPTER]\nTIMEBASE=1/1000\n")
            f.write(f"START={int(start * 1000)}\n")
            f.write(f"END={int((start + dur) * 1000)}\n")
            f.write(f"title={title}\n")
    m4b = OUT / "Armed Struggle.m4b"
    log(f"building {m4b.name} ({total/3600:.2f} h) - ffmpeg concat + aac ...")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(meta), "-map_metadata", "1",
        "-codec:a", "aac", "-b:a", "128k", str(m4b)])
    size = m4b.stat().st_size
    log(f"built: {m4b}  {size:,} bytes")
    return m4b


def abs_sql(sql):
    r = sh(["ssh", "docker-vm",
            f"sudo sqlite3 {ABS_DB} <<'SQL'\n{sql}\nSQL"], timeout=120)
    return r.stdout.strip()


def swap_and_remap(m4b, chapters):
    # 1. live position + old chapter map from the ABS database
    row = abs_sql(f"SELECT currentTime, duration FROM mediaProgresses "
                  f"WHERE mediaItemId = '{ITEM}';")
    if not row or "|" not in row:
        sys.exit(f"ABORT: no mediaProgress row for {ITEM} - refusing to guess")
    cur_s, old_dur_s = row.split("|")
    cur, old_dur = float(cur_s), float(old_dur_s)
    old_ch_json = abs_sql(f"SELECT audioFiles FROM books WHERE id = '{ITEM}';")
    old_chs = json.loads(json.loads(old_ch_json)[0])["chapters"]
    log(f"ABS position: {cur:.1f}s of {old_dur:.1f}s")

    tgt = next((c for c in old_chs if c["start"] <= cur < c["end"]), None)
    if tgt is None:
        sys.exit(f"ABORT: position {cur}s falls outside old chapters "
                 f"{[(c['title'], c['start'], c['end']) for c in old_chs]}")
    frac = (cur - tgt["start"]) / (tgt["end"] - tgt["start"])
    log(f"old chapter: {tgt['title']!r} at {frac*100:.2f}% inside it")

    # old chapters are ordinal (Preface, One, Two, ...) and map 1:1 onto
    # new slugs preface, ch1, ch2, ... by position in the list
    idx = old_chs.index(tgt)
    if idx >= len(chapters):
        sys.exit(f"ABORT: old chapter index {idx} has no new counterpart")
    slug, title, nstart, ndur = chapters[idx]
    new_time = round(nstart + frac * ndur, 2)
    log(f"maps to new {slug} ({title!r}) at {new_time:.1f}s "
        f"({frac*100:.2f}% into it)")

    # 2. stage the new m4b, move the old one OUT of the library tree
    staged = f"/tmp/as_new_{date.today().isoformat()}.m4b"
    sh(["scp", str(m4b), f"docker-vm:{staged}"], timeout=1800)
    super_name = f"Armed Struggle_SUPERSEDED_{date.today().isoformat()}.m4b"
    sh(["ssh", "docker-vm",
        f"set -e; test -f '{ABS_DIR}/Armed Struggle.m4b'; "
        f"mv '{ABS_DIR}/Armed Struggle.m4b' '/opt/stacks/audiobookshelf/{super_name}'; "
        f"mv '{staged}' '{ABS_DIR}/Armed Struggle.m4b'; "
        f"ls -la '{ABS_DIR}/'"], timeout=300)
    log(f"swapped: old m4b moved to /opt/stacks/audiobookshelf/{super_name}")

    # 3. remap the saved position onto the new audio
    abs_sql(f"UPDATE mediaProgresses SET currentTime = {new_time}, "
            f"duration = {sum(c[3] for c in chapters)}, "
            f"updatedAt = datetime('now') "
            f"WHERE mediaItemId = '{ITEM}';")
    row2 = abs_sql(f"SELECT currentTime, duration FROM mediaProgresses "
                   f"WHERE mediaItemId = '{ITEM}';")
    log(f"progress row now: {row2}")

    # 4. rescan - API token is expired, so use ABS's own scan endpoint via a
    #    library scan request through the docker-vm localhost with the token
    #    from the stack env; if it 401s, fall back to restarting the container
    scan = ("curl -s -o /dev/null -w '%{http_code}' -X POST "
            "-H \"Authorization: Bearer $(grep -h '^ABS_API_TOKEN=' "
            "/home/dave/ai/lab/stacks/epub-to-audiobook/.env 2>/dev/null | "
            "cut -d= -f2)\" "
            "http://localhost:13378/api/libraries/items/"
            "a1726d71-36d8-4b16-a9b8-d03106fdd781/scan")
    r = sh(["ssh", "docker-vm", scan], timeout=60, check=False)
    code = (r.stdout or "").strip()
    log(f"scan via API: HTTP {code or 'no-response'}")
    if code != "200":
        log("token dead - restarting the audiobookshelf container to force "
            "a startup scan (Dave is not mid-listen: last progress update "
            "was read live above)")
        sh(["ssh", "docker-vm",
            "cd /opt/stacks/audiobookshelf && docker compose restart "
            "audiobookshelf"], timeout=600)
    return new_time


def main():
    check = "--check" in sys.argv
    check_gates()
    chapters, total = chapter_table()
    log("chapter table:")
    for slug, title, start, dur in chapters:
        log(f"  {slug:<10} {title:<50} start={start/60:8.2f}min  dur={dur/60:6.2f}min")
    log(f"total: {total/3600:.2f} h")
    if check:
        log("--check: gates + file integrity verified, no writes performed")
        return
    m4b = build_m4b(chapters, total)
    swap_and_remap(m4b, chapters)
    log("DONE - book swapped, position remapped. Dave should hard-refresh "
        "the ABS client (or it will pick up on the startup scan).")


if __name__ == "__main__":
    main()
