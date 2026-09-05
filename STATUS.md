# Project Status & Remaining Tasks

> ## 2026-09-05 Breakneck Removal & Deepgram Hyperion 3-Page Preview — COMPLETED
>
> 1. **Complete Removal of Prior Breakneck Audiobook**:
>    - Deleted the app-generated *Breakneck* library item (`9476cd4e-1ce3-43cf-91a6-01ab00e93669`) from Audiobookshelf via API (`DELETE /api/items/{id}`).
>    - Removed the entire directory `/opt/stacks/audiobookshelf/audiobooks/Dan Wang/Breakneck - Chinas Quest to Engineer the Future` and parent folder from `docker-vm`.
>    - Rescanned Audiobookshelf library (item count updated 24 → 23; zero *Breakneck* matches).
>    - Purged stale TOC cache from Zorin.
> 2. **Deepgram Hyperion 3-Page Previews Rendered & Verified**:
>    - Synthesized the first 3 print pages of both candidate opening sections of Dan Wang's *Breakneck* using Deepgram Aura-2 **Hyperion** (`deepgram_hyperion` / `aura-2-hyperion-en`):
>      - **Track 1 (Prologue / Introduction)**: Pages ix–xi (902 words, 6.24 mins, 95.0% Faster-Whisper ASR similarity).
>      - **Track 2 (First Proper Chapter)**: Chapter 1: Engineers vs. Lawyers, Pages 1–3 (861 words, 6.49 mins, 91.7% Faster-Whisper ASR similarity).
>    - Built a single chaptered M4B with embedded cover art: `Breakneck (Pages 1-3 Preview).m4b` (12.73 mins, 8.89 MB).
>    - Registered job `breaknec` in `jobs.db` with status `completed`. Available live in the web app player and history at `http://192.168.1.41:8881`.
>    - Verified all endpoints with `curl -I`: HTTP 200 OK for inline streaming and ZIP download.
>
> ## 2026-09-01 Calibre-Web Mobile UI, Zero Trust SSO & Auto-Deduplication — COMPLETED
>
> 1. **Mobile Navbar & Floating Action Button (FAB)**:
>    - Added prominent `⚡ Grab Book` badge button directly into the mobile header navbar next to search/profile.
>    - Added fixed `⚡ Grab Book` Floating Action Button (FAB) on mobile viewports for 1-tap capture anywhere across the library.
>    - Automated auto-hide of FAB when search modal opens.
> 2. **Cloudflare Zero Trust Header SSO (Passwordless Admin)**:
>    - Configured `Cf-Access-Authenticated-User-Email` reverse proxy header authentication for `david@davidmagnus.co.uk`.
>    - Automatic passwordless Admin authentication when accessing via Cloudflare Access.
> 3. **Strict Login Wall Enforced (`config_anonbrowse = 0`)**:
>    - Anonymous guest browsing disabled. Any private window or unauthenticated visitor is strictly redirected to `/login`.
>    - Cloudflare Access auto-authenticates `david@davidmagnus.co.uk` seamlessly as Admin.
> 4. **Audiobookshelf Domain SSO & Auto-Registration**:
>    - Configured Google/Cloudflare OpenID Connect on `abs.magnusfamily.co.uk` with `authOpenIDAutoRegister = true` and `authOpenIDMatchExistingBy = "email"`.
>    - Eliminated private IP Error 400 callback failures.
> 5. **1-Year Persistent Sessions ("Remember Me")**:
>    - Set `REMEMBER_COOKIE_DURATION` and `PERMANENT_SESSION_LIFETIME` to 365 days with automatic token refresh on each request.
> 6. **Library Auto-Deduplication & Smart Ingest Merging**:
>    - Cleared duplicate groups down to 190 unique titles using `highest_quality_format` strategy.
>    - Enabled `auto_ingest_automerge = 'ignore'` and `duplicate_auto_resolve_enabled = 1` for permanent silent background deduplication.
> 7. **Live Verification via Signed-in Edge (`playwright-edge` MCP)**:
>    - Validated live on Edge `library.magnusfamily.co.uk` and `abs.magnusfamily.co.uk`.

> ## 2026-08-30 1-Click Book Finder Widget & Gluetun VPN Gateway — COMPLETED
>
> 1. **Dedicated OpenBooks Gateway on Docker-VM (`openbooks-vpn`)**:
>    - Deployed `evanbuss/openbooks:latest` routed through **Gluetun (ProtonVPN WireGuard - Sweden)**.
>    - All IRC book queries and downloads exit via encrypted VPN with zero ISP/IP exposure.
>    - Eliminates single-user browser lockouts by using a dedicated service nick (`magnuslib`).
> 2. **1-Click Book Finder in Webapp & Calibre-Web**:
>    - Native search & grab widget on Home/Library tab connecting to `ws://192.168.1.113:6082/ws`.
>    - Standalone `/embed/bookfinder` widget modal embedded into Calibre-Web (`library.magnusfamily.co.uk`).
>    - One-click grab downloads directly to `/home/dave/docker-apps/calibre-web-automated/book-ingest/` and auto-indexes into Calibre and Audiobook Studio.
> 3. **Live Deepgram Credit Telemetry**:
>    - Added live credit remaining pill (`$194.61 USD`) to active converting job cards and topbar navigation across all screens.
> 4. **Calibre-Web Deduplication & MOBI Reader Support**:
>    - Cleaned and merged 13 duplicate book entries in Calibre database.
>    - Automated MOBI to EPUB conversion for in-browser reader support.

> ## 2026-08-30 Deepgram Cloud TTS Integration (Aura-2) — COMPLETED
>
> Integrated Deepgram as a first-class cloud TTS engine with UI API key management,
> `tts-proxy` routing, and pre-cached voice previews:
>
> 1. **Aura-2 Voices Registered & Pre-Cached**:
>    - **Orion** (`deepgram_orion` / `aura-2-orion-en`): Flagship American baritone narrator.
>    - **Orpheus** (`deepgram_orpheus` / `aura-2-orpheus-en`): Smooth, measured American male narrator.
>    - **Arcas** (`deepgram_arcas` / `aura-2-arcas-en`): Warm, conversational American male narrator.
>    - **Pandora** (`deepgram_pandora` / `aura-2-pandora-en`): Articulate British female narrator.
>    - **Hyperion** (`deepgram_hyperion` / `aura-2-hyperion-en`): Natural Australian male narrator.
> 2. **Aura-1 Rejection (Angus)**:
>    - Angus (`aura-angus-en`) evaluated on Chapter 1 of *Armed Struggle: The Story of the IRA* and rejected by Dave (monotone/flat delivery, no speed control). Excluded from the application.
> 3. **TTS Pipeline & Preprocessing**:
>    - Bound to the `'explicit'` text normalization contract (expanding years, currency, numbers, ordinals, and initialisms like `I.R.A.` and `G.P.O.`).
>    - Sentence/clause chunking ($\le 400$ chars) with narrative silence insertion (300 ms sentence, 650 ms paragraph).
> 4. **Settings & UI Integration**:
>    - `DEEPGRAM_API_KEY` setting field and live connectivity test button (`/api/settings/test_deepgram`) in **Settings → API Keys**.
>    - All 5 canonical previews rendered on `SAMPLE_TEXT` and persisted to `/data/previews/`.
> 5. **Tests**: All 339 unit & integration tests passing (`pytest tests/`).

> ## 2026-08-28 LoudKit and Sopro CPU auditions — HEARD, both rejected
>
> Dave heard eight arms and rejected all of them: **none good enough.** Neither
> LoudKit 0.1.0 / loudr-1 nor Sopro v2 turbo becomes an application engine, and
> neither earns a longer gate. Chatterbox Nano / Beatrice remains the default.
>
> The first four arms were run against a **cloned Arthur reference that Dave had
> not asked for** — the harness chose it and then wrote that choice into the
> README and a passing test, which made an unrequested assumption look settled.
> Sopro in that gate also ran at `temperature=0.7`, copied from the Audio8
> harness and documented nowhere by Sopro, whose own default is 0.8; those were
> not default renders. Both were corrected, a guard now pins that the harness
> cannot choose a reference, and Dave chose Beatrice for Sopro.
>
> The corrected gate rendered LoudKit's own shipped English voices `joe` and
> `kathleen` at upstream defaults on ONNX CPU (RTF 1.261 / 1.263, ~3.2–3.3 GiB
> peak working set), and Sopro on Beatrice at upstream defaults (RTF 0.738,
> 1,031 MiB) plus a solver `steps 16` arm (RTF 1.622). The two Sopro arms have
> identical duration because `steps` drives only the acoustic decoder, so that
> A/B rules the solver default out as the limitation. All rejected by ear.
>
> One earlier claim was **retracted**: the first gate concluded that LoudKit
> dropping the same sentence on both backends "points at the model or its
> windowing". That was wrong and untested. `max_new_tokens` and
> `max_speech_tokens` both default to 255; at 512 on the PyTorch path
> `hit_token_cap` clears and all 13 chunks return clean with no trimmed tails.
> The omission was the default window. The fix is unavailable on the fast path:
> ONNX refuses the wider window because its graphs are static at query 255 /
> prompt 238, and PyTorch measures RTF 6.96. Escaping the cap needs the ONNX
> graphs re-exported.
>
> Also recorded: **Sopro ships no native voices at all** — `--ref` is required
> and the model repository contains no profiles — so it can never be auditioned
> on native supported voices.
>
> No ASR was used on the second gate. Everything ran locally on CPU: no GPU on
> the host, no Kaggle, no Vast, no paid API. No engine registered, no voice
> added, no deployment state changed.

> ## 2026-08-22 Audio8 / Scylla v2 / ZONOS2 CPU auditions — HEARD
>
> Dave heard all six exact files from the isolated CPU gate. Audio8's Arthur
> voice was good, but both arms audibly dropped or faded; the prepared arm also
> changed pace/tone as though it had been chunked. That arm was in fact twelve
> independent calls with seeds 42–53 and 200 ms joins. Three forced boundaries
> split sentences at “percent / and,” “over / two hundred,” and “Dr. / Wang.”
> Signal measurement found every call's final 100 ms fell to 0.5–12% of the
> preceding speech level. The prepared clip's content was structurally complete,
> but this continuity path fails; the raw clip also omitted the end of the
> eighteen-hour-days sentence. Audio8 remains a bounded corrective candidate,
> not an app engine or long-form pass.
>
> Scylla's Band v2 / Ink failed by ear in both INT8 and FP32: robotic, no
> emotion, and effectively one long sentence despite acceptable pronunciation.
> The matching verdict across quantisations rules out INT8 as the material
> explanation. Stop at the short gate; no Scylla integration or longer render.
>
> ZONOS2 Arthur Q4's complete 19.888-second first paragraph was “really good.”
> The 56.517-second single-pass arm audibly dropped its ending and the Arthur
> voice disappeared; structural ASR independently found the final 35 words
> missing. This is a short voice-quality pass but a sustained-narration failure.
> The model emitted EOS near its generated frame limit, but listening does not
> establish why the identity drifted. The only justified follow-up is a
> persistent fixed-setting, sentence/paragraph-bounded continuity A/B before
> any longer gate. Q8 remains untested because Q4 peaked at 12.3 GiB in a
> 14 GiB WSL cap. No product, deployment, GPU, cloud or paid route changed.
>
> The authorised corrective stage then produced two new listening candidates.
> Audio8's 82.709-second `prepared_sentence_fixed` arm keeps the exact prepared
> words, uses nine complete-sentence calls with seed 42 throughout and adds no
> join silence. Three sentences exceed upstream's recommended 150 characters
> (173/235/187), which remains an explicit limitation. The MP3 fully decodes;
> structural ASR covers the complete passage (WER 0.120), with differences
> dominated by numeric/acronym formatting and pronunciation uncertainty.
>
> ZONOS2's first persistent-server/cached-Arthur sentence arm exposed another
> real truncation: its 139-character iPhone sentence stopped after “revenue”
> and omitted the entire App Store clause. That failed arm is retained. A
> narrow same-setting repair split only that compound sentence at its natural
> conjunction, changing punctuation but no words. Both halves completed, and
> the rebuilt 69.718-second MP3 fully decodes with structural ASR covering the
> complete source (WER 0.110). This is **not yet a quality or continuity pass**:
> both exact corrective files await Dave's listening verdict. No engine was
> registered and no deployment state changed.
>
> Dave then heard both exact corrective MP3s. Audio8 was **“better”**. That
> confirms the complete-sentence/fixed-seed/no-added-silence changes materially
> improved the earlier join behavior, but it is not yet an explicit long-form
> approval. Audio8 is the only candidate from this gate still eligible for a
> separately authorised longer test.
>
> ZONOS2 still sounded like different voices, with Arthur fading in and out.
> Dave considered the underlying/base voice itself OK. The persistent model,
> one cached speaker embedding and fixed settings rule out model reload and
> per-request re-encoding as explanations for this particular result; they do
> not establish the remaining model-side cause. The current cloned-Arthur
> audiobook path fails continuity and is closed. No app engine was added.

> ## 2026-08-21 Gemini preset preview cache complete — 30/30 verified
>
> The final Free-tier-only batch cached Achird, Gacrux, Pulcherrima, Sadachbia,
> Sadaltager, Sulafat, Vindemiatrix and Zubenelgenubi in one request with no
> retry. The persistent Pacific-day ledger finished at 8/10 used, leaving two
> calls; no billing, Vertex route, paid fallback, project/key change or ASR was
> used. Before the request, UI, worker and live checkout matched SHA `3ae6502`,
> app/adapter health passed and the queue had no queued or active work.
>
> Independent validation then opened the exact preview path for every one of
> the 30 Gemini IDs. All 30 returned HTTP 200 `audio/mpeg`, probed as MP3,
> 24 kHz mono, had nontrivial durations/sizes (79.008–89.088 seconds;
> 1,580,204–1,781,804 bytes), and completed a full FFmpeg decode with no error.
> This completes the requested instant-play audition cache. It does **not**
> approve 30 narrators: Achernar remains the only Gemini preset to pass Dave's
> long-form listening gate; the other 29 are cached auditions.

> ## 2026-08-15 Piper retired; NVIDIA Magpie raw path rejected / diagnosis open
>
> Piper has been removed from the product rather than merely stopped: Compose
> service/profile/volume declarations, environment settings, proxy routing,
> engine and voice catalogues, preview generation, health probes and helper
> scripts are gone. Old queued Piper jobs fail closed instead of silently using
> another engine. The controlled rejection evidence remains in `ENGINES.md` and
> `VOICES.md`; it is history, not an executable option.
>
> Dave heard all five exact Magpie short files and the John long file. Every
> short arm had a repeatable defect at about five seconds and was poor; the long
> arm had the same clipping/cut class. Accents and tone were good, but all six
> fail production reliability. The shared timing aligns with Magpie's first
> automatic sentence-state boundary. The harness creates one model waveform and
> performs no PCM joins, ruling out the app's audiobook stitcher. The test still
> used the public raw NeMo path, not NVIDIA's production hosted NIM, and differed
> from the current documented example on text normalization and temperature.
> Root cause therefore remains **open**, scoped to raw NeMo versus hosted NIM.
> No Magpie voice is exposed.
>
> NVIDIA's official Developer Program provides free hosted NIM endpoints for
> prototyping, subject to rate limits. It is not a guaranteed free whole-book or
> production allowance; production NIM deployment requires NVIDIA AI Enterprise.
> One focused official NIM PCM request is the next valid diagnostic when an API
> key is available. Do not repeat-query it or use it for a book.

> ## 2026-08-15 NVIDIA MagpieTTS v2607 — FREE-T4 CAPACITY PASSED / LISTENING FAILED
>
> NVIDIA's current official model card and long-form guide identify MagpieTTS
> Multilingual v2607 as a 364M, five-preset model with beta stateful English
> long-form inference aimed at audiobook/content narration. The private Kaggle
> gate `davedavedavedavenm/nvidia-magpie-v2607-longform-gate` pinned official
> model revision `5023df68bd3f5b5ce6d666a50979bc501af145cc` and NeMo Speech
> v3.0.0 commit `fd6a877539710e2b98f28c43272ff81312f83417`. It refused paid,
> CPU and non-T4 fallback. Version 1 stopped before setup because Kaggle changed
> a Unicode source literal; version 2 loaded the exact model but exposed a
> nightly-versus-v3.0.0 helper-signature mismatch. Version 3 used the exact
> pinned official signature and completed; neither correction changed model,
> inference settings, text or requested hardware.
>
> All five official presets rendered the same exact 202-word prepared hard
> passage: Aria 70.914 s, Jason 74.025 s, John 89.211 s, Leo 78.344 s and Sofia
> 72.446 s. John also completed a 1,470-word / 79-stateful-chunk continuity arm:
> **9:14.260**, 11,086,934 bytes. Independent local validation reconstructed
> both source hashes, matched every MP3 size/SHA, found six distinct 22.05 kHz
> mono MP3s and fully decoded all six. T4 RTF is **1.081–1.142**; the long arm
> peaked at **11.61 GiB allocated / 14.31 GiB reserved**, within the 16 GiB T4.
> No ASR was used. Capacity and file structure passed, but Dave subsequently
> rejected every output for a shared early cut/clipping defect and poor overall
> quality. This section preserves the capacity evidence; it is not the current
> quality verdict. No app engine, default or selectable voice changed.

> ## 2026-08-15 Index join diagnosis + Gemini full-catalogue work
>
> Dave heard garbling at approximately 28 and 58 seconds in both IndexTTS-2.5
> arms. This is now measured, not inferred: the source WAVs contain Index's
> exact 200 ms inserted joins at 30.151/57.983 s (native) and 27.632/59.620 s
> (prepared). The official 120-token splitter cut the prepared arm after “six
> days a week,” and after “the E U,”; the native arm also ended its second
> segment on a comma. The MP3s fully decode, so this is a synthesis-boundary
> failure rather than MP3 damage. The prepared arm separately passed raw `1.5`
> with Index normalization disabled, explaining “one five gigawatts”: our
> explicit input/configuration was wrong.
>
> One replacement private free-T4 job,
> `davedavedavedavenm/indextts25-arthur-boundary-fix`, completed. It generated
> exactly one corrected output as nine complete-sentence calls, proves the
> official splitter cannot subdivide them, writes “one point five gigawatts”,
> joins PCM with documented 200 ms sentence gaps and uses no paid compute or
> ASR. The corrected output is 85.529 s, MP3 SHA-256
> `dc1dbfba54cf3d4c4fa10d41f246b002f14776bfe78d2509d40d6a43c11cbd94`.
> All nine source/segment hashes, the eight exact 200 ms joins, WAV structure
> and full MP3 decode passed independent local validation. Dave then heard the
> corrected clip: the corruptions were improved, but timing and pacing were
> poor and it remained far less natural than Gemini Zephyr or Chatterbox.
> **IndexTTS-2.5 is rejected for production; its listening gate is closed.**
>
> Gemini's complete official 30-preset catalogue is registered and, as of
> 2026-08-21, all 30 exact app-path previews are cached and independently
> decoded (`30/30`). Achernar remains the only long-form-approved voice; the
> other 29 are auditions. The adapter has a persistent Pacific-day usage ledger
> which counts failures and refuses request eleven before upstream. The
> catalogue was warmed across Free quota days, one batch action per day and one
> attempt per preset, without attaching billing. New-user setup is consolidated
> in `GEMINI-SETUP.md`.
> Preview, web-worker and standalone explicit-number paths now all use
> `modern=True, expand_numbers=True`, fixing the bare-decimal gap in every
> parallel path.

> ## 2026-08-15 IndexTTS-2.5 — FREE-T4 CAPACITY PASSED / QUALITY REJECTED
>
> Dave authorised the next free/open-weight candidate after selecting Gemini.
> One private Kaggle job, `davedavedavedavenm/indextts25-arthur-focused-gate`,
> completed on explicit `NvidiaTeslaT4` free compute. The harness pins official
> release commit `39207d91c30899cad1e7c1b9eb678c241f678e55`, model revision
> `c39ce5ba981572cb187443877ff559dfb246ce63`, FP32 and the exact Arthur
> reference. It refuses P100/CPU fallback and paid compute. One model load
> produced only two short same-seed arms: Index's native normalizer and the
> repo's explicit number/currency preparation. No ASR was used. Do not start a
> long-form render unless Dave accepts a clip.
> The first staged version was deleted while running after the full host suite
> proved its prepared-text builder had taken the normalizer's missing-dependency
> fallback. No result from that invalid version will be handed off. The
> replacement byte-pins raw SHA-256
> `f6294d0b3a9257277f26cf505f6814933500da641f826d3e6ca3cc1e28c45a0f`
> and production-prepared SHA-256
> `57b51dd4df3795dda2e1dab04c68d25c7eea97f5b160dfd8b65537bd5ee2389c`.
> The corrected run loaded in 86.880 s at 10.982 GiB peak reserved GPU memory.
> Native is 66.124 s, RTF 1.863, MP3 SHA-256
> `1a41d20f819ba641345b2494b08dee07d5ecef62c637d42aad73fc4074beb791`;
> prepared is 68.237 s, RTF 1.796, MP3 SHA-256
> `2070d5b41ea4e439e5c299df4217a786b89b6b9e426fd6f41003edfda5ac9997`.
> Both are 22.05 kHz mono, distinct, non-trivial and passed independent local
> hash/WAV/full-MP3-decode validation. The technical T4 capacity gate passes;
> voice, pronunciation, numbers and pacing remain Dave's listening decision.
>
> ## 2026-08-15 Gemini 3.1 Flash TTS — ACCEPTED FREE-ONLY NARRATOR
>
> Dave rated the Google AI Studio `gemini-3.1-flash-tts-preview` + Achernar
> sample “very good” and asked for a free or near-free route. The repo now has a
> dedicated non-root OpenAI-compatible adapter using Google's official
> `google-genai==2.18.1` SDK and current Gemini Developer API **Interactions**
> endpoint. It is pinned to that one model and the 30 official presets; only
> cached presets are selectable and only Achernar is long-form approved. It
> cannot call Vertex, Batch, another paid model or a configurable
> upstream. Only a key belonging to an unbilled AI Studio project whose plan is
> Free is permitted. It fails closed without the separate operator assertion
> `GEMINI_FREE_PROJECT_CONFIRMED=1`; the docs explicitly state that the inference
> API cannot verify tier and the unbilled project is the real boundary. Free
> Tier input/output is currently listed as free; Google
> states Free Tier content is used to improve its products.
>
> Production plumbing is deployed on Zorin: opt-in Compose/deploy profile,
> engine-bound Achernar voice, explicit number/currency preprocessing,
> paragraph-aware 2,200-character requests, lossless passage joins, one request
> per passage, SHA-keyed resume cache, and a hard no-auto-retry branch at both
> HTTP and job recovery levels. Quota exhaustion marks the job failed with a
> manual-resume message; completed passages remain cached. Preview creation is
> an explicit Settings action and repeated clicks are cache hits. No API request
> is made at startup.
>
> A dedicated unbilled project (`dave-audio-free-20260815`) and API-restricted key
> are live; the key remains only in the host `.env`. Whole-stack revision
> `17e45937b17128f15d37ba2fe7c2da740a077cb4` is healthy in both web and worker,
> and `gemini-tts` is healthy. The current deployed whole-stack revision is
> `d8ca10d812a71e6d1c7672a28297509bb3dee102`; the checkout, web and worker
> report the same SHA. Exactly one final SDK preview request produced the
> persisted app-path file: 81.576 s, 1,631,564 bytes, MP3/24 kHz/mono, SHA-256
> `7a17a180bf34ecffb75022f4f6a0a9d6bed33483f52f69e95cf35f5b88975ea3`.
> It fully decoded, `/api/preview/gemini_achernar` returned the identical bytes,
> and `/api/voices` reported `118/118` configured previews ready.
> Post-change verification now passes 308 host tests plus all eleven adapter
> tests in its pinned SDK environment (319 total).
>
> The original raw-REST bring-up made two generation calls whose audio could not
> be decoded from the undocumented wire shape; one intervening request was
> rejected at HTTP 400 before generation. No automatic retry occurred. Further
> trial-and-error calls were stopped and the adapter was changed to the exact
> official SDK response path. Adapter coverage is now nine tests and explicitly
> pins `HttpRetryOptions(attempts=1)`. Dave then approved the exact cached
> preview, allowing the spend-controlled long-form gate recorded below.
>
> Dave approved the exact cached preview as “very good”. The first bounded
> long-form attempt used a 1,644-word, complete-paragraph public-domain excerpt
> from *The Yellow Wallpaper* (source SHA-256
> `99675d31a06db51ee0cba5eab7e3b9f7199ac01ec98023c8ca95a3f551ba800e`,
> excerpt SHA-256
> `b8e27d17adcaab3c68f19ce5e66ed3c8a9699ecd0afe55f416295be6e1652a86`).
> The production 2,200-character paragraph pack produced five planned requests.
> Request one returned upstream HTTP 503 `service_unavailable`; Google’s live
> metrics record one Free Tier request and **zero output tokens**. No passage was
> cached, no second request was sent, and the app remained responsive. Google’s
> official error reference defines 503 as temporary overload/down and recommends
> waiting before retrying. At that point the listening gate remained open;
> resume had to be a later explicit action, never an automatic retry.
>
> Dave explicitly authorised a later manual resume. That run succeeded with
> exactly five one-attempt requests and no cache regeneration. The final file is
> 10:10.128, 12,202,952 bytes, MP3/24 kHz/mono, SHA-256
> `3f9d1ce6482eb3313b9065c16439d8bd47e63c1f4ca0fb88000a232be8e76841`.
> Full ffmpeg decode passed. The six captured transcript records were proven to
> be the failed first passage followed by the exact successful five-passage
> sequence; the successful sequence reconstructs all 1,644 processed words and
> 8,524 characters. Cloud Monitoring records nine of ten Free Tier requests used
> today (three bring-up previews, the zero-output 503, and five successful gate
> passages). Billing remains disabled and actual cost is zero. The **technical
> long-form technical gate passes**. Dave then heard this exact file, called it
> **“one of the best”**, and selected it for use. Achernar is now an accepted
> explicit book narrator. It is not the portable repo default because the
> account has only ten requests/day and a new installation has no Gemini key.
> At the proven 2,200-character packing, a 600,000-character novel would require
> roughly 273 calls—about 28 quota-days—with passage cache/resume across days.
> Structured Gemini failures now retain Google's documented machine code and
> safe message in converter/job diagnostics while redacting keys/tokens,
> omitting arbitrary response bodies and preserving the one-attempt policy.

> ## 2026-08-15 Azure Speech access — F0 LIVE / SYNTHESIS PAUSED
>
> Dave authorised the installed official Azure CLI using Microsoft's device-code
> flow. The exact active subscription shown in his portal was selected, the
> previously unregistered Cognitive Services provider was registered, and a
> dedicated UK South `SpeechServices` resource was created at SKU **F0** inside
> its own `free-only` test resource group. No Speech key was printed, persisted
> in Git, or added to the production app; S0 was not created or enabled.
>
> The official live voice endpoint returned 15 GA Australian, two GA Irish and
> two GA South African neural voices. An initial catalogue-oriented harness was
> interrupted when Dave mandated focused short tests. Seven Australian requests
> had completed by the time the interrupt landed; no Irish or South African
> synthesis started. Exact estimated text use is **7 × 1,142 = 7,994 characters**,
> **1.599%** of the 500,000-character monthly F0 allowance, with no draw on the
> subscription's $200 credit. There is no background renderer or retry running.
>
> `scripts/render_azure_accent_samples.py` now fails closed unless the operator
> supplies one to three exact live GA IDs. Its default total character ceiling
> is 1,000, it refuses duplicate voices and an output directory already holding
> MP3s, and it never promotes the resource off F0. Unit/regression coverage pins
> those limits.
>
> Dave then explicitly approved one voice per accent. The focused gate used one
> 300-character normalized passage and exactly three requests (900 characters,
> 0.18% of F0): Australian `en-AU-DarrenNeural` 16.344 s / 326,880 bytes /
> SHA-256 `ecc56c462a95c92f317f084f5b0427fa46670e3333fd5338e0c3bcbb9718d4cf`;
> Irish `en-IE-ConnorNeural` 17.856 s / 357,120 bytes /
> `943ea74de4511ac696f880c44a511c543010e941425a0fe51abbaa327a475d00`;
> and South African `en-ZA-LukeNeural` 16.176 s / 323,520 bytes /
> `62f1be8f84f11aacb66af93a9fd1a985efe53cdcefc51c2cf059dae2d62fb17a`.
> All three are 24 kHz mono MP3s, fully decoded locally and match their manifest
> hashes. Estimated cumulative F0 synthesis text is now 8,894 characters
> (1.7788%); subscription-credit use remains $0. Dave's verdict: **all three
> accents are spot on, but all three voices sound robotic and degraded**. This
> is an accent pass and overall audiobook-quality failure; none is approved or
> exposed in the app. No additional Azure synthesis is authorised by this gate.
>
> The delivered files used 24 kHz / 160 kbps mono MP3. That is not a low bitrate,
> but Microsoft's current REST documentation says requesting 48 kHz invokes a
> separate high-fidelity standard-voice model and supports lossless
> `riff-48khz-16bit-mono-pcm`. One same-voice lossless 48 kHz control can
> therefore isolate the “degraded” complaint. It cannot be assumed to cure the
> robotic timbre: Connor and Luke are officially Standard voices with no listed
> speaking styles, while SSML prosody changes rate/pitch/range/volume rather than
> the underlying voice. Australian preview offers materially different MAI and
> Dragon HD Omni models, but the live UK South catalogue did not expose them.
>
> Dave then approved one endpoint-isolation control after noting that the app's
> existing Edge voices sounded better. The earlier comparison had not used the
> same speaker: Edge exposed Australian William/Natasha, while the Azure gate
> used Darren. On the exact same pinned 300-character text, neutral prosody and
> `en-AU-WilliamNeural`, one Edge Read Aloud request and one Azure F0 request
> produced structurally matched 16.032-second, 24 kHz mono, 48 kbps MP3s. Edge:
> 96,192 bytes, SHA-256
> `ab2fb5c430fd8b4c423b72dddb4c953a70e073154428a8c78c1b5e63f9fb9cc5`;
> Azure: 96,192 bytes,
> `c03485700f9e7e54097d326bd994c0becfc98f0872ed7d32b7f3f04376569e62`.
> Both fully decode. This consumed exactly 300 more estimated F0 characters,
> bringing cumulative estimated synthesis text to 9,194 (1.8388%); subscription
> credit use remains $0. Dave's same-voice verdict: **Azure is only slightly
> better, but it is better**. This closes the endpoint question: Azure did not
> cause the earlier perceived degradation relative to Edge. The earlier large
> difference was confounded by speaker and input; it must not be attributed to
> the service route. This is a relative result, not production approval for
> William or Azure. No production default changed and no further Azure request
> is authorised by this control.
>
> Dave next requested longer correctly processed samples for all three accents.
> A single 737-word / 4,037-character source was prepared once and sent once to
> each already-heard male regional voice: Australian William, Irish Connor and
> South African Luke. It combines 24 complete *Yellow Wallpaper* paragraphs
> with the hard Apple/numbers passage. The app normalizer expanded every number,
> percentage and currency expression; no digits or currency symbols survived.
> Twenty-nine SSML paragraphs preserve title/author/body pacing, and Azure's
> documented IPA `<phoneme>` mechanism handles 12 pinned difficult terms,
> including `co-heirs`, `draught`, Huawei, Xiaomi and Nguyen. The legacy shouted
> respellings were not used.
>
> Exactly three F0 requests produced lossless high-fidelity 48 kHz mono PCM:
> William 3:51.887 / 22,261,244 bytes / SHA-256
> `412e5320e9e1a74f8d4b07bffca3fd140d3dc107fafaa63a42494b57b9af9cad`;
> Connor 4:11.863 / 24,178,844 bytes /
> `8fffdba7701d67de8e352f8101540f9cc25306ffe280b74771deb2fbd2b13b38`;
> Luke 3:49.000 / 21,984,044 bytes /
> `71fe491786e8d2d8126d90359433beacaba1317901552f9cab171b0d197997e0`.
> All fully decode. Microsoft's billing documentation counts the SSML body
> markup as well as its visible text (only the outer `speak`/`voice` tags are
> excluded), so the corrected estimate is 14,367 billable F0 characters, not
> the earlier 12,111 plain-text count. Cumulative estimated synthesis is 23,561
> characters (4.7122% of 500,000); the resource remains F0 and production
> defaults remain unchanged.
>
> Dave's verdict: **all three accents are acceptable and all three voices are
> acceptable**. They are not great for emotion and none sounds as real as
> Arthur, but they pass his minimum standard. This approves William, Connor and
> Luke as opt-in Azure regional voices, not as the system default and not as an
> automatic cloud fallback. No further Azure work is running.

> ## 2026-08-15 Groq decommission audit — LIVE / NOT CURRENTLY IN USE
>
> Groq was used historically, which explains the account activity screenshot and
> the old `epub`-key request count. It is not the live provider now: neither
> running app container has a cloud `LLM_API_KEY`; `app_settings` contains no
> LLM/Groq override. Their otherwise-unused cloud slot still has the OpenAI
> default URL/model but no key; both separately configure the shared local
> Ollama `qwen2.5:7b` for the background, non-deciding QA explanation path. Its
> OpenAI-compatible models endpoint returned 200 and listed that exact model.
> No secret values were printed during the audit.
>
> Groq's official deprecation page confirms `llama-3.3-70b-versatile` shuts down
> on 2026-08-16 for Free/Developer usage. The stale setup example and Settings
> selector have been corrected to current official IDs, led by
> `openai/gpt-oss-120b`; a regression guard forbids the three retired Groq IDs
> from returning to the selector. This is a repo/setup migration, not a live
> credential migration, and it incurs no cloud use or charge.

> ## 2026-08-15 controlled Chatterbox gate — HEARD / ALL FIVE REJECTED
>
> Five same-text, seeded CPU renders now exist under the ignored evidence bundle
> `scratch/chatterbox-control/20260815T073048Z`. The source is the exact deployed
> 182-word hard passage (1,015 UTF-8 bytes; SHA-256 `9a4b6bd1f48b6f745f53ceb284306b3d57488fe565af9736b9f4d47e3fffe083`).
> Every MP3 has one 24 kHz mono stream, passed full `ffmpeg` decode, and its
> downloaded local copy matches the recorded hash:
>
> | Arm | Duration | Bytes | SHA-256 |
> |---|---:|---:|---|
> | Arthur / Turbo | 76.344 s | 1,221,548 | `39de9fd7fed84b959f1a2637700117b1518da5c493c565e943837f1f45030585` |
> | Arthur / V3 / CFG 0 | 79.896 s | 1,278,380 | `be231c65f24f03725daeff930bda04a0e6c29b197686affbdb30d289d2adc4f7` |
> | Arthur / V3 / CFG 0.5 | 69.984 s | 1,119,788 | `6e8fc2dbde97f3c192964d25f82f496a79745c762ca1371b50871bea47dbd049` |
> | Human Irish Tadhg / V3 / CFG 0.5 | 59.688 s | 955,052 | `5c747db407e5058bb1e90bcab39801399c19b90ef6c62edab91ddb5977a442ac` |
> | Human Australian VCTK p374 / V3 / CFG 0.5 | 71.064 s | 1,137,068 | `a4c568ae3331aab080c579a503454ae25b186fb411dd1d4c55f8fa445c4396b9` |
>
> The product-health monitor recorded zero errors and no health request slower
> than 0.05 s while synthesis ran. Dave then rejected every arm. Arthur/Turbo
> repeated or broke “engineer”, mangled the large-number phrase after “over”,
> pronounced Huawei badly, and sounded more distilled than the Arthur he had
> liked. Both Arthur/V3 arms were poor. The human Irish and Australian V3 arms
> were also poor, with bad accent/pronunciation. All five handled numbers badly.
> None is production-approved. The temporary p374 runtime copy was removed after
> validation; its immutable retained Git LFS object remains available.
>
> The numeric failure is partly an input-path failure, not a clean engine result:
> the exact production payload retained raw `$1.2 billion`, `3,400`, `230,000`,
> `1.5`, `52%`, `£24.6 billion` and `7,000`. That disproves the repo's prior
> “modern engines cope with raw numbers” assumption. It does not establish that
> spelling those values fixes the other voice, pronunciation or accent failures.
> The bounded Arthur/Turbo numeric-only control has now rendered from an
> explicitly normalized `modern` payload (202 words; source SHA-256
> `8ccd447f2890e5f7cb7b9f8d41bb77cf4fe08a5cb40de2320a76559715afac1e`).
> It is 71.064 s / 1,137,068 bytes / 24 kHz mono MP3, passed full decode, and
> the downloaded handoff copy matches SHA-256
> `6446f882879b68f24ddb01d65e7d2b9c61dd33389b5219d21eb9551e459f1ddb`.
> The exact source and manifest accompany the clip. Dave's first listening
> verdict is that this voice is **much improved**. Because the engine, Arthur
> reference and hard passage were retained while the numeric forms were
> expanded, this establishes text preparation as a material cause of the first
> arm's failure. It does not by itself approve the remaining Huawei/ordinary-word
> pronunciation or make Turbo the production default. Production preprocessing
> remains unchanged until that narrower acceptance decision is made.

> The corrected repo commit `8f2e6fd266c8424c0ccb699840235267d5cb77f8` is live on
> both webapp and worker; `/api/health` reports overall `ok`, the queue is
> unpaused with zero queued/active jobs, all 117 configured voice previews are
> cached, and both GitHub workflows passed. The rejected optional
> `chatterbox-v3` and `melotts-tts` containers are stopped (not deleted); their
> evidence and reproducible profiles remain available.

> ## 2026-08-15 Chatterbox V3 regional gate — HEARD / EXACT PATH REJECTED
>
> Dave heard all three: Australian accent was okay, Irish was totally off, and
> South African was the best but still not great. All had mediocre pacing/tone,
> average pronunciation and badly failed numbers. None is production-approved
> or exposed as a selectable narrator.
>
> This was **not Arthur with only an accent changed**. Arthur uses the official
> 350M English Turbo architecture and a clean human narration reference. These
> clips used the separate 500M Multilingual V3 model, a language-aware tokenizer
> and CFG generation. Irish was conditioned on speech synthesized by the later-
> rejected Piper path; South African is verified Edge-derived; Australian is
> synthetic but its exact generating vendor cannot be proved from retained
> evidence.
> The harness also forced `cfg_weight=0` while V3's official same-language
> default is `0.5`. Official zero-CFG advice is for a reference-language versus
> target-language mismatch; every reference here and `language_id` were English.
>
> Live audit: source `resemble-ai/chatterbox@5de7a54aa4e5e2baadb0182dde554908b48b85c2`;
> official Hugging Face weights snapshot
> `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`; CPU; 280-character chunks;
> `exaggeration=0.5`; `cfg_weight=0`. The exact tested path is rejected. Cause
> remains divided among model, synthetic reference quality and the unjustified
> setting. The later controlled arms have now been heard and rejected.
>
> A subsequent reference audit found genuine human candidates that this gate
> never used: Irish narrator `tadhg_hynes.wav` and Australian VCTK p374. Both
> were then tested at official CFG 0.5 and rejected by ear. No human South
> African reference exists locally or in retained history. The local V3 accent
> route is closed; the rejected outputs remain evidence only.

> ## 2026-08-14 regional-accent direction — LISTENING VERDICT RECORDED
>
> Edge is the only option heard so far that comes close for genuine regional
> accents. The other surfaced Australian/Irish/etc. labels are rejected by ear;
> metadata is not a quality result. Arthur establishes Chatterbox Turbo as an
> excellent general narrator, not as an accent-preserving engine. Nano/Turbo
> accent cloning therefore remains closed.
>
> At that point Chatterbox Multilingual V3 at `cfg_weight=0` was the one
> materially different Chatterbox path still open; Australian joined the
> existing Irish/ZA audition. The 2026-08-15 verdict above closes that exact path.
> The Australian hard sample rendered locally in 310.45 s: 77.736 s,
> 1,243,820-byte, 24 kHz mono MP3 at 128 kbps, SHA-256
> `434e8bfee2fd483292961779ca4667987ca2f132ca599fe0b75d2b83be29111a`.
> It fully decodes and its live sample endpoint returns the exact 1,243,820
> bytes as `audio/mpeg`. The 2026-08-15 verdict above supersedes this then-open
> listening status.
>
> Official Chatterbox docs provide neither an Australian/Irish dedicated English
> pack nor a supported public fine-tuning workflow. If V3 fails by ear, the next
> honest comparison is Azure's native regional voices with its documented SSML
> phoneme/custom-lexicon controls. Azure F0 advertises 0.5 million Standard
> Neural characters/month; no paid use is enabled or implied.

> ## 2026-08-14 real Telegram multi-article E2E — PASSED / TEST DATA REMOVED
>
> Dave's actual Telegram account sent one message containing two public article
> URLs to `@grabthebook_bot`. The production webhook replied `2 queued, 0
> failed`; jobs `8f470892` and `13e7a958` used local Chatterbox Nano/Beatrice,
> completed as 50.016 s / 1,000,634-byte and 109.056 s / 2,181,436-byte MP3s,
> decoded end-to-end, synced to the ABS Articles library, appeared in public RSS
> and both enclosure URLs returned HTTP 206 byte ranges. Telegram delivered both
> completion notifications. The two test conversions were then deleted from
> the app and their exact ABS copies; their DB rows, outputs, uploads and RSS
> entries are absent.
>
> The cleanup exposed one real bug: History deletion removed the original EPUB
> but leaked its generated sibling `_tts.epub`. The two exact test remnants were
> removed and the delete path now removes both owned files with regression
> coverage. No user article or audiobook was deleted.

> ## 2026-08-14 VibeVoice documented turn-reset gate — HEARD / BOTH VIBE ARMS REJECTED
>
> The earlier negative verdict remains scoped to one flattened `Speaker 1:`
> chapter. The exact pinned community runtime documents a materially different
> remedy for speech that becomes too fast: repeat the same speaker label at
> text boundaries while retaining one model generation. The production HTTP
> adapter cannot represent that format because it collapses whitespace and
> prepends one label, so this evaluation uses a dedicated direct-runtime
> harness and does not change production code or defaults.
>
> Two independent private free-Kaggle jobs now cover the same corrected first
> 78 complete paragraphs of *The Yellow Wallpaper*: **1,998 words**, source
> SHA-256 `3b8808c4295c11cae751a33067a502452e3ebe4a10c7aaea5cadfe108625f0f4`.
> The known malformed `draught , and` input was corrected to `draught, and` in
> every arm; `romantic felicity - but` was deliberately retained. Both Vibe
> jobs used official `microsoft/VibeVoice-1.5B` weights, community runtime
> `07cb79feadd2d3fd7f47530d4c964a12857936a0`, exact Arthur reference SHA
> `8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252`,
> cfg 2.0, DDPM 10, seed 12345, FP16 and SDPA. Each used a fresh process.
>
> Blind A uses four internal turns and rendered **7:16.533** / 8,732,205 bytes
> (ASR word ratio 1.001, structural similarity 0.9865). Blind B uses seven
> internal turns and rendered **6:59.200** / 8,385,645 bytes (ratio 1.0005,
> similarity 0.9862). Their short durations are preserved as pacing evidence,
> not padded or trimmed. Blind C is the same source/reference through the
> already-supported local Chatterbox Turbo path: **10:50.800** / 13,017,164
> bytes. All three MP3s decode end-to-end and their downloaded hashes match the
> render manifests. ASR is used only for Vibe content-completeness; it does not
> rank voice quality. Dave rejected both Vibe arms A and B as unacceptable.
> Chatterbox Turbo + Arthur arm C was "almost perfect" with no progressive fast
> speech; the one heard defect was `co-heirs` sounding like `coheirs`. This
> closes the documented-turn remedy without reversing Vibe's production
> rejection. A later seeded hard sample failed, so Turbo + Arthur is now a
> per-book audition rather than an unconditional quality reference.
> Nano/Beatrice remains default and no paid compute or automatic cloud path was
> enabled.
>
> Kaggle's 2026-08 image exposed global NumPy package contamination. The final
> successful harness follows the repo's proven `uv` isolation pattern: managed
> Python 3.10, seeded venv, no inherited `PYTHONPATH`/user site, NumPy 1.26.4,
> SciPy 1.12.0 and scikit-learn 1.4.2. SciPy's official compatibility matrix
> documents 1.12 as supporting Python 3.9–3.12 with NumPy 1.22.4–<2.0. Failed
> setup attempts are environment failures, not Vibe listening results.

> ## 2026-08-14 Pocket + Kitten app integration — LIVE / OPT-IN ADMISSION COMPLETE
>
> Pocket TTS 2.1 and KittenTTS 0.8.1 now have isolated, non-root, CPU-only
> OpenAI-compatible services behind explicit Compose/deploy opt-ins. The app
> registers Pocket's 21 official English presets and Kitten's eight official
> presets, probes both services, and warms only healthy local voices. A Play
> control still requires a persisted non-trivial MP3; catalogue registration
> does not bypass the cache gate.
>
> Preview, first-render and recovery paths now share an explicit text profile
> for these engines: numbers/currency are spoken deterministically while
> legacy phonetic respellings are excluded. This matches the arm Dave selected
> for Peter, Jasper and Rosie and corrects the raw-input evaluation mistake.
> Live Zorin proof now covers both healthy CPU-only containers, all **21/21
> Pocket + 8/8 Kitten** persisted previews, and the app's complete **117/117**
> configured-ready catalogue. `ffprobe` validated every new MP3: 56–101 seconds
> and 1.12–2.01 MB, with no empty/cold Play entries. Chatterbox Nano/Beatrice
> remains the production default; Pocket and Kitten are optional CPU-only book
> choices and never automatic fallbacks. The shared six-core host now reserves
> capacity for the product by capping each candidate service at four CPU cores.
>
> **Long-form verdict:** Peter: **16:27**, 19,742,312
> bytes, 80/80 chunks. Rosie: **21:16**, 25,520,552 bytes, 80/80 chunks. Both
> captured inputs are exactly 3,600 words with excerpt SHA-256
> `a47c6ae855c7c5e23b5e852bcff9a97cac0dd157508594fc444dace68cb02972`;
> both MP3s decode end-to-end. ASR was not used as a voice-quality judge. Dave
> found Peter's body decent/promising but sometimes lifeless and poorly paced;
> Rosie's body was not bad and better than Peter for pace/tone. Both cleared the
> optional-engine floor; neither displaced the default.
>
> **Opening root cause proven:** both captured first requests contain the same
> flattened Project Gutenberg machine metadata (`Title`, `Author`, dates,
> credits) joined directly to the first sentence. The source EPUB's generated
> `pg-header` was passed as narration, so the run-on title/author failure is our
> input defect, not evidence that two engines independently failed the same way.
> Exact Gutenberg header/footer containers are now structurally excluded; the
> track-title selector uses that same sanitized document. The listening-excerpt
> builder also now retains paragraph boundaries instead of flattening them.
> A controlled current-vs-paragraph-aware Peter/Rosie render is now ready.
> Every arm uses the same clean 600-word excerpt (SHA-256
> `b7f27ba46801efe5041d422c194f0111b3bda0cc2772181dc97f7e7e6178a970`),
> exact deployed revision `cc1b0c6122b4907c1456d81a1d8c935fa185ab05`, 280-character
> ceiling, explicit normalization, official voice/model defaults and no LLM,
> ASR, GPU or paid compute. Current packing uses 15 requests; paragraph-aware
> uses 28. Peter current/paragraph: **2:49 / 2:48**, 3,382,468 / 3,369,508
> bytes. Rosie current/paragraph: **3:40 / 3:40**, 4,400,068 bytes each.
> All four decode cleanly end-to-end and have distinct hashes. Captured text
> begins `It is very seldom...`; no Gutenberg metadata remains. The first
> Peter-current attempt was deliberately stopped during setup and left two
> stale capture records; validation uses the successful final contiguous 15
> records (exactly 600 words), matching the only MP3 written. Paragraph-aware
> **Corrective A/B verdict:** Peter current/clean packing sounded more natural
> and was preferred; its intonation is still imperfect but the overall audio is
> decent. Peter's paragraph-aware arm sounded stranger. Rosie sounded decent in
> both arms with no meaningful difference. Current 15-request sentence packing
> therefore remains the app behavior for both engines; paragraph-aware packing
> is rejected as a default because 28 model resets produced no audible gain.

> ## 2026-08-14 Bond King generated copies withdrawn — LIVE VERIFIED / ZERO ON SHELF
>
> The earlier decision to retain both generated *Bond King* copies after a
> failed acquisition search was wrong: no acquired replacement justifies one
> fallback, not two. A fresh official LazyLibrarian per-book audiobook search
> completed with zero accepted results. Two Prowlarr routes returned HTTP 429,
> so this is not proof that no original audiobook exists; the title remains
> Audiobook Wanted for future torrent-first searches.
>
> Later retry `59d36718` had only one QA chapter recorded and was quarantined
> from ABS at
> `/home/dave/quarantine/abs-generated-dedup-20260814-1815/`, then removed from
> app History/local output after its job record was saved at
> `/home/dave/quarantine/app-generated-dedup-20260814-1818/59d36718-job.json`.
> Dave then rejected the remaining Kokoro/Fable render `592af51b`. It was moved
> out of ABS to `/home/dave/quarantine/abs-generated-withdrawn-20260814-1835/`,
> its exact ABS row removed, and its app output/history removed after saving the
> job record under `/home/dave/quarantine/app-generated-withdrawn-20260814-1835/`.
> Live proof now shows **zero** *Bond King* folders/jobs and 16 ABS audiobook
> folders with no duplicates. LazyLibrarian remains Audiobook Wanted with no
> AudioFile/AudioLibrary. No TTS retry will happen until Dave explicitly chooses
> the engine-bound narrator.

> ## 2026-08-14 VibeVoice cfg-2 production-path gate — RERUN VALIDATED / BLIND LISTENING READY
>
> The first exact 6,166-word free-Kaggle app-path run hit EOS at generation step
> **155/460 (34%)**. Official Kaggle output showed HTTP 200, so transport did not
> fail; the adapter produced a truncated but valid WAV. The proven direct path
> collapses whitespace before adding `Speaker 1:` while `vibevoice/server.py`
> preserved EPUB paragraph newlines. The adapter now applies that same whitespace
> contract, with a regression guard. The corrected free-Kaggle run completed:
> the app-path MP3 is 22:38.736 / 27,175,245 bytes and the direct-runtime arm is
> 22:52.056 / 27,441,645 bytes. Both decode fully and share the pinned 6,166-word
> source hash, runtime commit, Arthur reference hash, cfg 2.0, DDPM 10 and seed.
> A 45-second blind focus pair around “romantic felicity” plus both full files
> were heard. Dave selected **B**, the corrected production HTTP path. A, the
> older direct-runtime cfg-2 arm, did speak “but that would be asking too much
> of fate” but inserted a brief “byah”-like sound at the preceding hyphen.
> Exact prompt reconstruction proves both model inputs were byte-identical,
> including `felicity - but`; the hyphen is therefore the failure location, not
> a proven preprocessing cause. A was generated after cfg 3 in a shared loaded
> process, while B used a fresh app server/model process, so the remaining cause
> is generation-context instability rather than an app text-path defect. The
> corrected app path clears the reported defect. Dave then heard the full B:
> its opening was very good, but there was a local garble after “draught” and,
> from roughly three minutes onward, the delivery became progressively faster,
> more emotional/run-on and less intentional until it was far too fast. The
> exact shared source contains malformed `draught , and`, so that isolated
> glitch is not assigned to the engine without a controlled correction A/B.
> The progressive drift rejects this exact single-pass Vibe path for audiobook
> production. Qwen's retained 33:03 render uses the same 6,166-word/token source
> in 105 bounded passes and was already judged “really good” throughout; Qwen
> wins the long-form consistency re-rank. Nano/Beatrice remains default. No paid
> compute was started.
> The generated kernel metadata also now uses the actual Kaggle owner slug;
> the earlier two-`dave` slug caused a false permission error while monitoring.

> ## 2026-08-14 Goodreads audiobook-only wishlist — LIVE VERIFIED
>
> The supplied private `to-read` RSS feed is active in LazyLibrarian as an
> RSS/WishList provider with `DLTYPES=A`. Its URL/token remains runtime-only and
> is not recorded here. A live import added *Unruly* as Audiobook Wanted while
> leaving ebook status unset, and the full acquisition verifier passed. The
> Goodreads shelf therefore feeds the existing-audiobook search path rather
> than starting TTS conversion.

> ## 2026-08-14 generated-audiobook replacement sweep — LIVE VERIFIED
>
> Existing audio is now explicitly preferred not only before generation but
> after it: generated ABS entries are replaceable fallbacks. LazyLibrarian keeps
> them Audiobook Wanted and searches torrent-first. Automatic replacement-based
> retirement waits until acquired audio completes, passes the production import
> guard, reaches ABS and is structurally verified. Dave may separately withdraw
> an unwanted render at any time. Retirement is recoverable quarantine plus
> rescan, never deletion merely because a search matched or a grab started.
>
> The live sweep covered every current generated ABS title plus *Apple in
> China*. *Apple in China* is already a completed qBittorrent download: its
> standalone 406,415,524-byte M4B matches the completed torrent and the
> production guard passes it at 812 minutes. It was retained. Fresh targeted
> audiobook searches found no acceptable acquired result for *The Bond King*
> or *Breakneck*. The unnecessary second generated *Bond King* render was
> nevertheless quarantined as a duplicate; Dave subsequently withdrew the
> remaining generated *Bond King*. *Bond King* and *Breakneck* remain Audiobook
> Wanted, but only *Breakneck* currently has a generated shelf fallback.
>
> **Proof:** the effect-level acquisition verifier passes all assertions. Five
> providers answered and two Prowlarr-proxied providers (`Newznab_5` and
> `Torznab_1`) were rate-limited in the latest check. There are no grabs older
> than two days, the search sweep is current, the last successful grab is
> current and ABS has 16 non-duplicate audiobook folders. No cloud or paid GPU
> work ran.

> ## 2026-08-14 conversion history + ABS provenance audit — DEPLOYED / LIVE VERIFIED
>
> History now presents completed **books and articles together**, newest first,
> with actual narrator/engine, completion time and ABS state. Completed articles
> and books can be deleted locally or, through a separate explicit action, from
> both the app and their exact app-owned ABS destination. Single-file output is
> downloaded directly as MP3; only multi-chapter MP3 sets use a ZIP. The global
> player remains outside every tab, now advances chapters and persists playback
> speed while navigating. Batch APIs reject independent engine overrides:
> selecting a cached narrator selects its engine.
>
> **Proof:** Python/JS parse, Ruff and the full local suite pass: **264
> tests**, including direct-vs-ZIP delivery, safe deletion failure, article
> episode ownership, voice/engine binding, persistent navigation and chapter
> advancement. Full-stack deploy `865aff4` reports webapp and worker healthy at
> the exact same revision. In the live browser an article advanced from 0:14 to
> 0:25 while navigating History → Home, and then closed normally. Live response
> headers prove a one-track article downloads as `audio/mpeg` while the 21-track
> Bond render downloads as `application/zip`. The delete controls and confirmation
> copy render live; the destructive ABS path was deliberately not exercised and
> no ABS media was deleted during this verification.
>
> **Current ABS provenance (live after cleanup, 16 audiobook entries):** one folder is
> identifiable as app-generated: *Breakneck* `a3481358`. Both *Bond King*
> Kokoro/Fable jobs (`592af51b`, `59d36718`) are absent from ABS and app state;
> *Breakneck* is a historical render
> whose job row is no longer present. The other 15 entries are acquired audio,
> not TTS renders. There is no automatic library-to-
> conversion cron or timer now; Zorin only has the 15-minute ebook-library rsync,
> `GPU_RENDER_ENABLED=0`, and autoscaling is disabled. The two Bond jobs were
> created separately on 11 August; evidence cannot identify the caller, so they
> must not be attributed to Dave.
>
> **Acquisition defect — corrected 2026-08-14:** LazyLibrarian accepted raw release `10-27-weingarten`
> as Gene Weingarten's *One Day*. The delivered MP3 is 51:07, while Penguin
> Random House documents the unabridged audiobook as **11h 51m**. It is a wrong
> discussion/interview release, not an app conversion. The sibling `infra` repo
> now deploys a documented LazyLibrarian pre-import guard; the exact bad file was
> held with exit 42 in production, its native history row is Failed, and the ABS
> folder is in recoverable quarantine. *One Day* is AudioBook Wanted after a fresh
> search found no credible replacement. The unrelated duplicate *Apple in China*
> M4B was also removed from the Gombrich folder to quarantine while its correct
> standalone ABS item remains. Final acquisition health and effect-level checks
> pass every assertion.

> ## 2026-08-14 GitHub Actions image-build failures — REPAIRED / VERIFIED GREEN
>
> The repeated red runs were not failing unit tests or failed webapp images.
> `build-engines.yml` treated every `webapp/**` change as a reason to rebuild
> all four large engine images; Chatterbox then failed because the old PyTorch
> CUDA 12.4 index no longer served its exact `nvidia-cudnn-cu12==9.1.0.70`
> dependency, and matrix `fail-fast` cancelled TADA, VibeVoice and Qwen before
> they could report their own result.
>
> Commit `548f933` separated the webapp image into its own path-filtered
> workflow, made the engine workflow calculate a changed-engine matrix with
> native Git/GitHub job outputs, and disabled matrix fail-fast. Chatterbox now
> installs the matched `torch==2.6.0` / `torchaudio==2.6.0` CUDA 12.6 pair using
> PyTorch's official v2.6 wheel index. Regression tests prevent `webapp/**` or
> `scripts/convert_book.py` from being added back to the all-engine trigger.
> Commit `2bc8c73` also moved every workflow from the deprecated Node-20 action
> majors to the maintainers' current Node-24 majors: Checkout/Setup Python v7,
> Docker Login v4, Docker Build/Push v7 and Upload Artifact v7.
>
> **Proof:** local suite **256 passed** (253 existing plus three workflow guards).
> GitHub run `31780315340` passed lint, tests and Compose validation; run
> `31780315404` built/pushed the isolated webapp image; run `31780315342`
> independently built/pushed **Chatterbox, TADA, VibeVoice and Qwen**, all
> successful. A following docs-only push launched only CI (`31781112194`) and
> no image builds, proving the negative path. The current-major proof then
> passed CI (`31781244635`), webapp publication (`31781244701`) and all four
> independent engine builds (`31781244595`) without the Node-20 annotations.
> No deployment, engine default, GPU or paid-compute setting was changed.

> ## 2026-08-14 CPU numbers/currency root-cause A/B — HEARD / CAUSE CLOSED
>
> The original Peter, Jo, Jasper and Rosie auditions used each pinned engine's
> official API with raw `voice_sample` text. They were playable in the app but
> bypassed `normalize_text_for_tts`; prior “app-path clip” wording was wrong.
> The heard failure therefore did not establish engine fault.
>
> A controlled blind test now holds model, version, voice, seed/settings and
> source semantics fixed. Raw arms use source SHA-256 `84f91361...a5b0` (330
> characters); normalized arms use input SHA-256 `2a38087e...5179` (651
> characters) and explicitly speak years, prices, currencies, ranges,
> ordinals, percentages and large numbers. All eight MP3s are non-trivial and
> `ffprobe`-valid: Peter 27.024/34.944 s, Jo 37.344/45.888 s, Jasper
> 38.736/40.104 s and Rosie 43.080/44.904 s. NeuTTS completed all six sentence
> chunks in both arms.
>
> The first Pocket normalized attempt was rejected before handoff because its
> evaluation image lacked `num2words` and silently retained digits. That output
> was deleted; every image now pins the app's `num2words==0.5.14`, and the
> harness fails closed if it is absent. The corrected Pocket arm has the same
> normalized-input hash as every other engine. Blind assignments are retained
> only in the ignored evaluation manifest. No production engine/default or GPU
> setting changed.
>
> **Live handoff:** full-stack deployment `f04cbd5` completed with matching
> healthy webapp/worker revision. The Voices page puts the completed diagnostic
> first, identifies the selected normalized arms and surfaces the official
> inventory without offering uncached Play buttons. A real browser at 780×493
> loaded all eight evidence players at `readyState=4` with their expected
> durations and no media errors. Every
> internal sample URL returned `200` with the validated byte count. A fresh
> request to `https://audio.magnusfamily.co.uk` correctly redirected to
> Pangolin SSO; authenticated users reach this same deployed app. The source
> clips and private assignment manifest remain in the ignored evaluation
> output, while only the eight lowercase allowlisted handoff files remain in
> the preview cache.
>
> **Verdict/unblinding:** Peter A, Jo A, Jasper A and Rosie B were all the
> normalized arm. Dave therefore selected explicit spoken wording **4/4**. The
> original shared numbers/currency failure was caused by the evaluation path
> passing raw symbols/digits, not an inherent shared engine limitation. Peter
> had no reported residual defect. Jo inserted/stumbled “the e order” around
> “the order”; Jasper's opening was slightly scratchy; Rosie gave perhaps the
> best handling of the content. Those two artifacts remain synthesis-quality
> evidence separate from numeric normalization. Any future integration of
> these engines must use the normalized path; Chatterbox Nano/Beatrice remains
> the production default pending long-form admission tests.
>
> **Official voice inventory:** Pocket documents 21 English catalogue voices
> plus five named non-English voices and custom-WAV input. NeuTTS documents six
> English, one Spanish, one German and one French ready reference plus custom
> 3–15 second cloning. Kitten documents eight fixed presets. Exact names,
> source links and boundaries are recorded in `ENGINES.md` and `VOICES.md`.
> Only Peter, Jo, Jasper and Rosie are currently cached for these evaluation
> engines; the other official names are inventory, not yet playable claims.

> ## 2026-08-13 cross-host map and automatic-queue audit — VERIFIED / REPAIRED
>
> The sibling `infra` repo now contains the canonical visual and
> machine-readable book/audiobook topology. Live tracing corrected the active
> library path: homelab-pi stages ebooks, Zorin rsyncs them every 15 minutes to
> `/home/dave/booklib`, and that local path — not host `/mnt/openbooks` — is the
> UI/worker `LIBRARY_DIR`. LazyLibrarian delivers acquired audiobooks directly
> to Audiobookshelf; infra `book_sync.sh` is ebook-only by default.
>
> The same audit found an untracked Zorin cron still armed to auto-submit
> *House of Huawei* to free Kaggle when it appeared. Its sentinel was absent but
> no matching job existed. The cron is now removed with a mode-`0600` backup and
> a second sentinel guard. Current Zorin crontab contains zero automatic book
> submitters. Free Kaggle remains explicit per job; paid GPU remains off/manual.

> ## 2026-08-13 current baseline, Vibe verdict and cache contract — VERIFIED / DEPLOYED
>
> **Historical live services at 2026-08-13:** `epub-to-audiobook-worker` was
> running/healthy, exit 0 and `OOMKilled=false`; the earlier 3 August exit-137
> report was stale. `piper-tts` was intentionally stopped at that point and was
> fully removed on 2026-08-15. Chatterbox Nano/Beatrice remains the default
> local narrator. No paid GPU path is armed.
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
> rejected. Compose now defaults Vibe to 2.0. **Superseded by the completed
> gate at the top of this file:** the app-path check cleared that isolated
> insertion, but full-file listening then rejected the single-pass path for
> progressive speed/prosody drift. The completed blind-handoff monitor was
> removed.
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
> **CPU auditions:** Dave has now heard the already-rendered Pocket TTS/Peter
> Yearsley, NeuTTS Air/Jo and KittenTTS/Jasper + Rosie clips. All four voices
> are decent/good and clear the basic voice-quality screen. The original raw
> clips struggled with numbers/currency; the controlled follow-up selected
> normalized text for all four and closed that shared cause as evaluation-path
> error. None is wired into production or made a default.
>
> ## 2026-08-13 public article delivery + CPU engine screen — VERIFIED / HEARD; NUMERIC CAUSE CLOSED 2026-08-14
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
> audition files without a GPU. The persisted MP3 measures 64.128 s; the
> original render completed in 66.220 s
> (RTF 1.033, peak 1307.6 MiB) using its official Peter Yearsley preset, but
> emitted a 50-token chunk-limit warning and its cloning weights remain behind
> Kyutai's model-terms gate. Kitten Jasper measured RTF 2.304 / 1047.9 MiB and
> Rosie RTF 1.761 / 1090.4 MiB; these are preset voices, not clones. Dave heard
> all four voices as decent/good, while all four handled numbers and
> dollar/currency amounts poorly in the raw-input evaluation. The later
> controlled A/B selected explicit normalization for all four, proving the
> shared weakness came from the evaluation path. NeuTTS's first whole-passage run truncated because
> the official model documents an approximately 30-second
> context. The corrected ten-sentence render's persisted MP3 measures 72.672 s;
> synthesis produced it in 357.875 s
> (RTF 4.925, peak 2842.4 MiB) with its official Jo reference. That clip is
> complete by duration/chunk accounting, but the engine emitted phonemizer
> word-count warnings. Jo's later normalized arm retained one insertion;
> Jasper's had a scratchy opening; Rosie gave the strongest content handling.
> Chatterbox Nano/Beatrice remains the production default pending each
> candidate's separate long-form gate.
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
> 6. **Superseded 2026-08-14:** the 4-minute acoustic result did not predict
>    audiobook comfort. The corrected 22:39 app-path file became progressively
>    fast and run-on after roughly three minutes and was rejected by ear. This
>    exact single-pass path is not fit for books.
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
> capability question. **Current correction:** cfg 2.0 won the setting test and
> passed the app path structurally, but the full output failed human listening
> through progressive pace/prosody drift; no exact-image smoke can promote that
> quality result. Default rendering remains local/free Chatterbox Nano. Vast cost numbers remain
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
> **Historical snapshot:** the Vibe-vs-Qwen ranking below is superseded first by
> the cfg 1.3 discovery and finally by the corrected cfg-2 app-path rejection at
> the top of this file; the individual listening quotes remain evidence.
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
> **Historical interpretation, corrected 2026-08-15:** an accent label or
> reference clip does not establish authentic generated phonetics. Nano at
> `cfg_weight=0` was the best arm in that listening comparison, but the claimed
> mechanism—"0 lets the accent through"—was not stated by upstream and is now
> retracted. Official zero-CFG guidance concerns a reference/target-language
> mismatch. Neither Nano zero-CFG nor the later V3 path passed the quality bar.
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
(kokoro/edge) comfortable**. Fixed IPs: **.41 wired / .47 wireless** (DHCP
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

## Historical scorecard snapshot (2026-07-20; superseded by entries above)

The aims below were Dave's, stated verbatim or near-verbatim during development.
This table records the 2026-07-20 snapshot only. Do not use it for current
cache counts, ASR policy, engine defaults or priority order; the dated entries
at the top of this file and `DECISIONS.md` govern.

| Aim (as stated) | State | Evidence |
|---|---|---|
| "I go to the web UI, choose narrate, and it'll **just work**, all automatic" | ✅ | Kaggle and Local render both proven end-to-end (Chapters -> Preprocessing -> Subprocess -> Verify -> ID3 Tags -> ABS Sync). |
| Everything **checked automatically** — no blind trust | ✅ | **Restored 2026-07-27.** Transcript capture works on every engine (it was impossible for Chatterbox/TADA, so no book had ever been verifiable), a gate that inspected nothing says so instead of writing a clean pass, and **ASR verification is now ON by default**. The reason it was opt-in — "Whisper roughly doubles render time" — was my assumption and was wrong: measured 20× realtime, ~6% of a render. See below. |
| Accurate progress/ETA, no fake numbers | ✅ | Real per-chapter progress (ntfy call-home); honest "chapter X/N"; no ETA before evidence. Was elapsed-guesswork before. |
| Chapter selection = the actual book, by title | ✅ | Both local and Kaggle paths unified on `chapters.py` numbering. |
| Covers + metadata land in ABS, chapters navigable | ✅ | Full ID3 tagging implemented for both rendering paths. |
| **All voices cached**, instant, judged on hard text | ✅ | 69/69 then-configured local voices, plus all 30 Gemini presets as of 2026-08-21. Every Gemini preview was opened and fully decoded; only Achernar is long-form approved. |
| Clear visually which voice is speaking | ✅ | Speaking card: accent glow, equaliser, stop toggle, single-voice rule. |
| LLM guard: check/sort/act, local or free | ✅ | Shared khpi5 Ollama `qwen2.5:7b` is live and reachable; no Groq cloud key/model is currently configured. All LLM-assisted paths fail open to deterministic rules. |
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
| [#44](../../issues/44) | enhancement | Evaluate VibeVoice 90-minute single-pass rendering | Closed / capability proved, audiobook promotion rejected by ear |
| [#45](../../issues/45) | enhancement | Persistent voice-sample play/pause across tabs and menus | Closed |
| [#41](../../issues/41) | enhancement | Automatically re-render chunks that fail ASR | Closed |
| [#42](../../issues/42) | enhancement | Article RSS and Telegram link capture | Closed |
| [#43](../../issues/43) | enhancement | Chatterbox Multilingual V3 accents + per-voice `cfg_weight` | Closed |
| [#40](../../issues/40) | bug | Two renders of one book are indistinguishable in Audiobookshelf | Closed |
| [#37](../../issues/37) | bug | Settings save blocked by wrong WAL ownership | Closed |
| [#33](../../issues/33) | bug | Local render silently skipped ASR verification | Closed |
| [#21](../../issues/21) | enhancement | TADA: path to production-ready | Closed |


## Historical live deployment check (2026-07-25; superseded)

Verified against the running stack at `192.168.1.41`, not from documentation:

- **Deployed commit is `a34be70`** — current `origin/main`. The working tree on
  zorin is clean apart from untracked `data/` and one `.bak` compose file.
  (`/api/health` reports `git_sha: "local"`, which is the build label, not
  evidence of a live patch — don't read it as one.)
- **Engines live at that time:** chatterbox (Turbo), chatterbox_nano, kokoro, piper, edge
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
   **tts-proxy**. At that time, `get_engine_url()` routed
   piper/edge/polly/inworld/kokoro
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

**Live plan: PLAN-V5.md.** PLAN-V4 and earlier plans are historical;
**PLAN.md is PLAN V2 and is superseded** — kept for reasoning only.

| Doc | What it's for | State |
|---|---|---|
| **STATUS.md** | current-state index — this file | live |
| **PLAN-V5.md** | current forward plan | live |
| PLAN-V4.md | previous correctness sprint | historical |
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
