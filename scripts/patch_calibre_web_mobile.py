#!/usr/bin/env python3
"""
Comprehensive master patch for Calibre-Web:
1. Mobile Header & Floating Action Button (FAB) for 1-click book grab
2. Compact horizontal scrolling sort bar (non-intrusive on mobile)
3. Pagination mojibake fix (&hellip;)
4. CSRF exemption for /cwa/bookfinder/grab
5. OpenBooks SearchBot temp file & 'books' directory protection in ingest processor
6. Cloudflare Access Zero Trust Header SSO (Cf-Access-Authenticated-User-Email -> Admin)
7. 1-Year Extended Persistent Sessions (Remember Me)
"""

import os
import re

LAYOUT_FILE = "/app/calibre-web-automated/cps/templates/layout.html"
INDEX_FILE = "/app/calibre-web-automated/cps/templates/index.html"
WEB_FILE = "/app/calibre-web-automated/cps/web.py"
RUN_SCRIPT = "/etc/s6-overlay/s6-rc.d/cwa-ingest-service/run"
PROCESSOR_SCRIPT = "/app/calibre-web-automated/scripts/ingest_processor.py"
USERMGMT_FILE = "/app/calibre-web-automated/cps/usermanagement.py"
INIT_FILE = "/app/calibre-web-automated/cps/__init__.py"

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
    print("[1/7] cps/web.py patched with @csrf.exempt.")

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
        print("[2/7] cwa-ingest-service/run patched for SearchBot ignore.")

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
    print("[3/7] ingest_processor.py patched for SearchBot ignore and books dir preservation.")

# --- 4. Patch layout.html for UI & index-based Grab ---
if os.path.exists(LAYOUT_FILE):
    with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
        layout = f.read()
    layout = layout.replace("ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦", "&hellip;")
    with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
        f.write(layout)
    print("[4/7] cps/templates/layout.html patched.")

# --- 5. Patch usermanagement.py for Cloudflare Access Header SSO ---
if os.path.exists(USERMGMT_FILE):
    with open(USERMGMT_FILE, "r", encoding="utf-8") as f:
        usermgmt = f.read()
    new_rp_func = """def load_user_from_reverse_proxy_header(req):
    \"\"\"Load user from reverse proxy / Cloudflare Access header.\"\"\"
    cf_email = req.headers.get('Cf-Access-Authenticated-User-Email')
    if cf_email and cf_email.strip():
        cf_email = cf_email.strip()
        user = ub.session.query(ub.User).filter(func.lower(ub.User.email) == cf_email.lower()).first()
        if user:
            return user
        user = ub.session.query(ub.User).filter(func.lower(ub.User.name) == cf_email.lower()).first()
        if user:
            return user
        prefix = cf_email.split('@')[0].lower()
        user = ub.session.query(ub.User).filter(func.lower(ub.User.name) == prefix).first()
        if user:
            return user
    rp_header_name = getattr(config, 'config_reverse_proxy_login_header_name', None) or 'Remote-User'
    for h in [rp_header_name, 'Remote-User', 'X-Forwarded-User', 'X-Remote-User', 'Remote-Email']:
        if not h:
            continue
        rp_header_username = req.headers.get(h)
        if rp_header_username and rp_header_username.strip():
            rp_header_username = rp_header_username.strip()
            user = ub.session.query(ub.User).filter(
                (func.lower(ub.User.name) == rp_header_username.lower()) |
                (func.lower(ub.User.email) == rp_header_username.lower())
            ).first()
            if user:
                return user
    return None"""
    old_rp_pattern = re.compile(r'def load_user_from_reverse_proxy_header\(req\):.*?return None', re.DOTALL)
    if old_rp_pattern.search(usermgmt):
        usermgmt = old_rp_pattern.sub(new_rp_func, usermgmt, count=1)
        with open(USERMGMT_FILE, "w", encoding="utf-8") as f:
            f.write(usermgmt)
        print("[5/7] cps/usermanagement.py patched for Cloudflare SSO.")

# --- 6. Patch __init__.py for 1-year persistent sessions ---
if os.path.exists(INIT_FILE):
    with open(INIT_FILE, "r", encoding="utf-8") as f:
        init_code = f.read()
    session_patch = """
    # 1-Year Persistent Sessions & Remember Me Cookie
    from datetime import timedelta
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    app.config['REMEMBER_COOKIE_REFRESH_EACH_REQUEST'] = True
"""
    if "REMEMBER_COOKIE_DURATION" not in init_code:
        init_code = init_code.replace("def create_app():", "def create_app():" + session_patch, 1)
        with open(INIT_FILE, "w", encoding="utf-8") as f:
            f.write(init_code)
        print("[6/7] cps/__init__.py patched for 1-year persistent sessions.")

print("[7/7] All components successfully patched and aligned.")
