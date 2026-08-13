# Getting Started 🎧

This app turns an ebook or public article into audio. The supported baseline
runs on local CPU and costs nothing. Optional network voices, LLMs and cloud
rendering are separate choices; none is required and paid GPU use is never
triggered by the queue.

Before converting a book, look for an existing good audiobook. Use this app
when one is unavailable or fails your quality needs: generation is a fallback,
not the first acquisition route.

This guide assumes **zero** technical background. If you can copy and paste a few
lines, you can do this. It takes about 15 minutes, most of which is waiting.

---

## Step 1 — Install Docker (one-time, ~5 min)

Docker is a free program that runs the app for you so you don't have to install
lots of fiddly things by hand.

- **Windows or Mac:** download **Docker Desktop** from
  [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop),
  run the installer, and open it once so it's running (you'll see a little whale
  icon).
- **Linux:** install Docker Engine + the Compose plugin from
  [docs.docker.com/engine/install](https://docs.docker.com/engine/install/).

That's the only thing you need to install. No GPU, no accounts, no API keys.

---

## Step 2 — Download and start the app (~5 min the first time)

Open a terminal (on Windows, open **PowerShell**; on Mac, open **Terminal**) and
paste these lines one at a time:

```bash
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook
./scripts/bootstrap.sh
```

On Windows PowerShell, use this third line instead:

```powershell
.\scripts\bootstrap.ps1
```

The helper creates `.env` with the clone's real absolute path, validates the
Compose model, starts Chatterbox Nano and waits for the app health check. It
never overwrites an existing `.env`.

The last line starts everything. **The first run downloads the voice model
(a few minutes)** — after that it's instant. When it finishes, open your web
browser and go to:

### 👉 http://localhost:8881

You should see the **Audiobook Studio** — a clean library screen. That's it,
you're running.

Confirm both the app and its default narrator before uploading anything:

```bash
curl --fail http://localhost:8881/api/health
curl --fail http://localhost:8881/api/engines/health
```

The first response should report `"overall":"ok"`; the second should show
`"chatterbox_nano":true`. If Nano is false, the most common cause is starting
Compose without `--profile chatterbox-nano`.

> **Out of the box voice:** **Beatrice (Nano)** is the default British narrator.
> Kokoro is also local. Network/paid engines are not silently used as fallbacks.

---

## Step 3 — Make your first audiobook (3 clicks)

1. **Add a book.** Click **Upload** in the sidebar and drop in an `.epub` file
   (or `.pdf`, `.mobi`). It appears in your Library.
2. **Pick a voice.** Find the book in the Library, click **Narrate**, and choose
   a narrator. Open **Voices** first and listen: a Play button always reads an
   already-persisted MP3 and never makes you wait for a hidden render. During a
   new installation, a voice stays out of the picker until its sample is ready.
3. **Press go.** Click **Narrate this book**. The job moves to the **Queue** tab
   where you can watch its progress.

When it's done, your audiobook lands in the `data/audiobooks/` folder inside the
app, one MP3 per chapter. Copy them to your phone, or connect
[Audiobookshelf](#optional-listen-anywhere) to stream them anywhere.

That is the minimum working path. Everything below is optional.

## Check preview readiness

The app warms healthy local voices in the background without saturating the
host. It skips existing files, waits for low load and pauses between renders.
Check the measured state rather than guessing:

```bash
curl --silent http://localhost:8881/api/voices
```

The response contains `cache.configured_ready` and
`cache.configured_total`. They should match before you expect every configured
voice to appear in **Voices**. Missing credentials keep paid engines out of the
configured total; the app will not spend money to populate previews. On a
small host, set `VOICE_CACHE_ON_START=0` in `.env` and curate samples manually.

---

## Turn articles into a private podcast

Open **Articles**, paste a public article URL, and submit it. The app fetches
the readable text and automatically queues an MP3 using your current default
narrator and the free local render target. You do not need to choose an engine
for each article.

If Telegram is configured, sending a URL to the bot does exactly the same thing.
Only the configured owner chat is accepted. Completed article narrations appear
in the RSS feed shown on the Articles screen; add that feed URL to your podcast
app.

When the app is behind Pangolin, keep the UI behind SSO but allow only the exact
RSS and audio-enclosure paths through without interactive authentication.
Podcast clients cannot complete the SSO flow. Anyone who has the feed URL can
listen to its episodes, so do not publish it openly. Verify all three effects:

1. the feed URL returns RSS XML without a login page;
2. one enclosure supports a byte-range request (`206`);
3. an unrelated path such as `/api/jobs` still redirects to SSO.

See [OPERATIONS.md](OPERATIONS.md#article-capture-and-podcast-delivery) for the
exact path boundary and rollback checks.

---

## How long does it take?

Making an audiobook is real work for your computer — it's generating speech
second by second. A full novel on a normal computer (no graphics card) can take
a few hours. That's normal. A couple of ways to speed it up:

- **Have a compatible NVIDIA GPU?** Explicitly start a GPU engine profile; the
  app never rents or attaches one automatically.
- **No GPU?** You can send the job to a **free cloud GPU (Kaggle)** — pick it as
  the render target when you start a book. Same result, just faster, still free.

---

## Optional: smarter pronunciation

If you connect an AI provider (for example Groq or Google Gemini), the app will
read each book first and figure out how to say tricky names and places correctly
— all automatically. It's not required; the app works fine without it. See the
**Settings** tab to add a key if you want this.

## Optional: listen anywhere

[Audiobookshelf](https://www.audiobookshelf.org/) is a free app that streams
your audiobooks to your phone with bookmarks and playback speed. If you run it,
add its address in **Settings → Audiobookshelf** and finished books sync to it
automatically.

---

## Choosing a voice (when you're ready to fuss)

Voices are grouped by **engine**. You don't have to care about this to start —
but when you want the best result:

- **Chatterbox Nano** — the default. A fast local CPU engine using the Beatrice
  human-cloned British narrator.
- **Kokoro** — fast, clear and useful for comparison, but no longer the default.
- **Chatterbox Turbo** — voice-cloned British narrators (Arthur, Edmund,
  Harriet, Beatrice). Excellent for long books; runs on CPU or GPU. Enable with
  the `chatterbox` profile.
- **Hume TADA** — the most expressive/natural on easy text, but a research
  model with rough edges on dense non-fiction. Enable with the `tada` profile.
- **VibeVoice / Qwen3-TTS finalists** — GPU-only local profiles or explicit
  free-Kaggle render targets. VibeVoice's pinned long-form listening winner is
  `cfg_scale=2.0`; the isolated garble in the winning clip keeps production
  promotion open until the exact app path is checked. Starting a Compose
  profile assumes a GPU is already attached; it never rents one. See
  [ENGINES.md](ENGINES.md) for runtime/licence and measured-hour boundaries.

Which sounds best depends on the book. Trust your ears. Automated transcription
can detect missing or repeated speech, but it cannot tell you whether a voice
is natural, clear or pleasant. More detail: [ENGINES.md](ENGINES.md) and
[VOICES.md](VOICES.md).

## Optional: Goodreads → LazyLibrarian → audiobook first

This integration is outside the conversion stack, but the intended boundary is
important:

```text
Goodreads “Want to Read”
  → LazyLibrarian audiobook wishlist (AudioBook only)
  → torrent providers first; Usenet fallback
  → existing audiobook delivered to Audiobookshelf
  → this app only when no acceptable audiobook is found
```

Goodreads no longer issues new API keys. LazyLibrarian's official documentation
says its supplied Goodreads key is read-only and cannot sync shelves, so a new
Goodreads account should use the shelf's RSS URL as an **RSS/WishList provider**.
Set its LazyLibrarian download type to **AudioBook (`A`) only**. Do not import
the shelf as ebook Wanted at the same time: that would start TTS work before the
audiobook search has had a chance to succeed.

The Goodreads RSS URL is account-specific and may contain a private token. Put
it only in LazyLibrarian's configuration—never in Git, an issue or a screenshot.
The active homelab topology and torrent-first settings belong to the sibling
`infra` repo's `docs/protocols/book-acquisition-pipeline.md`; this repository
does not duplicate its credentials or host layout.

Official references:

- [LazyLibrarian RSS/WishList providers](https://lazylibrarian.gitlab.io/config_providers/#rsswishlist-providers)
- [LazyLibrarian Goodreads API/sync limits](https://lazylibrarian.gitlab.io/config_importing/#goodreads-sync)
- [LazyLibrarian Manage/wishlist import behavior](https://lazylibrarian.gitlab.io/manage/)
- [LazyLibrarian API](https://lazylibrarian.gitlab.io/api/)

---

## If something goes wrong

- **The page won't open at localhost:8881** — make sure Docker Desktop is
  actually running, then run
  `docker compose --profile chatterbox-nano up -d --build` again.
- **A voice says "offline"** — that engine isn't started. Start it with its
  profile while retaining Nano, for example
  `docker compose --profile chatterbox-nano --profile chatterbox up -d`.
- **A voice is not listed** — check `/api/voices`. If it is configured but its
  `preview_cached` value is false, the background cache has not completed or
  its engine is offline. A Play click will not cold-render it.
- **A conversion failed** — open the job's **Log** in the Queue tab; it usually
  says exactly what happened. Press **Resume** to retry just the missing
  chapters.
- **Collect evidence:** attach `docker compose ps`, the relevant container log,
  `/api/health`, `/api/engines/health`, and the Git revision from `/api/version`.
  Remove tokens, private feed URLs and book text.
- **Still stuck?** Open an issue on the
  [GitHub repo](https://github.com/davedavedavenm/epub-to-audiobook/issues) with
  the log text — that's the fastest way to get help.

---

## Where things live (for the curious)

| Thing | Where |
|-------|-------|
| The web app | http://localhost:8881 |
| Your finished audiobooks | `data/audiobooks/<book name>/` |
| Books you've uploaded | `data/uploads/` |
| Settings + API keys | the **Settings** tab (stored in the app database on the `/data` volume) |

## Official setup references

- [Docker Engine installation](https://docs.docker.com/engine/install/)
- [Docker Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)
- [Audiobookshelf documentation](https://www.audiobookshelf.org/docs/)
- [Kaggle API documentation](https://github.com/Kaggle/kaggle-api)
- Engine-specific upstream documentation and tested-version caveats:
  [ENGINES.md](ENGINES.md)

Enjoy your audiobooks. 🎧
