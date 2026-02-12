"""
Queue worker process.
Runs the queue loop + watchdog separate from the web UI.
"""

import time

from app import app, is_queue_paused, maybe_start_next_queued_job


def main():
    app.logger.info("Worker starting")
    while True:
        try:
            if not is_queue_paused():
                # Try to fill all concurrent slots
                while maybe_start_next_queued_job():
                    pass
            time.sleep(10)
        except Exception as e:
            app.logger.error(f"Worker loop error: {e}")
            time.sleep(10)


if __name__ == '__main__':
    main()
