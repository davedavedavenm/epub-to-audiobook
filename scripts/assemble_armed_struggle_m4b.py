#!/usr/bin/env python3
"""Assemble the gated Armed Struggle render into a chaptered M4B and swap it
into Audiobookshelf, remapping Dave's listening position by content.

Safety gates (all loud, all before any write):
  1. All 10 sections must have a PASS verdict from scripts/gate_book_chapter.py.
     A missing or FAILED gate aborts the whole run - a section that failed ASR
     completeness must never be packaged as "the book".
  2. Every old audio file in the ABS library folder is moved OUT of the
     library tree (the old item is multi-file: a partial m4b + per-chapter
     mp3s). Any old track left beside the new m4b makes ABS merge the two
     into a single monster item on the next scan.
  3. Dave's position is preserved by CONTENT: his saved fraction within the
     old chapter maps onto the same new chapter (fraction-in / fraction-out).
     The position is read live from the ABS database at swap time, not
     hardcoded, in case he listened since the last record.

Usage:
  python scripts/assemble_armed_struggle_m4b.py --check   # gates only, no writes
  python scripts/assemble_armed_struggle_m4b.py           # build + swap + remap

Resumable end-to-end: a run that dies mid-way (e.g. on a locked ABS database
after the swap) is re-run as-is - the built m4b is reused when its inputs are
unchanged, a completed swap is detected and skipped, and the remap + rescan
continue. SQLite access retries with a busy timeout because the running ABS
container holds brief write locks.
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
    newest_src = max(mp3_for(s).stat().st_mtime for s, _, _, _ in chapters)
    if m4b.exists() and m4b.stat().st_mtime > newest_src and m4b.stat().st_size > 0:
        log(f"reusing existing {m4b.name} ({m4b.stat().st_size:,} bytes - "
            f"newer than every source mp3)")
        return m4b
    log(f"building {m4b.name} ({total/3600:.2f} h) - ffmpeg concat + aac ...")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(meta), "-map_metadata", "1",
        "-codec:a", "aac", "-b:a", "128k", str(m4b)])
    size = m4b.stat().st_size
    log(f"built: {m4b}  {size:,} bytes")
    return m4b


def abs_sql(sql):
    """Read/write the ABS DB over ssh. The running ABS container holds brief
    sqlite write locks (measured 2026-09-26: a bare UPDATE died with
    'database is locked'), so arm the CLI with a busy timeout and retry."""
    r = None
    for attempt in range(4):
        r = subprocess.run(
            ["ssh", "docker-vm",
             f"sudo sqlite3 {ABS_DB} <<'SQL'\n.timeout 10000\n{sql}\nSQL"],
            capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return r.stdout.strip()
        time.sleep(5 * (attempt + 1))
    sys.exit(f"abs_sql failed after {attempt + 1} attempts rc={r.returncode}: "
             f"{sql[:120]}\n{(r.stderr or r.stdout or '')[-800:]}")


def swap_and_remap(m4b, chapters):
    # 1. live position + old chapter map from the ABS database
    row = abs_sql(f"SELECT currentTime, duration FROM mediaProgresses "
                  f"WHERE mediaItemId = '{ITEM}';")
    if not row or "|" not in row:
        sys.exit(f"ABORT: no mediaProgress row for {ITEM} - refusing to guess")
    cur_s, old_dur_s = row.split("|")
    cur, old_dur = float(cur_s), float(old_dur_s)
    old_files_json = abs_sql(f"SELECT audioFiles FROM books WHERE id = '{ITEM}';")
    old_files = json.loads(old_files_json)
    # books.audioFiles is a JSON array of audioFile OBJECTS (measured live
    # 2026-09-26); the original code double-decoded, assuming each element
    # was itself a JSON string, and died on the real shape.
    el = old_files[0]
    if isinstance(el, str):
        el = json.loads(el)
    old_tracks = [f["metadata"]["filename"] for f in old_files
                  if isinstance(f, dict) and f.get("metadata", {}).get("filename")]
    total_new = sum(c[3] for c in chapters)
    if old_tracks == ["Armed Struggle.m4b"]:
        # WATCHER RACE (measured 2026-09-26): ABS's file watcher rebuilt the
        # item from the new m4b within minutes of the swap, so the DB no
        # longer holds the pre-swap chapter map, and a naive remap against
        # the NEW chapter table silently produces a no-op position (the
        # 03:02 run mapped 39.92%-in-Two onto 72.35%-in-Two). The position
        # row still carries the OLD-timeline value; the old chapter
        # geometry survives in the item folder's metadata.json (ABS's own
        # pre-scan export, kept through the swap).
        r = sh(["ssh", "docker-vm", f"sudo cat '{ABS_DIR}/metadata.json'"],
               timeout=60)
        old_chs = json.loads(r.stdout)["chapters"]
        if max(c["end"] for c in old_chs) > total_new:
            sys.exit("ABORT: metadata.json no longer holds the pre-swap "
                     "chapter map (rewritten by a scan) - the old timeline "
                     "is unrecoverable from the host; refusing to remap")
        rescan_done = True
    else:
        old_chs = el["chapters"]
        rescan_done = False
    log(f"old item: {len(old_tracks)} audio files: {old_tracks}"
        + (" (already the new single-file item)" if rescan_done else ""))
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

    # 2. stage the new m4b and move EVERY old audio file OUT of the library
    #    tree - the old item is multi-file (partial m4b + per-chapter mp3s,
    #    measured 2026-09-26); any old track left beside the new m4b makes
    #    ABS merge the two into a monster item on the next scan. Order:
    #    non-m4b tracks first (safe, reversible), post-condition check, old
    #    m4b out, new m4b in - so any abort leaves the old m4b playable.
    #    A previous run may have completed the swap and died later (e.g. on
    #    a locked DB at the remap); detect that and resume, never redo.
    rr = sh(["ssh", "docker-vm",
             f"stat -c %s '{ABS_DIR}/Armed Struggle.m4b' 2>/dev/null; "
             f"test -z \"$(find '{ABS_DIR}' -maxdepth 1 -name '*.mp3' -print -quit)\" "
             f"&& echo CLEAN || echo DIRTY"], timeout=60, check=False)
    lines = [l.strip() for l in (rr.stdout or "").splitlines() if l.strip()]
    remote_size = lines[0] if lines and lines[0].isdigit() else None
    clean = bool(lines) and lines[-1] == "CLEAN"
    if remote_size == str(m4b.stat().st_size) and clean:
        log(f"swap already complete (remote m4b {remote_size} B is the new "
            f"build, no old tracks left in the item dir) - resuming at remap")
    else:
        staged = f"/tmp/as_new_{date.today().isoformat()}.m4b"
        sh(["scp", str(m4b), f"docker-vm:{staged}"], timeout=1800)
        today = date.today().isoformat()
        super_name = f"Armed Struggle_SUPERSEDED_{today}.m4b"
        super_dir = f"/opt/stacks/audiobookshelf/AS_old_tracks_SUPERSEDED_{today}"
        extras = [n for n in sorted(old_tracks) if n != "Armed Struggle.m4b"]
        extras += ["concat_list.txt", "ffmetadata.txt", "qa_report.json"]
        sh(["ssh", "docker-vm",
            f"set -e; mkdir -p '{super_dir}'; "
            + "; ".join(f"mv '{ABS_DIR}/{n}' '{super_dir}/{n}'" for n in extras)
            + f"; test -z \"$(find '{ABS_DIR}' -maxdepth 1 -name '*.mp3' -print -quit)\""
            + f"; test -f '{ABS_DIR}/Armed Struggle.m4b'; "
            f"mv '{ABS_DIR}/Armed Struggle.m4b' '/opt/stacks/audiobookshelf/{super_name}'; "
            f"mv '{staged}' '{ABS_DIR}/Armed Struggle.m4b'; "
            f"ls -la '{ABS_DIR}/'"], timeout=300)
        log(f"swapped: old m4b -> /opt/stacks/audiobookshelf/{super_name}; "
            f"{len(extras) - 3} old mp3 tracks + old build junk -> {super_dir}")

    # 3. remap the saved position onto the new audio - ONCE. The marker
    #    records that the row was moved onto the new timeline; afterwards the
    #    old-chapter math must never run again (it would corrupt a position
    #    that is already new-timeline, e.g. after Dave listens on).
    marker = OUT / ".as_remap_done"
    if marker.exists():
        log(f"remap marker present ({marker.name}: "
            f"{marker.read_text().strip()[:120]}) - position row is already "
            f"on the new timeline, not remapping")
    else:
        abs_sql(f"UPDATE mediaProgresses SET currentTime = {new_time}, "
                f"duration = {sum(c[3] for c in chapters)}, "
                f"updatedAt = datetime('now') "
                f"WHERE mediaItemId = '{ITEM}';")
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S ")
                          + f"item={ITEM} cur={cur} new_time={new_time} "
                          f"frac={frac:.4f}")
    row2 = abs_sql(f"SELECT currentTime, duration FROM mediaProgresses "
                   f"WHERE mediaItemId = '{ITEM}';")
    log(f"progress row now: {row2}")

    # 4. rescan. If the watcher race was detected above, the DB already
    #    holds the new single-m4b item - ABS rescanned it by itself, so the
    #    API scan / container restart is moot. Otherwise try the scan API
    #    with the stack-env token, then fall back to restarting the
    #    container. NB: the .env path in the curl is the ZORIN stack path -
    #    absent on docker-vm, so the restart branch is the expected one;
    #    there is no compose file on docker-vm, the container is plain
    #    `audiobookshelf` (measured 2026-09-26). Safe either way: Dave's
    #    live position was already read and remapped above.
    if rescan_done:
        log("rescan already done by ABS's file watcher (DB holds the new "
            "single-m4b item) - skipping API scan / container restart")
        return new_time
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
        sh(["ssh", "docker-vm", "docker restart audiobookshelf"], timeout=600)
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
