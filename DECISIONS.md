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

## Shared-host CPU candidates reserve capacity for the product — Active

Pocket and Kitten remain CPU-only, but each service is capped at **four CPU
cores by default** on the six-core production host. More dedicated CPU can
reduce render time; it does not establish better voice quality. UI and queue
capacity take priority over maximum background throughput. PyTorch's official
guidance is the basis for bounding intra-op threads before inference:
<https://docs.pytorch.org/docs/stable/generated/torch.set_num_threads.html>.

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

## VibeVoice `cfg_scale` — 2.0 selected; 1.3 and 3.0 rejected — Active

Use **`cfg_scale=2.0`** for VibeVoice. The pinned 351-word blind test unblinded
as A=`3.0`, B=`2.0`. Dave selected B: *"much better ... otherwise perfect.
really really good."* A was rejected as muffled and distant despite an
acceptable/emotional voice. The default in Compose is therefore 2.0.

This selects the best tested Vibe setting, not the production narrator. The original
direct-runtime cfg-2 arm contained a brief “byah”-like insertion at the
`felicity - but` boundary while still speaking all source words. The corrected
production HTTP path was preferred and cleared that insertion. Both paths sent
the model the same byte-for-byte prompt, including the hyphen, so there is no
evidence for a global hyphen-removal rule.

The corrected full app-path file then **failed the long-form listening gate**.
Its opening was very good, but after roughly three minutes the delivery became
increasingly emotional, fast and run-on, lost narrative intent, and continued
to worsen. A local garble after “draught” is not assigned to the engine: the
exact shared source says `draught , and`, with a malformed space before the
comma. The progressive pace drift is the production blocker. The tested
single-pass Vibe path is therefore rejected for audiobook production; Qwen
ranks above it for long-form stability. Chatterbox Nano/Beatrice remains the
system default.

**Why:** the pinned community runtime exposes `cfg_scale`; Microsoft's official
TTS documentation does not define it as a supported tuning contract. Its role
here is therefore an empirical repo finding, not an official Microsoft fact.
At 1.3 the clone's pitch IQR was 14.4 against the reference's 72.8 (nearly
monotone). Raising it moved pitch, range and brightness toward the reference
without a structural intelligibility loss in that short test. 1.3 was inherited
unexamined from an early kernel. The longer human test overruled 3.0's more
reference-like pitch statistics: acoustic metrics did not predict its muffled,
distant sound. Above 3.0 is untested and has no reason to be pursued.

## Prior VibeVoice listening verdicts — Superseded

Every VibeVoice quality judgement recorded before 2026-08-13 was made at
`cfg_scale=1.3` (now rejected) and, where the audition passage was used, on text
that costs Vibe roughly 0.13 ASR. This includes the 2026-07-29 full-chapter
finalist gate and the "Vibe provisional quality leader / Qwen consistency
leader" ranking.

**Do not cite those verdicts as current.** The corrected cfg 2/3 comparison
selected 2.0, and the exact app-path file was subsequently heard. It failed on
progressive long-form pace/prosody drift, so Qwen now ranks above this Vibe path
for audiobook consistency. Neither replaces the Nano/Beatrice default.

## Voice auditions are persisted before they are offered — Active

A voice Play button must never begin cold synthesis. The audition UI offers a
voice only when `/data/previews/<voice-id>.mp3` exists and is non-trivial; the
API exposes configured ready/total counts. Healthy free local families may be
warmed in the background with load throttling, skip-existing behavior and an
off-switch. Startup maintenance must never call paid Polly/Inworld voices or a
network Edge voice without explicit operator action. Unconfigured paid engines
remain hidden.

**Why:** Dave requires every offered voice to be testable immediately. Previous
cold previews took minutes, timed out after successful synthesis, saturated the
host and made healthy services look offline.

## Existing audiobook first; generation only as fallback — Active

For a reading-list integration, request an **audiobook only** first. Prefer the
free torrent path, then the existing Usenet fallback. Do not simultaneously
mark the ebook Wanted and do not auto-queue TTS merely because a book was added
to Goodreads. This app is used only after no acceptable existing audiobook is
available; the absence/quality judgement is operator evidence, not something
ASR or a search timeout can decide.

For new Goodreads accounts, use the account-specific `to-read` RSS feed as a
LazyLibrarian RSS/WishList provider with `DLTYPES=A`. Goodreads no longer
issues new API keys and LazyLibrarian documents its supplied key as read-only,
so OAuth shelf sync is not a valid new-account setup. The feed URL may contain
a private token and must never be committed. Operational ownership remains in
the sibling `infra` repo.

An app-generated audiobook remains a replaceable fallback, not the preferred
permanent copy. Keep its LazyLibrarian `AudioStatus` at **Wanted** so scheduled
torrent-first searches continue. Retire a generated copy automatically only
after acquired audio completes, passes the production import-integrity guard,
reaches Audiobookshelf and is structurally verified. Separately, Dave may reject
or withdraw a generated render at any time; search failure is not a reason to
keep an unwanted engine/voice on the shelf. Move withdrawn media to recoverable
quarantine before an ABS rescan. A future TTS attempt starts only after Dave
explicitly selects the engine-bound narrator; never regenerate automatically.

**Live baseline (2026-08-14):** *Apple in China* is already a completed
qBittorrent M4B, not a generated fallback (812 minutes; production guard pass).
A fresh official LazyLibrarian `searchBook` run found no acceptable *Bond King*
audiobook, although two Prowlarr-proxied providers returned 429 and therefore
make that search incomplete rather than proof that no release exists. Dave
rejected both Kokoro/Fable renders: jobs `592af51b` and `59d36718` are absent
from the app and live ABS shelf. *Bond King* remains Audiobook Wanted; if no
acquired version appears, Dave will explicitly choose the next engine/voice.
*Breakneck* remains a generated fallback and Wanted.

## Narrator and engine are one selection — Active

Every selectable narrator is bound to the engine that produced its cached
preview. Batch and re-convert APIs must reject an independent engine override;
the UI asks for a narrator only. A voice preview from one engine must never be
silently rendered by another engine.

**Date/reason:** 2026-08-14. Two duplicate *Bond King* conversions in the live
history used the retired Kokoro/Fable path even though the system default is
Beatrice/Nano. The older batch API allowed engine and voice to diverge. The
exact caller cannot be reconstructed, so the unsafe state is removed rather
than attributed to the user.

## Conversion deletion is explicit about Audiobookshelf — Active

History combines completed book and article conversions newest-first. Deleting
"from this app" removes only the app's input copy, output and history row;
deleting "here and from Audiobookshelf" additionally removes only the exact
app-owned ABS folder or podcast episode. Source ebooks are never deleted.
Article episode filenames include the job id because episodes share a podcast
folder and title/date alone is not unique. A single MP3 downloads directly;
multiple chapter MP3s remain a ZIP.

The [official Audiobookshelf API](https://api.audiobookshelf.org/) documents that
`DELETE /api/items/<id>` removes database state but no media files, so app-owned
media is removed over the same SSH/rsync trust path and ABS is then rescanned.

## VibeVoice generation settings — Active

`ddpm_inference_steps = 10` for VibeVoice. Do not raise it. Measured 2026-08-12:
raising it to 20 then 30 degraded ASR similarity monotonically (0.872 → 0.847 →
0.809) on identical text, voice and seed, while costing 20–45% more GPU time.
Peak VRAM is 5.31 GiB regardless of steps or input length.

**Why:** this looks like an obvious quality knob and it is not — it is inverted.
See STATUS.md 2026-08-12 for the six-arm sweep.

## VibeVoice long-form capability proven; production quality rejected — Active

VibeVoice completed 13,666 source words in one generation, producing about 77
minutes of audio on a free Kaggle P100 (13,597 ASR words, WER 0.0887). This
reproduces the practical substance of Microsoft's "up to 90 minutes" claim and
answers issue #44's capability question. Capability is not suitability: the
corrected 6,166-word production-path file became progressively faster and more
run-on after roughly three minutes and failed human listening. Issue #44 is
closed with that negative promotion verdict. A separate 916-word / 4m19s run
showed stable pitch and measured 5.31 GiB peak VRAM.

**Boundary:** the 77-minute run's VRAM probe was attached to the parent while
generation ran in a subprocess and therefore reported zero. Long-duration VRAM
remains unmeasured; do not extrapolate the 4-minute 5.31 GiB result. The exact
single-pass fp16/SDPA/community-runtime path must not be reopened with another
seed or undocumented speed control. Reconsider only with current upstream
evidence for a materially different long-form path and a new controlled human
listening gate. Date corrected: 2026-08-14.

## Audition-passage validity per engine — Open, NOT settled

The canonical `voice_sample.SAMPLE_TEXT` measurably handicaps VibeVoice:
0.81–0.87 ASR on it versus 0.98+ on plain prose, across ddpm steps and seeds.
`voice_sample.MODERN_ENGINES` is `("chatterbox", "tada")` — VibeVoice and Qwen
are in neither branch by consideration, only by omission.

One input-policy question remains unresolved; the ranking consequence is now
settled:
1. Whether Vibe needs the legacy number treatment (`modern=False`) is untested.
   Run that arm before changing `MODERN_ENGINES`.
2. The 2026-07-29 "Vibe provisional quality leader / Qwen consistency leader"
   ranking was formed on invalid Vibe settings and is superseded. The corrected
   same-book comparison now puts Qwen ahead for long-form consistency.

**Why this is an entry at all:** the failure is silent. The audition renders,
passes structural QA, and sounds like an engine problem rather than an input
problem. Date: 2026-08-12.

## TTS engine defaults & Narrator — Active

Chatterbox Nano is the default production engine, and **Beatrice (Nano)** (`uk_female_samuel_nano`) is the default system narrator voice. Piper is legacy/debug only (`ENABLE_PIPER_PROFILE=1` required, not a fallback). Chatterbox Turbo and TADA require explicit opt-in (`ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1`).

**Why:** Beatrice (Nano) offers high-quality UK human-cloned narration at fast CPU speeds (~0.87x RTF) without requiring extra docker profiles or GPU hardware. Piper audio was rejected on listening ("absolute shit") on 2026-07-28.

## Article Ingest & Fast QA Bypass — Active

Web article URL ingest (`POST /api/articles/narrate_url`) and short content (< 15,000 chars) skip post-flight ASR verification by default. Generated article audio is automatically published to the Podcast RSS 2.0 feed (`/api/articles/rss`).

The Articles-tab paste action and owner-only Telegram capture both use the same
queue helper and the current system default narrator. They always create a
local, free, MP3 article job; neither path may choose a paid/cloud target or
inherit the legacy SQLite `kokoro` default accidentally.

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

**Host schedulers are part of this boundary.** On 2026-08-13 an undocumented
Zorin cron was found polling for *House of Huawei* and prepared to submit it to
Kaggle automatically. It had not created a job. The cron was retired with a
backup and sentinel guard. A future “no automatic cloud render” audit must
inspect cron/timers and external callers, not only `app.py` and Compose.

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

Qwen is the current full-precision long-form leader: its 6,166-word Yellow
Wallpaper chapter was “really good” and remained audiobook-listenable through
the full 33:03. The corrected Vibe cfg-2 production path used the same source
token sequence but failed from progressive pace/prosody drift after roughly
three minutes. Vibe's strong opening does not pass the audiobook gate. MOSS
remains eliminated; Higgs remains usable but not dependable enough to lead.

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
| VibeVoice full precision, community fp16/SDPA single-pass path | **Rejected for audiobook production** | cfg 2.0 has a very good opening but progressively accelerates/runs on and loses intent after ~3 minutes. Reopen only for a materially different officially supported long-form path, not another seed or undocumented knob. |
| Qwen3-TTS full precision | **Current long-form leader; not default** | Full 6,166-word chapter passed human listening and beat the corrected Vibe path for consistency. It still requires explicit free-Kaggle/local-GPU selection and book-specific auditioning. |
| CosyVoice 3 | **Keep / integration candidate** | A real 30-minute free-Kaggle render was listenable. Proper nouns need attention; this is not a rejection. |
| TADA-1B | **Keep / opt-in** | Works free on local CPU or Kaggle; high naturalness but residual pacing/control issues. Not rejected. |
| Chatterbox Multilingual V3 | **Unverified by ear** | Rendered accent clips exist; listen before promoting or rejecting. |
| Pocket TTS 2.1 Peter Yearsley preset | **Accepted opt-in; not default** | In the 3,600-word file, the body was decent with some emotion but sometimes lifeless/poorly paced. The clean 600-word A/B sounded more natural with current sentence packing; paragraph-aware packing made intonation stranger. Peter remains imperfect but passed as an optional free CPU narrator. Cloning remains unproven. |
| NeuTTS Air 1.4.1 Q4 + Jo | **Voice and normalized numeric path pass; residual insertion** | Dave selected normalized A, but heard “the e order” around “the order”. Treat that as a separate synthesis defect. Sentence chunking remains mandatory. |
| KittenTTS 0.8.1 Jasper/Rosie | **Accepted opt-in; not default** | Dave selected normalized A for Jasper (scratchy opening) and B for Rosie. Rosie's long-form body led for pace/tone. In the clean 600-word A/B both packing modes sounded decent with no meaningful difference, so current sentence packing wins on fewer resets. Preset-only; no UK-identity claim. |
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

The 2026-08-13 Pocket/NeuTTS/Kitten result is a listening verdict about clips
generated by the isolated evaluation scripts with raw text through each
official API. They were served by the app, but did **not** use the app's text
normalizer; earlier “app-path clip” wording was incorrect. The 2026-08-14
follow-up held model, voice and settings fixed and changed only raw versus
explicit spoken wording. Dave selected the normalized arm for **all four**
voices. The original shared numbers/currency failure was therefore the
evaluation path passing raw text, not evidence of an inherent shared engine
failure. Any future Pocket, NeuTTS or Kitten integration must use explicit
deterministic number/currency normalization. Jo's “the e order” insertion and
Jasper's scratchy opening remain separate synthesis defects; Rosie gave the
strongest overall handling. None of these candidates replaces the Chatterbox
Nano/Beatrice production default until its own long-form gate is passed.

Pocket and Kitten are therefore implemented as **opt-in CPU-only book choices**,
never as defaults or automatic fallbacks. Their preview, first-render and
recovery commands use the named `explicit` text profile: deterministic spoken
numbers/currency and acronym letter-spacing, without the legacy phonetic
lexicon. Every offered official preset must have a persisted preview before it
is selectable. Catalogue presence is not a human quality verdict for every
voice; it guarantees immediate audition and an engine-bound conversion choice.

The first Peter/Rosie long-form gate is valid evidence about the voices' body
quality, but **invalid evidence about title/author delivery**. Both engines were
sent the identical flattened first request beginning `Title: ... Author: ...`
and continuing directly into the first sentence. The source was Project
Gutenberg's generated `pg-header`, not book prose. Exact `pg-header`/`pg-footer`
containers are now excluded structurally. Paragraph-aware request boundaries
remain an A/B candidate, not a production default, until heard.

The corrective 600-word gate was rendered and heard at revision `cc1b0c6`:
current 280-character sentence packing (15 requests) versus exact source-
paragraph boundaries (28 requests), for both Peter and Rosie. No engine
parameter changed. Dave preferred current packing for Peter because it sounded
more natural; the paragraph-aware arm had stranger intonation. Rosie showed no
meaningful audible difference. Current packing therefore remains production
behavior for both engines: paragraph preservation does not justify nearly
twice as many model resets without an audible gain.

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

## Application HTTP Basic authentication — Superseded

The UI and private APIs require environment-owned HTTP Basic credentials. An
empty password fails closed; the settings database cannot set or reveal it.
Podcast RSS/audio plus health/version probes remain public for non-browser
clients.

**Superseded 2026-08-13:** this ignored the actual deployment boundary. The app
is LAN-only and its public hostname already has Pangolin SSO. Stacking HTTP
Basic behind Pangolin created a second incompatible login and made Pangolin's
health check report the healthy target as unhealthy. Dave explicitly reversed
this after testing the real public URL.

## LAN, Pangolin SSO, podcast access and article SSRF boundary — Active

The app is intentionally passwordless on the trusted LAN. External browser
access uses Pangolin SSO at `audio.magnusfamily.co.uk`; the application must not
add a second password prompt behind it. Flask trusted-host validation includes
the LAN names/addresses and the Pangolin hostname, and browser writes retain
same-origin enforcement. Podcast delivery bypasses Pangolin SSO only for the
exact feed path `api/articles/rss` and enclosure shape
`api/articles/audio/*/*`; the health probe is evaluated by Pangolin against the
private target. The Telegram callback has its own exact
`api/telegram/webhook` bypass. All other public-host paths retain SSO.

Telegram's public webhook requires the official
`X-Telegram-Bot-Api-Secret-Token` header and the incoming chat must equal the
configured owner `TELEGRAM_CHAT_ID`. Article URL ingest permits public
HTTP(S) destinations only, checks all resolved addresses plus the connected
peer, validates every redirect, and bounds response size.

**Official basis:** Flask 3.1 request lifecycle/security documentation,
Python `ipaddress`/`urllib.parse`, Requests redirect controls, and Telegram Bot
API `setWebhook(secret_token=...)`, plus Pangolin's public-resource
authentication and ordered path-rule documentation, read 2026-08-13. This
keeps identity at the real ingress boundary without weakening webhook or
server-side request-forgery controls.

## Article Podcast RSS Feed & Telegram Capture (#42) — Active

Articles are served via a standard RSS 2.0 podcast feed (`/api/articles/rss`) with
audio enclosures for Pocket Casts/Overcast/ABS, and article URLs sent via Telegram
webhook (`/api/telegram/webhook`) are automatically fetched, converted to EPUB,
and enqueued for narration. Deployments behind a proxy set `PUBLIC_BASE_URL` so
the feed emits canonical HTTPS enclosure URLs instead of its internal LAN
origin.

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
