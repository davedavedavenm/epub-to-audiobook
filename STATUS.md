# Project Status & Remaining Tasks

> ## 2026-08-13 current baseline, Vibe verdict and cache contract — VERIFIED / DEPLOYED
>
> **Live services:** `epub-to-audiobook-worker` is running/healthy, exit 0 and
> `OOMKilled=false`; the earlier 3 August exit-137 report is stale. `piper-tts`
> is intentionally stopped: its historical exit 137 was not an OOM kill and the
> tested Piper path is rejected for production. Chatterbox Nano/Beatrice remains
> the default local narrator. No paid GPU path is armed.
>
> **UI:** the first navigation
> destination is now explicitly **Home**, the brand and persistent top-bar Home
> control both return there, navigation targets have larger high-contrast labels
> plus descriptions, and widths up to 980 px use a labelled Menu drawer rather
> than crushing the content. A real browser check at 780×493 loaded Home and the
> Voices listening card successfully.
>
> **VibeVoice verdict:** A and B contain
> the same first 351 source words from *The Yellow Wallpaper*; timed transcription
> alignment measured sequence ratios of 0.9957 and 1.0000 at the cut points, and
> `ffprobe` measured 93.408 s / 1,868,698 bytes and 99.432 s / 1,989,178 bytes.
> Both browser players reached `readyState=4`. Dave selected **B = cfg 2.0** as
> much better and otherwise excellent, with one brief garble after “romantic
> felicity”. **A = cfg 3.0** is rejected as muffled/distant; cfg 1.3 was already
> rejected. Compose now defaults Vibe to 2.0. Production promotion remains open
> only for a direct-upstream versus app-path check of B's isolated defect; the
> completed blind-handoff monitor was removed.
>
> **Preview cache:** `/api/voices` now reports **88/88 configured voices ready**.
> Four exact TADA previews were generated on the local CPU; the validated Qwen
> Arthur candidate and Dave's selected Vibe B/cfg-2.0 file were persisted under
> their exact catalogue IDs. Every file is non-trivial and each configured
> preview route returns audio immediately. Unconfigured Polly/Inworld voices are
> excluded and cannot spend money in the background. Play is now a cache read,
> the UI hides unready auditions, and the free-local warmer is load-throttled,
> skip-existing and disableable. TADA was enabled only for this local prewarm and
> then returned to its normal opt-in state.
>
> **Repository/onboarding:** README, Getting Started, Decisions, engine/voice,
> operations, cost and current-plan documents now agree on audiobook-first,
> local/free defaults, the human-listening boundary, Vibe cfg 2.0 and cached
> auditions. New Linux/PowerShell bootstrap helpers write a real absolute
> `STACK_PATH`, enable Nano and wait for health; documented shell helpers now
> carry executable bits. The complete suite passes: **247 tests**.
>
> **CPU auditions:** the Voices page also surfaces the already-rendered Pocket
> TTS/Peter Yearsley, NeuTTS Air/Jo and KittenTTS/Jasper + Rosie clips. These are
> listening candidates only; none is wired into production or made a default.
>
> ## 2026-08-13 public article delivery + CPU engine screen — VERIFIED / LISTENING PENDING
>
> **RSS/Pangolin:** the live public feed returned `200`, parsed as RSS 2.0 and
> contained six episodes; a real enclosure byte-range request returned `206`.
> Pangolin exceptions are restricted to the exact feed and enclosure paths;
> `/api/jobs` still redirects to SSO. `PUBLIC_BASE_URL` now makes feed and
> enclosure URLs canonical HTTPS rather than leaking the internal LAN origin.
>
> **Article capture:** the Articles-tab URL paste and Telegram link capture now
> share one queue path. Both use the configured default narrator, derive its
> actual engine, create MP3 article jobs and force the local/free render target.
> Telegram additionally requires both its official secret header and the
> configured owner chat ID. The bot webhook must be verified live after the
> full-stack deploy before this item moves from code-verified to operationally
> verified.
>
> **CPU candidates:** Pocket TTS and KittenTTS produced complete canonical
> audition files without a GPU. Pocket measured 64.080 s audio in 66.220 s
> (RTF 1.033, peak 1307.6 MiB) using its official Peter Yearsley preset, but
> emitted a 50-token chunk-limit warning and its cloning weights remain behind
> Kyutai's model-terms gate. Kitten Jasper measured RTF 2.304 / 1047.9 MiB and
> Rosie RTF 1.761 / 1090.4 MiB; these are preset voices, not clones. No engine
> is admitted or rejected until Dave listens. NeuTTS's first whole-passage run
> truncated because the official model documents an approximately 30-second
> context. The corrected ten-sentence render produced 72.610 s in 357.875 s
> (RTF 4.929, peak 2842.4 MiB) with its official Jo reference. That clip is
> complete by duration/chunk accounting, but the engine emitted phonemizer
> word-count warnings and needs listening before any conclusion.
>
> **Cost boundary:** all screens are isolated four-core CPU containers with no
> queue registration, GPU devices or paid fallback. `GPU_RENDER_ENABLED=0`
> remains the live production setting.

> ## 2026-08-13 repo + live-system audit — VERIFIED FINDINGS, FIXES DEPLOYED
>
> **Live baseline:** Zorin checkout `/home/dave/ai/lab/stacks/epub-to-audiobook`
> had no tracked changes at `934bed5` (untracked runtime/backup artifacts exposed
> ignore-rule gaps); webapp and worker reported the same revision, all
> containers had zero restarts, SQLite integrity passed, and the host had no
> active/failed render work (103 historical jobs: 46 complete, 57 cancelled).
> `AUTOSCALE_ENABLED=false`, `GPU_RENDER_ENABLED` was unset/off, the app reported
> GPU state `idle`, and no GPU tunnel/container or status file existed. After
> repairing the exact-key mount, the pinned official Vast CLI authenticated from
> the worker and returned **zero provider instances**. The paid-GPU environment
> gate remains explicitly off.
>
> **Critical audit correction:** the worker still contained a legacy
> queue-length → `GPUManager.scale_up()` path that did not check the
> `GPU_RENDER_ENABLED` master gate. It happened to be dormant only because the
> environment flag was false. Local hardening now removes that path and its
> Compose switches, makes the manager fail closed without an explicit manual
> authorization, removes Vast from per-book selection, and rejects any ordinary
> job target other than local/free Kaggle. Paid enablement is now
> environment-only: the Settings API/UI cannot arm the manual endpoint.
> Regression coverage is added. These changes are live on both webapp and worker
> from git revision `80b0fac`.
>
> **Other confirmed defects and disposition:** the unused ASR-driven
> `--auto-rerender` path is removed; single-chapter recovery atomically merges
> whole-book QA evidence; article RSS now encloses a deliberately public,
> validated audio route; EPUB overlays map only renderable chapters and use
> `ffprobe` duration from the finished media; trusted-host and same-origin write
> checks protect the app while Pangolin SSO protects its public URL; Telegram uses its
> official webhook-secret header; and article fetch validates every DNS,
> connected-peer and redirect address while bounding response size. Vibe's
> rejected cfg 1.3 is still not being replaced until the blind cfg 2/3 chapter
> test is heard.
>
> **Additional local fixes:** `deploy.sh` now defaults to `master`/version 2.0.0
> rather than the stale v1.3 tag; background preview caching is restricted to
> currently healthy free/local Chatterbox/TADA engines and cannot silently call
> Polly, Inworld or Edge at startup; and runtime/secret-backup paths are ignored
> without deleting them. `git lfs pull` restored all 16 tracked narrator WAVs
> locally; all have RIFF headers and Arthur matches the expected 864,182-byte
> SHA-256 `8774082c...`.
> The deprecated runtime download of `vast.py` from a moving GitHub `master`
> branch is removed; the image now pins Vast's supported official `vastai==1.5.4`
> package. Its declared `requests>=2.33.0` dependency initially conflicted with
> the repo's `requests==2.32.4` pin; the repo now pins `requests==2.33.0`, the
> full requirement set resolves, and a regression guard covers the pairing.
> The legacy credential mount is now an exact untracked key-file mount readable
> by the worker group; `vastai show instances --raw` authenticates successfully
> and returned zero instances. This repairs observability only and does not arm
> paid provisioning.
>
> **Secret-history audit:** Gitleaks scanned all 550 commits / ~5.2 MB and found
> the same historical `EVOLUTION_API_KEY` value in two public commits
> (`docker-compose.yml` at `6737384` and `PLAN-v1.1-fixes.md` at `fcf061e`).
> Values were redacted during inspection. The old credential was tested directly
> against Evolution's official `GET /instance/fetchInstances` endpoint: it
> returns **401**, while the distinct current key returns **200**.
> Rotation/revocation is therefore proven.
> GitHub's Dependabot/code/secret-scanning APIs were unavailable for this
> repository/account and therefore provide no clean-bill evidence.
>
> **Documentation decisions settled:** quality is the human admission floor,
> then free generation wins, then the lowest measured paid cost per finished
> book. Official upstream documentation for the exact version is mandatory
> before experimentation. Engine rejection boundaries are now explicit in
> `DECISIONS.md`. ASR remains structural collapse/completeness evidence only;
> it cannot grade voice quality or select the better render.
>
> **Acquisition boundary:** this repo contains only the wanted-monitor/OpenBooks
> bridge. The active torrent-first path is in the sibling `infra` repo:
> LazyLibrarian → Prowlarr → qBittorrent, with Usenet fallback. Do not
> duplicate those operational docs here.
>
> **Verification and deployment:** 243 tests pass; Ruff, Python compilation,
> Compose config, shell syntax, staged Gitleaks and `git diff --check` pass. A
> real Zorin `ffprobe` probe and a real bounded public fetch also passed. The
> the whole stack deployed the audited revision; live checks proved exact
> SHA/overall health, Host and Origin rejection,
> Telegram secret enforcement, loopback SSRF rejection, five RSS enclosures and
> a successful `206` request against the first enclosure. Both webapp and worker
> are healthy with zero restarts. The corrected free-Kaggle Vibe cfg 2-vs-3
> full-chapter blind test is still running; no default will change before Dave
> listens.

> **Authentication correction (2026-08-13):** application HTTP Basic was
> removed after testing the actual deployment boundary. The app is intentionally
> passwordless on the trusted LAN; `audio.magnusfamily.co.uk` already has
> Pangolin SSO. The stacked prompt was redundant, broke the public login flow,
> and made Pangolin's `/` health check report `unhealthy` on an otherwise healthy
> service. Same-origin writes, trusted hosts, Telegram secret validation, SSRF
> controls and all paid-GPU guards remain in force. The corrected stack was
> verified with LAN `200`, no `WWW-Authenticate` challenge, an external `302`
> to Pangolin's login, and a Pangolin target state of `healthy` after its probe
> moved from `/` to `/api/health`.

> ## 2026-08-13 `cfg_scale` is the VibeVoice speaker-similarity lever — 1.3 REJECTED BY EAR
>
> **Dave, on identical 190-word renders differing only in `cfg_scale`:**
> *"2 and 3 are fine. 1 is trash."* (1 = cfg 1.3, 2 = cfg 2.0, 3 = cfg 3.0.)
>
> **How this surfaced:** after the Breakneck A/B Dave said neither clip "sounded
> like Arthur", though both were decent. That was checked as a plumbing fault
> first and cleared — the reference is genuine (URL serves the real 864182-byte
> WAV, sha256 `8774082c...` matches). So the conditioning was correct and the
> timbre still was not arriving.
>
> Every VibeVoice clip ever produced in this repo ran `cfg_scale=1.3`, inherited
> unexamined from the Yellow Wallpaper kernel. The pinned community runtime
> exposes `cfg_scale`; the short sweep empirically shows speaker-conditioning
> behaviour analogous to Chatterbox's `cfg_weight`. Microsoft's official TTS
> documentation does not define that parameter contract, so this is a measured
> repo finding, not an official Microsoft claim. Nobody had moved it for Vibe.
>
> | clip | cfg | f0 median | f0 IQR | centroid | ASR | Dave |
> |------|----:|----------:|-------:|---------:|----:|------|
> | **Arthur reference** | — | **131.2** | **72.8** | **2135** | — | target |
> | baseline | 1.3 | 112.9 | **14.4** | 1838 | 0.976 | **"trash"** |
> | | 2.0 | 114.9 | 31.9 | 1919 | 0.992 | fine |
> | | 3.0 | **130.4** | 39.8 | 1955 | 0.984 | fine |
>
> Pitch, pitch range and brightness all move monotonically toward the reference
> as `cfg_scale` rises; at 3.0 median pitch lands on Arthur's (130.4 vs 131.2).
> The baseline's pitch IQR of 14.4 against Arthur's 72.8 is near-monotone, which
> is the most likely thing Dave was hearing. Intelligibility does not suffer
> (ASR 0.976–0.992, best at 2.0). One measure dissents — mean-MFCC cosine drifts
> down — but that statistic is dominated by gross spectral shape and is a weak
> speaker proxy; recorded so it is not rediscovered as a contradiction.
>
> **Even cfg 3.0 carries about half Arthur's pitch range.** Above 3.0 is untested.
>
> **What this invalidates:** every VibeVoice listening judgement in this repo was
> made at `cfg_scale=1.3` — the full-chapter finalist gate (2026-07-29), the
> 27-minute Yellow Wallpaper clip, the Raven E2E job, and the "Vibe provisional
> quality leader / Qwen consistency leader" ranking. Note the direction of the
> error: **Vibe won that gate while handicapped**, at the setting Dave has now
> called trash, on an audition passage that separately costs it ~0.13 ASR. A
> fair re-run can only move Vibe up.
>
> **Kernel hardening shipped with this sweep:** the Yellow Wallpaper kernel
> downloads the reference with no integrity check, while `run_vibevoice.py`
> asserts RIFF magic, exact byte count and sha256 — because the voices are
> Git-LFS tracked and a pointer file looks like a successful download. Those
> assertions are now in the sweep kernels too.
>
> **Unrelated but found today: the local voice files are LFS pointers.**
> `chatterbox/voices/uk_male_minter.wav` on the Windows working copy is 131
> bytes of pointer text, not audio. Kaggle renders are unaffected (they fetch
> from GitHub) but anything reading that path locally gets text. Run `git lfs pull`.
>
> Artifacts: `scratch/vibe90/cfg_out/`, reference at
> `scratch/vibe90/ARTHUR_reference.wav`.

> ## 2026-08-12 VibeVoice drift sweep — the audition passage is the variable, not length or ddpm
>
> **Origin:** an outside "low-cost TTS" report was reviewed against this repo and
> found to be mostly cost analysis aimed at hardware we do not render on. While
> auditioning Arthur on VibeVoice to check the report's premise, Dave heard the
> 62-second audition clip as "the first part and last part sounded totally
> different" — while calling the earlier 27-minute Yellow Wallpaper clip
> excellent. Both ran identical settings. That contradiction is what was tested.
>
> **Method:** one Kaggle kernel, one model load, six arms, everything held fixed
> except the named variable (`scratch/stage_sweep_kernel.py`, kernel
> `davedavedavedavenm/vibevoice-drift-sweep`). Engine
> `microsoft/VibeVoice-1.5B`, runtime `vibevoice-community/VibeVoice@07cb79f`,
> reference `uk_male_minter` (Arthur), fp16 + SDPA, `cfg_scale=1.3`,
> `do_sample: False`. "hard" = the canonical `voice_sample.SAMPLE_TEXT`
> preprocessed with `modern=True`; "easy" = Yellow Wallpaper prose.
>
> | arm | text | words | ddpm | seed | audio s | RTF | peak VRAM | ASR sim |
> |-----|------|------:|-----:|-----:|--------:|----:|----------:|--------:|
> | A | hard | 182 | 10 | 12345 | 61.5 | 1.18 | 5.31 GiB | 0.872 |
> | B | hard | 182 | 20 | 12345 | 62.4 | 1.43 | 5.31 GiB | 0.847 |
> | C | hard | 182 | 30 | 12345 | 53.7 | 1.69 | 5.31 GiB | 0.809 |
> | D | easy | 217 | 10 | 12345 | 64.5 | 1.18 | 5.31 GiB | **0.988** |
> | E | easy | 916 | 10 | 12345 | 258.8 | 1.22 | 5.31 GiB | **0.979** |
> | F | hard | 182 | 10 | 777 | 51.9 | 1.16 | 5.31 GiB | 0.836 |
>
> Median f0 per sixth of each clip (drift proxy): E spread **25 Hz**, D **37 Hz**,
> F **17 Hz** — versus B **219 Hz** and C **115 Hz**. Arm A sat at the tracker's
> floor throughout (very low/creaky). Clips in `scratch/vibe90/sweep_out/`.
>
> **Findings, in order of usefulness:**
>
> 1. **The hard audition passage is what destabilises VibeVoice.** Every arm on
>    it scores 0.81–0.87; every arm on plain prose scores 0.98+. Same voice,
>    same engine, same settings.
> 2. **Length is exonerated.** 916 words / 4m19s is the *most* stable arm
>    (f0 spread 25 Hz, ASR 0.979). Short inputs are not the problem — the
>    `MIN_CHARS = 220` parallel from `build_chapter_kernel.py` does not apply here.
> 3. **ddpm steps are exonerated and inverted.** 10 → 20 → 30 degraded ASR
>    monotonically (0.872 → 0.847 → 0.809). More diffusion is worse. Leave it at 10.
> 4. **Not seed luck.** A different seed on the hard text still scores 0.836.
> 5. **Peak VRAM is 5.31 GiB flat** across every arm including the 916-word one
>    — measured in-process, so this figure is sound up to ~4 minutes of audio.
>    See the correction below: the equivalent measurement at 77 minutes failed,
>    so do not extrapolate this to full-length single-pass renders.
> 6. **VibeVoice is fit for books.** Continuous real prose at 4+ minutes shows
>    essentially no drift. Nothing here argues against rendering full chapters.
>
> **Suspected mechanism, NOT yet confirmed:** the audition render forced
> `modern=True`, which leaves bare digit strings in the text (`3400`, `230000`,
> `52%`, `$1.2 billion`, `£24.6 billion`). Chatterbox and TADA cope; Vibe may
> not. The confirming arm (`modern=False` on the same passage) has not been run.
> Do not treat this as settled.
>
> **Caveat that matters for the finalist ranking:** every VibeVoice audition to
> date has gone through this passage, including the listening that produced the
> 2026-07-29 "Vibe provisional quality leader / Qwen consistency leader" call.
> That comparison was made on input that measurably handicaps Vibe. It may
> survive a fair rerun; it has not had one.
>
> **Two live traps found in passing:**
> - `voice_sample.MODERN_ENGINES` is `("chatterbox", "tada")`. VibeVoice and Qwen
>   are absent, so auditioning either through the normal path applies the legacy
>   treatment (numbers spelled out, phonetic respellings). Whichever side Vibe
>   belongs on, the current state is unconsidered rather than chosen.
> - The proven Vibe kernel's `verify()` carries `min_minutes=20, max_minutes=70`.
>   Any short render reports `KernelWorkerStatus.ERROR` **after** writing correct
>   audio and a valid QA report. An audition-length render always looks failed.
>
> **Also verified today:** `kaggle kernels output` now pulls artifacts correctly
> (a 78 MB WAV came down clean). The July `kernels.get` permission failure that
> blocked the CosyVoice audition runs is gone — those are unblocked.
>
> **CORRECTION 2026-08-13 — the Holmes run answered #44 after all.** It was
> left running overnight rather than stopped, and completed: **13,666 source
> words rendered in a single generation, ~77 minutes of audio, WER 0.0887**
> (flagged only because the threshold is 0.08), 13,597 words heard against
> 13,666 expected, on a Tesla P100. So VibeVoice's 90-minute single-pass claim
> is **real and reproduced here**, and #44's capability question is answered
> yes. Artifacts: `scratch/vibe90/out/`.
>
> The judgement that it was the wrong *priority* still stands — a real book
> answers the same question and leaves something worth listening to — but it
> was not wasted, and this entry originally said it was. The 30 flagged
> divergences are almost all ASR failures on archaic vocabulary (brougham,
> ostlers, twopence, landau, vizard, pshaw, chamois), which per the ASR
> evidence boundary is not evidence the engine mispronounced them.
>
> **Instrumentation bug, mine:** the peak-VRAM probe added to that kernel
> reported 0.0 GiB because it ran in the parent process while generation
> happened inside the `convert_book.py` subprocess. **The 90-minute VRAM figure
> was therefore never captured.** The 5.31 GiB in the table above is sound —
> that sweep measured in-process — but it covers up to 916 words only. Treat
> "VRAM is flat with length" as established to ~4 minutes and untested at 77.


> ## 2026-08-09 Studio Upgrade & Production Baseline — DEPLOYED (559a1f5, c316cce)
>
> All features and fixes from the August 2026 Studio Upgrade session are tested
> (`231/231 passed`) and live-deployed to the Zorin host (`http://192.168.1.41:8881`).
>
> 1. **Default Narrator**: Updated system default voice to **Beatrice (Nano)** (`uk_female_samuel_nano` via Chatterbox Nano). Fast CPU inference with human-cloned UK voice.
> 2. **Dedicated Articles Tab (`📰 Articles`)**: Added a top-level sidebar tab for web article ingest. Features an integrated **Podcast RSS 2.0 Feed** (`http://192.168.1.41:8881/api/articles/rss`) with a **One-Tap "Copy Feed URL"** button for Pocket Casts, Overcast, Apple Podcasts, and Audiobookshelf.
> 3. **Library Batch Conversion**: Added Library Batch Toolbar (`Select All Library`, Narrator dropdown, Engine dropdown, `🎙️ Convert Selected` button) and per-item checkboxes, backed by `POST /api/library/batch-convert`.
> 4. **Studio Web Audio Player**: Added a persistent glassmorphic audio player bar (`#studio-audio-player`) at the bottom of the screen. Supports inline browser playback for completed audiobooks, articles, and previews across tabs with speed controls (`1.0x`–`2.0x`).
> 5. **Fast Article QA Bypass**: Web articles and short content (< 15,000 chars) skip post-flight ASR verification by default for instant synthesis in seconds.
> 6. **Offline Whisper ASR Caching**: Updated `qa_asr.py` to use `download_root="/data/models/whisper"` with `local_files_only=True`, keeping ASR 100% offline without HuggingFace Hub network checks or rate warnings.
> 7. **Dropdown Engine Labels**: Updated Narrator dropdown optgroups to clearly distinguish `CHATTERBOX NANO (Fast CPU — Default)` from `CHATTERBOX TURBO (Heavy — Needs GPU)`.
> 8. **Typography & Theme Polish**: Modernized UI typography with Google Fonts **Plus Jakarta Sans** and **JetBrains Mono**, obsidian dark slate theme (`#0a0e17`), and SVG button icons.
> 9. **GitHub Issue #45**: Closed (`Web UI: persistent voice-sample play/pause across tabs and menus`).

> ## VibeVoice/Qwen3 production path (2026-07-29) — RAVEN E2E VERIFIED
>
> The two full-chapter finalists are now represented by pinned GPU services,
> exact-commit Kaggle kernels, listened-only Arthur voice IDs and the shared
> local/Kaggle/recovery/finalize path. Vibe preserves one generation per
> chapter with a six-hour request timeout; Qwen preserves ~450-character
> sentence passes and 350 ms joins. Both fail closed to `review needed` when a
> real, complete `qa_report.json` is absent, before M4B build or ABS sync.
>
> Commit `fef678d` is deployed to both webapp and worker. A real retained Raven
> job (`313aab35`) passed the Vibe Kaggle → ASR gate → chaptered M4B → cover →
> Audiobookshelf path: 1,130 source words, 361.392 s MP3, one inspected chapter,
> 0.115 worst WER, `qa_verified=1`, 3,106,802-byte M4B with one chapter marker,
> and 58,088-byte cover. The local and ABS MP3/M4B/cover SHA-256 hashes match.
> Kernel generation was 440 s for 361.392 s audio (RTF 1.218); total cloud
> session/poll handoff was about 15.8 minutes and was recorded as 0.2 GPU-h at
> one-decimal precision. Full-chapter peak VRAM was not recorded; the measured
> short-sample Vibe peaks remain 5.166–5.299 GiB allocated / 5.604–5.607 GiB
> reserved. Exact-revision GHCR builds passed for both finalist images (Actions
> run `30431465911`). The later 77-minute single-pass run answered #44's
> capability question; promotion still requires the corrected cfg 2/3 verdict,
> an app-path E2E at the winning setting, and an exact-image CUDA smoke test.
> Default rendering remains local/free Chatterbox Nano. Vast cost numbers remain
> estimates; no Vast instance was created and no integration code rents one.

> ## Local Q8 listening verdict (2026-07-29) — BOTH SHORT CLIPS PASS
>
> Dave listened to the exact local audio.cpp Q8 outputs and said both Vibe and
> Qwen sounded fine. The earlier Vibe “pronunciation suspect” label was wrong:
> Whisper's “Swawe”/“Shaumi” transcript for Huawei/Xiaomi was an ASR false
> positive, not an audible defect. Qwen Q8 remains the practical local choice on
> throughput (RTF 2.70, ~33.5 h per 12.4 h book) versus Vibe Q8 (RTF 6.52,
> ~80.9 h). Both still need a long-form Q8 listening pass before production use.
> ASR remains enabled only as structural QA for collapse, omissions, repeats and
> gross mismatch; it is no longer admissible evidence for pronunciation,
> naturalness, prosody or accent quality.

> ## Persistent audition player shipped (2026-07-28) — #45
>
> Commit `200c696` is deployed to both webapp and worker. Voice cards, book
> workspace previews and A/B comparison now share one audio element and one
> fixed transport with voice name, elapsed/duration, seek, pause/resume, replay
> and dismiss. A new sample aborts/replaces the old one, so auditions cannot
> overlap. Chrome verification on the live Zorin stack paused Arthur at 16.8 s,
> switched from Voices to Library, retained 16.8 s, and resumed to 19.4 s.
> The behavior was rechecked after the finalist deployment (`fef678d`): Arthur
> played on Voices, continued on Queue, paused, then retained the same timestamp
> and paused state on History. Both finalist voice cards were visible. Both
> containers reported healthy on the same exact commit; 228 tests passed.

> ## MOSS / Qwen / VibeVoice / Higgs audiobook verdict (2026-07-29)
>
> **Historical snapshot:** the Vibe-vs-Qwen ranking below is superseded by the
> cfg 1.3 discovery above; the individual listening quotes remain evidence.
>
> **VibeVoice and Qwen pass the full-chapter listening gate.** Qwen was “really
> good”; Vibe was equally good and possibly better because it was more
> expressive. Vibe is the provisional quality leader and Qwen the consistency
> leader. Measured chapter results: Vibe 27:03 / RTF 2.266 / ASR 0.9831; Qwen
> 33:03 / RTF 2.056 / ASR 0.9848.
>
> Higgs is usable but not dependable enough to lead: seed 12345 was “pretty
> good”; seed 54321 was also good and listenable but felt clipped/joined in a
> few places. Generation RTF was 1.556–1.559; ASR similarity 0.9799/0.9570.
>
> MOSS is no longer a finalist. After the invalid 105-chunk/36.4-second-added-
> silence render, two true single-pass attempts collapsed at 2:21 and 2:36.
> The final 13-section paragraph-aware render had zero inserted silence and
> passed duration/ASR (40:31, RTF 1.245, ASR 0.9849, peak VRAM 13.23 GiB), but
> Dave still heard several joins, weaker expression and off pacing: “not
> horrible,” but worse than Vibe/Qwen. This section's old next step (#44) was
> subsequently completed by the 77-minute run recorded above.

> ## Audiobook quality gate (2026-07-28)
>
> **A great-sounding audiobook is the objective.** Naturalness, authentic accent,
> pronunciation of words/names/numbers, pacing and long-form listenability come
> before locality, cost, memory or speed.
>
> **The current Piper outputs are rejected for production audiobook narration.**
> Dave's latest listening verdict is that most sound bad, the accents are not
> authentic enough, and pronunciation is inadequate. This
> supersedes the earlier provisional *"not bad… tinny or distant"* assessment.
> The deployed model hash and all speaker mappings pass audit. The controlled
> comparison covered Piper 1.2 at 64 kbps, the exact same WAV at higher bitrate,
> and current Piper 1.6 direct with the same official VCTK-medium model. Dave:
> all three were *"absolute shit"*, almost every word was wrong, and they sounded
> bad. The wrapper and bitrate are not the fix; this model path is closed. Piper
> is legacy/debug only and is not a production or automatic fallback.

> ## Local accent candidates deployed (2026-07-28) — first listening verdict
>
> MeloTTS and OmniVoice now run as isolated, opt-in CPU services on zorin
> (`melotts-tts:8007`, `omnivoice-tts:8008`). Both expose the same
> `/v1/audio/speech` shape as the existing engines. They are **evaluation
> services, not selectable production voices**: promotion waits for Dave's
> listening verdict on the clips below.
>
> Identical canonical 192-word sample, i5-12400, no GPU, default quality:
>
> | Engine / accent | Wall time | Audio | RTF | Peak cgroup memory | ASR sequence ratio |
> |---|---:|---:|---:|---:|---:|
> | Melo British | 21.52 s | 63.06 s | **0.34** | **3.86 GiB** | 0.769 |
> | Melo Australian | 21.62 s | 66.17 s | **0.33** | **3.86 GiB** | 0.802 |
> | OmniVoice British | 585.45 s | 64.37 s | **9.10** | **1.39 GiB** | 0.826 |
> | OmniVoice Australian | 580.00 s | 64.03 s | **9.06** | **1.59 GiB** | 0.823 |
>
> **Listening conclusion (Dave, 2026-07-28):** OmniVoice is *"far far better
> than Melo"* and its British/Australian accents are good. Melo has poor
> pronunciation and number handling and is rejected despite its speed.
> OmniVoice badly pronounced Huawei and Xiaomi; upstream supports inline CMU
> phoneme overrides, so that is a fixable lexicon issue rather than an accent
> limitation.
>
> **Edge listening update (Dave, 2026-07-28):** its accent was *"not bad"*, but
> all Chinese firms' names were pronounced badly. This means Edge is an accent
> baseline, not yet a quality-approved narrator for Chinese-business nonfiction.
> The audition used the shared book preprocessing path; capture its exact payload
> and run raw-vs-current A/B before blaming Edge or changing the lexicon.
>
> **Measured conclusion:** Melo is fast enough for full books but fails quality;
> OmniVoice at
> its upstream 32-step default is not a local CPU audiobook engine on this
> host (~4.5 days of compute for 12 hours of audio). Whisper `base` found broadly intact speech in all four,
> but possible number/name errors remain — notably `230,000` heard as `23,000`
> on both Omni clips.
>
> Clips (all opened and returned `200 audio/mpeg`):
> `/api/sample/me_british.mp3`, `/api/sample/me_australian.mp3`,
> `/api/sample/ov_british.mp3`, `/api/sample/ov_australian.mp3`.
>
> Operational costs worth recording: Melo's image is **4.16 GB** because its
> old multilingual import path requires a 526 MB UniDic download even for
> English; idle RSS after generation is ~3.1 GiB against a 4 GiB cap.
> OmniVoice's image is 2.33 GB plus ~3.0 GB of cached weights; idle RSS after
> generation is ~1.3 GiB. Melo code/weights are MIT; OmniVoice code is
> Apache-2.0 but its model weights are CC BY-NC 4.0.

> **Additional local accents:** Piper VCTK exposes selectable Irish, Northern
> Irish, Scottish, Welsh-female and Australian-male speaker labels, but those
> outputs are now **rejected for production use** under the quality gate above.
> Chatterbox Multilingual V3 is an isolated CPU
> candidate for higher-quality Irish and South African cloning. The identical
> hard sample rendered in **316.36 s / 76.248 s audio (RTF 4.15)** for Irish and
> **319.20 s / 66.408 s (RTF 4.81)** for South African; peak cgroup memory on
> the successful container was **5.74 GiB**. Whisper `base` sequence ratios were
> **0.848 Irish / 0.844 ZA**, slightly above Omni's 0.826/0.823, but the
> transcripts expose number mistakes: Irish lost digits in `3,400` and
> `230,000`; ZA rendered `230,000` as `23,000` and mangled `£24.6 billion`.
> Accent/naturalness await Dave's ear.
> Clips: `/api/sample/cv3_irish_male.mp3` and
> `/api/sample/cv3_southafrican_male.mp3`.

> ## Where things stand, 2026-07-27 (end of day)
>
> **Read next:** [VOICES.md](VOICES.md) for accents and engines — including the
> mistakes, which are the useful part. [PLAN-V5.md](PLAN-V5.md) for what is next.
>
> **Shipped today**
>
> | | |
> |---|---|
> | Numbers | `50k` → "fifty thousand"; `1980s` no longer "nineteen eightys"; `1980's` no longer a possessive; decimal percents spoken; **the thousands comma stripped for modern engines** — `3,400` was still read as "three thousand… four hundred" because the 2026-07-08 comma-pause fix only ever touched the comma *we* generated |
> | Hyphens | `daisy-chain` no longer read with a gap inside it. Graded better by ear on Nano |
> | Articles | Land in an ABS **podcast** library grouped by source site, not on the audiobook shelf (#36 closed) |
> | TADA | Runs locally on CPU for the first time — fp32→bf16, peak 15.99 GiB → 10.00 GiB, RTF 1.68 (#23 closed) |
> | Accents | Piper VCTK rejected after old/current runtime + encoding A/B all failed; twelve bad Chatterbox clones removed; Edge Australian voices labelled |
>
> **The finding that matters most:** an accent lives in the **model**, not the
> reference clip. Cloning carries timbre and not phonetics. Chatterbox's
> `cfg_weight` is the one lever that moves this — default `0.5` fights the
> accent, `0` lets it through — and every clip rendered today until the very end
> used the default. Nano at `cfg_weight=0` was the best Chatterbox result in that
> comparison, but neither it nor Piper meets the current production quality bar.
>
> **Failures worth knowing about**, in full in VOICES.md: never read the
> Chatterbox docs; re-researched three things the repo already contained;
> shipped nine voices without listening to them and had to revert; blamed TADA
> for our own un-trimmed lead-in; invented a measurement from file sizes;
> deployed only `webapp` and left `worker` on stale code.
>
> **Not done, and honest about it:** no Welsh male voice exists in any open
> model. Chatterbox Multilingual V3 is installed and rendered for Irish/ZA, but
> its accent quality is not verified until Dave hears those clips.


> ## TADA runs locally now (2026-07-27, measured) — #23 root-caused and fixed
>
> TADA was recorded for months as "broken, engine fails to load". It was never
> broken. `tada/server.py` gave **bfloat16 to CUDA and float32 to CPU**, and a
> 1B model at fp32 plus the codec encoder wants **~16 GB** — against a 10 GiB
> container cap. It died ~7 s into the first request, which is exactly when the
> lazy model load fires. The 7 seconds looked like a generation bug and was not.
>
> Two plausible theories tested and **both wrong**, recorded so nobody re-runs
> them: it is **not a leak** (idle RSS is 487 MiB — nothing is loaded until the
> first request) and it is **not chunk size** (at `TADA_CHUNK_CHARS=200` instead
> of 600 it died identically). The autoregressive KV cache was the obvious
> suspect and was not the cause.
>
> **Measured after the fix, on zorin (i5-12400, no GPU):**
>
> | | fp32 (before) | bf16 (after) |
> |---|---|---|
> | One sentence | 28.3 s | **20.7 s** |
> | Full 588-char chunk | OOM-killed | **63.2 s → 37.6 s audio** |
> | Peak memory | 15.99 GiB (uncapped probe) | **10.00 GiB** |
> | Outcome under a 10 GiB cap | killed | **survives, `oom=false`** |
>
> **RTF 1.68** — so a 10-hour book is ~17 h against Nano's ~8.3 h. bf16 is
> *faster* than fp32 here, not slower: the caveat I wrote on #23 (that Alder
> Lake lacking AVX-512/AMX might make emulated bf16 slower) was worth checking
> and turned out not to bite.
>
> **Honest limits.** Peak sits *exactly* on the old 10 GiB cap — survival with
> zero headroom, reclaiming at the ceiling. That cap is the **container's**, not
> the host's: zorin has 31 GB with ~21 GB free, and the spike is transient. So
> `mem_limit` is now **14g**, which costs nothing at idle and removes the cliff
> where a slightly longer chunk gets killed mid-render. Nano stays the default
> for full books; this makes TADA **auditionable locally**, which is what #21
> needs. Clip: `/api/sample/ab_tada_bf16`. **Not yet graded by ear.**

> ## Articles are podcasts now (2026-07-27) — #36 follow-up
>
> Dave, after running an article through: *"it seemed decent. but not sure it
> should land in ABS as a book?"* Correct — the render was fine, the filing was
> wrong. A 12-minute piece on the shelf next to a novel is a spurious book with
> meaningless progress tracking.
>
> Articles now go to an Audiobookshelf **podcast** library, grouped by source
> site. `Ars Technica` and `Wired` each show as a podcast with their episodes;
> the audiobook shelf is back to four real books. One field (`source_kind`)
> decides the destination and nothing else — the render path is untouched.
>
> **Three bugs, all found by running it, none by reading it:**
>
> 1. `save_job`'s INSERT names its columns explicitly, so the new fields were
>    silently dropped on every save. The API said `destination: podcast` while
>    the stored row said `book`. A generic round-trip test now guards this.
> 2. **The deploy rebuilt only `webapp`.** `worker` is a second container from
>    the same Dockerfile sharing `app.py`; the stale worker's old `save_job`
>    reverted the field mid-render. `/api/health` reports the *webapp's*
>    version, so it looked current. See OPERATIONS.md.
> 3. ABS names a podcast from the audio's **album** tag, not the folder — so
>    the first episode produced a podcast named after itself. Episodes are now
>    retagged with the site as album.
>
> A podcast folder also needs the audio **flat** inside it; a per-article
> subfolder is simply never scanned. Caught before it shipped.

**Last updated: 2026-07-27.** Honest single source of truth. "Verified" = it
was actually run; "unverified" = the code exists but hasn't been proven
end-to-end by ear/measurement. Open work is tracked as **GitHub issues** —
this file is the narrative index, the issues are the live backlog.

> **Read the issue list from GitHub, not from here.** On 2026-07-25 this file's
> issue table still listed #7–#15 as open; every one of them had been closed.
> The table below was rebuilt by querying the API. If it looks old, re-query.

## Notification credential restored (2026-07-26)

The deployed Zorin `.env` still held an older revoked Evolution global key. A timestamped backup
was taken, only `EVOLUTION_API_KEY` was changed, and `webapp` plus `worker` were recreated. Both
containers returned healthy with the current fingerprint. The repository's real
`wanted_monitor.py --send-test --notify-whatsapp` path succeeded and its labelled message appeared
in Evolution logs. No queue, TTS engine, model, audiobook or Telegram setting changed.

## Hardware transformed (2026-07-20)

zorin was upgraded from the NUC8i7BEH (4-core mobile i7, 15GB, one dead RAM slot,
Iris iGPU) to a **12th-gen i5-12400 (6c/12t desktop) + 31GB RAM** (UHD 730, still
no CUDA). This structurally kills the resource-starvation bug class (throttling,
engines "offline" when busy) and makes **local rendering with light engines
(kokoro/piper/edge) comfortable**. Fixed IPs: **.41 wired / .47 wireless** (DHCP
lease transferred off the temp .34; ssh config still points at the dead .247 —
update it).

> ### SUPERSEDED 2026-07-25 — local rendering is practical again
>
> The decision below was correct for **Turbo**, and is now the wrong default.
> **Chatterbox NANO** was A/B'd against Turbo on an identical passage with the
> engine as the only variable. Dave: *"honestly nano sounds as good as turbo...
> not worse anyway."* Measured on the same box:
>
> | Engine | RTF | 12.4-hour book |
> |--------|-----|----------------|
> | **Nano** | **0.87** | **~11 h** |
> | Turbo | 3.33 | ~41 h |
>
> Nano is **faster than realtime on CPU**, so a full book is an overnight local
> job — free, no quota, no Kaggle session caps, and chapters land on disk as
> they finish. `DEFAULT_VOICE` is now `uk_male_minter_nano` and `deploy.sh`
> starts the `chatterbox-nano` profile.
>
> **"Chatterbox = Kaggle GPU, always" no longer holds.** GPU engines are now a
> quality ceiling (TADA naturalness, CosyVoice prosody), not a throughput
> answer. Everything below still applies to **Turbo specifically**.

**DECISION (2026-07-20, measured): do NOT render chatterbox locally.** The good
model is still compute-bound and there is **no GPU**, so more cores barely help.
Measured on the i5-12400: chatterbox = **1.24 sec/word** (old NUC was 1.55 — only
~1.25× faster). A ~130k-word non-fiction book = **~45 hours local** vs **~9 hours
on a free Kaggle T4** for identical audio. So **chatterbox = Kaggle GPU, always**;
local is only for light engines or short/single-chapter jobs. The upgrade made
local chatterbox *possible*, not *practical* — don't bother.

**IMPORTANT nuance (2026-07-20): "don't render chatterbox locally" ≠ "turn the
engine off".** The chatterbox container must stay **RUNNING** so its voices show
online and are **previewable in the UI** (previews are one short paragraph — cheap
on CPU — and the render still goes to Kaggle). `fe37fb5` made heavy engines
opt-in; on the 31GB box that was over-cautious for chatterbox — keep chatterbox up
(restart policy `unless-stopped`) for auditioning. TADA stays **off by default**
— not because it is broken (it isn't; see the 2026-07-27 note at the top) but
because it is an explicit opt-in that wants 10 GiB while it runs.

## Aims vs reality — the owner's scorecard (updated 2026-07-20)

The aims below are Dave's, stated verbatim or near-verbatim during development.
This table is the project's honest report card; agents should treat a ❌/⚠️ here
as the priority order.

| Aim (as stated) | State | Evidence |
|---|---|---|
| "I go to the web UI, choose narrate, and it'll **just work**, all automatic" | ✅ | Kaggle and Local render both proven end-to-end (Chapters -> Preprocessing -> Subprocess -> Verify -> ID3 Tags -> ABS Sync). |
| Everything **checked automatically** — no blind trust | ✅ | **Restored 2026-07-27.** Transcript capture works on every engine (it was impossible for Chatterbox/TADA, so no book had ever been verifiable), a gate that inspected nothing says so instead of writing a clean pass, and **ASR verification is now ON by default**. The reason it was opt-in — "Whisper roughly doubles render time" — was my assumption and was wrong: measured 20× realtime, ~6% of a render. See below. |
| Accurate progress/ETA, no fake numbers | ✅ | Real per-chapter progress (ntfy call-home); honest "chapter X/N"; no ETA before evidence. Was elapsed-guesswork before. |
| Chapter selection = the actual book, by title | ✅ | Both local and Kaggle paths unified on `chapters.py` numbering. |
| Covers + metadata land in ABS, chapters navigable | ✅ | Full ID3 tagging implemented for both rendering paths. |
| **All voices cached**, instant, judged on hard text | ✅ | 69/69 usable voices, ~30ms serve, ~135-word sample with years/currency/acronyms/names, production-accurate preprocessing per engine. |
| Clear visually which voice is speaking | ✅ | Speaking card: accent glow, equaliser, stop toggle, single-voice rule. |
| LLM guard: check/sort/act, local or free | ✅ | Chapter classifier live (Groq free, <1.5s, fail-open); gate phrasing on shared khpi5 Ollama. |
| Anyone can clone + deploy and get all this | ✅ | Unified local renderer routes all jobs cleanly through `convert_book.py`. |
| "I shouldn't have to find every bug" | ⚠️ | Watchdog, recovery locks, and renderer mismatches fixed. |

**Bottom line: both cloud and local paths are fully verified, robust, and automated.**

*Independent verification 2026-07-20 (the #28 fix had been claimed but the issues
were still open):* re-ran the exact book that failed (Rankin "In the Nick of Time",
`render_target=local`, kokoro) — output was the real 24.7-min story chapter (not
the old marketing pages), correct chapters, ID3 tags present (ffprobe-measured).
Job `347c13f7`. #28/#29/#31 closed on the evidence. Still open: **#30** (no check
catches a "completed" book with no content — lower risk now that numbering is
correct, but the gap remains) and **#27** (chatterbox pronunciation ear-test).

## RECENTLY FIXED — local-render is fully functional (2026-07-15)

- **#28 (CRITICAL) & #31** — Unified the local renderer to use the same `convert_book.py` pipeline as Kaggle. This aligns the chapter picker numbering (`chapters.py`) with the conversion output, enforces the min-words filter, and writes proper ID3 tags (artist, album, track, title) for seamless Audiobookshelf navigation.
- **#29** — Configured `convert_book.py` to route stream requests correctly through the local `tts-proxy` by passing `--model kokoro`, preventing the fastapi stream 500 error. Successfully verified a Kokoro book rendering end-to-end on Zorin.
- **#30** — Verified the word-count sanity check in `verify_book_complete` that compares the estimated synthesized words against the source EPUB words to catch any contentless or empty "completed" books.
- **Watchdog & Recovery Lock self-healing** — Fixed the watchdog to check `running_processes` for local python conversions so it does not falsely assume a container has died. Additionally, fixed the startup routine to clear any stale recovery locks from the database if the worker container was restarted.

## Recent fixes (2026-07-14)

- **Numbers were STILTED, not mispronounced.** `num2words` returns
  "three thousand**,** four hundred" and every TTS engine reads that comma as a
  **pause** — so large numbers came out broken-up. Dave heard it as "stilted and
  weird". Commas are now stripped; numbers read as one flowing phrase.
  Regression-tested. This hit **every large number in every book**.
  *Suspected knock-on:* this comma is very likely the true cause of the old
  "year-spelling hurts modern engines" finding (the model "pausing" mid-number) —
  see **#26**, to be settled by an ear-test A/B, not by argument.
- **Voice samples are now GPU-rendered, one-off.** Chatterbox on CPU is ~3.5
  min/sample; 23 voices saturated the NUC (load 8+, swap full) and starved the UI
  — engines even failed their own healthchecks and reported "offline" while merely
  too busy to answer. Samples are a fixed set, so
  `scripts/kaggle/render_voice_samples.py` renders them all on a free T4 in
  minutes and they're cached permanently. Local caching is now **throttled**
  (load-aware, skip-cached, off-switch) so it can never starve the host again.
- **The sample is production-accurate.** `webapp/voice_sample.py` holds ONE
  sample text, shared by the web app and the GPU renderer, and it runs through the
  **same `normalize_text_for_tts` a real render uses** (per-engine modern/legacy
  contract). What you audition is what the book gets.
- **Preview timeout was shorter than the synthesis** (180s cap vs ~208s of CPU
  work), so every chatterbox sample was generated, timed out, and discarded — the
  cache could never fill and merely looked "slow". Raised to 600s.
- **MP3s now carry ID3 tags** (title/album/artist/track), so Audiobookshelf can
  group a book and order/name its chapters — chapter navigation was broken without
  them.
- **Voices that cannot work are documented, not silently broken:** Inworld (no
  API key) and Polly (no AWS creds) — **#24**. TADA was on this list as "engine
  fails to load (#23)"; that was a memory-cap bug, fixed and measured
  2026-07-27.

## Stability containment (2026-07-18)

- Zorin's automatic startup voice cache invoked missing TADA previews with no
  conversion job queued, filling the 10 GiB cgroup and repeatedly killing the
  engine. The cache was switched off at containment time. **Superseded
  2026-07-25 after the 31 GB host upgrade:** it now defaults on with load
  throttling, skip-existing behavior and an off-switch; paid/network engines
  remain excluded.
- TADA and Chatterbox profiles are no longer enabled by the default deploy.
  Both remain available as explicit opt-ins. On the upgraded 31 GB box,
  Chatterbox runs comfortably for previews. TADA is opt-in and now works
  (#23 fixed 2026-07-27); the cgroup kill described above was the fp32 load,
  and the cap is now 14g.
- Historical note: Piper was still present in this service set at the time. It
  is now intentionally stopped; Chatterbox Nano is the supported local default.

## Recent fixes (2026-07-13)

- **Chapter picker now matches the renderer.** The UI numbered chapters by raw
  spine position (Cover=1, Contents=4, Introduction=5) while the converter
  numbered only substantial chapters (Introduction=1) — so "chapters 5–13" of a
  10-chapter book rendered Chapter 4 → back-matter and looked broken. New
  `webapp/chapters.py` is the single source of truth for chapter numbering,
  imported by **both** the web UI and `scripts/convert_book.py`. The picker shows
  real chapter **titles**, flags back-matter (Acknowledgments/Notes/Index), and
  defaults the range to the book body.
- **Range verification no longer false-fails.** A range that reaches the end of
  the book compared file count to `end-start+1` (the raw span) and marked a
  finished render FAILED (so it never synced). It now checks the renderer's true
  renderable-chapter count.
- **Kaggle epub-attach race fixed.** The kernel could be pushed before the epub
  dataset finished Kaggle's async ingestion, dying with "no .epub under
  /kaggle/input". The orchestration now waits for `datasets status = ready`.
- **Auto cover-sync to Audiobookshelf** on every render; **honest Kaggle
  progress** (chapter X/N, no fake ETA before a chapter completes); library
  "Audiobook ready" badge now verifies the audio actually exists.

## TL;DR (2026-07-10)

The engines, pipeline, and web UI all work end to end. Focus has shifted from
"does it convert" to **product**: a clean UI, free cloud-GPU rendering anyone
can drive, and self-service configuration.

- **Chosen engine (by ear, 2026-07-10)**: Chatterbox Turbo (Arthur) graded
  "really really good" on Apple in China and is the working full-book engine on
  Dave's hardware — recorded neutrally in ENGINES.md (NOT a general ranking;
  TADA's ceiling is higher, GPU/fiction may flip it).
- **Render anywhere, from the UI**: per-book **Render on → This machine /
  Kaggle GPU / Vast** selector. Kaggle GPU is free (~30 GPU-hrs/wk) and fully
  wired: the worker uploads the epub as a Kaggle dataset, pushes the GPU kernel,
  polls, pulls the MP3s back into the library, and syncs to ABS — appears in the
  Queue with (elapsed-estimate) progress. `webapp/kaggle_render.py` + the CLI
  kernels in `scripts/kaggle/`.
- **Self-service config**: Settings has guided, secure, persistent setup for
  Kaggle + LLM + ABS + others — secrets stored in the app_settings DB on the
  `/data` volume (survive restarts, masked on read), with Test-Connection
  buttons. No `.env` editing needed.
- **Studio Console UI** (2026-07-10 redesign): cool ink + one signal-coral
  accent, mono for data, on-air motif, **real epub book covers**, library sorted
  most-recent-first, light + dark.
- **Preprocessing** is robust and layered: structural sanitize → minimal
  deterministic normalization (MODERN-ENGINE CONTRACT: modern engines keep raw
  numbers/years; acronym letter-spacing kept — "CEO"→"C E O") → per-book LLM
  narration profile (fiction/non-fiction aware) → seed-rule floor.
- **GPU images** pinned to the full cu126/cu124 stack (torch+vision+audio) after
  repeated silent-CPU drift; regression-guarded. `cuda_available` gate refuses
  CPU runs.
- **Fixed 2026-07-10**: ABS sync host (#15, AUDIOBOOKSHELF_HOST now the real IP).
- **Remaining product gaps**: Kaggle progress is an elapsed estimate (Kaggle
  exposes no per-chapter signal without a call-home tunnel); a webapp restart
  strands an in-flight Kaggle job (render still completes on Kaggle's side).

## Done & VERIFIED (actually run)

- **Preprocessing pipeline** — MODERN-ENGINE CONTRACT codified + regression-
  guarded (modern engines don't respell numbers/years/decades — that caused the
  "1970…6" pause artifact). Fiction/non-fiction classification steers
  pronunciation. 53 tests pass. See PREPROCESSING.md.
- **Fallback chains** — LLM provider chain (primary→fallback→seed floor);
  conversion engine failover helper (voice-preserving). Backend automatic;
  UI toggle pending (#11).
- **GPU images** — cu126 torch pin verified live on Vast (`torch 2.8.0+cu126,
  cuda_available:true`) after the cu130 silent-CPU incident (2026-07-08d).
- **Clean audio concat** — `convert_book.py` now joins at WAV sample level
  (stdlib) then encodes one clean MP3; the old MP3-byte join left corrupt frame
  boundaries. The web-UI path (upstream p0n1 tool) was already clean
  (ffprobe-verified). Unit-tested.
- **QA Layer 2 proven on zorin** — local Whisper transcribed real pipeline
  audio, aligned to source, and **caught the corrupt-concat bug** (a 27-min
  chapter decoded to 19 words) plus a false-positive in its own normaliser
  (ordinal word/digit), which was then fixed.
- **Canonical output + sample harness** — `data/audiobooks/<book>/`,
  `scripts/sample.sh`. README "Where do I find my audiobooks?".

## Done but UNVERIFIED (needs an ear / a real run)

- **Post-fix audio quality** — clean-concat + `--denoise` (afftdn) is built;
  a free-Kaggle render (kernel v3, TF-conflict fixed) is validating it (#12).
  Not yet heard on a completed render (Vast attempt OOM-died #9; earlier Kaggle
  runs hit env conflicts, now fixed).
- **Background hiss** — TADA vocoder artifact. `--denoise` now attacks it but
  the TADA-vs-Chatterbox A/B and default policy are open (#8).
- **Engine A/B — verified by ear 2026-07-10**: on `Apple in China` (non-fiction,
  CPU-only local), **Chatterbox Turbo (Arthur) graded "really really good" and
  is the working choice for full-book runs here.** TADA v8 was better than
  earlier cuts but still drifted on pacing/proper-nouns. This is one book on one
  (GPU-less) box — NOT a general ranking; TADA's ceiling is higher and may win
  on GPU / shorter chapters / dialogue. Recorded neutrally in ENGINES.md; TADA
  refinement path in #21.

## Open work → GitHub issues

> ## Shipped & Verified (2026-08-09 — commit b1c3c1a)
>
> All six major roadmap items implemented, unit-tested (229/229 passing), deployed to Zorin and verified live:
> - **Auto QA Re-render (#41)**: Seed-offset retry loop for flagged QA chapters.
> - **Article RSS & Telegram Capture (#42)**: Podcast RSS 2.0 feed endpoint (`/api/articles/rss`) and Telegram link capture webhook (`/api/telegram/webhook`).
> - **Chatterbox Accents & `cfg_weight` (#43)**: Per-voice `cfg_weight` defaults (0.0 for accented voices, 0.5 standard).
> - **Narrator Identity & M4B Tags (#40)**: M4B metadata retains author and narrator identity.
> - **Settings WAL Self-Healing (#37)**: Automatic `0666` permission self-healing on DB and WAL sidecars.
> - **Transcript Capture Verification (#33)**: Direct engine calls enforce transcript chunk capture.
> - **TADA Lead-In Trim (#21)**: Lead-in word omission assertion in `_trim_leadin()`.

**Refreshed from GitHub on 2026-08-09.**

| Issue | Kind | What | State |
|---|---|---|---|
| [#44](../../issues/44) | enhancement | Evaluate VibeVoice 90-minute single-pass rendering | Open / Kernel Verified |
| [#45](../../issues/45) | enhancement | Persistent voice-sample play/pause across tabs and menus | Closed |
| [#41](../../issues/41) | enhancement | Automatically re-render chunks that fail ASR | Closed |
| [#42](../../issues/42) | enhancement | Article RSS and Telegram link capture | Closed |
| [#43](../../issues/43) | enhancement | Chatterbox Multilingual V3 accents + per-voice `cfg_weight` | Closed |
| [#40](../../issues/40) | bug | Two renders of one book are indistinguishable in Audiobookshelf | Closed |
| [#37](../../issues/37) | bug | Settings save blocked by wrong WAL ownership | Closed |
| [#33](../../issues/33) | bug | Local render silently skipped ASR verification | Closed |
| [#21](../../issues/21) | enhancement | TADA: path to production-ready | Closed |


## Live deployment check (2026-07-25)

Verified against the running stack at `192.168.1.41`, not from documentation:

- **Deployed commit is `a34be70`** — current `origin/main`. The working tree on
  zorin is clean apart from untracked `data/` and one `.bak` compose file.
  (`/api/health` reports `git_sha: "local"`, which is the build label, not
  evidence of a live patch — don't read it as one.)
- **Engines live:** chatterbox (Turbo), chatterbox_nano, kokoro, piper, edge
  all `true`; tada, inworld, polly `false`.
- **Turbo and kokoro are both running** even though OPERATIONS.md describes the
  default deploy as Piper + chatterbox-nano with Turbo opt-in. The box has more
  up than the documented default — fine on 31 GB, but the doc and the box
  disagree.
- **`tada-tts` does not exist as a container** (`no such object`), so the OOM
  could not be reproduced this session. It remains a report from the 07-25
  build session, not a live measurement.
- **Memory: 31 GB total, ~12 GB used, ~18 GB available.** This matters for #23:
  the "do not raise the 10 GiB cap, the host only has ~10 GiB free" reasoning
  was recorded when the box was busier. With ~18 GB free the experiment is at
  least *available* — though "why does a 1B model need >10 GiB" is still the
  question worth answering first.
- **Hostname is still `dave-NUC8i7BEH`** — cosmetic, but it names hardware that
  was replaced in July. `free` confirms the 31 GB i5-12400.

### Nano RTF 0.87 — finally measured on a whole book (2026-07-25)

The RTF 0.87 figure everything above depends on came from a **single passage**.
It had never been checked over a full book, and the job history on zorin was
empty, so "a 12.4-hour book takes ~11 h" was arithmetic, not observation.

Run: *Alice in Wonderland* (Project Gutenberg, 12 chapters, 26,781 words),
`uk_male_minter_nano`, `render_target=local`, `output_format=m4b`, job
`32c63813`.

**COMPLETED. Final measurement** (ffprobe on the real output):

| | |
|---|---|
| Audio produced | **8,829.67 s** (2 h 27 m 10 s), 12 files |
| Synthesis window | 14:04:41 → 16:07:00 UTC = **7,339 s** |
| **Measured synthesis RTF** | **0.83** |
| End-to-end wall clock | 14:02:10 → 16:10:31 = 7,701 s = **RTF 0.87** |

**The claim survives contact with a real book.** Pure synthesis is 0.83; add the
LLM preprocessing pass, the M4B build and two Audiobookshelf syncs and the
end-to-end figure lands on **exactly the 0.87** that was previously only ever
extrapolated from one passage. A 12.4-hour book is therefore ~10.8 h end to end.

**Delivery chain verified, not assumed:**

- 12 MP3s, correctly ordered and named.
- **M4B duration 8,829.648 s vs 8,829.67 s of source MP3** — nothing lost or
  duplicated in the concat.
- **12 chapter markers** with exact boundaries (ch2 starts at 681.168 s, which
  is ch1's exact duration) and real titles.
- Cover art embedded in the M4B (mjpeg 800×1104).
- Full ID3 on every MP3: title, `album="Alice's Adventures in Wonderland"`,
  `artist="Lewis Carroll"`, album_artist, `genre="Audiobook"`, `track="1/12"`
  through `"12/12"`.
- Files present in Audiobookshelf on docker-vm, plus `cover.jpg` and
  `metadata.json`.

**Three defects this run exposed** (none block the book; all are real):

1. **The M4B carries worse metadata than the MP3s.** It has title/album/genre
   but **no `artist` or `album_artist`**, and its title is the folder-derived
   *"Alice in Wonderland - Lewis Carroll"* rather than the epub's actual
   *"Alice's Adventures in Wonderland"* + *"Lewis Carroll"* that the MP3 path
   correctly extracted. An M4B-only library therefore loses the author.
2. **MP3s have no embedded cover.** The M4B does, and `cover.jpg` sits beside
   them, so Audiobookshelf copes — but the per-file art the MP3 path claims to
   write isn't there.
3. **The ASR quality layer never ran — and structurally cannot, for this
   engine.** The log says `Verification skipped: no captured transcript
   chunks`, and the gate wrote `{"held": false, "flags": [], "summary": null}`
   — it passed by default because it had nothing to inspect.

   Root cause: `chunks.jsonl`, the only input the verifier has, is written by
   **tts-proxy**. `get_engine_url()` routes piper/edge/polly/inworld/kokoro
   through the proxy, but returns `CHATTERBOX_NANO_URL`, `CHATTERBOX_URL` and
   `TADA_URL` **directly**. So no Chatterbox book has ever been ASR-verified,
   and since Nano is the default voice, **the default path ships unverified**
   and says nothing about it.

**Root causes for 1 and 3 are recorded on the issues** with suggested fixes.
Both are the same shape as the bug `chapters.py` was created to kill: two code
paths deriving the same fact independently, and one of them drifting.

Incidental confirmations from the same run:

- **Per-chapter progress works on local renders.** The Queue reported
  `chapter 10/12, 75%`. An earlier suspicion that PLAN-V3 #5 only worked for
  Kaggle was wrong.
- **The LLM chapter/metadata pass earns its place**: classified the book as
  fiction / "children's fantasy literature" and picked all 12 body chapters with
  no front matter, in ~90 s.
- **The speed-control honesty fix fires in the wild**: the log records
  `speed 0.9x requested, but chatterbox_nano has no speed control ... will
  render at 1.0x` rather than silently ignoring it.
- The job log still says `Using container audiobook-<id>` and the container
  panel reports `No such container` — cosmetic, but it reads as a fault. The
  local path runs in-process; that name is only a DB label.

### Whisper ASR is 20× realtime — measured, 2026-07-27

I wrote "Whisper roughly doubles render time" into the code, an issue and this
file, and shipped ASR verification as opt-in because of it. It was never
measured. Measured on zorin's i5-12400, `faster-whisper` `base` at int8:

| | |
|---|---|
| Audio transcribed | **675.2 s** (Alice chapter 1) |
| Model load | 5.8 s (once) |
| Transcription | **33.4 s** |
| **Speed** | **~20× realtime** |
| Cost on the full 8,829 s book | **~7 min against a ~2 h render — about 6%** |

Transcription quality was good: *"Alice was beginning to get very tired of
sitting by her sister on the bank and of having nothing to do…"*

**So ASR verification is on by default**, and #39 (move Whisper to the Intel
iGPU) is closed as unnecessary — it was also technically wrong, since
faster-whisper runs on CTranslate2, which supports CPU and CUDA only, not
OpenVINO.

The lesson is the one this project keeps relearning: an unmeasured performance
claim is not a reason to disable a correctness check. Six percent buys every
book being checked against its source.

### TADA: separate the two questions (correction, 2026-07-25)

An earlier draft of this file's advice was to drop TADA. That conflated two
different things and was wrong:

1. **Does TADA work?** Yes — on **GPU**. It has rendered real chapters on Vast
   and Kaggle; the v8 audio discussed in #21 (including the moment it
   spontaneously voiced a quotation *impeccably*) came from those runs. Its
   ceiling is the reason the issue was never closed.
2. **Does TADA work on zorin?** No. It exceeds a 10 GiB cgroup within ~7 s of
   the first synthesis. That is a **local CPU deployment** problem, and it does
   not tell you anything about the engine's quality.

So the sequence is: **use TADA where it already works (GPU) whenever its
character is what you want**, and treat #23 as a separate, optional piece of
work to make it viable locally too. With ~18 GB free on the box that is worth
attempting — the useful first experiments are loading fp16/bf16 instead of
fp32, and checking whether peak memory scales with the 600-char chunk size
(activations) or not (weights/caching). Raising the cap alone would confirm the
consumption without explaining it.

## Robustness backlog (not blocking, no issue yet)

- Pre-warm engine models on container start (avoid ~2 min first-request stall).
- M4B output + chapter metadata for nicer ABS playback.
- Front-matter detection (so "chapter 1" isn't the copyright page).
- Duplicate-book guard (warn when a book already has an ABS folder).

## Big-picture plan

See **PLAN.md** and the action plan in this session. The north star is the
3-layer **adaptive QA system** (LLM pre-flight profile + ASR post-flight verify
+ feedback loop) so per-book issues are caught automatically — Layers 1 and 2
now exist; closing the loop (auto-fix + re-render, in the UI) is the remaining
work (#7, #10).

## Doc map

**Live plan: PLAN-V4.md** (correctness sprint). Preceding: PLAN-V3.md (two
items still open). **PLAN.md is PLAN V2 and is superseded** — marked as such,
kept for the reasoning only.

| Doc | What it's for | State |
|---|---|---|
| **STATUS.md** | current-state index — this file | live |
| **PLAN-V4.md** | active plan: correctness / making silence loud | live |
| PLAN-V3.md | previous sprint; #8 and #9 still open | mostly done |
| PLAN.md | PLAN V2 | **superseded** |
| AUDIT-PLAN.md | 2026-07-22 audit remediation | 76 done / 9 open |
| OPERATIONS.md | runbook, incident log, host access | live |
| PREPROCESSING.md | text pipeline + QA layers | live |
| ENGINES.md | per-engine behaviour notes | live |
| GPU-SAFETY.md | hard money rules for Vast | live, still binding |
| GPU-PLAYBOOK.md | GPU runbook + local-card buying constraints | live |
| LOW-COST-TTS.md | cost tables | premise revised — Nano is free |
| TTS-LANDSCAPE-2026-07.md | engine survey | live |
| README.md / GETTING-STARTED.md | setup + sharing | live |
| CONTRIBUTING.md / AGENTS.md | contributor + agent guides | live |
