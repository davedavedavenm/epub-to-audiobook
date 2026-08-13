"""
Queue worker process.
Runs the queue loop + watchdog separate from the web UI.
Optionally manages teardown/health for a manually authorized paid GPU.
"""

import logging
import sys
import time

from app import (app, is_queue_paused, maybe_start_next_queued_job,
                 queued_job_count, running_job_count, set_gpu_manager)

# Ensure Flask and all loggers output to stdout (visible in `docker logs`)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
# Remove existing handlers to prevent duplicate log lines
app.logger.handlers.clear()
app.logger.addHandler(_handler)
app.logger.setLevel(logging.INFO)
app.logger.propagate = False
# Also capture gpu_manager logs
logging.getLogger('gpu_manager').addHandler(_handler)
logging.getLogger('gpu_manager').setLevel(logging.INFO)

# Legacy Vast manager (import conditionally so CPU-only deployments work fine).
# Queue-driven paid provisioning is deliberately retired: queue length is never
# authority to spend money. The manager remains for adopting/tearing down an
# instance that was started manually after an explicit user request.
try:
    from gpu_manager import GPUManager
    _gpu = GPUManager()
    set_gpu_manager(_gpu)  # Register with app so API endpoints can read status
    app.logger.info("GPU manager loaded (automatic paid provisioning disabled)")
except ImportError:
    _gpu = None
    app.logger.info("GPU manager not available — CPU only mode")


def main():
    app.logger.info("Worker starting")
    health_check_counter = 0

    while True:
        try:
            if not is_queue_paused():
                queued = queued_job_count()
                running = running_job_count()

                # A manually started paid instance is still torn down
                # automatically when work drains. There is intentionally no
                # inverse queue->scale_up path.
                if _gpu:
                    if queued == 0 and running == 0 and _gpu.state == 'active':
                        app.logger.info("Paid GPU: queue empty, tearing down GPU")
                        _gpu.scale_down()

                    # Mark activity when jobs are running (resets idle timer)
                    if running > 0 and _gpu.state == 'active':
                        _gpu.mark_activity()

                # ── Start queued jobs ─────────────────────────────
                while maybe_start_next_queued_job():
                    pass

            # ── GPU Health & Safety (every 30s = every 3 loops) ──
            if _gpu and _gpu.state == 'active':
                health_check_counter += 1
                if health_check_counter >= 3:
                    health_check_counter = 0
                    if not _gpu.health_check():
                        app.logger.warning("GPU health check failed")
                        _gpu.handle_health_failure()
                    _gpu.check_idle_timeout()
                    _gpu.check_cost_cap()

            time.sleep(10)

        except Exception as e:
            app.logger.error(f"Worker loop error: {e}")
            time.sleep(10)


if __name__ == '__main__':
    main()
