"""fish_lane.py — locked-recipe Fish/Cillian book renders on a GPU lane.

Mirrors webapp/kaggle_render.py's contract: ``render_on_lane(epub, voice, lane,
start, end, out_dir, ...) -> (ok, msg)`` with ``log(msg)`` and
``on_status(state, minutes, prog)`` callbacks (on_status raises when the job
was cancelled — the caller turns that into a clean abort). Chapters are banked
into *out_dir* as they finish, so a lane that dies mid-book costs at most the
chapter in flight, exactly like the Kaggle path.

Every lane consumes the same artefact: the ``as_bundle.zip`` built by
scripts/fish_bundle.py (payloads + refs + manifest), rendered by
scripts/fish_colab_runner.py inside ``$FISH_BASE``. The recipe itself lives in
the runner — this module is only submit/poll/harvest plumbing.

Lanes:
  lightning  official SDK. Creates/starts a dedicated studio (default
             ``as-fish-lane``), uploads bundle+runner to a per-job workspace,
             polls ``as_state.json`` through ``studio.run``, downloads finished
             chapters, and stops the studio in ``finally`` when IT started it
             — a paid lane must not keep billing after the job ends.
  colab      SSH to the control-plane host (khpi5) running lane_ctl.sh, the
             durable wrapper around the google-colab-cli that already renders
             the production lanes. Same lifecycle, same state file.
  kaggle     quota + engine kernels exist for other engines; the fish kernel is
             pending (documented honestly rather than faked).

Credentials come from webapp/lanes.py (Settings DB / env), never the repo.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

POLL_SECONDS = 60           # state is saved every 20 sentences (~7 min); 60 s poll is plenty
MAX_CRASH_RELAUNCHES = 2    # crash relaunches (a "10h budget" clean exit is NOT a crash)
STUDIO_START_TIMEOUT = 900  # Lightning cold start + machine provisioning
LANE_FAILS_BEFORE_ERROR = 5 # consecutive probe failures before giving up


def _repo_root() -> Path:
    # webapp/fish_lane.py -> repo root (in-container: /app/fish_lane.py -> /app)
    return Path(__file__).resolve().parent.parent


def runner_path() -> Path:
    p = os.environ.get('FISH_RUNNER') or str(_repo_root() / 'scripts' / 'fish_colab_runner.py')
    return Path(p)


def _log(log, msg):
    if log:
        try:
            log(msg)
        except Exception:
            pass


def lane_ready(lane: str) -> tuple:
    """(configured?, reason) — credentials plus LOCAL wiring, never a network probe
    (live probes are lanes.lane_status). Checked as the first step of
    render_on_lane(), so a job that cannot possibly run fails here with an
    actionable reason rather than minutes later with a traceback."""
    try:
        import lanes as L
    except Exception as e:
        return False, f'lanes module unavailable: {e}'
    if lane not in L.LANES:
        return False, f'unknown lane {lane}'
    if not L.lane_configured(lane):
        return False, L.lane_status(lane).get('reason') or f'{lane} not configured'
    if lane == 'kaggle':
        return False, ('Fish-on-Kaggle kernel not wired yet (its e2e test is blocked '
                       'by the exhausted weekly quota — see STATUS.md); '
                       'use Colab or Lightning')
    if lane == 'lightning' and not L.lightning_sdk_available():
        # Credentials are present but the SDK cannot be: it conflicts with
        # vastai's urllib3>=2.7.0 (see webapp/requirements.txt). Naming the lane
        # is still the authorization to spend — this is an environment gap, not
        # an authorization one — so it is refused here, at render start, with
        # the same words the Render Lanes panel already shows.
        return False, ('lightning-sdk not installed in this environment (it '
                       'conflicts with the Vast CLI urllib3 pin — see '
                       'webapp/requirements.txt and DECISIONS.md). The paid '
                       'Lightning lane needs a separate venv.')
    return True, ''


def _build_bundle(epub_path, start, end, log):
    """Build the as_bundle.zip for the requested chapter range (1-based renderable
    indexes, the same numbers the job picker shows). Returns (zip_path, manifest)."""
    scripts = _repo_root() / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import fish_bundle
    tmp = Path(tempfile.mkdtemp(prefix='fishjob_'))
    z = tmp / 'as_bundle.zip'
    manifest = fish_bundle.build_bundle(epub_path, z, start=start, end=end)
    _log(log, f"lane: bundle built ({manifest['bytes']} bytes, "
              f"{len(manifest['chapters'])} chapters, "
              f"{len(manifest.get('digit_runs', []))} bare digit runs)")
    return z, manifest


def _total_sents(manifest) -> int:
    return sum(int(c.get('sents') or 0) for c in manifest.get('chapters', []))


def _state_done(state: dict) -> tuple:
    """(done sents, completed slugs) from a runner as_state.json dict."""
    if not state:
        return 0, set()
    progress = state.get('progress') or {}
    # progress[slug] is the index of the LAST banked sentence; completed
    # chapters keep their final counts there too.
    done = sum(int(v or 0) for v in progress.values())
    return done, set(state.get('completed') or [])


def _harvest_targets(manifest, out_dir: Path) -> dict:
    """{slug: destination path} — banked as ``NNN_title.mp3`` so the shared
    rename/cleanup/verify tail formats them like every other render path."""
    targets = {}
    for c in manifest.get('chapters', []):
        title = re.sub(r'[\\/:*?"<>|]', '', str(c.get('title') or c['slug'])).strip()[:80]
        title = title or c['slug']
        targets[c['slug']] = out_dir / f"{int(c['index']):03d}_{title}.mp3"
    return targets


def _mp3_name(manifest, slug: str) -> str:
    book = manifest.get('book_tag') or 'book'
    voice = manifest.get('voice_tag') or 'cillian'
    return f'{book}_{slug}_{voice}.mp3'


def _max_hours(lane: str) -> float:
    try:
        import lanes as L
        return float(L._cfg('FISH_LANE_MAX_HOURS', '12') or 12)
    except Exception:
        return 12.0


# --------------------------------------------------------------------------
# Lightning (official SDK)
# --------------------------------------------------------------------------

def _lightning_client():
    """(Studio, ts, studio_name, machine) with env credentials set.
    Import is lazy: lightning-sdk is heavy and most requests never touch it."""
    import lanes as L
    key = L._cfg('LIGHTNING_API_KEY')
    user = L._cfg('LIGHTNING_USERNAME')
    if not key or not user:
        raise RuntimeError('Lightning not configured (Settings → Render Lanes)')
    os.environ['LIGHTNING_API_KEY'] = key
    os.environ['LIGHTNING_USERNAME'] = user
    from lightning_sdk import User, Studio
    ts = User(user).teamspaces[0]
    name = L._cfg('LIGHTNING_STUDIO', 'as-fish-lane')
    machine = L._cfg('LIGHTNING_MACHINE', 'L4')
    return Studio, ts, name, machine


def _studio_state(studio) -> str:
    s = str(getattr(studio, 'status', ''))
    return s.rsplit('.', 1)[-1]


def _run(studio, cmd: str) -> str:
    return (studio.run(cmd) or '').strip()


def render_lightning(bundle: Path, manifest: dict, out_dir: Path,
                     log=None, on_status=None) -> tuple:
    import lanes as L
    Studio, ts, sname, machine = _lightning_client()
    _log(log, f'lane lightning: studio={sname} machine={machine} '
              f'(official rates: T4 ${L.LIGHTNING_RATES["T4"]}/h, '
              f'L4 ${L.LIGHTNING_RATES["L4"]}/h)')

    studio = Studio(name=sname, teamspace=ts, create_ok=True)
    started_here = False
    if _studio_state(studio) != 'Running':
        _log(log, f'lane lightning: starting studio {sname} ({machine})…')
        studio.start(machine=machine)
        started_here = True
        t0 = time.time()
        while _studio_state(studio) != 'Running':
            if time.time() - t0 > STUDIO_START_TIMEOUT:
                return False, (f'Lightning studio {sname} did not reach Running '
                               f'in {STUDIO_START_TIMEOUT}s')
            time.sleep(10)

    max_hours = _max_hours('lightning')
    job_tag = f'job{int(time.time())}'
    crash_relaunches = 0
    budget_relaunches = 0
    fails = 0
    t_start = time.time()
    targets = _harvest_targets(manifest, out_dir)
    total = _total_sents(manifest)
    harvested = {p for p in targets.values() if p.exists()}
    ws = ''

    try:
        home = _run(studio, 'echo $HOME').splitlines()[-1]
        ws = f'{home}/fishjobs/{job_tag}'
        # Fresh workspace per job: a stale as_state.json from another book would
        # share slugs (ch01…) and silently skip whole chapters. Weights, the
        # fish-speech clone and the venv live OUTSIDE the workspace so they are
        # reused across jobs instead of re-downloaded (5 GB + minutes each).
        _run(studio, f'mkdir -p {ws}/out && rm -f {ws}/as_state.json {ws}/render.log')
        _log(log, f'lane lightning: uploading bundle to {ws}…')
        studio.upload_file(str(bundle), f'{ws}/as_bundle.zip')
        studio.upload_file(str(runner_path()), f'{ws}/runner.py')

        def launch():
            _run(studio, f'cd {ws} && FISH_BASE={ws} nohup python3 runner.py '
                         f'> {ws}/render.log 2>&1 & echo launched')
            time.sleep(3)

        # run_and_detach is the SDK's documented way to start background work;
        # confirm liveness by log content on the next poll instead of trusting
        # the return tuple.
        studio.run_and_detach(f'cd {ws} && FISH_BASE={ws} nohup python3 runner.py '
                              f'> {ws}/render.log 2>&1 &', timeout=15)
        _log(log, 'lane lightning: runner launched (cold start: apt + fish-speech '
                  '+ weights ≈ 5-10 min)')

        while True:
            time.sleep(POLL_SECONDS)
            if time.time() - t_start > max_hours * 3600:
                return False, (f'lane budget cap reached ({max_hours} h — '
                               f'FISH_LANE_MAX_HOURS); resume with Retry')

            try:
                raw = _run(studio, f'cat {ws}/as_state.json 2>/dev/null || true')
                state = json.loads(raw) if raw else {}
                alive = 'A' in _run(studio, 'pgrep -f runner.py >/dev/null && echo A || echo D')
                logtail = _run(studio, f'tail -c 1500 {ws}/render.log 2>/dev/null || true')
                fails = 0
            except Exception as e:
                fails += 1
                _log(log, f'lane lightning: probe error ({fails}/{LANE_FAILS_BEFORE_ERROR}): {e}')
                if fails >= LANE_FAILS_BEFORE_ERROR:
                    return False, f'Lightning unreachable: {e}'
                continue

            done, completed = _state_done(state)

            # Bank each finished chapter the moment it appears.
            for slug in sorted(completed):
                dest = targets.get(slug)
                if dest is None or dest in harvested:
                    continue
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    studio.download_file(f'{ws}/out/{_mp3_name(manifest, slug)}', str(dest))
                    if dest.stat().st_size > 10_000:
                        harvested.add(dest)
                        _log(log, f'lane lightning: banked {dest.name}')
                except Exception as e:
                    _log(log, f'lane lightning: harvest {slug} deferred ({e})')

            elapsed_min = (time.time() - t_start) / 60
            if on_status:
                on_status('running', elapsed_min, (done, total))

            if len(completed) >= len(targets) and len(harvested) == len(targets):
                _log(log, f'lane lightning: all {len(targets)} chapters banked '
                          f'in {elapsed_min:.0f} min')
                return True, f'all {len(targets)} chapters rendered in {elapsed_min:.0f} min'

            if not alive:
                if '10h budget' in logtail:
                    # The runner's own safety cap: a clean, resumable exit.
                    budget_relaunches += 1
                    _log(log, f'lane lightning: 10 h self-cap — relaunching to resume '
                              f'({budget_relaunches})')
                    launch()
                elif crash_relaunches < MAX_CRASH_RELAUNCHES:
                    crash_relaunches += 1
                    _log(log, f'lane lightning: runner exited early — relaunch '
                              f'{crash_relaunches}/{MAX_CRASH_RELAUNCHES}; log tail:\n'
                              f'{logtail[-500:]}')
                    launch()
                else:
                    return False, f'runner died: {logtail[-600:]}'
    finally:
        # Cost discipline: a studio WE started must not bill after the job.
        # A studio that was already running belongs to whoever left it up.
        if started_here:
            try:
                studio.stop()
                _log(log, 'lane lightning: studio stopped (billing ends here)')
            except Exception as e:
                _log(log, f'lane lightning: studio stop failed ({e}) — check the '
                          f'Render Lanes panel; a running studio bills by the hour')


# --------------------------------------------------------------------------
# Colab (SSH control plane)
# --------------------------------------------------------------------------

def _ssh_base() -> list:
    import lanes as L
    host = L._cfg('COLAB_SSH_HOST')
    if not host:
        raise RuntimeError('Colab bridge not configured (Settings → Render Lanes)')
    user = L._cfg('COLAB_SSH_USER', 'dave')
    port = L._cfg('COLAB_SSH_PORT', '22')
    base = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6',
            '-o', 'StrictHostKeyChecking=accept-new']
    if port and port != '22':
        base += ['-p', str(port)]
    base.append(f'{user}@{host}')
    return base


def _ssh(cmd: str, timeout=90) -> str:
    r = subprocess.run(_ssh_base() + [cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or 'ssh failed').strip().splitlines()
        raise RuntimeError(msg[-1] if msg else 'ssh failed')
    return r.stdout


def _scp(local, remote, timeout=600):
    """Push local -> remote. Modern scp defaults to SFTP, which does NOT expand
    '~' in remote paths — callers pass absolute paths (resolved from $HOME)."""
    import lanes as L
    host, user, port = L._cfg('COLAB_SSH_HOST'), L._cfg('COLAB_SSH_USER', 'dave'), L._cfg('COLAB_SSH_PORT', '22')
    cmd = ['scp', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6',
           '-o', 'StrictHostKeyChecking=accept-new']
    if port and port != '22':
        cmd += ['-P', str(port)]
    cmd += [str(local), f'{user}@{host}:{remote}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or 'scp failed').strip().splitlines()[-1])


def _scp_pull(remote, local, timeout=600):
    import lanes as L
    host, user, port = L._cfg('COLAB_SSH_HOST'), L._cfg('COLAB_SSH_USER', 'dave'), L._cfg('COLAB_SSH_PORT', '22')
    cmd = ['scp', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6',
           '-o', 'StrictHostKeyChecking=accept-new']
    if port and port != '22':
        cmd += ['-P', str(port)]
    cmd += [f'{user}@{host}:{remote}', str(local)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or 'scp failed').strip().splitlines()[-1])


def render_colab(bundle: Path, manifest: dict, out_dir: Path,
                 log=None, on_status=None) -> tuple:
    """SSH -> lane_ctl.sh on the control-plane host: submit the job to the
    google-colab-cli plane, poll its state, pull banked chapters. lane_ctl owns
    the remote session lifecycle (submit/progress/fetch/done/stop/log)."""
    import lanes as L
    ctl = L._cfg('COLAB_LANE_CTL', 'as-lane/lane_ctl.sh')
    home = _ssh('echo $HOME').strip()
    workdir = f'{home}/as-lane/jobs'
    job_tag = f'fish{int(time.time())}'
    job_dir = f'{workdir}/{job_tag}'
    targets = _harvest_targets(manifest, out_dir)
    total = _total_sents(manifest)
    harvested = {p for p in targets.values() if p.exists()}
    fails = 0
    stopped = False
    t_start = time.time()
    max_hours = _max_hours('colab')

    def stop_job():
        nonlocal stopped
        if stopped:
            return
        stopped = True
        try:
            _ssh(f'bash -lc "{ctl} stop {job_tag}"', timeout=60)
        except Exception as e:
            _log(log, f'lane colab: stop probe failed ({e}) — check the lanes panel')

    try:
        _log(log, f'lane colab: pushing bundle to {job_dir} on {L._cfg("COLAB_SSH_HOST")}')
        _ssh(f'mkdir -p {job_dir}/out')
        _scp(bundle, f'{job_dir}/as_bundle.zip')
        _scp(runner_path(), f'{job_dir}/runner.py')
        _ssh(f'bash -lc "{ctl} submit {job_tag}"', timeout=300)
        _log(log, f'lane colab: session submitted ({job_tag}); cold start ≈ 5-10 min')

        while True:
            time.sleep(POLL_SECONDS)
            if time.time() - t_start > max_hours * 3600:
                stop_job()
                return False, f'lane budget cap ({max_hours} h) reached; session stopped — resume with Retry'
            try:
                payload = json.loads(_ssh(f'bash -lc "{ctl} progress {job_tag}"'))
                fails = 0
            except Exception as e:
                fails += 1
                _log(log, f'lane colab: probe error ({fails}/{LANE_FAILS_BEFORE_ERROR}): {e}')
                if fails >= LANE_FAILS_BEFORE_ERROR:
                    stop_job()
                    return False, f'colab bridge unreachable: {e}'
                continue

            state = payload.get('state') or {}
            done, completed = _state_done(state)

            for slug in sorted(completed):
                dest = targets.get(slug)
                if dest is None or dest in harvested:
                    continue
                try:
                    _ssh(f'bash -lc "{ctl} fetch {job_tag} {_mp3_name(manifest, slug)}"',
                         timeout=180)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    _scp_pull(f'{job_dir}/out/{_mp3_name(manifest, slug)}', dest)
                    if dest.stat().st_size > 10_000:
                        harvested.add(dest)
                        _log(log, f'lane colab: banked {dest.name}')
                except Exception as e:
                    _log(log, f'lane colab: harvest {slug} deferred ({e})')

            if on_status:
                on_status('running', (time.time() - t_start) / 60, (done, total))

            if len(completed) >= len(targets) and len(harvested) == len(targets):
                try:
                    _ssh(f'bash -lc "{ctl} done {job_tag}"', timeout=60)
                finally:
                    stopped = True
                _log(log, f'lane colab: all {len(targets)} chapters banked')
                return True, f'all {len(targets)} chapters rendered'

            if payload.get('dead_permanent'):
                stop_job()
                return False, (f"runner died on lane: "
                               f"{str(payload.get('log_tail') or '')[-600:]}")
    except BaseException:
        # Cancelled or crashed: never leave a session burning compute units.
        stop_job()
        raise
    finally:
        pass


# --------------------------------------------------------------------------
# Public entry
# --------------------------------------------------------------------------

def render_on_lane(epub_path, voice, lane, start, end, out_dir,
                   log=None, on_status=None, resume=False) -> tuple:
    """Render chapters [start..end] of *epub_path* on *lane* into out_dir.

    Returns (ok, msg). Raises whatever on_status raises (cancellation) after
    doing lane-side cleanup — same convention as kaggle_render.render_on_kaggle.
    """
    ready, why = lane_ready(lane)
    if not ready:
        return False, why
    bundle, manifest = _build_bundle(epub_path, start, end, log)
    if not manifest.get('chapters'):
        return False, f'no renderable chapters in range {start}-{end}'

    if lane == 'lightning':
        return render_lightning(bundle, manifest, Path(out_dir),
                                log=log, on_status=on_status)
    if lane == 'colab':
        return render_colab(bundle, manifest, Path(out_dir),
                            log=log, on_status=on_status)
    return False, why or f'lane {lane} cannot render fish books yet'
