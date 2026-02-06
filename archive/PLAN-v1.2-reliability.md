# v1.2 Reliability & Intelligence Plan

## Overview
Three major improvements to make Audiobook Studio more robust and intelligent.

---

## Feature A: Library WhatsApp Number Input

### Current State
- Library tab has WhatsApp checkbox but no number field
- Uses DEFAULT_WHATSAPP_NUMBER env var (set in environment)
- Convert tab has full number input

### Changes Required

**1. HTML (index.html)**
```html
<!-- In library-header, after WhatsApp checkbox -->
<input type="tel" id="library-whatsapp-number"
       class="whatsapp-input library-whatsapp-input"
       placeholder="Phone (optional, uses default)">
```

**2. CSS**
```css
.library-whatsapp-input {
    width: 160px;
    display: none;  /* Hidden until checkbox checked */
}
.library-whatsapp-input.visible {
    display: block;
}
```

**3. JavaScript**
```javascript
// Show/hide number input when checkbox toggled
document.getElementById('library-notify-whatsapp').addEventListener('change', (e) => {
    document.getElementById('library-whatsapp-number')
        .classList.toggle('visible', e.target.checked);
});

// In convertFromLibrary(), pass the number
const whatsappNumber = document.getElementById('library-whatsapp-number').value || null;
// Include in POST body
```

**4. Backend (app.py)**
- `/api/library/convert` already accepts `whatsapp_number` parameter
- No backend changes needed

### Files to Modify
- `webapp/templates/index.html` (HTML + CSS + JS)

---

## Feature B: ETA Learning Algorithm

### Current State
- ETA calculated from: `char_count / 600` (assuming 600 chars/min)
- Static, doesn't learn from actual performance
- Often inaccurate (some voices faster, some files denser)

### Proposed Solution

**New Database Table: `conversion_metrics`**
```sql
CREATE TABLE conversion_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice TEXT NOT NULL,
    engine TEXT NOT NULL,
    file_type TEXT NOT NULL,  -- epub, pdf, mobi, txt
    char_count INTEGER NOT NULL,
    chapter_count INTEGER NOT NULL,
    actual_duration_seconds INTEGER NOT NULL,
    chars_per_second REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Learning Algorithm**
1. On job completion, record actual metrics
2. Calculate `chars_per_second` for that voice/engine/format combo
3. Store in metrics table
4. When estimating new job:
   - Query avg `chars_per_second` for matching voice+engine+format
   - Fall back to engine average if no voice match
   - Fall back to global average (600 chars/min = 10 chars/sec) if no data

**ETA Calculation Formula**
```python
def estimate_eta(voice, engine, file_type, char_count):
    # Try exact match
    rate = get_avg_rate(voice, engine, file_type)

    if not rate:
        # Try engine + format
        rate = get_avg_rate(None, engine, file_type)

    if not rate:
        # Global default
        rate = 10  # chars/second

    # Add 20% buffer for safety
    eta_seconds = (char_count / rate) * 1.2
    return int(eta_seconds / 60)  # Return minutes
```

### Files to Modify
- `webapp/app.py` - Add metrics table, recording, and estimation
- Database migration on startup

---

## Feature C: Orphan Job Detection & Recovery

### Current State
- Jobs can get stuck in "converting" status if container dies
- No automatic detection or recovery
- Manual intervention required (cancel + retry)

### Proposed Solution

**1. Startup Cleanup (app.py)**
```python
def cleanup_orphan_jobs():
    """Run on webapp startup - detect and handle orphan jobs"""

    # Find all jobs marked as "converting"
    converting_jobs = db.execute(
        "SELECT id, container_name FROM jobs WHERE status = 'converting'"
    ).fetchall()

    for job in converting_jobs:
        # Check if container actually exists and is running
        container_exists = check_container_running(job['container_name'])

        if not container_exists:
            # Mark as failed with clear reason
            db.execute("""
                UPDATE jobs
                SET status = 'failed',
                    error = 'Container died unexpectedly. Click Retry to restart.'
                WHERE id = ?
            """, (job['id'],))

            logger.warning(f"Orphan job {job['id']} marked as failed")

    db.commit()
```

**2. Health Check Endpoint**
```python
@app.route('/api/health')
def health_check():
    """Check system health including Kokoro TTS"""
    checks = {
        'webapp': 'ok',
        'database': check_db_connection(),
        'kokoro': check_kokoro_health(),
        'disk_space': check_disk_space()
    }

    all_ok = all(v == 'ok' for v in checks.values())
    return jsonify(checks), 200 if all_ok else 503
```

**3. Watchdog Background Task**
```python
import threading
import time

def watchdog_loop():
    """Background thread to monitor job health"""
    while True:
        time.sleep(60)  # Check every minute

        # Find jobs running longer than 2x their ETA
        overdue_jobs = db.execute("""
            SELECT id, started_at, eta_minutes
            FROM jobs
            WHERE status = 'converting'
            AND datetime(started_at, '+' || (eta_minutes * 2) || ' minutes') < datetime('now')
        """).fetchall()

        for job in overdue_jobs:
            # Check if container is still making progress
            # If not, mark as stalled
            logger.warning(f"Job {job['id']} exceeded 2x ETA, checking health...")

# Start watchdog on app init
watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
watchdog_thread.start()
```

**4. Auto-Retry Logic**
```python
def handle_failed_job(job_id, error_type):
    """Handle job failure with auto-retry logic"""

    job = get_job(job_id)
    retry_count = job.get('retry_count', 0)

    if retry_count < 3 and error_type in ['container_died', 'timeout']:
        # Auto-retry with exponential backoff
        delay = 30 * (2 ** retry_count)  # 30s, 60s, 120s

        db.execute("""
            UPDATE jobs
            SET status = 'queued',
                retry_count = retry_count + 1,
                error = NULL
            WHERE id = ?
        """, (job_id,))

        logger.info(f"Auto-retrying job {job_id} (attempt {retry_count + 1}/3)")
    else:
        # Max retries exceeded, mark as permanently failed
        db.execute("""
            UPDATE jobs
            SET status = 'failed',
                error = ?
            WHERE id = ?
        """, (f"Failed after {retry_count} retries: {error_type}", job_id))
```

### Files to Modify
- `webapp/app.py` - Startup cleanup, watchdog, health check, auto-retry

---

## Implementation Order

### Phase 1: Quick Wins (30 min)
1. Library WhatsApp number input
2. Basic orphan job detection on startup

### Phase 2: Core Reliability (1 hour)
3. Health check endpoint
4. Watchdog background thread
5. Auto-retry with backoff

### Phase 3: Intelligence (1 hour)
6. Metrics table schema
7. Record metrics on job completion
8. ETA learning algorithm
9. Update estimation to use learned data

---

## Database Schema Changes

```sql
-- Add to jobs table
ALTER TABLE jobs ADD COLUMN retry_count INTEGER DEFAULT 0;

-- New metrics table
CREATE TABLE IF NOT EXISTS conversion_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice TEXT NOT NULL,
    engine TEXT NOT NULL,
    file_type TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    chapter_count INTEGER NOT NULL,
    actual_duration_seconds INTEGER NOT NULL,
    chars_per_second REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX idx_metrics_lookup ON conversion_metrics(voice, engine, file_type);
```

---

## Testing Plan

### A. Library WhatsApp (IMPLEMENTED 2026-02-04)
- [x] Check WhatsApp, verify number field appears
- [ ] Convert book with custom number, verify in job
- [ ] Convert book without number, verify uses default

### B. ETA Learning
- [ ] Complete 3+ jobs with same voice
- [ ] Check metrics table has entries
- [ ] New job shows improved ETA estimate
- [ ] Different voices show different estimates

### C. Orphan Recovery
- [ ] Kill a container mid-job
- [ ] Restart webapp, verify job marked failed
- [ ] Verify retry button works
- [ ] Test auto-retry by simulating failure

### D. Watchdog
- [ ] Start a job, wait for 2x ETA
- [ ] Verify watchdog logs warning
- [ ] Test auto-retry triggers

---

## Rollback Plan

All changes are additive. To rollback:
1. Revert git commit
2. Rebuild container
3. Database changes are non-destructive (new columns/tables only)
