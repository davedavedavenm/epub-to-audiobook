"""Kaggle free-GPU render backend for the web UI.

When a job's render_target is 'kaggle', the webapp calls render_on_kaggle()
instead of spawning a local docker conversion. This codifies the exact manual
flow proven in July 2026: upload the epub as a private Kaggle dataset, push a
GPU kernel that runs the repo's real engine + preprocessing, poll it, then pull
the finished MP3s back into the job's audiobook dir.

No official Kaggle quota API exists, so GPU-hours are tracked locally in a
state file (best-effort, for the UI readout — Kaggle enforces the real limit).

All Kaggle calls go through the `kaggle` CLI (`python -m kaggle ...`), matching
what was validated by hand; the CLI must be installed and a token present at
KAGGLE_CONFIG_DIR (or ~/.kaggle/). Pure helpers (metadata build, kernel
templating, status/quota parsing) are import-safe and unit-tested.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone, timedelta

# Weekly free GPU allowance Kaggle grants (hours). Used only for the UI
# readout + a soft pre-flight warning; Kaggle enforces the real cap.
WEEKLY_GPU_HOURS = float(os.environ.get("KAGGLE_WEEKLY_GPU_HOURS", "30"))
STATE_PATH = os.environ.get("KAGGLE_RENDER_STATE", os.path.expanduser("~/.kaggle_render_state.json"))
POLL_SECONDS = int(os.environ.get("KAGGLE_POLL_SECONDS", "60"))
# Kaggle kernel sessions are capped (~9-12h). Refuse to wait past this.
MAX_RENDER_HOURS = float(os.environ.get("KAGGLE_MAX_RENDER_HOURS", "11"))

# Which engines can render on Kaggle, and the kernel template + server dir each
# uses. Templates live in scripts/kaggle/ in the repo.
_ENGINE_KERNEL = {
    "chatterbox": "run_chatterbox.py",
    "tada": "run.py",
    "cosyvoice": "run_cosyvoice.py",
    "vibevoice": "run_vibevoice.py",
    "qwen3": "run_qwen3.py",
}


def render_engines():
    """Engines that can render a full book on Kaggle GPU (the single source of
    truth the webapp gate checks against)."""
    return tuple(_ENGINE_KERNEL)


# --- session planning ------------------------------------------------------
# Kaggle caps a session (~9-12h) AND commits outputs only when the kernel
# FINISHES: `kaggle kernels output` returns zero files for a kernel that is
# still running, and a session killed at the cap therefore yields nothing at
# all (verified 2026-07-25 against a live render). A book too big for one
# session must be split into several kernels, each of which completes and
# commits its own chapters.
SESSION_BUDGET_HOURS = float(os.environ.get("KAGGLE_SESSION_BUDGET_HOURS", "5"))
WORDS_PER_MINUTE = 155.0        # narration pace
SETUP_HOURS = 0.3               # per-session install + model download overhead
# Measured realtime factors on Kaggle GPUs (gen seconds per audio second).
ENGINE_RTF = {
    "cosyvoice": 0.9,
    "chatterbox": 0.85,
    "tada": 0.45,
    # Measured on the accepted full Yellow Wallpaper chapter, Kaggle P100.
    "vibevoice": 2.266,
    "qwen3": 2.056,
}


def estimate_hours(words, rtf=0.9):
    """GPU hours needed to narrate `words` at this engine's realtime factor."""
    return (float(words) / WORDS_PER_MINUTE / 60.0) * rtf


def plan_batches(chapters, start=1, end=0, rtf=0.9, budget_hours=None):
    """Pack chapters [start..end] into contiguous batches that each fit a session.

    `chapters` is [{'index': int, 'words': int}, ...] (chapters.list_renderable_chapters).
    Returns [(start_index, end_index, est_hours), ...] — always at least one batch,
    so callers can loop unconditionally. An oversized single chapter still gets
    its own batch: splitting below chapter granularity isn't possible here.
    """
    budget = float(budget_hours or SESSION_BUDGET_HOURS)
    sel = [c for c in (chapters or [])
           if c.get('index', 0) >= (start or 1) and (not end or c.get('index', 0) <= end)]
    if not sel:
        return [((start or 1), end or 0, 0.0)]
    batches, cur, cur_h = [], [], 0.0
    for c in sel:
        h = estimate_hours(c.get('words', 0), rtf)
        if cur and (cur_h + h + SETUP_HOURS) > budget:
            batches.append((cur[0]['index'], cur[-1]['index'], cur_h))
            cur, cur_h = [], 0.0
        cur.append(c)
        cur_h += h
    if cur:
        batches.append((cur[0]['index'], cur[-1]['index'], cur_h))
    return batches


def kernel_slug(epub_path):
    """Kernel slug for a book's render. Single source of truth so `cancel` can
    find the same kernel `render_on_kaggle` created."""
    book = os.path.splitext(os.path.basename(epub_path))[0]
    return _slug(f"render-{book}")


def _merge_qa_report(src_path, dst_path):
    """Merge per-session QA into the book-level report.

    Kaggle commits one batch at a time. Blindly copying qa_report.json made the
    final batch overwrite every earlier chapter, so the pre-sync gate appeared
    verified while inspecting only the tail of the book.
    """
    with open(src_path, encoding="utf-8") as f:
        incoming = json.load(f)
    current = {}
    if os.path.exists(dst_path):
        try:
            with open(dst_path, encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            current = {}
    chapters = {}
    for report in (current, incoming):
        for chapter in report.get("chapters", []):
            if chapter.get("chapter") is not None:
                chapters[int(chapter["chapter"])] = chapter
    merged_chapters = [chapters[k] for k in sorted(chapters)]
    suggestions = {}
    suggestions.update(current.get("lexicon_suggestions") or {})
    suggestions.update(incoming.get("lexicon_suggestions") or {})
    merged = dict(current or incoming)
    merged.update({
        "chapters": merged_chapters,
        "flagged_chapters": [c["chapter"] for c in merged_chapters if c.get("flagged")],
        "lexicon_suggestions": suggestions,
    })
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)


def stop_kernel(slug, log=print):
    """Actually halt a running Kaggle kernel.

    The Kaggle CLI has no stop/cancel verb, and cancelling a job in the webapp
    only stopped our *polling* — the GPU kept billing against the weekly quota
    while the user believed they had stopped it (found 2026-07-25). Pushing a
    new version to the same slug supersedes the running one, so push a no-op
    (CPU, no internet) to end the session.
    """
    try:
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "run.py"), "w", encoding="utf-8") as f:
                f.write('print("superseded: render stopped by operator")\n')
            with open(os.path.join(td, "kernel-metadata.json"), "w", encoding="utf-8") as f:
                json.dump({"id": slug, "title": slug.split("/")[-1], "code_file": "run.py",
                           "language": "python", "kernel_type": "script", "is_private": True,
                           "enable_gpu": False, "enable_internet": False,
                           "dataset_sources": [], "competition_sources": [],
                           "kernel_sources": []}, f)
            r = _kaggle("kernels", "push", "-p", td, timeout=180)
        ok = r is not None and getattr(r, "returncode", 1) == 0
        log(f"Kaggle: {'stopped' if ok else 'FAILED to stop'} kernel {slug}")
        return ok
    except Exception as e:
        log(f"Kaggle: error stopping kernel {slug}: {e}")
        return False


def kaggle_username():
    """Resolve the Kaggle username from kaggle.json or env (needed for the
    dataset/kernel slug). Returns None if unresolvable."""
    u = os.environ.get("KAGGLE_USERNAME")
    if u:
        return u
    cfg_dir = os.environ.get("KAGGLE_CONFIG_DIR", os.path.expanduser("~/.kaggle"))
    for fn in ("kaggle.json",):
        p = os.path.join(cfg_dir, fn)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    return json.load(f).get("username")
            except Exception:
                pass
    return None


def kaggle_ready():
    """True if the CLI is importable and credentials are present."""
    cfg_dir = os.environ.get("KAGGLE_CONFIG_DIR", os.path.expanduser("~/.kaggle"))
    has_creds = (os.environ.get("KAGGLE_KEY") and os.environ.get("KAGGLE_USERNAME")) or \
        os.environ.get("KAGGLE_API_TOKEN") or \
        os.path.exists(os.path.join(cfg_dir, "kaggle.json")) or \
        os.path.exists(os.path.join(cfg_dir, "access_token"))
    if not has_creds:
        return False
    try:
        import kaggle  # noqa: F401
        return True
    except Exception:
        # CLI may still be runnable as a module even if import has side effects
        r = subprocess.run(["python", "-m", "kaggle", "--version"],
                           capture_output=True, text=True)
        return r.returncode == 0


# ---- pure helpers (unit-tested) -------------------------------------------

def _slug(text, maxlen=40):
    s = re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return (s[:maxlen] or "book").strip("-")


def dataset_metadata(username, slug, title):
    """Kaggle dataset-metadata.json content for the epub upload."""
    return {"title": title[:50], "id": f"{username}/{slug}", "licenses": [{"name": "other"}]}


def kernel_metadata(username, slug, dataset_id, enable_gpu=True):
    """Kaggle kernel-metadata.json referencing the epub dataset."""
    return {
        "id": f"{username}/{slug}",
        "title": slug,
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": enable_gpu,
        "enable_internet": True,
        "dataset_sources": [dataset_id],
        "competition_sources": [],
        "kernel_sources": [],
    }


def render_kernel_source(template_src, voice, start, end, progress_url="", app_ref=""):
    """Substitute the knobs block of a kernel template. END<=0 means to end."""
    s = re.sub(r'VOICE\s*=\s*"[^"]*"', f'VOICE  = "{voice}"', template_src, count=1)
    s = re.sub(r'START\s*=\s*\d+', f'START  = {int(start) if start else 1}', s, count=1)
    s = re.sub(r'END\s*=\s*\d+', f'END    = {int(end) if end else 0}', s, count=1)
    if 'PROGRESS_URL' in s:
        s = re.sub(r'PROGRESS_URL\s*=\s*"[^"]*"', f'PROGRESS_URL = "{progress_url}"', s, count=1)
    if 'APP_REF' in s:
        s = re.sub(r'APP_REF\s*=\s*"[^"]*"', f'APP_REF = "{app_ref}"', s, count=1)
    return s


def _ntfy_progress(topic):
    """Fetch the latest real progress the kernel POSTed to its ntfy topic.
    Returns (pct, done, total) or None. Kaggle kernels have outbound internet,
    so they phone home per-chapter — no tunnel/infra needed."""
    try:
        import urllib.request
        url = f"https://ntfy.sh/{topic}/json?poll=1"
        raw = urllib.request.urlopen(url, timeout=8).read().decode("utf-8", "ignore")
        latest = None
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                body = msg.get("message")
                if body:
                    latest = json.loads(body)
            except Exception:
                continue
        if latest and "pct" in latest:
            return int(latest["pct"]), latest.get("done"), latest.get("total")
    except Exception:
        pass
    return None


def parse_status(cli_out):
    """Normalize `kaggle kernels status` output to one of:
    queued|running|complete|error|cancelled|unknown."""
    t = (cli_out or "").lower()
    if "complete" in t:
        return "complete"
    if "error" in t:
        return "error"
    if "cancel" in t:
        return "cancelled"
    if "running" in t:
        return "running"
    if "queued" in t:
        return "queued"
    return "unknown"


def _wait_dataset_ready(user, ds_slug, log, timeout=300):
    """Block until an uploaded epub dataset finishes Kaggle's async ingestion.

    A kernel pushed before the dataset is 'ready' attaches an EMPTY version, so
    the render dies instantly with "no .epub under /kaggle/input" (intermittent
    race, hit 2026-07-13). `kaggle datasets status` returns 'ready' once the file
    is processed — poll it before pushing the kernel.
    """
    ref = f"{user}/{ds_slug}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = _kaggle("datasets", "status", ref, timeout=60)
        if "ready" in (s.stdout + s.stderr).lower():
            return True
        time.sleep(6)
    return False


def _load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {"runs": []}


def gpu_hours_used(state=None, now=None):
    """GPU-hours consumed in the trailing 7 days (from local state)."""
    state = state or _load_state()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    total = 0.0
    for r in state.get("runs", []):
        try:
            ts = datetime.fromisoformat(r["ended"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                total += float(r.get("hours", 0))
        except Exception:
            continue
    return round(total, 2)


def gpu_hours_left(state=None):
    return round(max(0.0, WEEKLY_GPU_HOURS - gpu_hours_used(state)), 2)


def _record_run(hours):
    state = _load_state()
    state.setdefault("runs", []).append(
        {"ended": datetime.now(timezone.utc).isoformat(), "hours": round(hours, 3)})
    state["runs"] = state["runs"][-200:]
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


# ---- orchestration ---------------------------------------------------------

def _kaggle(*args, timeout=300):
    return subprocess.run(["python", "-m", "kaggle", *args],
                          capture_output=True, text=True, timeout=timeout)


def render_on_kaggle(epub_path, voice, engine, start, end, out_dir,
                     repo_kaggle_dir, log=print, on_status=None, resume=False):
    """Render a book on Kaggle GPU end-to-end. Blocks until done.

    Returns (ok: bool, message: str). Writes MP3s + qa_report.json into out_dir.
    `repo_kaggle_dir` is the path to scripts/kaggle/ (for the kernel template).
    """
    if engine not in _ENGINE_KERNEL:
        return False, f"engine {engine!r} can't render on Kaggle (supported: {', '.join(render_engines())})"
    user = kaggle_username()
    if not user:
        return False, "Kaggle username unresolved (no kaggle.json / KAGGLE_USERNAME)"

    template_path = os.path.join(repo_kaggle_dir, _ENGINE_KERNEL[engine])
    if not os.path.exists(template_path):
        return False, f"kernel template missing: {template_path}"
    with open(template_path, encoding="utf-8") as f:
        template_src = f.read()
    app_ref = os.environ.get("APP_GIT_SHA", "").strip()
    if engine in ("vibevoice", "qwen3") and not re.fullmatch(r"[0-9a-fA-F]{40}", app_ref):
        return False, ("APP_GIT_SHA must be the full deployed 40-character commit for "
                       f"{engine}; refusing to run a drifting Kaggle checkout")

    book = os.path.splitext(os.path.basename(epub_path))[0]
    ds_slug = _slug(f"epub-{book}")
    kslug = kernel_slug(epub_path)
    dataset_id = f"{user}/{ds_slug}"
    os.makedirs(out_dir, exist_ok=True)
    # Stable per-render ntfy topic (deterministic so resume tracks the same one).
    import hashlib
    topic = "aud-" + hashlib.md5(f"{user}/{kslug}".encode()).hexdigest()[:16]
    progress_url = f"https://ntfy.sh/{topic}"

    with tempfile.TemporaryDirectory() as tmp:
        if not resume:
            # 1. dataset (epub upload) — create, or new version if it exists
            ds_dir = os.path.join(tmp, "ds")
            os.makedirs(ds_dir)
            shutil.copy(epub_path, os.path.join(ds_dir, os.path.basename(epub_path)))
            with open(os.path.join(ds_dir, "dataset-metadata.json"), "w") as f:
                json.dump(dataset_metadata(user, ds_slug, book), f)
            log(f"Kaggle: uploading epub as dataset {dataset_id}")
            r = _kaggle("datasets", "create", "-p", ds_dir, "-r", "zip", timeout=600)
            if "already exists" in (r.stdout + r.stderr).lower() or r.returncode != 0:
                r = _kaggle("datasets", "version", "-p", ds_dir, "-m", "update",
                            "-r", "zip", timeout=600)
            if r.returncode != 0 and "already" not in (r.stdout + r.stderr).lower():
                return False, f"dataset upload failed: {(r.stderr or r.stdout)[:200]}"

            # Wait for Kaggle to finish ingesting the epub before pushing the
            # kernel — otherwise the kernel attaches an empty dataset version and
            # dies with "no .epub under /kaggle/input".
            log(f"Kaggle: waiting for dataset {dataset_id} to be ready")
            if not _wait_dataset_ready(user, ds_slug, log):
                return False, "epub dataset did not become ready on Kaggle in time"

            # 2. kernel (push the GPU render job)
            k_dir = os.path.join(tmp, "k")
            os.makedirs(k_dir)
            with open(os.path.join(k_dir, "run.py"), "w", encoding="utf-8") as f:
                f.write(render_kernel_source(template_src, voice, start, end, progress_url, app_ref))
            with open(os.path.join(k_dir, "kernel-metadata.json"), "w") as f:
                json.dump(kernel_metadata(user, kslug, dataset_id), f)
            log(f"Kaggle: pushing GPU kernel {user}/{kslug} (engine={engine}, voice={voice})")
            r = _kaggle("kernels", "push", "-p", k_dir, timeout=300)
            if r.returncode != 0:
                return False, f"kernel push failed: {(r.stderr or r.stdout)[:200]}"
        else:
            log(f"Kaggle: resuming tracking for existing kernel {user}/{kslug}")

        # 3. poll
        started = time.time()
        while True:
            time.sleep(POLL_SECONDS)
            if (time.time() - started) / 3600 > MAX_RENDER_HOURS:
                return False, f"render exceeded {MAX_RENDER_HOURS}h cap — Kaggle likely killed the session"
            r = _kaggle("kernels", "status", f"{user}/{kslug}", timeout=120)
            st = parse_status(r.stdout + r.stderr)
            # Real per-chapter progress the kernel phoned home (falls back to
            # the caller's elapsed estimate when nothing's arrived yet).
            prog = _ntfy_progress(topic)
            if on_status:
                # Forward the whole (pct, done, total) tuple so the caller can
                # show honest chapter-based progress and suppress a fake ETA
                # until a chapter has actually completed.
                on_status(st, round((time.time() - started) / 60), prog)
            if st in ("complete", "error", "cancelled"):
                break

        hours = (time.time() - started) / 3600
        _record_run(hours)

        # 4. pull output
        out_tmp = os.path.join(tmp, "out")
        os.makedirs(out_tmp)
        _kaggle("kernels", "output", f"{user}/{kslug}", "-p", out_tmp, timeout=600)
        mp3s = [f for f in os.listdir(out_tmp) if f.lower().endswith(".mp3")]
        if st != "complete" or not mp3s:
            tail = ""
            slog = os.path.join(out_tmp, "server.log")
            if os.path.exists(slog):
                with open(slog, encoding="utf-8", errors="ignore") as f:
                    tail = f.read()[-400:]
            return False, f"Kaggle render {st} with {len(mp3s)} mp3s. {tail}"
        for f in mp3s:
            shutil.copy(os.path.join(out_tmp, f), os.path.join(out_dir, f))
        for f in [x for x in os.listdir(out_tmp) if x.endswith(".json")]:
            src = os.path.join(out_tmp, f)
            dst = os.path.join(out_dir, f)
            if f == "qa_report.json":
                _merge_qa_report(src, dst)
            else:
                shutil.copy(src, dst)
        log(f"Kaggle: pulled {len(mp3s)} chapters into {out_dir} ({hours:.1f} GPU-hours)")
        return True, f"rendered {len(mp3s)} chapters on Kaggle GPU"
