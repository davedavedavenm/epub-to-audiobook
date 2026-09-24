import glob
import json

alive = False
for p in glob.glob("/proc/[0-9]*/cmdline"):
    try:
        if b"runner.py" in open(p, "rb").read():
            alive = True
            break
    except Exception:
        pass
try:
    done = len(json.load(open("/content/as_state.json")).get("completed", []))
except Exception:
    done = 0
print(("ALIVE" if alive else "DEAD") + " " + str(done))
