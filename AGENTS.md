# AGENTS.md — EPUB to Audiobook

Self-hosted ebook-to-audiobook conversion app with Docker services, TTS engines, queue processing, Audiobookshelf sync, and optional Telegram/WhatsApp notifications.

## Decisions — Check Before Acting

[DECISIONS.md](DECISIONS.md) holds settled, closed questions for this repo —
engine defaults, GPU policy, deploy discipline, current quality-gate verdicts.
It is not a changelog; STATUS.md is. **Before proposing to change, redo, or
re-open something, check DECISIONS.md for an existing entry on that topic
first.** If a session settles a new question or reverses one, update
DECISIONS.md in the same session — don't just log it in STATUS.md and leave
DECISIONS.md stale.

## Authoritative-Source Gate — RTFM Before Experimenting

For every external engine, model, API, SDK, container, deployment tool, or
integration, agents **must read the current official documentation before
changing code, parameters, dependencies, or operational advice**. Trial and
error is for answering questions the documentation does not answer; it is not a
substitute for reading the manual.

The required order is:

1. Read this repo's `DECISIONS.md` and the relevant repo documentation/history.
2. Read the vendor/maintainer's current official README, model card, API docs,
   release notes and parameter documentation that apply to the exact version in
   use.
3. If the deployed path uses an unofficial/community wrapper, read and pin that
   wrapper too, and state the boundary clearly. Official weights do not make a
   community runtime official.
4. Record the authoritative URL plus the exact model, tag/commit, important
   defaults, licence/use restrictions, and pricing date (when cost is relevant)
   in the evidence trail. A claim without this provenance remains **unverified**.
5. Only then design an experiment for the remaining unknown. Audible quality
   still requires Dave's listening verdict; documentation and metrics cannot
   replace it.

If official documentation is missing, disabled, contradictory, or does not
cover the deployed behaviour, say so explicitly. Do not silently promote a
blog, search result, community issue, or remembered default to an official fact.

## Current Direction & Doc Map (2026-08)

Read these before changing anything TTS- or text-related:

| Doc | What it holds |
|-----|---------------|
| [DECISIONS.md](DECISIONS.md) | **Settled questions — check first, before STATUS.md.** |
| [GETTING-STARTED.md](GETTING-STARTED.md) | New-user walkthrough: install, convert, connect an LLM, voices, ABS. |
| [OPERATIONS.md](OPERATIONS.md) | Runbook + incident log: job states, failure responses, capacity truths. |
| [STATUS.md](STATUS.md) | **Current state & remaining tasks — read first.** What's verified vs unverified vs not-done. |
| [PREPROCESSING.md](PREPROCESSING.md) | **Mandatory** text pipeline (6 stages; 1–4 implemented in `webapp/tts_preprocess.py`, 5 designed, 6 core implemented). Why upstream `--remove_endnotes` must never return. |
| [LOW-COST-TTS.md](LOW-COST-TTS.md) | Engine bake-off, listening verdicts, cost model, UK reference voices. |
| [TTS-LANDSCAPE-2026-07.md](TTS-LANDSCAPE-2026-07.md) | Mid-2026 state-of-the-art review: new engines, cost updates, what to evaluate next. |
| [ENGINES.md](ENGINES.md) | Official engine facts + listening outcomes — the baseline for all engine claims. |
| [VOICES.md](VOICES.md) | **Read before ANY voice or accent work.** Listening verdicts, exact rejection boundaries, the corrected `cfg_weight` interpretation, and wrong turns already taken. |
| [PLAN-V6.md](PLAN-V6.md) | **Current forward plan** (2026-09-02): Smart Library — WhatsApp book bot, auto-series completion, AI library curator, family wishlists. |
| [PLAN-V5.md](PLAN-V5.md) | Previous forward plan (2026-07-27): automatic re-render, article RSS + Telegram capture, Chatterbox V3. |
| [PLAN.md](PLAN.md) | Superseded. Historical forward plan. |
| [GPU-SAFETY.md](GPU-SAFETY.md) | **READ FIRST for any GPU work.** Default-local rules; how to not drain the Vast balance. |
| [GPU-PLAYBOOK.md](GPU-PLAYBOOK.md) | Vast.ai RTX 3060 batch pattern + operational steps. |

## Verification Discipline (2026-07-15 — every rule here was paid for)

These are not style preferences. Each rule exists because its violation shipped a
broken result that the **user** had to find. An agent that follows the diagnosis
playbook but skips these is a net negative.

1. **"Fixed" means measured or listened-to, never deployed.** A deploy that
   compiles and restarts proves nothing. Before claiming a render works: check the
   output files exist, are full-length (duration/size vs source words), and — for
   anything audible — that a human has heard it or an ASR pass matches the source.
   *Violation: "being rendered correctly right now" claimed while only 1 of 3
   chapters existed on disk.*
2. **When you fix a bug in one code path, audit every parallel path for the same
   class before announcing the fix.** This repo has duplicate paths by design
   (Kaggle vs local render; webapp vs recovery vs finalize). A fix to one is a
   *claim about all of them* the moment you describe it as "the app now does X".
   *Violation: chapter numbering unified for Kaggle only; the local p0n1 path kept
   its own numbering and rendered publisher junk instead of the book (#28).*
3. **When you change an input, re-check every limit sized to the old input.**
   Longer sample text broke a 180s timeout sized for shorter text; every chatterbox
   sample was synthesised, timed out, and discarded — and it looked like slowness,
   not failure.
4. **When you invalidate state, stop describing its former condition.** After
   wiping a cache, "cached and instant" is false until re-verified — say
   "regenerating, N/M done" instead.
5. **Background work shares the host with the product.** Throttle it (load-aware,
   skip-done, off-switch) and check UI latency + engine healthchecks while it runs.
   *Violation: unthrottled sample generation drove load to 8+, starved the UI, and
   made healthy engines report "offline".*
6. **Repeat the user's nouns, not your own.** If the user says kokoro, the work is
   about kokoro. Restate their complaint in their words before diagnosing; do not
   substitute the component you were already thinking about.
7. **TTS conclusions come from rendering and listening, never reasoning.** Two
   documented bans (year-spelling; suspect: respellings) came from misdiagnosing a
   formatting artefact as a conceptual failure. The A/B harness
   (`scripts/kaggle/render_voice_samples.py` + `/api/sample/<name>`) makes this
   cheap. See PREPROCESSING.md "read this first".
8. **Status must distinguish claim-levels.** STATUS.md separates *verified* /
   *unverified* / *open* — GitHub issues carry measured evidence. Never move an
   item up a level without the measurement in hand.
9. **Pass the Authoritative-Source Gate above before researching or trying
   anything.**
   *Violations, all on 2026-07-27:* the VCTK accent voices, the Edge Australian
   voices and TADA's `LEADIN` cold-start fix were each "discovered" by research
   while already present in the codebase; and a full day of accent work ran
   without first reading Chatterbox's documented controls. A later agent made
   the opposite error and promoted `cfg_weight=0` for same-language accent
   preservation, although upstream documents zero for a reference/target-
   language mismatch and `0.5` as the normal default. Both failures came from
   interpreting a parameter before reading its exact documented boundary.
   Check `VOICES` in `app.py`, `git log`, and the upstream README first.
10. **Never hand over a URL, path or clip you have not opened yourself.**
    *Violation: `/api/sample/ab_tada_cpu` was given to the user and 404'd —
    the file existed, the endpoint allowlist did not have the name.*
11. **Deploy the whole stack, not one service.** `webapp` and `worker` are two
    containers built from the same Dockerfile sharing `app.py`; rebuilding one
    leaves the other on old code, and `/api/health` reports only the webapp's
    version so it looks current. Use `scripts/deploy.sh`. See OPERATIONS.md.
12. **A regression guard that fires is right until proven otherwise.** They
    encode decisions that were paid for, often by ear. If one blocks a change,
    the default is that the change is wrong — not the guard.
13. **Listening proves the output failed; it does not prove why.** Before
    rejecting an engine, blaming a model, or proposing a replacement, audit the
    exact deployed synthesis path against the repo history and the vendor's
    current docs. Verify model identity/hash and quality tier, voice/speaker
    mapping, language/phonemizer, inference defaults, wrapper/runtime version,
    preprocessing, cache freshness and output transcoding. Then render a direct
    upstream-vs-app A/B. Report the listening verdict separately from the
    root-cause conclusion; leave the cause open when the A/B has not been heard.
14. **A voice is offered only after its exact preview is cached and playable.**
    The Voices screen is an audition surface, not a synthesis trigger: a Play
    click must never start cold generation. After adding, renaming or changing
    a voice, generate its persisted preview, verify the exact ID through
    `/api/voices`, open `/api/preview/<voice_id>` yourself, and record the
    ready/total count. Never describe a wiped or incomplete cache as ready.

Key facts an agent must know:
- Conversion runs the upstream container `ghcr.io/p0n1/epub_to_audiobook` (a *different* project with a confusingly similar name); our webapp orchestrates it and preprocesses a `_tts.epub` copy first.
- The deployed stack is currently a Git checkout on Zorin at `/home/dave/ai/lab/stacks/epub-to-audiobook` (the older `/opt/epub-to-audiobook` documentation was stale). Deploy **from git only**; never patch application source live. The default deploy enables Chatterbox Nano with **Beatrice (Nano)** (`uk_female_samuel_nano`) as system default narrator. Piper is fully retired after its controlled old/current-runtime + encoding A/B failed quality: do not restore its service, profile, route or voices without an explicit decision reversal. Chatterbox Turbo and TADA require the explicit `ENABLE_CHATTERBOX_PROFILE=1` / `ENABLE_TADA_PROFILE=1` opt-ins. Zorin was upgraded to an i5-12400 / 31 GB (2026-07-20); Chatterbox now runs comfortably for previews. TADA is opt-in and **works** as of 2026-07-27 (#23 closed — the OOM was fp32 on CPU; bf16 fits the cap, RTF 1.68).
- Two custom engines are BUILT and containerised: `chatterbox/` (Turbo) and `tada/` (TADA), both OpenAI-compatible, UK human-cloned voices baked in. Adding an engine = VOICES entries + a branch at the three `tts_engine ==` sites in app.py.

## Scope

- App code, scripts, tests, Docker Compose, and deployment docs for this repo.
- Target stack paths and host-specific deployment details are documented in `README.md` and `GPU-PLAYBOOK.md`.
- Do not expose or commit `.env`, `.secrets/`, SSH keys, generated audio, job databases, or local screenshots unless explicitly requested and reviewed.

## MCPProxy / Tool Surfaces

- Use the MCPProxy instance local to where the agent is running. Windows normally uses `http://127.0.0.1:8080/mcp`; `khpi5` uses `http://127.0.0.1:9092` for work started on that host.
- **Tool discovery is mandatory, not optional.** Do not assume a tool exists or doesn't exist — call `retrieve_tools` on the local MCPProxy at the moment you need a capability. Use exact `server:tool` names and verify the server name before every call, especially before any write.
- Use `win-filesystem` / local shell for repo edits and local checks.
- Use SSH for deployment host checks when the task targets a remote stack.
- Nango surfaces are not primary for this repo. If notifications or external service proofs are needed, pick the project-appropriate email/calendar/Telegram/WhatsApp surface explicitly and avoid Callout/Clean Bean Stripe or Cloudflare surfaces unless the task names them.
- Appwrite is not part of this repo.

### Signed-in Edge Browser (Windows MCPProxy only)
For authenticated-browser tasks (the webapp UI, Audiobookshelf at `192.168.1.113:13378`, signed-in sites), use the MCPProxy upstream `playwright-edge` — Microsoft's official Playwright Extension attached to the live Edge `Default` profile (`David M` / `davidm@live.co.uk`). **This route exists only on the Windows MCPProxy (`http://127.0.0.1:8080/mcp`) — khpi5 has no signed-in browser route.** Never use Edge debugging mode, port 9222, or profile clones. Canonical runbook: `C:\Users\Dave\repos\windows\mcpproxy\signed-in-edge-automation.md`; prove health with `Test-SignedInEdgeAutomation.ps1 -RequireLiveProof` before first use (operational, full gate + authenticated identity readback verified 2026-08-30).

## Core Rules

1. Build and test locally before changing deployment state.
2. Preserve Docker Compose service boundaries; do not remove worker/queue services without proving queue behavior.
3. Treat TTS model assets and generated audiobooks as large runtime artifacts, not source.
4. Stage only intentional files; never `git add -A`.
5. **GPU/Vast.ai costs real money — default is LOCAL. Never spin up a Vast
   instance or enable `GPU_RENDER_ENABLED` without an explicit user request
   for the current task, and always destroy instances you create in the same
   session. Read [GPU-SAFETY.md](GPU-SAFETY.md) before ANY GPU action.**

## Verification

Prefer targeted checks:
- unit or smoke scripts in `tests/` / `scripts/`
- `docker compose config`
- app smoke check against the configured local or remote URL
