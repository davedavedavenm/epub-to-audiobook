# PLAN V5 — what is next (2026-07-27)

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
incl. the `_trim_leadin` bug) · **#40** (duplicate-book naming).

---

## 1. Automatic re-render of chunks that fail verification — #41

The highest-value item, and the direct answer to the constraint above.

The ASR layer already transcribes every chunk and computes divergence from the
source text. Today that produces a **report**. It should produce a **fix**.

- [ ] 1.1 On a chunk whose divergence exceeds threshold, re-render it with a
      different seed and keep the better of the two by WER.
- [ ] 1.2 Cap retries (2–3) so a pathological chunk cannot stall a book.
- [ ] 1.3 Log every retry with before/after WER — silent self-healing is its own
      kind of dishonesty, and this project has been bitten by that before.
- [ ] 1.4 Test: a chunk that transcribes badly triggers exactly one re-render;
      a clean chunk triggers none.

**Why it works:** the defects seen today — TADA saying "Ellis" for "Alice", the
stray `LEADIN` leaking through — are *sampling* artefacts, not systematic ones.
A different seed usually gets them right. This attacks the whole class without
naming any instance.

**Known limit, must be written into the code:** ASR normalises a mispronounced
proper noun back to the expected word. Verified 2026-07-27 — Whisper transcribed
a clearly-wrong "Alice" as "Alice", and a deliberately mis-spelled "Aliss" as
"Alice" too. So this catches drops, insertions and gross substitutions, **not**
pronunciation. Do not let a clean WER report imply a clean render.

## 2. Articles: RSS feed, so any podcast app works — #42

Dave, on the current Audiobookshelf podcast library: *"not very elegant… maybe
it's worth considering whether there's a better app."*

- [ ] 2.1 Serve the podcast folders as a standard RSS feed.
- [ ] 2.2 Feed metadata from the existing article record — title, site, date,
      source URL, duration.
- [ ] 2.3 Subscribe ABS to its own feed, or drop the second ABS library entirely.

**Why:** it decouples the destination from Audiobookshelf permanently. Pocket
Casts, Overcast, AntennaPod and ABS all subscribe to a URL. The second-library
awkwardness stops being a decision.

## 3. Articles: Telegram capture — #42

Dave: *"probably also worth deciding whether the web UI is best suited to
articles at the moment. My suggestion is it isn't."*

- [ ] 3.1 Send a link to the bot → it converts and replies with the audio.
- [ ] 3.2 Reuse the existing Telegram integration; no new auth, no new app.
- [ ] 3.3 Keep the URL tab for bulk work; it stops being the capture path.

**Why:** opening a web UI to save a link is the wrong shape for "as and when I
come across something". Telegram already works from phone and desktop.

## 4. Chatterbox Multilingual V3 for accents — #43

- [ ] 4.1 Install V3 (500M) and A/B against Nano `cfg_weight=0` on identical
      references.
- [ ] 4.2 If it wins, make it the accented-narrator engine.
- [ ] 4.3 Expose `cfg_weight` per voice — accented narrators default `0`,
      ordinary narrators stay `0.5`.

V3 is the only model in the Chatterbox family that claims **accent
preservation**. Nano and Turbo are English-only agent models. See VOICES.md.

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
- [ ] 6.4 Grade those A/Bs by ear. Keep the current path out of production now;
      call it a model/engine ceiling only after the direct-current clip also
      fails. Do not spend time on EQ until this cause split is measured.

---

## Done today, for reference

Numbers (`50k`, decades, decimal percents, the thousands comma modern engines
pause at) · hyphenated compounds no longer read with a pause · articles land in
an ABS podcast library grouped by site · TADA runs locally on CPU (#23, bf16,
RTF 1.68) · native-accent Piper voices installed · twelve bad accent clones
removed · `cfg_weight` identified as the accent lever.

Full detail: STATUS.md, VOICES.md, OPERATIONS.md, and the closed issues.

---

## Standing rules this plan inherits

- **Settle audio questions by ear, not argument.** Broken twice on 2026-07-27;
  both times the argument was wrong.
- **Read the code and the vendor's docs before researching.** Three things were
  re-derived on 2026-07-27 that the repo already had.
- **Test the link, the URL and the deploy before handing them over.**
- **A component that cannot do its job must say so.**
