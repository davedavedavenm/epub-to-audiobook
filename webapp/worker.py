"""
Queue worker process.
Runs the queue loop + watchdog separate from the web UI.
Optionally manages GPU auto-scaling via gpu_manager.
"""

import os
import time

from app import (app, is_queue_paused, maybe_start_next_queued_job,
                 queued_job_count, running_job_count, set_gpu_manager)

# GPU auto-scaling (import conditionally so CPU-only deployments work fine)
try:
    from gpu_manager import GPUManager, AUTOSCALE_ENABLED, AUTOSCALE_THRESHOLD
    _gpu = GPUManager()
    set_gpu_manager(_gpu)  # Register with app so API endpoints can read status
    app.logger.info(
        f"GPU manager loaded (autoscale={'ON' if AUTOSCALE_ENABLED else 'OFF'}, "
        f"threshold={AUTOSCALE_THRESHOLD})")
except ImportError:
    _gpu = None
    AUTOSCALE_ENABLED = False
    app.logger.info("GPU manager not available — CPU only mode")


def main():
    app.logger.info("Worker starting")
    health_check_counter = 0

    while True:
        try:
            if not is_queue_paused():
                queued = queued_job_count()
                running = running_job_count()

                # ── GPU Auto-Scaling ──────────────────────────────
                if _gpu and AUTOSCALE_ENABLED:
                    # Scale up: enough books queued and GPU not already active
                    if queued >= AUTOSCALE_THRESHOLD and _gpu.state == 'idle':
                        app.logger.info(
                            f"Auto-scale: {queued} books queued "
                            f"(threshold={AUTOSCALE_THRESHOLD}), spinning up GPU")
                        _gpu.scale_up()

                    # Scale down: queue drained and all jobs finished
                    if queued == 0 and running == 0 and _gpu.state == 'active':
                        app.logger.info("Auto-scale: queue empty, tearing down GPU")
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
