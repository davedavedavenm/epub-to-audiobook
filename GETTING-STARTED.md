# Getting Started 🎧

Welcome! This app turns any ebook into an audiobook you can listen to — read
aloud by a natural-sounding voice, right on your own computer. No subscriptions,
nothing sent to the cloud, and it's free to run.

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
docker compose up -d
```

The last line starts everything. **The first run downloads the voice model
(a few minutes)** — after that it's instant. When it finishes, open your web
browser and go to:

### 👉 http://localhost:8881

You should see the **Audiobook Studio** — a clean library screen. That's it,
you're running.

> **Out of the box voices**: The app defaults to **Beatrice (Nano)** — a human-cloned British narrator running fast on CPU. You can also pick any Kokoro or Edge voice. `docker compose up -d` includes Chatterbox Nano by default.

---

## Step 3 — Make your first audiobook (3 clicks)

1. **Add a book.** Click **Upload** in the sidebar and drop in an `.epub` file
   (or `.pdf`, `.mobi`). It appears in your Library.
2. **Pick a voice.** Find the book in the Library, click **Narrate**, and choose
   a narrator from the dropdown. Hit **Preview** on any voice to hear a sample
   first.
3. **Press go.** Click **Narrate this book**. The job moves to the **Queue** tab
   where you can watch its progress.

When it's done, your audiobook lands in the `data/audiobooks/` folder inside the
app, one MP3 per chapter. Copy them to your phone, or connect
[Audiobookshelf](#optional-listen-anywhere) to stream them anywhere.

That's the whole thing. Everything below is optional.

---

## How long does it take?

Making an audiobook is real work for your computer — it's generating speech
second by second. A full novel on a normal computer (no graphics card) can take
a few hours. That's normal. A couple of ways to speed it up:

- **Have a gaming GPU?** It'll be much faster automatically.
- **No GPU?** You can send the job to a **free cloud GPU (Kaggle)** — pick it as
  the render target when you start a book. Same result, just faster, still free.

---

## Optional: smarter pronunciation

If you connect a free AI provider (like Groq or Google Gemini), the app will
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

- **Kokoro** — the default. Fast, clear, low effort. Great for a first run.
- **Chatterbox Turbo** — voice-cloned British narrators (Arthur, Edmund,
  Harriet, Beatrice). Excellent for long books; runs on CPU or GPU. Enable with
  the `chatterbox` profile.
- **Hume TADA** — the most expressive/natural on easy text, but a research
  model with rough edges on dense non-fiction. Enable with the `tada` profile.
- **VibeVoice / Qwen3-TTS finalists** — the best full-chapter audition results,
  but GPU-only and still provisional. Select Arthur with **Kaggle GPU** for the
  normal free path. A 12.4-hour book consumes roughly 28.10/25.49 GPU-hours,
  so either can use most of Kaggle's nominal weekly allowance. If this machine
  already has a compatible NVIDIA GPU, the optional local services are
  `docker compose --profile vibevoice --profile qwen3 up -d`; these profiles
  do not rent cloud hardware. Vibe's runtime has an important research-use/
  community-fork boundary documented in [ENGINES.md](ENGINES.md).

Which sounds best depends on the book and your hardware — trust your ears, and
use **Preview** to compare. (More detail in [ENGINES.md](ENGINES.md).)

---

## If something goes wrong

- **The page won't open at localhost:8881** — make sure Docker Desktop is
  actually running (the whale icon), then run `docker compose up -d` again.
- **A voice says "offline"** — that engine isn't started. Start it with its
  profile, e.g. `docker compose --profile chatterbox up -d`.
- **A conversion failed** — open the job's **Log** in the Queue tab; it usually
  says exactly what happened. Press **Resume** to retry just the missing
  chapters.
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

Enjoy your audiobooks. 🎧
