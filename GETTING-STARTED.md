# Getting Started — Full Walkthrough

A step-by-step guide for a brand-new user. This app turns **any** ebook
(EPUB, PDF, MOBI, and more) into an audiobook, entirely on your own machine.
Nothing here is specific to any one book — the whole pipeline is general.

## 1. What you need

- A computer with **Docker** and **Docker Compose** installed (Windows, Mac,
  or Linux). That's it — no GPU, no accounts, no API keys required to start.
- ~10 GB free disk (for TTS models, downloaded once on first run).

## 2. Install & first run

```bash
git clone https://github.com/davedavedavenm/epub-to-audiobook.git
cd epub-to-audiobook
cp .env.example .env        # optional — defaults work as-is

# Start. Choose which voice engines to enable via "profiles":
docker compose up -d                                          # Kokoro (fast, default)
docker compose --profile chatterbox up -d                    # + Chatterbox Turbo (best UK voices)
docker compose --profile tada up -d                          # + TADA (most natural)
docker compose --profile chatterbox --profile tada --profile piper up -d   # everything
```

Open **http://localhost:8881**. First start downloads each enabled engine's
model once (cached in a Docker volume afterwards).

## 3. Convert your first book

Two ways in the UI:
- **Library tab** — browse an ebook folder (set `LIBRARY_DIR` in `.env`) and
  click **Narrate this Book**.
- **Upload tab** — drop an EPUB/PDF/etc. from your computer.

Then for any book:
1. **Pick a Narrator** (voice). Voices are grouped by engine — see §5.
2. Optionally set a **chapter range** (skip the copyright/title front-matter;
   start at the real Chapter 1).
3. Optionally open **Advanced** for a voice blend (Kokoro) or per-book
   pronunciation fixes (see §4).
4. Click **Create Audiobook**. Watch it in the **Queue** tab (progress, live
   log, cancel). Finished books appear in **History** (download) and, if
   configured, sync to Audiobookshelf (§6).

Every conversion automatically runs the **text preprocessing pipeline** first
(strips footnote/endnote markers, normalizes numbers/years/currency/units,
cleans unicode) — this is on for every book, no setup needed. Details in
PREPROCESSING.md.

## 4. Connect an AI (LLM) for smarter preprocessing — optional but recommended

An optional LLM makes pronunciation and metadata smarter **per book** (e.g.
working out that "US" is "U-S" not "us", or how to say an unusual name). It is
**not required** — the deterministic pipeline works without it — but it lifts
quality on tricky books.

**Any OpenAI-compatible provider works, including free ones:**

1. In the UI go to **Settings → LLM Integration**.
2. Pick a **Provider**:
   - **Z AI (Zhipu)** — has a free flash tier. Good default.
   - **Groq** — generous free tier, very fast.
   - **Google Gemini** / **OpenAI** / **DeepSeek** / **xAI** — paid or
     free-tier depending on your account.
   - **Custom** — any OpenAI-compatible base URL.
3. Paste your **API key**, pick a **model** (a cheap "flash"/"mini" model is
   ideal), and click **Test LLM** to confirm it connects.
4. Save. From then on, conversions use it to auto-generate per-book
   pronunciation help.

You can also maintain a **global pronunciation dictionary** (Settings →
Pronunciation Dictionary) with `search==replace` rules applied to every book,
and **per-book** rules in each book's Advanced panel.

> Roadmap: an **adaptive QA system** (LLM pre-flight review + Whisper
> post-flight verification) that automatically catches and fixes per-book
> pronunciation issues is planned — see PLAN.md §1.

## 5. Voices

**Built-in, all local & free:**
- **Kokoro** — 20+ voices (British, American, European). Fast, the default.
- **Chatterbox Turbo** — voice-cloned **British human narrators**: Arthur,
  Edmund (male), Harriet, Beatrice (female). Highest quality; CPU-friendly.
- **TADA** — the same British narrators, "most natural" variant (Arthur —
  TADA, etc.). Slower but the most expressive.
- **EdgeTTS** — free Microsoft neural voices (needs internet).
- **Piper** — lightweight fallback.

Preview any voice in the **Voices** tab before converting.

**Add your own voice (any narrator you like):** the Chatterbox/TADA voices are
cloned from short (~15 s) reference clips of real narrators. To add one, drop
a `yourvoice.wav` (24 kHz mono) into `chatterbox/voices/` (and
`tada/voices/yourvoice_tada.wav` for TADA), rebuild that engine's container,
and it appears as a selectable voice. Public-domain LibriVox recordings are a
great, legal source.

## 6. Audiobookshelf sync — optional

To auto-send finished audiobooks to your Audiobookshelf server:
- Settings → **Audiobookshelf Sync**: set the server URL + API token, or
- set `AUDIOBOOKSHELF_DIR` / `AUDIOBOOKSHELF_HOST` in `.env` for rsync-based
  file sync.

Each conversion lands in its **own folder** (named with a unique job id) — it
**never overwrites** an existing audiobook.

## 7. Cloud GPU (optional, OFF by default)

Everything runs on local CPU by default (a novel takes a few hours — leave it
running). If you want speed, you can enable **Cloud GPU** rendering (Vast.ai)
in Settings → Render Location. It is **off by default and costs money** — read
GPU-SAFETY.md first. You never need it; it's purely an accelerator.

## 8. Notifications — optional

Settings supports Telegram and WhatsApp completion alerts. All optional.

## Troubleshooting

- **A voice won't preview / first conversion is slow** — the engine loads its
  model on first use (~1–2 min). Subsequent uses are fast.
- **Chapter 1 is the copyright page** — set a chapter range to start at the
  real first chapter.
- **Chatterbox/TADA voices missing** — start with that engine's profile
  (`--profile chatterbox` / `--profile tada`).
- More detail and current status: STATUS.md.
