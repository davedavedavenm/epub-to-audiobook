"""GPU render lanes: configuration + live status for the Fish/Cillian recipe.

Three lanes can render a book with the locked recipe (CILLIAN-RECIPE.md):

  colab      headless `google-colab-cli` control plane on an SSH-reachable host
             (khpi5 in this deployment). Free — paid from the AI-Pro balance.
  kaggle     the existing free weekly GPU quota (kaggle_render backend).
  lightning  a Lightning AI studio. PAID: official rates T4 $0.55/h,
             L4 $0.79/h, L40S $2.14/h (lightning.ai/pricing, checked 2026-09-24).

Credentials never live in the repo: they come from the app settings DB (the
Settings screen) with environment-variable fallback, exactly like the Kaggle
and Modal keys already do. `lanes_status()` is TTL-cached per lane because the
UI polls it every 10 s — local configuration checks are recomputed cheaply,
network probes (SSH to the Colab host, the Lightning SDK) are shared for a
minute so a busy browser cannot hammer either endpoint.

Every lane reports the same shape so the UI has one contract:

    {'configured': bool, 'reason': str, 'state': str, 'detail': {...},
     'checked_at': float}

`state` is one of: 'ok' (usable right now), 'not-configured' (no credential),
'unreachable' (configured but the probe failed), 'error' (probe broke).
"""
import json
import os
import subprocess
import time

LANES = ('colab', 'kaggle', 'lightning')
# The lanes 'auto' is allowed to choose. The paid lane is deliberately absent:
# queueing a book is work to do, never authorization to spend (DECISIONS.md
# "Queue length must never provision a paid GPU" — the autoscale incident).
# 'lightning' is used only when NAMED: on the job (lane field) or in Settings
# (FISH_LANE). Adding it here makes an ordinary queue spend money.
FREE_LANES = ('colab', 'kaggle')

# Official on-demand rates, recorded with their source + date so no agent has
# to re-derive them from a marketing page (Authoritative-Source Gate).
LIGHTNING_RATES = {
    'T4': 0.55,
    'L4': 0.79,
    'L40S': 2.14,
    'source': 'lightning.ai/pricing, checked 2026-09-24',
}

# Network probes are slow (SSH round-trip, SDK import + REST call); the UI's
# 10 s poll reads the cache. Local checks are free and always recomputed.
_NET_TTL = 45.0
_cache: dict = {}


def _cfg(key: str, default: str = '') -> str:
    """Settings DB first (the UI writes there), environment second."""
    try:
        from app import get_setting  # lazy: app imports this module at load
        v = get_setting(key)
        if v:
            return str(v).strip()
    except Exception:
        pass
    return (os.environ.get(key) or default).strip()


def lane_configured(lane: str) -> bool:
    """Could this lane ever work here? (Credential present — not a live probe.)"""
    if lane == 'colab':
        return bool(_cfg('COLAB_SSH_HOST'))
    if lane == 'kaggle':
        if _cfg('KAGGLE_API_TOKEN'):
            return True
        try:
            import kaggle_render as KR
            return bool(KR.kaggle_ready())
        except Exception:
            return False
    if lane == 'lightning':
        return bool(_cfg('LIGHTNING_API_KEY')) and bool(_cfg('LIGHTNING_USERNAME'))
    return False


def configured_lanes() -> tuple:
    return tuple(l for l in LANES if lane_configured(l))


def lightning_sdk_available() -> bool:
    """Can the PAID Lightning lane run here at all?

    Credentials say a lane is *authorised*; this says the environment can
    *honour* it. `find_spec` first so the normal (absent) case never executes
    the module — lightning-sdk is heavy — then the exact symbols
    `_lightning_client()` imports, so a partial install is caught here rather
    than as a traceback mid-render.
    """
    import importlib.util
    try:
        if importlib.util.find_spec('lightning_sdk') is None:
            return False
        from lightning_sdk import User, Studio  # noqa: F401
        return True
    except Exception:
        return False


def resolve_lane(explicit: str | None = None) -> str:
    """Pick the lane for a fish render.

    'auto' (or empty) resolves from FREE_LANES only — colab, then kaggle — and
    NEVER falls through to the paid Lightning lane, even when it is the only
    configured one: a queued book must not be able to spend money (the
    autoscale incident, DECISIONS.md "Queue length must never provision a paid
    GPU"). If only the paid lane is configured, auto refuses with the exact
    action that authorises it instead of silently selecting it.

    An explicit pick must be a known lane, and that lane must be configured —
    otherwise it is refused with a reason rather than falling through to auto
    (an unknown FISH_LANE must never become an implicit lane choice).
    """
    if explicit in (None, '', 'auto'):
        for lane in FREE_LANES:
            if lane_configured(lane):
                return lane
        if lane_configured('lightning'):
            raise ValueError(
                "Only the paid Lightning lane is configured and auto never "
                "selects a paid lane. Name it explicitly to authorise spend: "
                "lane='lightning' on the render, or FISH_LANE=lightning in "
                "Settings → Render Lanes (rates shown there).")
        raise ValueError('No GPU lane configured — add one in Settings → Render Lanes')
    if explicit not in LANES:
        raise ValueError(f"Unknown lane '{explicit}' — choose one of: "
                         f"auto, {', '.join(LANES)}")
    if lane_configured(explicit):
        return explicit
    raise ValueError(f"Lane '{explicit}' is not configured "
                     f"(configured: {', '.join(configured_lanes()) or 'none'})")


def _probe(lane: str, fn) -> dict:
    """Run a status probe with per-lane TTL caching; never raise."""
    now = time.time()
    hit = _cache.get(lane)
    if hit and now - hit[0] < _NET_TTL:
        return hit[1]
    try:
        out = fn()
    except Exception as e:
        out = {'configured': lane_configured(lane), 'state': 'error',
               'reason': f'{type(e).__name__}: {e}', 'detail': {}}
    out.setdefault('configured', lane_configured(lane))
    out.setdefault('reason', '')
    out.setdefault('detail', {})
    out['checked_at'] = now
    _cache[lane] = (now, out)
    return out


def _status_colab() -> dict:
    """SSH to the control-plane host and read its lane_ctl.sh status JSON.

    The remote script is the only thing that knows how to talk to the Colab
    CLI (Linux-only, OAuth tokens on that host); the webapp just relays.
    """
    host = _cfg('COLAB_SSH_HOST')
    if not host:
        return {'configured': False, 'state': 'not-configured',
                'reason': 'No COLAB_SSH_HOST set (Settings → Render Lanes)'}
    user = _cfg('COLAB_SSH_USER', 'dave')
    port = _cfg('COLAB_SSH_PORT', '22')
    ctl = _cfg('COLAB_LANE_CTL', '~/as-lane/lane_ctl.sh')
    cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6',
           '-o', 'StrictHostKeyChecking=accept-new']
    if port and port != '22':
        cmd += ['-p', str(port)]
    cmd += [f'{user}@{host}', f'{ctl} status']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or 'ssh failed').strip().splitlines()
        return {'configured': True, 'state': 'unreachable',
                'reason': (msg[-1] if msg else 'ssh failed')[:200], 'detail': {}}
    try:
        detail = json.loads(r.stdout)
    except Exception:
        return {'configured': True, 'state': 'error',
                'reason': 'lane_ctl status did not return JSON', 'detail': {}}
    sessions = detail.get('sessions') or []
    busy = [s for s in sessions if str(s.get('state', '')).lower() in
            ('running', 'busy', 'alive', 'executing')]
    state = 'ok' if sessions else 'idle'
    reason = ''
    if not sessions:
        reason = 'No active Colab sessions (lanes idle)'
    return {'configured': True, 'state': state, 'reason': reason,
            'detail': {'host': host, 'sessions': sessions,
                       'harvest': detail.get('harvest') or [],
                       'scopes': detail.get('scopes') or {},
                       'progress': detail.get('progress') or {},
                       'busy_count': len(busy)}}


def _status_kaggle() -> dict:
    if not _cfg('KAGGLE_API_TOKEN') and not lane_configured('kaggle'):
        return {'configured': False, 'state': 'not-configured',
                'reason': 'No Kaggle token (Settings → Free Cloud GPU — Kaggle)'}
    try:
        import kaggle_render as KR
        used = KR.gpu_hours_used()
        weekly = KR.WEEKLY_GPU_HOURS
        left = round(max(0.0, weekly - used), 1)
        state = 'ok' if left > 0 else 'quota-exhausted'
        return {'configured': True, 'state': state,
                'reason': '' if left > 0 else 'Weekly 30 h GPU quota used up',
                'detail': {'weekly': weekly, 'used': round(used, 2), 'left': left,
                           'engines': list(KR.render_engines())}}
    except Exception as e:
        return {'configured': True, 'state': 'error',
                'reason': f'{type(e).__name__}: {e}', 'detail': {}}


def _status_lightning() -> dict:
    key = _cfg('LIGHTNING_API_KEY')
    user = _cfg('LIGHTNING_USERNAME')
    if not key or not user:
        return {'configured': False, 'state': 'not-configured',
                'reason': 'Needs LIGHTNING_API_KEY + LIGHTNING_USERNAME '
                          '(Settings → Render Lanes)'}
    try:
        import lightning_sdk  # noqa: F401  (import cost is why we cache)
    except ImportError:
        return {'configured': True, 'state': 'error',
                'reason': 'lightning-sdk not installed in this environment',
                'detail': {'rates': LIGHTNING_RATES}}
    os.environ['LIGHTNING_API_KEY'] = key
    os.environ['LIGHTNING_USERNAME'] = user
    from lightning_sdk import User
    ts = User(user).teamspaces[0]
    studios = []
    for s in ts.studios:
        st = getattr(s, 'status', '')
        st = st.value if hasattr(st, 'value') else str(st)
        mach = getattr(s, 'machine', '')
        mach = mach.value if hasattr(mach, 'value') else str(mach)
        studios.append({'name': s.name, 'status': st, 'machine': mach})
    running = [s for s in studios if str(s['status']).lower() == 'running']
    return {'configured': True, 'state': 'ok',
            'reason': '' if studios else 'No studios yet (one is created on first render)',
            'detail': {'teamspace': ts.name, 'studios': studios,
                       'running': len(running), 'rates': LIGHTNING_RATES,
                       'machine': _cfg('LIGHTNING_MACHINE', 'L4')}}


_PROBES = {'colab': _status_colab, 'kaggle': _status_kaggle,
           'lightning': _status_lightning}


def lane_status(lane: str) -> dict:
    if lane not in LANES:
        return {'configured': False, 'state': 'error',
                'reason': f'unknown lane {lane}', 'detail': {}, 'checked_at': time.time()}
    return _probe(lane, _PROBES[lane])


def lanes_status() -> dict:
    """Full status for every lane — the /api/lanes payload."""
    return {'lanes': {lane: lane_status(lane) for lane in LANES},
            'configured': list(configured_lanes()),
            'fish_available': bool(configured_lanes()),
            'updated_at': max((v['checked_at'] for v in
                               (_cache.get(l, (0, {'checked_at': 0}))[1] for l in LANES)),
                              default=0.0)}
