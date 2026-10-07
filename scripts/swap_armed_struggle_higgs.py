#!/usr/bin/env python3
"""Swap the Higgs (Cillian clone) Armed Struggle into Audiobookshelf and move Dave's place BY CONTENT.

Inputs (all produced by scripts/modal_higgs_book.py + the Colab lane adoption):
  scratch/modal_higgs_book/armed_struggle/chapters/NNN_<title>.mp3   one per bundle chapter
  scratch/modal_higgs_book/armed_struggle/chunks/<slug>/NNNN.wav     to rebuild each chapter's timeline
  scratch/modal_higgs_book/armed_struggle/audit/<slug>.asr.json      independent per-chunk ASR (chunk_asr_audit)

Position: the previous swap tool mapped "fraction through the old chapter" onto the new chapter;
with a different narrator's pacing that can be minutes out. Here the place is found by WORDS: 45 s
of the old m4b at the saved position was transcribed (2026-10-07: "Hundreds of pedestrians and city
workers were stopped in the streets..."), located in the new text (ch10 chunk 142, 30 words in),
and converted to a time through the V3 assembly timeline of that chapter. If the live position is
no longer the one the anchor was taken at, the script refuses - re-take the anchor.

Usage:
  python scripts/swap_armed_struggle_higgs.py --check     # gates + chapter table + new position, no writes
  python scripts/swap_armed_struggle_higgs.py             # build m4b, swap, set position, rescan
Dave must have the ABS player CLOSED (an open player re-uploads its old position).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "webapp")]

BOOK = ROOT / "scratch" / "modal_higgs_book" / "armed_struggle"
BUNDLE = ROOT / "scratch" / "modal_higgs_book" / "armed_struggle_bundle.zip"
ITEM = "7039379c-0265-4597-9fd8-d083da521f03"
LIB_ITEM = "a1726d71-36d8-4b16-a9b8-d03106fdd781"
ABS_DB = "/opt/stacks/audiobookshelf/config/absdatabase.sqlite"
ABS_DIR = "/opt/stacks/audiobookshelf/audiobooks/Richard English - Armed Struggle- The Story of the IRA_5bd54041"
# content anchor, taken at the saved position below (see module docstring)
ANCHOR_AT_S = 11394.729
ANCHOR = ("ch10", 142, 30)        # slug, chunk index (1-based), words into the chunk
REWIND_S = 3.0                    # land just before the anchor word, not on it
TITLES = {
    "ch08": "Preface",
    "ch09": "One - The Irish Revolution 1916-23",
    "ch10": "Two - New States 1923-63",
    "ch11": "Three - The Birth of the Provisional IRA 1963-72",
    "ch12": "Four - The Politics of Violence 1972-6",
    "ch13": "Five - The Prison War 1976-81",
    "ch14": "Six - Politicization and the Cycle of Violence 1981-8",
    "ch15": "Seven - Talking and Killing 1988-94",
    "ch16": "Eight - Cessations of Violence 1994-2002",
    "ch17": "Conclusion",
    "ch18": "Afterword",
}


def log(msg):
    print(time.strftime("[%H:%M:%S] "), msg, flush=True)


def sh(cmd, timeout=3600, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        sys.exit(f"command failed rc={r.returncode}: {' '.join(map(str, cmd))[:300]}\n"
                 f"{(r.stderr or r.stdout or '')[-1500:]}")
    return r


def abs_sql(sql):
    """ABS DB over ssh; the running container holds brief write locks, so retry with a busy timeout."""
    r = None
    for attempt in range(4):
        r = subprocess.run(["ssh", "docker-vm", f"sudo sqlite3 {ABS_DB} <<'SQL'\n.timeout 10000\n{sql}\nSQL"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return r.stdout.strip()
        time.sleep(5 * (attempt + 1))
    sys.exit(f"abs_sql failed: {sql[:120]}\n{(r.stderr or r.stdout or '')[-800:]}")


def duration(p: Path) -> float:
    """mp3/wav via soundfile; anything else from `ffmpeg -i` (no ffprobe on the Windows box)."""
    if p.suffix.lower() in (".mp3", ".wav"):
        import soundfile as sf
        return float(sf.info(str(p)).duration)
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p)], capture_output=True, text=True, timeout=120)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        sys.exit(f"ABORT: cannot read the duration of {p}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def chapter_files(man) -> list:
    out = []
    for c in man["chapters"]:
        hits = sorted((BOOK / "chapters").glob(f"{int(c['index']):03d}_*.mp3"))
        if len(hits) != 1:
            sys.exit(f"ABORT: expected one chapter mp3 for {c['slug']}, found {[h.name for h in hits]}")
        out.append((c["slug"], TITLES[c["slug"]], hits[0]))
    return out


def check_audits(man, pay):
    for c in man["chapters"]:
        f = BOOK / "audit" / f"{c['slug']}.asr.json"
        if not f.exists():
            sys.exit(f"ABORT: no independent ASR audit for {c['slug']} ({f})")
        rows = json.loads(f.read_text(encoding="utf-8"))
        n = len(pay[c["slug"]]["chunks"])
        bad = [r["i"] for r in rows if r.get("bad")]
        if len(rows) != n or bad:
            sys.exit(f"ABORT: {c['slug']} audit covers {len(rows)}/{n} chunks, bad={bad[:10]}")
    log(f"independent ASR audit: all {len(man['chapters'])} chapters, every chunk complete")


def chunk_start_in_chapter(slug, pay, idx, words_in) -> float:
    """Time of word `words_in` of chunk `idx` inside the assembled chapter (same maths as higgs_assemble)."""
    import soundfile as sf

    import higgs_assemble as ha
    chunks = pay[slug]["chunks"]
    pos, prev = 0.0, None
    for i, c in enumerate(chunks, 1):
        w, sr = sf.read(str(BOOK / "chunks" / slug / f"{i:04d}.wav"), dtype="float32")
        length = len(ha.shape(w, sr)) / sr
        if prev is not None:
            pos += -ha.XFADE_S if ha.joins_inside_paragraph(prev, c) else ha.PARA_GAP_S
        if i == idx:
            return pos + length * words_in / max(c["words"], 1)
        pos += length
        prev = c
    sys.exit(f"ABORT: chunk {idx} not in {slug}")


def build_m4b(table, total) -> Path:
    tmp = BOOK / "m4b_build"
    tmp.mkdir(exist_ok=True)
    concat = tmp / "concat_list.txt"
    concat.write_text("".join(f"file '{str(p.resolve()).replace(chr(92), '/')}'\n" for _, _, p, _, _ in table),
                      encoding="utf-8")
    meta = tmp / "ffmetadata.txt"
    lines = [";FFMETADATA1", "title=Armed Struggle: The Story of the IRA", "artist=Richard English",
             "album=Armed Struggle", "composer=Cillian Murphy voice clone (Higgs TTS 3)", "genre=History",
             "date=2008"]
    for _, title, _, start, dur in table:
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}", f"END={int((start + dur) * 1000)}",
                  f"title={title}"]
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    m4b = BOOK / "Armed Struggle.m4b"
    newest = max(p.stat().st_mtime for _, _, p, _, _ in table)
    if m4b.exists() and m4b.stat().st_mtime > newest and m4b.stat().st_size > 0:
        log(f"reusing {m4b.name} (newer than every chapter)")
        return m4b
    log(f"building {m4b.name} ({total / 3600:.2f} h) ...")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(meta),
        "-map_metadata", "1", "-map_chapters", "1", "-codec:a", "aac", "-b:a", "128k", str(m4b)])
    got = duration(m4b)
    if abs(got - total) > 5:
        sys.exit(f"ABORT: m4b is {got:.1f}s, chapters add up to {total:.1f}s")
    log(f"built {m4b} ({m4b.stat().st_size:,} B, {got / 3600:.2f} h)")
    return m4b


def metadata_json(table) -> str:
    return json.dumps({
        "tags": [], "title": "Armed Struggle", "subtitle": "The Story of the IRA", "authors": ["Richard English"],
        "narrators": ["Cillian Murphy voice clone (Higgs TTS 3, synthetic)"], "series": [],
        "genres": ["Audiobook", "History", "Irish History"], "publishedYear": "2008", "publishedDate": None,
        "publisher": None, "isbn": None, "asin": None, "language": "eng", "explicit": False, "abridged": False,
        "description": "The definitive history of the IRA by Richard English, narrated by a synthetic Cillian "
                       "Murphy voice clone (Higgs TTS 3).",
        "chapters": [{"id": n, "start": round(s, 3), "end": round(s + d, 3), "title": t}
                     for n, (_, t, _, s, d) in enumerate(table)],
    }, indent=2)


def main():
    from higgs_book_plan import load_bundle
    check = "--check" in sys.argv
    man, pay = load_bundle(BUNDLE)
    check_audits(man, pay)
    table, t = [], 0.0
    for slug, title, p in chapter_files(man):
        d = duration(p)
        table.append((slug, title, p, t, d))
        t += d
    total = t
    for slug, title, p, s, d in table:
        log(f"  {slug} {title:<52} start {s / 60:8.2f} min  dur {d / 60:6.2f} min")
    log(f"total {total / 3600:.2f} h")

    row = abs_sql(f"SELECT currentTime, duration FROM mediaProgresses WHERE mediaItemId = '{ITEM}';")
    cur = float(row.split("|")[0])
    if abs(cur - ANCHOR_AT_S) > 1.0:
        sys.exit(f"ABORT: live position {cur:.1f}s is not the anchored {ANCHOR_AT_S}s - Dave listened since; "
                 f"re-take the content anchor before swapping")
    slug, idx, words_in = ANCHOR
    ch_start = next(s for sl, _, _, s, _ in table if sl == slug)
    new_time = round(max(0.0, ch_start + chunk_start_in_chapter(slug, pay, idx, words_in) - REWIND_S), 2)
    log(f"position {cur:.1f}s (old) -> {new_time:.1f}s (new): {slug} chunk {idx}, {words_in} words in, "
        f"-{REWIND_S:.0f}s")
    if check:
        log("--check: no writes")
        return

    m4b = build_m4b(table, total)
    meta_local = BOOK / "m4b_build" / "metadata.json"
    meta_local.write_text(metadata_json(table), encoding="utf-8")
    today = date.today().isoformat()
    staged, staged_meta = f"/tmp/as_higgs_{today}.m4b", f"/tmp/as_higgs_{today}.metadata.json"
    sup = f"/opt/stacks/audiobookshelf/AS_SUPERSEDED_fish_{today}"
    rr = sh(["ssh", "docker-vm", f"stat -c %s '{ABS_DIR}/Armed Struggle.m4b'"], check=False)
    if rr.stdout.strip() == str(m4b.stat().st_size):
        log("swap already done (remote m4b is this build) - resuming at the position step")
    else:
        sh(["scp", str(m4b), f"docker-vm:{staged}"], timeout=3600)
        sh(["scp", str(meta_local), f"docker-vm:{staged_meta}"], timeout=120)
        sh(["ssh", "docker-vm",
            f"set -e; mkdir -p '{sup}'; mv '{ABS_DIR}/Armed Struggle.m4b' '{sup}/'; "
            f"mv '{ABS_DIR}/metadata.json' '{sup}/' 2>/dev/null || true; "
            f"test -z \"$(find '{ABS_DIR}' -maxdepth 1 \\( -name '*.mp3' -o -name '*.m4b' \\) -print -quit)\"; "
            f"mv '{staged}' '{ABS_DIR}/Armed Struggle.m4b'; mv '{staged_meta}' '{ABS_DIR}/metadata.json'; "
            f"ls -la '{ABS_DIR}/'"], timeout=600)
        log(f"swapped: old Fish m4b + metadata.json -> {sup}")
    marker = BOOK / ".position_set"
    if marker.exists():
        log(f"position already set ({marker.read_text().strip()}) - not touching it again")
    else:
        abs_sql(f"UPDATE mediaProgresses SET currentTime = {new_time}, duration = {round(total, 3)}, "
                f"updatedAt = datetime('now') WHERE mediaItemId = '{ITEM}';")
        marker.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} old={cur} new={new_time}")
    log("progress row: " + abs_sql(f"SELECT currentTime, duration FROM mediaProgresses WHERE mediaItemId='{ITEM}';"))
    sh(["ssh", "docker-vm", "docker restart audiobookshelf"], timeout=600)
    log("ABS restarted for a startup scan. Verify: item duration, 11 chapters, position (then Dave listens).")


if __name__ == "__main__":
    main()
