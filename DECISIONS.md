# Decisions — EPUB to Audiobook

Settled, closed questions for this repo. This is not a changelog — STATUS.md and
OPERATIONS.md hold the narrative (what happened, listening tests, incidents).
This file holds the current, settled position on each question, and its status.

**Before proposing to change, redo, or re-open something, check here first.**
If a session settles a new question or reverses one below, update this file in
the same session — don't just log it in STATUS.md and leave this stale.

Status values: **Active** (current) · **Superseded** (replaced, kept for history)
· **Evolving** (settled position exists but is expected to keep moving — check
the linked doc for the latest measurement before relying on it).

---

## Project optimisation order: quality floor, then free, then cheapest — Active

An audiobook must first pass Dave's human listening floor for naturalness,
accent, pronunciation, pacing and long-form comfort. Among engines that pass
that floor, choose in this order:

1. **Free generation wherever possible** — normally local CPU or free Kaggle.
2. If no free path reaches the quality floor, use the **lowest measured total
   cost per finished book** that does.
3. Pay more only when a cheaper passing option is unavailable or has failed the
   same controlled listening comparison.

Speed is not worth a bill by itself. Cost comparisons must use measured
book-level totals (including startup/retry overhead where known), not vendor
headline rates or hypothetical hardware speedups presented as facts.

**Why:** stated directly by Dave on 2026-08-13. This refines, rather than
reverses, the existing quality-priority decision: bad free audio is still not a
successful audiobook, but cost decides between options that are genuinely good.

## Official documentation before experimentation — Active

Before changing or evaluating any external engine, model, API, SDK, container,
deployment tool or integration, read the relevant repo decisions/history and
the current official vendor documentation for the exact version in use. Record
the official URL, model/version or commit, supported parameters/defaults,
licence/use limits and dated pricing where relevant. If a community runtime or
wrapper is used, pin and document it separately; official model weights do not
make an unofficial runtime official.

Experiments answer only what authoritative documentation leaves unknown. A
claim without source/version provenance stays **unverified**, and audible
quality still requires Dave's listening verdict.

**Why:** repeated sessions spent time rediscovering documented behaviour or
tuning the wrong default because agents experimented before reading the manual.
Mandated directly by Dave on 2026-08-13.

## VibeVoice `cfg_scale` — 1.3 rejected; production choice open

`cfg_scale=1.3` is **rejected**. Both **2.0 and 3.0 passed a short 190-word
listening screen**; 3.0 tracked the Arthur reference more closely on pitch and
range, while 2.0 scored marginally better on structural ASR. Dave: *"2 and 3
are fine. 1 is trash."* This does not select a production default: the pinned
full-chapter blind A/B must be heard first, then the winning setting must pass
through the actual app path.

**Why:** the pinned community runtime exposes `cfg_scale`; Microsoft's official
TTS documentation does not define it as a supported tuning contract. Its role
here is therefore an empirical repo finding, not an official Microsoft fact.
At 1.3 the clone's pitch IQR was 14.4 against the reference's 72.8 (nearly
monotone). Raising it moved pitch, range and brightness toward the reference
without a structural intelligibility loss in that short test. 1.3 was inherited
unexamined from an early kernel. Above 3.0 is untested, and cfg 3.0 still carried
only about half the reference's pitch range.

## Prior VibeVoice listening verdicts — SUPERSEDED, need re-run

Every VibeVoice quality judgement recorded before 2026-08-13 was made at
`cfg_scale=1.3` (now rejected) and, where the audition passage was used, on text
that costs Vibe roughly 0.13 ASR. This includes the 2026-07-29 full-chapter
finalist gate and the "Vibe provisional quality leader / Qwen consistency
leader" ranking.

**Do not cite those verdicts as current.** Re-run the comparison at
`cfg_scale` 2.0–3.0 before ranking Vibe against Qwen again. The handicap ran
against Vibe, so a fair re-run can only improve its standing — but it has to be
run, not assumed.

## VibeVoice generation settings — Active

`ddpm_inference_steps = 10` for VibeVoice. Do not raise it. Measured 2026-08-12:
raising it to 20 then 30 degraded ASR similarity monotonically (0.872 → 0.847 →
0.809) on identical text, voice and seed, while costing 20–45% more GPU time.
Peak VRAM is 5.31 GiB regardless of steps or input length.

**Why:** this looks like an obvious quality knob and it is not — it is inverted.
See STATUS.md 2026-08-12 for the six-arm sweep.

## VibeVoice long-form capability — Active

VibeVoice completed 13,666 source words in one generation, producing about 77
minutes of audio on a free Kaggle P100 (13,597 ASR words, WER 0.0887). This
reproduces the practical substance of Microsoft's "up to 90 minutes" claim and
answers issue #44's capability question. The issue is still open only because
its GitHub state is stale. A separate 916-word / 4m19s run showed stable pitch
and measured 5.31 GiB peak VRAM.

**Boundary:** the 77-minute run's VRAM probe was attached to the parent while
generation ran in a subprocess and therefore reported zero. Long-duration VRAM
remains unmeasured; do not extrapolate the 4-minute 5.31 GiB result. Long-form
quality still requires human listening. Date corrected: 2026-08-13.

## Audition-passage validity per engine — Open, NOT settled

The canonical `voice_sample.SAMPLE_TEXT` measurably handicaps VibeVoice:
0.81–0.87 ASR on it versus 0.98+ on plain prose, across ddpm steps and seeds.
`voice_sample.MODERN_ENGINES` is `("chatterbox", "tada")` — VibeVoice and Qwen
are in neither branch by consideration, only by omission.

Two things follow, both **unresolved**:
1. Whether Vibe needs the legacy number treatment (`modern=False`) is untested.
   Run that arm before changing `MODERN_ENGINES`.
2. The 2026-07-29 "Vibe provisional quality leader / Qwen consistency leader"
   ranking was formed on auditions using this passage. It has not been re-run
   fairly. Do not cite that ranking as settled until it has.

**Why this is an entry at all:** the failure is silent. The audition renders,
passes structural QA, and sounds like an engine problem rather than an input
problem. Date: 2026-08-12.

## TTS engine defaults & Narrator — Active

Chatterbox Nano is the default production engine, and **Beatrice (Nano)** (`uk_female_samuel_nano`) is the default system narrator voice. Piper is legacy/debug only (`ENABLE_PIPER_PROFILE=1` required, not a fallback). Chatterbox Turbo and TADA require explicit opt-in (`ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1`).

**Why:** Beatrice (Nano) offers high-quality UK human-cloned narration at fast CPU speeds (~0.87x RTF) without requiring extra docker profiles or GPU hardware. Piper audio was rejected on listening ("absolute shit") on 2026-07-28.

## Article Ingest & Fast QA Bypass — Active

Web article URL ingest (`POST /api/articles/narrate_url`) and short content (< 15,000 chars) skip post-flight ASR verification by default. Generated article audio is automatically published to the Podcast RSS 2.0 feed (`/api/articles/rss`).

**Why:** Short articles do not suffer from multi-chapter drift, and skipping post-flight ASR reduces turnaround time from minutes to seconds.

## Offline Whisper ASR Caching — Active

Whisper ASR models are downloaded persistently to `/data/models/whisper` and initialized with `local_files_only=True`.

**Why:** Prevents online HuggingFace Hub network checks, rate limit warnings, and latency delays during ASR verification passes.

## Integrated Studio Web Audio Player — Active

The web UI uses a single persistent glassmorphic audio player bar (`#studio-audio-player`) at the bottom right, supporting browser playback of completed audiobooks, articles, and previews across tabs with speed controls (`1.0x`–`2.0x`).

**Why:** Issue #45. Eliminates orphaned audio playback and allows seamless listening while navigating the web application.

## TADA — Active

TADA works as of 2026-07-27 (issue #23 closed). Opt-in only.

**Why:** the prior OOM was fp32 running on CPU, not a capability limit — bf16
fits the memory cap, RTF 1.68. Don't re-diagnose this as a hardware ceiling.

## GPU / Vast.ai policy — Active

Default is LOCAL. Never spin up a Vast.ai instance or enable
`GPU_RENDER_ENABLED` without an explicit user request for the *current* task.
Always destroy any instance created in-session. See GPU-SAFETY.md before any
GPU action.

**Queue length must never provision a paid GPU.** The legacy
`AUTOSCALE_ENABLED` queue trigger is retired: paid Vast provisioning is manual,
session-specific and requires an explicit action after the cost has been shown.
Free Kaggle is not a paid fallback and remains opt-in per job.

**Why:** costs real money; this is a standing safety rule, not a per-task
judgment call.

## Deploy discipline — Active

Deploy from git only via `scripts/deploy.sh`; never patch application source
live; deploy the whole stack (webapp + worker), not one service.

**Why:** webapp and worker are two containers built from the same Dockerfile
sharing `app.py`. Rebuilding one leaves the other on old code, and
`/api/health` only reports the webapp's version — a partial deploy looks
healthy while being wrong.

## Regression guards — Active

A regression guard that fires is right until proven otherwise. If one blocks
a change, the default assumption is that the change is wrong, not the guard.

**Why:** these guards encode decisions that were already paid for, often by
ear (a human listened and decided). Don't relax a guard to make a diff pass.

## Audiobook quality priority — Active

Naturalness, authentic accent, correct pronunciation, pacing and long-form
listenability outrank locality, cost, memory or speed when picking an engine.

**Date:** 2026-07-28.

## Long-form engine shortlist — Evolving

VibeVoice and Qwen remain the finalists on the full-chapter listening gate.
The 2026-07-29 ranking of Vibe as provisional quality leader and Qwen as
consistency leader is **not current**: all Vibe clips in that comparison used
the now-rejected `cfg_scale=1.3` and the audition passage separately shown to
handicap Vibe. Re-run a pinned full-chapter comparison at cfg 2.0 and 3.0 before
ranking them. MOSS remains eliminated; Higgs remains usable but not dependable
enough to lead.

**Why:** see STATUS.md for the underlying RTF/ASR measurements and listening
notes — this entry only tracks the current standing, not the evidence trail.
Check STATUS.md for anything newer before treating this as final.

## Engine rejection and hold boundaries — Active

"Rejected" applies only to the exact model, version, runtime, voice, settings
and delivery path that were actually rendered and heard. Agents must not
generalise a failed wrapper or voice into an engine-family verdict, and must not
reopen a closed path without both current official upstream evidence and a
materially different controlled listening hypothesis. See `ENGINES.md` and
`VOICES.md` for official sources and the complete listening evidence.

| Candidate/path | Settled status | Boundary / condition for reconsideration |
|---|---|---|
| Chatterbox Nano + Beatrice | **Accepted default** | Free local baseline. A replacement must first beat it by ear. |
| Chatterbox Turbo + Arthur | **Accepted quality reference** | Free local but slower; retain for books where it wins the audition. |
| VibeVoice full precision | **Finalist; ranking withheld** | Old cfg 1.3 comparisons are invalid. Grade the pinned cfg 2/3 long-form blind test, then prove the winning setting through the app path. |
| Qwen3-TTS full precision | **Finalist** | Full chapter passed; compare against corrected Vibe under equivalent text and listening conditions. |
| CosyVoice 3 | **Keep / integration candidate** | A real 30-minute free-Kaggle render was listenable. Proper nouns need attention; this is not a rejection. |
| TADA-1B | **Keep / opt-in** | Works free on local CPU or Kaggle; high naturalness but residual pacing/control issues. Not rejected. |
| Chatterbox Multilingual V3 | **Unverified by ear** | Rendered accent clips exist; listen before promoting or rejecting. |
| Higgs Audio V2 | **Reserve, not finalist** | Usable but seed-dependent seams. Reopen only for a materially improved official release/runtime or a book-specific audition. |
| OmniVoice current weights/path | **Short-form hold** | Accents were good; CPU RTF ~9 and non-commercial weights block normal books. Reconsider on official performance/licence change or a bounded short use. |
| EdgeTTS through `edge-tts` | **Conditional hold** | Free direct cost and accents were acceptable, but the interface is unofficial/fragile and proper nouns failed. Re-test only with a pronunciation fix and current service docs. |
| MOSS-TTS Local Transformer v1.5 | **Rejected as audiobook finalist** | Multiple corrective long-form structures still collapsed or sounded joined/off-paced. Reopen only for a materially changed official release, not another seed/chunk tweak. |
| MeloTTS tested UK/AU voices | **Rejected for production** | Human listening rejected overall TTS, pronunciation and numbers. Reopen only for a materially different official model/voice release. |
| Piper official VCTK-medium path | **Rejected for production** | Current/deployed runtime plus encoding-controlled A/Bs all failed. This does not reject every future Piper model; it closes this exact official model path. |
| Kokoro tested voices | **Retired from quality contention** | Keep only compatibility/debug uses unless a materially new official model clears the listening floor. Never use paid GPU merely to make rejected-quality audio faster. |
| AWS Polly Long-Form | **Rejected on cost/value** | Recheck current official price and run a quality/cost audition only if it becomes the cheapest option capable of passing the human floor. |

No ASR score in this table is a quality verdict. Dave's listening is the
admission/rejection evidence; measurements only establish completeness,
runtime and the exact tested boundary.

## Book acquisition pipeline docs — moved to infra — Active

The LazyLibrarian/Prowlarr/qBittorrent/SABnzbd grab-and-delivery pipeline
(topology, VPN coverage, credentials, failure modes) is host-stack
infrastructure, not this app. It briefly lived in this repo's
`OPERATIONS.md` (added 2026-07-31) but moved to `infra` on 2026-08-01 —
`docs/protocols/book-acquisition-pipeline.md`, with `book_sync.sh` and
`pipeline_healthcheck.sh` tracked at `infra/stacks/docker-vm/media-stack/scripts/`.

**Why:** it duplicated infra's own host-stack records and, separately,
overlapped un-cross-referenced with `mediahub`'s NAS-side `books-dl`
project. See `infra/DECISIONS.md` "Book acquisition pipeline docs
consolidated into infra" for the full reasoning. Don't re-add that material
here — this repo keeps only `scripts/wanted/` (the `wanted_monitor`
watcher), per `infra/docs/protocols/repo-map.md`.

## ASR evidence boundary — Active

ASR is structural QA only: use it to detect missing, repeated, truncated or
grossly mismatched audio. It does not rank naturalness, accent, prosody or
pronunciation, and an individual ASR substitution is never evidence that the
engine pronounced a word badly. Human listening is authoritative for audible
quality. The local Vibe Q8 clip proved the reverse-error case on 2026-07-29:
Dave heard Huawei/Xiaomi as fine while Whisper produced “Swawe”/“Shaumi”.

**Why:** ASR has now failed in both directions—normalising an audibly wrong
name back to the expected word, and transcribing an acceptable pronunciation
as the wrong word. Removing ASR entirely would also remove the guard that caught
collapsed outputs; keeping it within this narrow boundary preserves its value
without pretending it can hear like the listener.

## Wanted monitor Audiobook status query — Active

`scripts/wanted/wanted_monitor.py` queries LazyLibrarian's database matching
`Status = 'Wanted' OR AudioStatus = 'Wanted'`. LazyLibrarian tracks ebooks in
`Status` and audiobooks in `AudioStatus`.

**Why:** filtering on `Status` alone made the monitor blind to titles wanted
specifically as audiobooks (missed 4 of 12 wanted titles on 2026-08-07).
Fixed in commit `908d82b` alongside recovering openbooks queue idempotency guard.

## ASR WER auto-rerender (#41) — Retired

The `--auto-rerender` implementation is removed. ASR WER must never replace a
render or choose among seeds: it cannot judge audible quality and has produced
false conclusions in both directions. Structural ASR may hold grossly
incomplete/mismatched output for review. Any future retry mechanism must use
deterministic completeness failures only or preserve alternatives for Dave to
hear blind.

**Why:** live audit on 2026-08-13 found the missing production flag and a
single-chapter recovery path that could overwrite a whole-book QA report. The
old entry overstated both implementation and evidence. Retired by Dave on
2026-08-13 after the audit explanation.

## LAN authentication, podcast access and article SSRF boundary — Active

The UI and private APIs require environment-owned HTTP Basic credentials. An
empty password fails closed; the settings database cannot set or reveal it.
Podcast RSS/audio plus health/version probes remain public for non-browser
clients. Telegram's public webhook requires the official
`X-Telegram-Bot-Api-Secret-Token` header. Article URL ingest permits public
HTTP(S) destinations only, checks all resolved addresses plus the connected
peer, validates every redirect, and bounds response size.

**Official basis:** Flask 3.1 request lifecycle/security documentation,
Python `ipaddress`/`urllib.parse`, Requests redirect controls, and Telegram Bot
API `setWebhook(secret_token=...)`, read 2026-08-13. This closes the audited
unauthenticated mutation and server-side request-forgery paths without breaking
podcast clients.

## Article Podcast RSS Feed & Telegram Capture (#42) — Active

Articles are served via a standard RSS 2.0 podcast feed (`/api/articles/rss`) with
audio enclosures for Pocket Casts/Overcast/ABS, and article URLs sent via Telegram
webhook (`/api/telegram/webhook`) are automatically fetched, converted to EPUB,
and enqueued for narration.

**Why:** Decouples article narrations from the main audiobook shelf into a clean
podcast feed and provides one-tap link capture from phone/desktop via Telegram.

## Narrator Identity & M4B Metadata (#40) — Active

Single-file M4B builds preserve author and narrator identity (`composer` / `narrator`
ID3 tags).

**Why:** Prevents multiple renders of the same book using different voices from
collapsing into a single indistinguishable entry in Audiobookshelf.

## Settings DB WAL Permissions Self-Healing (#37) — Active

Startup entrypoint (`entrypoint.sh`) and webapp DB initialization (`init_db()`)
automatically enforce read-write permissions (`0666`) on SQLite database files
and WAL/SHM sidecars.

**Why:** Eliminates intermittent `READONLY` errors when saving Settings after system
reboots or file permission shifts.
