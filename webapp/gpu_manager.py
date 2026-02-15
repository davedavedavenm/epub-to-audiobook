"""
GPU Auto-Scaling Manager for Vast.ai

Manages the lifecycle of a GPU Kokoro instance on Vast.ai:
  scale_up()   → search → create instance → wait → tunnel → verify
  scale_down() → restore CPU → kill tunnel → destroy instance

The SSH tunnel runs as a host-network Docker container so that other
containers can reach the GPU Kokoro at 172.19.0.1:8890.

State is kept in-memory (singleton). If the worker restarts, the GPU
instance is detected via Vast.ai API and re-adopted.
"""

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────
VASTAI_TEMPLATE_HASH = os.environ.get(
    'VASTAI_TEMPLATE_HASH', 'e2588a22cf5eef43df3d444ef4f25705')
VASTAI_TEMPLATE_ID = int(os.environ.get('VASTAI_TEMPLATE_ID', '343755'))
VASTAI_CLI = os.environ.get('VASTAI_CLI', '/tmp/vast.py')
VASTAI_SSH_KEY = os.environ.get(
    'VASTAI_SSH_KEY', '/root/.ssh/vastai_ed25519')
VASTAI_API_KEY_FILE = os.environ.get(
    'VASTAI_API_KEY_FILE', '/root/.config/vastai/vast_api_key')

GPU_TUNNEL_PORT = int(os.environ.get('GPU_TUNNEL_PORT', '8890'))
GPU_KOKORO_URL = os.environ.get(
    'GPU_KOKORO_URL', f'http://172.19.0.1:{GPU_TUNNEL_PORT}/v1')
CPU_KOKORO_URL = os.environ.get(
    'CPU_KOKORO_URL', 'http://kokoro-tts:8880/v1')
DOCKER_GATEWAY_IP = os.environ.get('DOCKER_GATEWAY_IP', '172.19.0.1')

AUTOSCALE_ENABLED = os.environ.get(
    'AUTOSCALE_ENABLED', 'false').lower() in ('1', 'true', 'yes')
AUTOSCALE_THRESHOLD = int(os.environ.get('AUTOSCALE_THRESHOLD', '3'))
COST_CAP_DOLLARS = float(os.environ.get('AUTOSCALE_COST_CAP', '1.00'))
IDLE_TIMEOUT_MINUTES = int(os.environ.get('GPU_IDLE_TIMEOUT', '10'))
PROVISION_TIMEOUT_S = int(os.environ.get('GPU_PROVISION_TIMEOUT', '300'))
TUNNEL_CONTAINER = 'gpu-ssh-tunnel'

GPU_CONCURRENT_JOBS = int(os.environ.get('GPU_CONCURRENT_JOBS', '3'))
CPU_CONCURRENT_JOBS = int(os.environ.get('CPU_CONCURRENT_JOBS', '1'))


def _vast(*args) -> subprocess.CompletedProcess:
    """Run a vast.py CLI command."""
    cmd = ['python3', VASTAI_CLI] + list(args)
    logger.debug(f"vast.py: {' '.join(cmd)}")
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=60)


def _vast_json(*args) -> list | dict | None:
    """Run a vast.py command and parse JSON output."""
    result = _vast(*args)
    if result.returncode != 0:
        logger.warning(f"vast.py error: {result.stderr[:300]}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"vast.py non-JSON output: {result.stdout[:300]}")
        return None


class GPUManager:
    """Manages a single Vast.ai GPU instance lifecycle."""

    def __init__(self):
        self.state = 'idle'  # idle | provisioning | active | tearing_down | error
        self.instance_id = None
        self.instance_addr = None  # SSH host
        self.instance_port = None  # SSH port
        self.cost_per_hour = 0.0
        self.session_start = None
        self.last_job_activity = None  # For idle timeout
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────

    def scale_up(self) -> bool:
        """Provision a GPU instance, create tunnel, verify Kokoro.

        Returns True on success, False on failure (falls back to CPU).
        """
        with self._lock:
            if self.state != 'idle':
                logger.info(f"GPU scale_up skipped (state={self.state})")
                return self.state == 'active'
            self.state = 'provisioning'

        logger.info("GPU: Starting scale-up")
        try:
            # 1. Ensure vast.py CLI is available
            if not self._ensure_cli():
                raise RuntimeError("Cannot download vast.py CLI")

            # 2. Search for cheapest instance matching template
            instance_id = self._create_instance()
            if not instance_id:
                raise RuntimeError("No suitable GPU instance found")
            self.instance_id = instance_id
            logger.info(f"GPU: Created instance {instance_id}")

            # 3. Wait for instance to be running
            if not self._wait_instance_running(timeout=PROVISION_TIMEOUT_S):
                raise RuntimeError(
                    f"Instance {instance_id} not ready after {PROVISION_TIMEOUT_S}s")

            # 4. Get SSH connection details
            if not self._get_ssh_details():
                raise RuntimeError("Cannot get SSH details for instance")

            # 5. Wait for Kokoro to be healthy on the instance
            if not self._wait_remote_kokoro(timeout=180):
                logger.warning("GPU Kokoro not ready yet, continuing to try via tunnel")

            # 6. Create SSH tunnel
            if not self._create_tunnel():
                raise RuntimeError("Failed to create SSH tunnel")

            # 7. Verify tunnel works (Kokoro responds via tunnel)
            if not self._verify_tunnel(timeout=60):
                raise RuntimeError("Tunnel created but Kokoro not responding")

            # 8. Switch to GPU mode
            self._switch_to_gpu()

            with self._lock:
                self.state = 'active'
                self.session_start = datetime.now()
                self.last_job_activity = datetime.now()

            logger.info(
                f"GPU: Scale-up complete. Instance {instance_id}, "
                f"${self.cost_per_hour:.3f}/hr")
            return True

        except Exception as e:
            logger.error(f"GPU: Scale-up failed: {e}")
            # Clean up partial provisioning
            self._cleanup_on_failure()
            with self._lock:
                self.state = 'idle'
            return False

    def scale_down(self) -> bool:
        """Tear down GPU, kill tunnel, restore CPU config.

        Returns True on success.
        """
        with self._lock:
            if self.state not in ('active', 'error'):
                return True
            self.state = 'tearing_down'

        logger.info("GPU: Starting scale-down")
        try:
            # 1. Switch back to CPU
            self._switch_to_cpu()

            # 2. Kill tunnel
            self._kill_tunnel()

            # 3. Destroy instance
            if self.instance_id:
                logger.info(f"GPU: Destroying instance {self.instance_id}")
                _vast('destroy', 'instance', str(self.instance_id))

            cost = self.session_cost()
            logger.info(f"GPU: Scale-down complete. Session cost: ${cost:.2f}")

            # Reset state
            with self._lock:
                self.state = 'idle'
                self.instance_id = None
                self.instance_addr = None
                self.instance_port = None
                self.cost_per_hour = 0.0
                self.session_start = None
                self.last_job_activity = None

            return True

        except Exception as e:
            logger.error(f"GPU: Scale-down error: {e}")
            with self._lock:
                self.state = 'error'
            return False

    def health_check(self) -> bool:
        """Verify GPU Kokoro is responding via tunnel. Returns True if healthy."""
        if self.state != 'active':
            return False
        try:
            import requests
            resp = requests.get(
                f"{GPU_KOKORO_URL}/audio/voices", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def handle_health_failure(self):
        """Called when health_check fails. Try to recreate tunnel, or tear down."""
        logger.warning("GPU: Health check failed, attempting tunnel recovery")

        # Try recreating tunnel
        self._kill_tunnel()
        if self._create_tunnel() and self._verify_tunnel(timeout=30):
            logger.info("GPU: Tunnel recovered")
            return

        # Tunnel recreation failed — instance might be dead
        logger.error("GPU: Cannot recover tunnel, tearing down")
        self.scale_down()

    def check_idle_timeout(self):
        """Tear down GPU if idle for IDLE_TIMEOUT_MINUTES."""
        if self.state != 'active' or not self.last_job_activity:
            return
        idle_minutes = (datetime.now() - self.last_job_activity).total_seconds() / 60
        if idle_minutes >= IDLE_TIMEOUT_MINUTES:
            logger.info(
                f"GPU: Idle for {idle_minutes:.0f} min, tearing down")
            self.scale_down()

    def check_cost_cap(self):
        """Tear down GPU if session cost exceeds COST_CAP_DOLLARS."""
        if self.state != 'active':
            return
        cost = self.session_cost()
        if cost >= COST_CAP_DOLLARS:
            logger.warning(
                f"GPU: Cost cap reached (${cost:.2f} >= ${COST_CAP_DOLLARS:.2f}), "
                f"tearing down")
            self.scale_down()

    def mark_activity(self):
        """Mark that a job is actively using the GPU (resets idle timer)."""
        self.last_job_activity = datetime.now()

    def session_cost(self) -> float:
        """Calculate running cost based on elapsed time."""
        if not self.session_start or self.cost_per_hour <= 0:
            return 0.0
        elapsed_hours = (datetime.now() - self.session_start).total_seconds() / 3600
        return elapsed_hours * self.cost_per_hour

    def get_status(self) -> dict:
        """Return current GPU state for API/UI display."""
        return {
            'state': self.state,
            'instance_id': self.instance_id,
            'cost_per_hour': self.cost_per_hour,
            'session_cost': round(self.session_cost(), 3),
            'session_minutes': round(
                (datetime.now() - self.session_start).total_seconds() / 60, 1
            ) if self.session_start else 0,
            'autoscale_enabled': AUTOSCALE_ENABLED,
            'autoscale_threshold': AUTOSCALE_THRESHOLD,
            'cost_cap': COST_CAP_DOLLARS,
        }

    # ── Private Methods ───────────────────────────────────────────

    def _ensure_cli(self) -> bool:
        """Download vast.py if not present."""
        if Path(VASTAI_CLI).exists():
            return True
        logger.info("GPU: Downloading vast.py CLI")
        try:
            result = subprocess.run(
                ['curl', '-s',
                 'https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py',
                 '-o', VASTAI_CLI],
                capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"GPU: Failed to download vast.py: {e}")
            return False

    def _create_instance(self) -> str | None:
        """Search for cheapest offer and create instance. Returns instance ID."""
        # Search for offers matching our template requirements
        result = _vast(
            'search', 'offers',
            '--type', 'interruptible',
            '--gpu-name', 'RTX 3060',
            '--disk', '20',
            '--order', 'dph_total',
            '--limit', '5',
            '--raw')
        if result.returncode != 0:
            logger.error(f"GPU: Search failed: {result.stderr[:200]}")
            return None

        try:
            offers = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error(f"GPU: Cannot parse offers: {result.stdout[:200]}")
            return None

        if not offers:
            logger.error("GPU: No matching offers found")
            return None

        # Pick cheapest
        offer = offers[0]
        offer_id = offer.get('id')
        self.cost_per_hour = float(offer.get('dph_total', 0))
        logger.info(
            f"GPU: Selected offer {offer_id} at ${self.cost_per_hour:.3f}/hr")

        # Create instance from template
        create_result = _vast(
            'create', 'instance', str(offer_id),
            '--template', VASTAI_TEMPLATE_HASH,
            '--disk', '20',
            '--raw')
        if create_result.returncode != 0:
            logger.error(f"GPU: Create failed: {create_result.stderr[:200]}")
            return None

        try:
            data = json.loads(create_result.stdout)
            instance_id = data.get('new_contract')
            if instance_id:
                return str(instance_id)
        except (json.JSONDecodeError, KeyError):
            pass

        # Try parsing as text
        for word in create_result.stdout.split():
            if word.isdigit():
                return word

        logger.error(
            f"GPU: Cannot parse instance ID from: {create_result.stdout[:200]}")
        return None

    def _wait_instance_running(self, timeout: int = 300) -> bool:
        """Poll until instance status is 'running'."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            instances = _vast_json('show', 'instances', '--raw')
            if instances:
                for inst in instances:
                    if str(inst.get('id')) == str(self.instance_id):
                        status = inst.get('actual_status', '')
                        logger.debug(
                            f"GPU: Instance {self.instance_id} status: {status}")
                        if status == 'running':
                            return True
                        if status in ('exited', 'error'):
                            logger.error(
                                f"GPU: Instance entered {status} state")
                            return False
            time.sleep(15)
        return False

    def _get_ssh_details(self) -> bool:
        """Get SSH host and port for the instance."""
        instances = _vast_json('show', 'instances', '--raw')
        if not instances:
            return False
        for inst in instances:
            if str(inst.get('id')) == str(self.instance_id):
                ssh_host = inst.get('ssh_host')
                ssh_port = inst.get('ssh_port')
                if ssh_host and ssh_port:
                    self.instance_addr = ssh_host
                    self.instance_port = int(ssh_port)
                    logger.info(
                        f"GPU: SSH details: {ssh_host}:{ssh_port}")
                    return True
        logger.error("GPU: Cannot find SSH details for instance")
        return False

    def _wait_remote_kokoro(self, timeout: int = 180) -> bool:
        """Wait for Kokoro to be healthy on the remote instance via SSH."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # Use SSH to check health directly on the instance
                result = subprocess.run([
                    'ssh', '-i', VASTAI_SSH_KEY,
                    '-p', str(self.instance_port),
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'ConnectTimeout=5',
                    f'root@{self.instance_addr}',
                    'curl -s -o /dev/null -w "%{http_code}" http://localhost:8880/v1/audio/voices'
                ], capture_output=True, text=True, timeout=15)
                if result.stdout.strip() == '200':
                    logger.info("GPU: Remote Kokoro is healthy")
                    return True
            except Exception:
                pass
            time.sleep(10)
        return False

    def _create_tunnel(self) -> bool:
        """Create SSH tunnel as a host-network Docker container.

        Runs: ssh -L 0.0.0.0:8890:localhost:8880 root@instance
        on the host network, so all containers can reach it via 172.19.0.1:8890.
        """
        self._kill_tunnel()  # Clean up any stale tunnel

        cmd = [
            'docker', 'run', '-d',
            '--name', TUNNEL_CONTAINER,
            '--network', 'host',
            '--restart', 'unless-stopped',
            '-v', f'{VASTAI_SSH_KEY}:/key:ro',
            'alpine/ssh',
            'ssh', '-i', '/key',
            '-p', str(self.instance_port),
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-L', f'0.0.0.0:{GPU_TUNNEL_PORT}:localhost:8880',
            '-N',
            f'root@{self.instance_addr}'
        ]
        logger.info(f"GPU: Creating tunnel container")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"GPU: Tunnel container failed: {result.stderr[:200]}")
                return False
            return True
        except Exception as e:
            logger.error(f"GPU: Tunnel creation error: {e}")
            return False

    def _kill_tunnel(self):
        """Remove the tunnel container."""
        try:
            subprocess.run(
                ['docker', 'rm', '-f', TUNNEL_CONTAINER],
                capture_output=True, timeout=10)
        except Exception:
            pass

    def _verify_tunnel(self, timeout: int = 60) -> bool:
        """Verify Kokoro responds through the tunnel."""
        import requests
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"http://{DOCKER_GATEWAY_IP}:{GPU_TUNNEL_PORT}/v1/audio/voices",
                    timeout=5)
                if resp.status_code == 200:
                    logger.info("GPU: Tunnel verified — Kokoro responding")
                    return True
            except Exception:
                pass
            time.sleep(5)
        logger.error("GPU: Tunnel verification failed")
        return False

    def _switch_to_gpu(self):
        """Switch the app to use GPU Kokoro URL and higher concurrency."""
        # These are imported and modified at the app level
        import app as app_module
        app_module.KOKORO_URL = GPU_KOKORO_URL
        app_module.MAX_CONCURRENT_JOBS = GPU_CONCURRENT_JOBS
        logger.info(
            f"GPU: Switched to GPU mode (URL={GPU_KOKORO_URL}, "
            f"concurrent={GPU_CONCURRENT_JOBS})")

    def _switch_to_cpu(self):
        """Switch back to CPU Kokoro URL and single concurrency."""
        import app as app_module
        app_module.KOKORO_URL = CPU_KOKORO_URL
        app_module.MAX_CONCURRENT_JOBS = CPU_CONCURRENT_JOBS
        logger.info(
            f"GPU: Switched to CPU mode (URL={CPU_KOKORO_URL}, "
            f"concurrent={CPU_CONCURRENT_JOBS})")

    def _cleanup_on_failure(self):
        """Clean up after a failed scale-up attempt."""
        self._kill_tunnel()
        if self.instance_id:
            try:
                _vast('destroy', 'instance', str(self.instance_id))
                logger.info(f"GPU: Cleaned up instance {self.instance_id}")
            except Exception:
                pass
            self.instance_id = None
        self._switch_to_cpu()
