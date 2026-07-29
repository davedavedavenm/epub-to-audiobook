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

## TTS engine defaults — Active

Chatterbox Nano is the default production engine. Piper is legacy/debug only
(`ENABLE_PIPER_PROFILE=1` required, not a fallback). Chatterbox Turbo and TADA
require explicit opt-in (`ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1`).

**Why:** a controlled three-way Piper audit (1.2 @ 64kbps, same WAV at higher
bitrate, 1.6 direct with official VCTK-medium) was rejected on listening —
"absolute shit," wrong words, inauthentic accents — on 2026-07-28. Wrapper and
bitrate were ruled out as the fix; the model path itself is closed. Don't
re-run this audit without new evidence the underlying model changed.

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
