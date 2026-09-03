# PLAN V6 — The Smart Library (2026-09-02)

Successor to PLAN-V5. V5 was about **automation and reach** for the TTS
pipeline. V6 is about **the library as a service**: the ebook and audiobook
collection should actively find, curate, deliver, and complete itself — not
wait for a human to browse a file list.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

Everything here is agreed with Dave on 2026-09-02.

---

## Standing constraint (carried from V5)

> *"this shit needs to be done properly and auto… I cannot be manually tweaking
> per book or chapter."*

Extends to the library: nobody should need to browse a catalog, fix metadata,
notice a missing series entry, or wonder why a cover is blank. The system
handles it.

---

## Architecture context

The stack today:

| Component | Host | What it does |
|-----------|------|--------------|
| **CWA** (Calibre-Web Automated) | docker-vm | Ebook library, auto-ingest via inotify, format conversion |
| **Audiobookshelf** | docker-vm | Audiobook server + mobile apps |
| **OpenBooks + qBittorrent** | docker-vm (Gluetun VPN) | Book acquisition |
| **epub-to-audiobook** | zorin | TTS conversion pipeline (Chatterbox Nano, TADA) |
| **n8n** | n8n-vm | Workflow automation, WhatsApp integration |
| **Synology NAS** | Spain (nas-wg) | Bulk book archive (audiobooks, ebooks) |
| **Pangolin + Cloudflare** | hetzner / khpi5 | Reverse proxy, SSO, family access |

**Tracked as GitHub issues** — **#47** (WhatsApp Book Bot) · **#48** (Auto-Series
Completion) · **#49** (AI Library Curator) · **#50** (Family Wishlist Pipeline).

---

## 1. WhatsApp Book Bot — #47

**Goal:** Family member texts a book title → system acquires it → ingests into
CWA → optionally queues TTS conversion → replies with confirmation + cover art.

### Design

```
WhatsApp message ("The Nineties Chuck Klosterman")
  → n8n webhook (WhatsApp trigger)
  → Parse: extract title + author (LLM or simple split)
  → Search OpenBooks IRC via API / slskd search
  → Best match → download to book-ingest/
  → CWA inotify picks it up → auto-import
  → Wait for CWA import confirmation (poll metadata.db or webhook)
  → Optional: queue for TTS if requested ("audio" keyword)
  → WhatsApp reply: "✅ Added: The Nineties by Chuck Klosterman" + cover image
```

### Key decisions

- **Search source priority:** OpenBooks IRC → slskd/Soulseek → fallback "not found + Amazon link"
- **Duplicate guard:** Check CWA metadata.db before acquiring
- **Rate limiting:** Max 5 requests per user per hour
- **TTS trigger:** Only if message contains "audio" or "audiobook" keyword
- **Error handling:** "❌ Couldn't find that — try a more specific title?" reply

### Dependencies

- n8n WhatsApp integration (already working for other flows)
- OpenBooks/slskd API access from n8n-vm to docker-vm
- CWA book-ingest directory writable from n8n workflow

---

## 2. Auto-Series Completion — #48

**Goal:** When a book that's part of a series is ingested, detect the series and
flag (or auto-acquire) missing volumes.

### Design

```
CWA ingests "Hereward 01 - Hereward"
  → Post-ingest hook or scheduled scan
  → Query OpenLibrary / Google Books API for series membership
  → Series: "Hereward" by James Wilde, 4 books total
  → Check CWA: only book 1 present
  → Action: create "wanted" entries for books 2-4
  → If WhatsApp Bot (#47) is live: auto-search and acquire
  → Notify Dave: "📚 Hereward series: you have 1/4. Acquiring 2-4..."
```

### Key decisions

- **Metadata sources:** OpenLibrary Series API → Google Books → Goodreads (scrape)
- **Auto-acquire vs notify:** Start with notify-only; opt-in auto-acquire later
- **Scope:** Only flag series gaps for books ingested after feature is live (no backfill flood)
- **Storage:** Series data cached in a local SQLite or CWA custom table
- **Dedup:** Match by ISBN, title+author fuzzy match, or OpenLibrary work ID

### Dependencies

- OpenLibrary API (free, no auth required)
- CWA metadata.db read access
- WhatsApp Bot (#47) for auto-acquire path

---

## 3. AI Library Curator — #49

**Goal:** Automatically clean metadata, fetch covers, generate genre tags, and
write "why read this" blurbs for every book in the library.

### Design

```
Scheduled scan (daily or on-ingest trigger)
  → For each book with poor metadata:
    1. Clean title: strip filenames artifacts, "(epub)", "(retail)", ISBNs
    2. Fetch cover art: OpenLibrary Covers API → Google Books → generate placeholder
    3. Genre tags: LLM classifies from title + description + first 500 words
    4. Reading time estimate: word count ÷ 250 wpm
    5. "Why read this" blurb: LLM generates 2-sentence hook
    6. Write back to Calibre metadata.db via calibredb CLI
```

### Metadata quality tiers

| Tier | Criteria | Action |
|------|----------|--------|
| **Gold** | Has title, author, cover, description, genres, ISBN | Skip |
| **Silver** | Has title + author but missing cover or genres | Enrich |
| **Bronze** | Only has filename-derived title | Full enrichment |

### Key decisions

- **LLM choice:** Local (Ollama on zorin) for cost-free; fallback to API for quality
- **Cover art:** Never overwrite an existing cover — only fill blanks
- **Calibre write-back:** Use `calibredb set_metadata` CLI, not direct DB writes
- **Rate limiting:** Process max 20 books per run to avoid API throttling
- **Manual override:** If a user has manually set metadata, mark it "curated" and skip

### Dependencies

- OpenLibrary Covers API + Google Books API
- Ollama or LLM API access
- `calibredb` CLI available in CWA container or on docker-vm
- CWA metadata.db read access for audit

---

## 4. Family Wishlist Pipeline — #50

**Goal:** Family members can add books to a shared wishlist. The system
periodically searches for them and auto-acquires when found.

### Design

```
Input methods (any of):
  → WhatsApp: "wish: The Thursday Murder Club"
  → Simple web form (n8n form trigger)
  → Manual add to shared list

  → Wishlist stored in: n8n database / SQLite / Airtable
  → Scheduled search job (every 6 hours):
    → For each unfulfilled wish:
      → Search OpenBooks / slskd
      → If found: acquire → ingest → mark fulfilled → notify requester
      → If not found: skip (retry next cycle)
      → After 30 days unfulfilled: notify with buy link (Amazon/Kobo)
```

### Key decisions

- **Wishlist storage:** n8n's built-in database or a simple SQLite on docker-vm
- **Input parsing:** Same LLM/split logic as WhatsApp Bot (#47)
- **Fulfillment notification:** WhatsApp reply to original requester
- **Buy link fallback:** After 30 days, send Amazon affiliate link (or plain link)
- **Per-user limits:** Max 10 active wishes per family member
- **Priority:** Wishes from Dave get searched first (admin privilege)

### Dependencies

- WhatsApp Bot (#47) as primary input method
- OpenBooks/slskd search capability
- CWA book-ingest for fulfillment
- Notification channel (WhatsApp)

---

## Implementation order

```
#47 WhatsApp Bot ──────► #48 Series Completion
        │                        │
        ▼                        ▼
#50 Family Wishlist ◄──── #49 AI Curator
```

**Phase 1:** #47 (WhatsApp Bot) — the keystone. Everything else plugs into it.
**Phase 2:** #49 (AI Curator) — independent, can run in parallel.
**Phase 3:** #48 + #50 — both extend #47's search/acquire capability.

---

## Out of scope for V6

- Whispersync-style read/listen position bridging (long-term, needs CWA+ABS API work)
- Genre-aware narrator casting for TTS (creative but not urgent)
- Auto-push to devices (CWA auto-send exists; per-user device profiles are future)
