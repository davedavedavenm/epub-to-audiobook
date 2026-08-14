# PLAN V5 — what is next (reviewed 2026-08-13)

Successor to PLAN-V4, which is complete. V4 was about **truth** — subsystems
that reported success while doing nothing. V5 is about **automation and reach**:
the pipeline is honest now, but it still needs a human in three places it
shouldn't, and it delivers to one place when it should deliver anywhere.

**Status key:** `[ ]` not started · `[x]` done · `[~]` in progress

Everything here is agreed with Dave. Nothing in it is speculative scope.

---

## Standing constraint, stated by Dave and binding on all of it

> *"this shit needs to be done properly and auto… I cannot be manually tweaking
> per book or chapter."*

Any design that requires per-book configuration, a hand-maintained lexicon, or
Dave choosing settings per chapter is wrong by definition. Prefer a system that
detects and corrects itself over one that exposes another knob.

---

**Tracked as GitHub issues** — the issues are the live backlog, this file is the
narrative: **#41** (auto re-render) · **#42** (article RSS + Telegram) ·
**#43** (Chatterbox V3, `cfg_weight`, native warm-up) · **#21** (TADA quality,
incl. the `_trim_leadin` bug) · **#40** (duplicate-book naming) · **#44**
(VibeVoice selected app path) · **#46** (cached selectable CPU candidates).

---

## 1. Automatic ASR-driven re-render — Rejected/removed (#41 closed)

The implementation existed but was removed on 2026-08-13. WER cannot choose
the better-sounding render: it normalises audible mispronunciations and also
flags acceptable speech. Keeping it as an automatic replacement oracle would
let an algorithm overwrite audio Dave had never heard. ASR remains structural
evidence for gross truncation, repetition or mismatch only.

## 2. Articles: RSS feed, so any podcast app works — #42

- [x] 2.1 Serve the podcast folders as a standard RSS feed (`/api/articles/rss`).
- [x] 2.2 Feed metadata from the existing article record — title, site, date, source URL, duration.
- [x] 2.3 Subscribe ABS to its own feed or use standard podcast clients (Pocket Casts, Overcast).

**Why:** it decouples the destination from Audiobookshelf permanently. Pocket Casts, Overcast, AntennaPod and ABS all subscribe to a URL. The second-library awkwardness stops being a decision.

## 3. Articles: Telegram capture — #42

Dave: *"probably also worth deciding whether the web UI is best suited to
articles at the moment. My suggestion is it isn't."*

- [x] 3.1 Send a link to the owner bot → it queues the article with local defaults.
- [x] 3.2 Reuse the existing Telegram integration and require Telegram's official
      webhook-secret header plus the configured owner chat ID.
- [x] 3.3 Keep the Articles URL paste path; both routes share one queue function.

**Why:** opening a web UI to save a link is the wrong shape for "as and when I
come across something". Telegram already works from phone and desktop.

## 4. Chatterbox Multilingual V3 for accents — #43

- [x] 4.1 Install V3 (500M) and render Irish/South-African auditions.
- [x] 4.1a Render the Australian V3 audition at `cfg_weight=0`.
- [ ] 4.1b Grade Australian, Irish and South-African V3 by ear.
- [ ] 4.2 If it wins, make it the accented-narrator engine.
- [ ] 4.3 Expose `cfg_weight` per voice — accented narrators default `0`,
      ordinary narrators stay `0.5`.

V3 is the only model in the Chatterbox family that claims **accent
preservation**. Nano and Turbo are English-only agent models and their accent
cloning path is closed even though Arthur/Turbo is excellent general narration.
If V3 fails the AU/IE/ZA listening gate, close Chatterbox for regional accents
and compare the supported Azure regional voices plus pronunciation controls.
See VOICES.md.

## 5. Fix `_trim_leadin()` properly — #21

- [ ] 5.1 Measure the lead-in's real duration once at startup for the loaded
      voice and cut that, instead of hunting a silence gap and falling back to a
      hard-coded 0.45 s.
- [ ] 5.2 Or drop the spoken lead-in and prime with silence, so there is nothing
      to remove.
- [ ] 5.3 Assert it: the first chunk's transcript must not begin with the
      lead-in word. That test would have caught this immediately.

## 6. Audit the Piper synthesis path before closing it

- [x] 6.1 Verify model bytes and all speaker IDs against upstream. They match;
      there is no corrupt-download or wrong-speaker evidence.
- [x] 6.2 Audit the rest of the path. It uses Piper 1.2.0 in an archived wrapper,
      64 kbps MP3 previews, and the official medium VCTK model (US Lessac base,
      one RP phonemizer across speakers).
- [x] 6.3 Render same-text A/Bs for deployed 64 kbps, deployed synthesis from
      WAV, and current Piper 1.6 direct.
- [x] 6.4 Grade those A/Bs by ear. Dave: all three were *"absolute shit"*;
      almost every word was wrong and they sounded bad. Close VCTK-medium,
      remove Piper from automatic fallback, and do not spend time on EQ,
      bitrate, wrapper upgrades or inference tuning around this model.

## 7. Persistent voice-sample player — #45

- [x] 7.1 Use one global audio controller for every voice audition. Starting a
      new sample stops/replaces the old one; samples must never overlap.
- [x] 7.2 Show a persistent play/pause control with the current voice name
      whenever a sample is loaded.
- [x] 7.3 Preserve playing/paused state and current position across every
      in-app tab and menu selection. Navigation must not destroy or orphan it.
- [x] 7.4 Keep the control accessible and synchronized with playing, paused and
      ended events. Verify pause → navigate → resume from the same position.

## 8. Voice cache is the audition contract

- [x] 8.1 Play endpoints serve only persisted, non-trivial MP3s; they do not
      cold-render on click.
- [x] 8.2 Expose configured ready/total counts and hide unready auditions.
- [x] 8.3 Warm healthy free local engines with load throttling, skip-existing
      behavior and an off-switch; never auto-call paid/network engines.
- [x] 8.4 Keep the live production cache at 100% of configured/offered voices
      and verify each missing optional-engine artifact after deployment.
      Live proof on 2026-08-14: 117/117 ready; all 29 new Pocket/Kitten MP3s
      pass `ffprobe` and are 56–101 seconds long.

## 9. VibeVoice selected setting through the production path — #44

- [x] 9.1 Blind cfg 2.0 versus 3.0 on identical long-form text. cfg 2.0 won;
      cfg 3.0 was muffled/distant.
- [x] 9.2 Set the VibeVoice default to cfg 2.0.
- [x] 9.3 Reproduce or clear the brief garble after “romantic felicity” with a
      direct-upstream versus app-path A/B before promoting VibeVoice. The first
      app-path run exposed a separate 34%-length whitespace/EOS defect; fixed
      in the corrected free-Kaggle rerun. Both pinned 6,166-word arms now pass
      full decode and duration checks. Dave selected the corrected app-path B;
      direct A inserted a brief sound at `felicity - but` while retaining the
      words. The prompts, including the hyphen, were byte-identical, so no
      punctuation rewrite is justified. The production path clears the defect.
- [x] 9.4 Re-rank the corrected Vibe path against Qwen on the same text. The
      full cfg-2 app-path file opened very well, but after roughly three minutes
      became progressively faster, more run-on and less intentional. Qwen's
      retained 33:03 render of the same 6,166-word source remained “really
      good” and audiobook-listenable. Qwen wins the long-form consistency gate;
      Vibe single-pass is not promoted. The isolated garble after “draught” is
      kept separate because both inputs contain malformed `draught , and` text.

## 10. Public onboarding and support

- [x] 10.1 Make the first-run command start the actual default engine profile.
- [x] 10.2 Add health, engine and preview-cache proof commands plus evidence to
      collect when opening an issue.
- [x] 10.3 Document Pangolin/SSO RSS boundaries and the audiobook-first
      Goodreads/LazyLibrarian integration without committing private topology
      or feed tokens.

## 11. Admit the new CPU engines without offering cold voices — #46

Issue #46 is closed: Pocket and Kitten passed their admission gates and are
live opt-in choices. NeuTTS remains intentionally deferred, not half-enabled.

- [x] 11.1 Pin the official Pocket TTS, NeuTTS Air and KittenTTS versions,
      record their official voice inventories, and isolate them from the
      production queue while auditioning.
- [x] 11.2 Prove the shared number/currency failure was raw evaluation input;
      deterministic normalization won 4/4 controlled listening comparisons.
- [x] 11.3 Give each admitted candidate an opt-in, health-checked CPU service and route
      the same normalized text through preview, worker, recovery and finalise
      paths. Pocket and Kitten are implemented and live-verified. NeuTTS remains
      deferred and must retain sentence chunking for its documented context if
      separately admitted.
- [x] 11.4 Render and validate a persistent preview for every offered Pocket and
      Kitten voice before that voice is returned by the selectable catalogue.
      Never cold-render on Play. Live cache is 29/29 for these engines.
- [x] 11.5 Put the best heard voice from each candidate through a 15–30 minute
      app-path render and human listening gate before enabling book conversion.
      Peter and Rosie lead the operational shortlist; Jo's insertion and
      Jasper's scratchy opening remain open defects. Identical 3,600-word
      Peter/Rosie files are ready: 16:27 and 21:16 respectively, 80/80 chunks,
      identical 3,600-word input hash and clean full decode. Dave heard both:
      Rosie leads on body pace/tone; Peter is promising but uneven. The shared
      run-on opening was proven to be flattened Gutenberg metadata supplied by
      our path. Corrected 600-word current-vs-paragraph-aware Peter/Rosie pairs
      were heard. Current packing won for Peter; Rosie tied. Both candidates
      passed as optional engines.
- [x] 11.6 Enable only engines that pass 11.5 as opt-in choices. Pocket and
      Kitten are live CPU-only choices with every official offered voice cached
      (21/21 and 8/8; whole catalogue 117/117). Chatterbox Nano/Beatrice remains
      the default; neither engine is an automatic fallback or paid/cloud path.

---

## Done today, for reference

Numbers (`50k`, decades, decimal percents, the thousands comma modern engines
pause at) · hyphenated compounds no longer read with a pause · articles land in
an ABS podcast library grouped by site · TADA runs locally on CPU (#23, bf16,
RTF 1.68) · Piper VCTK installed, audited and rejected · twelve bad accent
clones removed · `cfg_weight` identified as the accent lever.

Full detail: STATUS.md, VOICES.md, OPERATIONS.md, and the closed issues.

---

## Standing rules this plan inherits

- **Settle audio questions by ear, not argument.** Broken twice on 2026-07-27;
  both times the argument was wrong.
- **Read the code and the vendor's docs before researching.** Three things were
  re-derived on 2026-07-27 that the repo already had.
- **Test the link, the URL and the deploy before handing them over.**
- **A component that cannot do its job must say so.**
