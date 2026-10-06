#!/usr/bin/env python
"""lane_launch.py — starts runner.py on the Colab VM, detached, and records
its pid so lane_probe.py can test liveness precisely.

Re-exec inside the runner preserves this pid (os.execv replaces the image but
keeps the process), so /content/runner.pid stays valid for the whole render.
Output goes to /content/render.log, exactly like the production lanes.
"""
import subprocess

with open("/content/render.log", "ab") as log:
    log.write(b"=== lane_ctl launch ===\n")
    log.flush()
    p = subprocess.Popen(
        ["python3", "/content/runner.py"],
        stdout=log, stderr=subprocess.STDOUT,
        cwd="/content", start_new_session=True,
    )
    with open("/content/runner.pid", "w") as pf:
        pf.write(str(p.pid))
print("runner pid", p.pid)
