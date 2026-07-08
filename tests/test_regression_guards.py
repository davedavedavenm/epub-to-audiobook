"""Regression guards for the 2026-07-07 incident fixes (see OPERATIONS.md).

These are deliberate tripwires: if someone reverts or refactors away one of
the incident fixes, a test fails naming the incident it re-opens. Structural
assertions on the source are crude but honest — they encode invariants that
full integration tests (docker + DB + engines) can't cheaply cover.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'webapp' / 'app.py').read_text(encoding='utf-8')
CB_SERVER = (ROOT / 'chatterbox' / 'server.py').read_text(encoding='utf-8')
TADA_SERVER = (ROOT / 'tada' / 'server.py').read_text(encoding='utf-8')
COMPOSE = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')


# --- incident 2026-07-07a: retries must actually run ---

def test_retry_clears_container_name():
    """Job d67c50ac: stale container_name aborted every auto-retry.

    Applies to EVERY path that requeues a job (auto-retry, orphan recovery,
    bulk retry-failed): a stale container_name trips the duplicate-start
    guard and silently no-ops the retry.
    """
    blocks = re.findall(r"UPDATE jobs\s+SET status\s?=\s?'queued',.*?WHERE id\s?=\s?\?", APP, re.S)
    assert len(blocks) >= 3, f"expected >=3 requeue UPDATEs, found {len(blocks)}"
    for b in blocks:
        assert re.search(r"container_name\s?=\s?NULL", b), (
            "a requeue path does not clear container_name — re-opens "
            "incident 2026-07-07a:\n" + b[:200])


def test_job_spawns_respect_queue_runner_flag():
    """The webapp must not race the worker (QUEUE_RUNNER_ENABLED=0)."""
    assert 'threading.Thread(target=start_next_queued_job' not in APP, \
        "direct start_next_queued_job spawn bypasses QUEUE_RUNNER_ENABLED"


# --- incident 2026-07-07b: engine OOM death-spiral ---

def test_engine_servers_serialize_generation():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert '_GEN_LOCK' in src and 'with _GEN_LOCK' in src, \
            f"{name} server generation no longer serialized — re-opens OOM incident 2026-07-07b"
        assert 'inference_mode' in src, f"{name} server lost inference_mode"


def test_engine_containers_have_memory_caps():
    for svc in ('chatterbox-tts', 'tada-tts'):
        block = COMPOSE.split(f'{svc}:', 1)[1][:800]
        assert 'mem_limit' in block, \
            f"{svc} lost its mem_limit — kernel OOM kills return (incident 2026-07-07b)"


def test_slow_engine_timeout_floor():
    assert 'SLOW_ENGINE_MIN_TIMEOUT' in APP or 'Timeout floored' in APP, \
        "slow-engine timeout floor removed — full books will time out again"


def test_metrics_only_from_full_books():
    assert 'partial-range jobs pollute' in APP, \
        "conversion metrics gating removed — ETA pollution returns"


# --- GPU images (incident 2026-07-06/07c) ---

def test_engine_images_gpu_capable():
    for eng in ('chatterbox', 'tada'):
        df = (ROOT / eng / 'Dockerfile').read_text(encoding='utf-8')
        assert 'NVIDIA_VISIBLE_DEVICES' in df, f"{eng} image lost NVIDIA env — silent CPU on GPU hosts"
        assert 'download.pytorch.org/whl/cu' in df, f"{eng} image lost explicit CUDA torch"


def test_health_reports_cuda():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert 'cuda_available' in src, f"{name} /health no longer reports CUDA — GPU issues undiagnosable"


# --- engine health lockdown ---

def test_engine_offline_queue_gate():
    assert 'engine is offline' in APP and 'check_engines_health' in APP, \
        "409 engine-offline gate removed — jobs can queue into dead engines again"


# --- GPU cost safety ---

def test_gpu_render_gate_default_off():
    assert "gpu_render_enabled" in APP and "GPU_RENDER_ENABLED', '0'" in APP.replace('"', "'"), \
        "GPU render gate weakened — paid GPU no longer default-off"


# --- incident 2026-07-08: cross-process recovery race ---

def test_recovery_has_cross_process_lock():
    """Resume API (webapp) and orphan cleanup (worker) raced two recovery
    threads; in-memory guards cannot work across processes."""
    assert 'recovery_lock_' in APP,         "cross-process recovery DB lock removed — re-opens 2026-07-08 recovery race"
