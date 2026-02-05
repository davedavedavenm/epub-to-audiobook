# Audiobook Studio - Comprehensive Test Plan

## Test Files
- `test-audiobook.epub` - Minimal 2KB EPUB (2 chapters)
- `test-audiobook.txt` - Plain text file

## Test Matrix

### 1. Upload & Format Support

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| EPUB upload | Drag/drop test-audiobook.epub | Shows filename with EPUB badge | |
| PDF upload | Drag/drop a PDF | Shows filename with PDF badge | |
| TXT upload | Drag/drop test-audiobook.txt | Shows filename with TXT badge | |
| MOBI upload | Drag/drop a MOBI (Calibre converts) | Shows filename with MOBI badge | |
| Invalid format | Try uploading .exe | Shows error, rejects file | |

### 2. Voice Selection

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Kokoro voices load | Page load | British/American/European sections show | |
| Piper voices load | Click Piper tab | Piper voices display | |
| Voice selection | Click a voice pill | Pill highlights blue | |
| Voice preview | Click ▶ on any voice | Audio plays | |
| Voice search | Type "Emma" | Only Emma voices show | |
| Engine switch | Switch Kokoro → Piper | Voice selection resets | |

### 3. Conversion

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Basic convert | Upload EPUB, select voice, click Convert | Job created, redirects to Queue | |
| Voice mix | Select secondary voice, convert | Job has voice2 set | |
| Chapter range | Set start=1, end=1 | Only chapter 1 converts | |
| WhatsApp notification | Check WhatsApp, enter number | Job has notify_whatsapp=1 | |
| Telegram notification | Check Telegram | Job has notify_telegram=1 | |

### 4. Queue Tab

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Jobs load | Switch to Queue tab | Active/waiting jobs display | |
| Progress updates | While job running | % and chapter update | |
| Cancel job | Click cancel on a job | Job status = cancelled | |
| Retry job | Click retry on cancelled job | New container starts | |

### 5. Library Tab

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Books load | Switch to Library tab | 46+ books display | |
| Search filter | Type "Alice" | Only matching books show | |
| Convert from library | Click Convert button | Job queued with selected voice | |
| Status indicators | Check completed/converting books | Shows ✅ Done or ⏳ % | |
| Voice selection | Change voice dropdown | Subsequent converts use new voice | |
| WhatsApp toggle | Check WhatsApp checkbox | Convert uses default WhatsApp number | |
| Telegram toggle | Check Telegram checkbox | Convert includes Telegram notification | |

### 6. History Tab

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Completed jobs load | Switch to History tab | Completed audiobooks display | |
| Download button | Click download | Downloads ZIP of generated audio files | |
| Sync to ABS | Click "Sync to ABS" | Files copied to Audiobookshelf | |
| Delete job | Click delete | Job removed from history | |

### 7. Theme Switching

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Light theme | Click "Light" | White/gray background | |
| Dark theme | Click "Dark" | Slate blue dark theme | |
| Midnight theme | Click "Midnight" | Deep purple/indigo theme | |
| Forest theme | Click "Forest" | Deep green theme | |
| Theme persistence | Refresh page | Same theme selected | |

### 8. Failsafe & Recovery

| Test | Steps | Expected | Status |
|------|-------|----------|--------|
| Orphan job detection | Restart webapp container | Stuck jobs detectable | |
| Job timeout | Job runs past ETA | Should warn or fail gracefully | |
| Kokoro down | Stop kokoro-tts | Error message, job fails cleanly | |
| File not found | Delete upload before convert | Clear error message | |
| Disk full | Simulate low space | Graceful failure | |

## Automated API Tests

```bash
# Run from zorin
# 1. Voices
curl -s http://localhost:8881/api/voices | jq '.voices | keys | length'

# 2. Preview
curl -s -w '%{http_code}' http://localhost:8881/api/preview/bf_emma -o /dev/null

# 3. Jobs
curl -s http://localhost:8881/api/jobs | jq 'length'

# 4. Library
curl -s http://localhost:8881/api/library | jq 'length'

# 5. History
curl -s http://localhost:8881/api/history | jq 'length'

# 6. Submit test job
curl -X POST http://localhost:8881/api/convert \
  -F "file=@test-audiobook.epub" \
  -F "voice=bf_emma" \
  -F "engine=kokoro"
```

## Reliability Checks (Current)

1. Verify startup recovery marks/reconciles orphan jobs correctly.
2. Verify watchdog logs and recovery behavior when a container dies.
3. Verify auto-retry caps at 3 attempts and surfaces clear error messages.
4. Verify queue survives webapp restart and resumes processing in order.
