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

## VibeVoice `cfg_scale` — Active

`cfg_scale=1.3` is **rejected**. Use **2.0–3.0**; 3.0 tracks the Arthur
reference most closely on pitch and range, 2.0 scores marginally better on ASR.
Settled by ear 2026-08-13 on identical 190-word renders: Dave, *"2 and 3 are
fine. 1 is trash."*

**Why:** `cfg_scale` is VibeVoice's voice-conditioning adherence lever — the
analogue of Chatterbox's `cfg_weight`. At 1.3 the clone does not carry the
narrator's timbre: pitch IQR 14.4 against the reference's 72.8, i.e. nearly
monotone. Raising it moves pitch, range and brightness monotonically toward the
reference at no cost to intelligibility. 1.3 was inherited unexamined from an
early kernel, never chosen. Above 3.0 is untested and cfg 3.0 still carries only
about half the reference's pitch range.

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

VibeVoice holds a stable speaker across continuous real prose: 916 words /
4m19s single-pass measured at f0 spread 25 Hz and ASR 0.979. Length is not a
degradation factor, and peak VRAM does not grow with it (5.31 GiB flat).

**Why:** closes the memory question behind #44 and removes "will it hold
together" as a blocker on rendering full chapters. The remaining #44 wording
("90-minute single-pass") is a vendor capability claim the per-chapter renderer
never exercises — do not spend GPU proving it. Date: 2026-08-12.

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

As of 2026-07-29: VibeVoice and Qwen are the finalists on the full-chapter
listening gate. Vibe is the provisional quality leader (more expressive);
Qwen is the consistency leader. MOSS is eliminated (single-pass renders
collapsed / weaker than Vibe-Qwen on repeat listening). Higgs is usable but
not dependable enough to lead.

**Why:** see STATUS.md for the underlying RTF/ASR measurements and listening
notes — this entry only tracks the current standing, not the evidence trail.
Check STATUS.md for anything newer before treating this as final.

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

## Automatic QA Re-Render (#41) — Active

Structural QA verification failures (WER >= 0.08) automatically trigger up to 2
re-renders with seed offsets (`seed + attempt * 10000`), retaining the audio
with the lowest WER.

**Why:** Sampling defects (seed variation or cold-start artefacts) are
self-healed automatically without human intervention or per-book parameter tuning.

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


