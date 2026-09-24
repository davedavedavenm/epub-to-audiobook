"""v2 lane-aware runner probe (matches khpi5 /tmp/runner_probe.py).

Prints `ALIVE|DEAD <remain>` where remain = chapters of this VM's lane scope
(/content/as_chapters.txt, comma-separated slugs) not yet in as_state.json.
Absent scope file = full ORDER (legacy single-lane behaviour).
"""
import glob
import json
from pathlib import Path

ORDER = ["preface", "ch1", "ch2", "ch3", "ch4", "ch5", "ch6", "ch7", "ch8", "conclusion"]
sf = Path("/content/as_chapters.txt")
scope = [s for s in sf.read_text().split(",") if s] if sf.exists() else ORDER
try:
    done = set(json.load(open("/content/as_state.json")).get("completed", []))
except Exception:
    done = set()
remain = [s for s in scope if s not in done]

alive = False
for p in glob.glob("/proc/[0-9]*/cmdline"):
    try:
        if b"runner.py" in open(p, "rb").read():
            alive = True
            break
    except Exception:
        pass
print(("ALIVE" if alive else "DEAD") + " " + str(len(remain)))
