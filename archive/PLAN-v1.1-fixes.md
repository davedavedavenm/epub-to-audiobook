# v1.1 Fix Plan - Audiobook Studio

## Issues Identified

### 1. Library Tab Empty
- **Cause**: docker-compose.yml missing OpenBooks mount
- **Fix**: Add `/mnt/openbooks:/mnt/openbooks:ro` volume and `LIBRARY_DIR=/mnt/openbooks` env

### 2. Voice Preview Not Working (UI)
- **Cause**: Unknown - backend API works (returns 200, files exist)
- **Test**: Check browser console for JS errors
- **Possible**: Audio element not triggering, CORS, or JS event handler issue

### 3. WhatsApp Config Missing
- **Cause**: Force push lost env vars
- **Fix**: Restore Evolution API config to docker-compose.yml

### 4. Design Too "Vibe Codey"
- **User Request**: Cleaner, fresher design (less dark/hacker aesthetic)
- **Changes Needed**:
  - Lighter color palette options
  - Simpler gradients or solid backgrounds
  - More whitespace
  - Cleaner typography
  - Remove neon/glow effects
  - Professional, modern look (think Linear, Notion, Vercel)

---

## Fix Tasks

### Task 1: Restore docker-compose.yml Config
```yaml
environment:
  - LIBRARY_DIR=/mnt/openbooks
  - EVOLUTION_API_URL=<set-in-env>
  - EVOLUTION_API_KEY=<set-in-env>
  - DEFAULT_WHATSAPP_NUMBER=<set-in-env>
volumes:
  - /mnt/openbooks:/mnt/openbooks:ro
```

### Task 2: Debug Voice Preview
- Test in browser with dev tools open
- Check for JS errors
- Verify audio element src is set correctly
- Test with curl to confirm API works

### Task 3: UI Redesign - Cleaner Theme
New design direction:
- **Light mode default** with optional dark
- **Neutral color palette**: Slate grays, subtle blues
- **No glow effects**: Clean shadows instead
- **Rounded corners**: Softer, 8-12px radius
- **Typography**: System fonts, clear hierarchy
- **Spacing**: Generous padding, breathing room
- **Accent**: Single accent color (blue or purple)

### Task 4: Full Function Validation
Test checklist:
- [ ] Upload EPUB
- [ ] Upload PDF
- [ ] Upload MOBI (Calibre conversion)
- [ ] Voice selection
- [ ] Voice preview playback
- [ ] Engine switching (Kokoro/Piper)
- [ ] Convert job submission
- [ ] Queue tab shows jobs
- [ ] Library tab loads books
- [ ] Library search works
- [ ] Library convert button
- [ ] History tab shows completed
- [ ] Theme switching
- [ ] WhatsApp notification toggle

---

## Execution Order

1. Fix docker-compose.yml (Library + WhatsApp)
2. Redeploy container
3. Test Library loads
4. Debug voice preview in browser
5. Redesign UI for cleaner look
6. Full validation pass
7. Commit and push
