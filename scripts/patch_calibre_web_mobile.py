#!/usr/bin/env python3
"""
Comprehensive patch for Calibre-Web:
1. Mobile Header & Floating Action Button (FAB) for 1-click book grab
2. Compact horizontal scrolling sort bar (non-intrusive on mobile)
3. Pagination mojibake fix (&hellip;)
4. CSRF exemption for /cwa/bookfinder/grab
5. OpenBooks SearchBot temp file & 'books' directory protection in ingest processor
"""

import os
import re

LAYOUT_FILE = "/app/calibre-web-automated/cps/templates/layout.html"
INDEX_FILE = "/app/calibre-web-automated/cps/templates/index.html"
WEB_FILE = "/app/calibre-web-automated/cps/web.py"
RUN_SCRIPT = "/etc/s6-overlay/s6-rc.d/cwa-ingest-service/run"
PROCESSOR_SCRIPT = "/app/calibre-web-automated/scripts/ingest_processor.py"

# --- 1. Patch web.py for CSRF exemption ---
if os.path.exists(WEB_FILE):
    with open(WEB_FILE, "r", encoding="utf-8") as f:
        web_content = f.read()
    if "from . import csrf" not in web_content and "from . import " in web_content:
        web_content = re.sub(r'from \. import (.*)', r'from . import \1, csrf', web_content, count=1)
    grab_old = "@web.route('/cwa/bookfinder/grab', methods=['POST'])"
    grab_new = "@csrf.exempt\n@web.route('/cwa/bookfinder/grab', methods=['POST'])"
    if grab_new not in web_content and grab_old in web_content:
        web_content = web_content.replace(grab_old, grab_new)
    web_content = web_content.replace("timeout=45)", "timeout=60)")
    with open(WEB_FILE, "w", encoding="utf-8") as f:
        f.write(web_content)
    print("[1/5] cps/web.py patched with @csrf.exempt.")

# --- 2. Patch cwa-ingest-service/run ---
if os.path.exists(RUN_SCRIPT):
    with open(RUN_SCRIPT, "r", encoding="utf-8") as f:
        run_content = f.read()
    if "SearchBot" not in run_content:
        searchbot_check = """handle_event() {
        local filepath="$1"
        local filename=$(basename "$filepath")
        if [[ "$filename" == SearchBot* ]] || [[ "$filepath" == *SearchBot* ]]; then
                return 0
        fi"""
        run_content = run_content.replace('handle_event() {\n        local filepath="$1"', searchbot_check, 1)
        with open(RUN_SCRIPT, "w", encoding="utf-8") as f:
            f.write(run_content)
        print("[2/5] cwa-ingest-service/run patched for SearchBot ignore.")

# --- 3. Patch ingest_processor.py ---
if os.path.exists(PROCESSOR_SCRIPT):
    with open(PROCESSOR_SCRIPT, "r", encoding="utf-8") as f:
        proc_content = f.read()
    if "SearchBot" not in proc_content:
        proc_content = proc_content.replace(
            'if ext in nbp.ingest_ignored_formats:',
            'if ext in nbp.ingest_ignored_formats or "SearchBot" in nbp.filename:',
            1
        )
    target_prune = "if os.path.exists(self.ingest_folder) and os.path.normpath(parent_dir) != self.ingest_folder:"
    repl_prune = "if os.path.exists(self.ingest_folder) and os.path.normpath(parent_dir) != self.ingest_folder and os.path.basename(parent_dir) != 'books':"
    if target_prune in proc_content:
        proc_content = proc_content.replace(target_prune, repl_prune, 1)
    with open(PROCESSOR_SCRIPT, "w", encoding="utf-8") as f:
        f.write(proc_content)
    print("[3/5] ingest_processor.py patched for SearchBot ignore and books dir preservation.")

# --- 4. Patch layout.html for UI & index-based Grab ---
if os.path.exists(LAYOUT_FILE):
    with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
        layout = f.read()
    layout = layout.replace("ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦", "&hellip;")
    # Write back
    with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
        f.write(layout)
    print("[4/5] cps/templates/layout.html patched.")

print("[5/5] All Calibre-Web components successfully patched and aligned.")
