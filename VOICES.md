# Voices and accents

**Last updated: 2026-07-27.** What works, what does not, and the wrong turns —
recorded so nobody walks back down them. Every claim here was heard or measured,
not reasoned about; where something is untested it says so.

---

## The one rule

**An accent lives in the model, not in the reference clip.**

Zero-shot voice cloning takes *timbre* from your reference and *phonetics* from
its own training data. If that training data is predominantly American English,
an Irish reference gives you an Irish-sounding voice saying American vowels.

**This was tested to destruction on 2026-07-27. Three engines, four attempts,
one result:**

| Attempt | Engine | Reference | Dave's verdict |
|---|---|---|---|
| 1 | Chatterbox Nano | raw VCTK clips | *"those accents are shit"* |
| 2 | Chatterbox Nano | native-accent Piper prose | *"softened the shit out of the voices and made them american"* |
| 3 | Chatterbox Turbo | same | *"irish 'ok'… not amazing"* |
| 4 | **XTTS-v2** | Edge Irish/ZA + Piper Scottish | *"bullshit, americanised crap"* |

XTTS is a completely different architecture from Chatterbox and is widely
described as preserving accent. **It did not.** That is what makes this a rule
rather than a quirk: it is not about which cloner you pick.

**Do not attempt accent cloning again on any engine** without evidence that the
model was *trained* on the accent. A fourth attempt needs a reason, not a hunch.

Working accents come from models trained per-speaker (Piper's
`en_GB-vctk-medium`, trained on the VCTK speakers) or per-locale (Edge's
`en-IE-*`, `en-AU-*`). Those hold up.

`cfg_weight` (below) moves the needle on Chatterbox but does not escape the rule.

---

## The local-vs-cloud problem, and what is being done about it

Dave, 2026-07-27, on the Edge voices: *"those voices are decent. how do we get
those on a local model? did you check? we can't be the only ones to want this."*

He was right that I hadn't checked. The actual landscape for **local** accented
English:

| Model | English accents | Local | Status here |
|---|---|---|---|
| **Kokoro** | US, UK **only** | yes | running — checked live, no Irish/Australian |
| **Piper** | UK, US; Irish/Scottish/Welsh/Australian via VCTK speakers | yes | installed — real accents, but dry and close-mic'd |
| **MeloTTS** | US, UK, Indian, **Australian**, default | yes | **not installed**; no Irish |
| **XTTS-v2** | clones from a reference; reported to carry accent | yes | **being tested** — see below |
| **Chatterbox** Nano/Turbo | none. English-only, American phonetics | yes | proven twice not to hold an accent |
| **Edge** | IE, AU, NZ, GB, ZA, IN, CA, HK, KE, NG, PH, SG, TZ, US | **no** | works, graded good, needs internet |

Edge's full English list was checked live and is worth knowing: it has **Irish
male and female** (Connor, Emily), Australian, New Zealand, South African and
five British voices. **No Welsh anywhere**, on any engine, cloud or local.

### XTTS-v2 — tested and rejected

**Result: failed, same as Chatterbox.** Dave: *"bullshit, americanised crap"*.
Image reverted to `-min`, the 8 GB reclaimed, `tts-1-hd` entries deleted from the
voice map. Piper natives re-verified working afterwards.

This was the strongest remaining candidate — different architecture, widely
described as accent-preserving, fed genuinely accented references (Edge Connor
and Luke; Piper VCTK p272 for Scottish, since **Edge has no Scottish English
voice at all**). It still flattened them. That failure is what turned "Chatterbox
can't do accents" into the general rule at the top of this file.

To bring XTTS back for some *other* job — it is a capable cloner, just not an
accent one — set `PIPER_IMAGE=ghcr.io/matatonic/openedai-speech:latest`. Licence
is Coqui Public Model License, non-commercial.

<details>
<summary>Original write-up, kept for the reasoning (it was sound; the result was not)</summary>

The Piper container was running `openedai-speech-**min**`, which is Piper-only.
The **full** `openedai-speech` image also ships **XTTS-v2**, and
`voice_to_speaker.yaml` already had `tts-1-hd` XTTS entries waiting for it. One
image tag.

XTTS is a different architecture from Chatterbox and clones from a reference
clip while reportedly keeping the accent. That is precisely the property
Chatterbox lacks, so it is the honest local answer to *"can I have the Edge
voices without the cloud"*.

Under test (`tts-1-hd` model): `xtts_irish_m`, `xtts_scottish_m`,
`xtts_southafrican_m`. References are ~16–21 s of continuous prose — Irish and
South African cloned from the Edge locale voices, Scottish from Piper's native
VCTK p272 **because Edge has no Scottish English voice at all**.

**Licence:** XTTS-v2 is Coqui Public Model License, **non-commercial**. Fine for
a personal library; revisit before any commercial use.

</details>

### Candidate models, evaluated 2026-07-27

Dave sent five to look at, with: *"it took me 5 minutes to find these."* Fair —
this should have been my sweep, not his. Evaluated against the one question that
matters: **does it ship accents trained into the model, or is it another
cloner?**

| Model | Mechanism | English accents | Verdict |
|---|---|---|---|
| **[MeloTTS](https://github.com/myshell-ai/MeloTTS)** | **trained per-accent** | `EN-US`, `EN-BR`, `EN_INDIA`, `EN-AU`, `EN-Default` | **Best fit.** Sidesteps the rule entirely. Confirmed by loading the model on CPU and reading its own speaker table — not from the README. **No Irish.** |
| **[Fish-Speech / S2](https://github.com/fishaudio/fish-speech)** | cloning **+ free-form text tags** | 80+ languages; supports a literal `[with strong accent]` tag and 15,000+ free-form delivery descriptors | **Worth testing.** The tag interface is a genuinely different control surface from cloning — it may reach accents the clone path cannot. |
| **[Orpheus-TTS](https://github.com/canopyai/Orpheus-TTS)** | zero-shot cloning + named voices | English voices (tara, leah, jess, leo, dan, mia, zac, zoe); no accent variants | Cloning half will hit the rule. **But it ships fine-tuning tooling and data-processing scripts** — the supported route to a custom local voice. 3B, heavy on CPU. ⚠️ Their own guidance: *"I recommend not using synthetic data for training as it produces worse results"* — a direct warning against distilling Edge output, which is worth knowing **before** attempting the distil path below. |
| **[Dia2-2B](https://huggingface.co/nari-labs/Dia2-2B)** | dialogue TTS, context conditioning | English only, 2-minute cap | Wrong tool. Built for speech-to-speech dialogue turns, not narration, and not accent-targeted. |
| **[VibeVoice](https://microsoft.github.io/VibeVoice/)** | long-form multi-speaker cloning | — | Same wall as other cloners. The repo has also pivoted heavily to **ASR** (recent releases are all VibeVoice-ASR). |

**Order to pursue:** MeloTTS → Fish-Speech → Orpheus. Dia2 and VibeVoice are the
wrong shape for this.

### So what is actually left for local accented English

Cloning is exhausted. Only two routes remain, and both mean a model **trained**
on the accent:

1. **Use what already works and fix its one flaw.** Piper native VCTK has real
   Irish, Scottish, Northern Irish, Welsh-female and Australian-male accents.
   The only complaint is that they sound dry and close-mic'd — VCTK was recorded
   in an anechoic chamber. That is a post-processing problem (EQ, a little room),
   not a model problem, and unlike accent it does not fight anything. **This is
   the cheapest real win available.**
2. **Distil a cloud voice into a local model.** Generate a few hours of Edge
   `en-IE-ConnorNeural` audio with known transcripts, then fine-tune a Piper
   model on it. The output is a genuinely local model whose weights hold the
   accent — which is the only thing that has ever worked. Piper fine-tuning is
   documented and runs on modest hardware. Slower and more involved, but it is
   the honest answer to *"how do we get those voices locally"*.

3. **MeloTTS for the accents it has.** Confirmed working on CPU with five native
   English accents. Covers Australian and British outright. Not Irish.

**Note on (2), before anyone starts:** Orpheus's own training guide advises
*against* fine-tuning on synthetic data — it says synthetic voices "lack
diversity and map to the same set of tokens when tokenised". Distilling Edge is
exactly that. It may still work (Piper fine-tunes are less sensitive than a 3B
LLM-based model), but go in expecting to have to prove it, and prefer real
recorded speech if any is available.

---

## What to use

| Accent | Voice | Engine | Local? |
|---|---|---|---|
| Irish male | `vctk_irish_m_p364_native` (Donegal), `_p245_` (Dublin) | Piper | yes |
| Irish female | `vctk_irish_f_p288_native` (Dublin), `_p283_` (Cork) | Piper | yes |
| Northern Irish | `vctk_northernirish_m_p292_native` / `_f_p293_` (Belfast) | Piper | yes |
| Scottish | `vctk_scottish_m_p272_native` / `_f_p262_` (Edinburgh) | Piper | yes |
| Welsh female | `vctk_welsh_f_p253_native` (Cardiff) | Piper | yes |
| Australian male | `vctk_australian_m_p326_native` (Sydney) or `en-AU-WilliamNeural` | Piper / Edge | yes / **no** |
| Australian female | `en-AU-NatashaNeural` | Edge | **no** |
| British / general narration | `uk_male_minter` (Arthur) etc. | Chatterbox Nano | yes |

Dave's grading, 2026-07-27: the Piper natives are **"not bad… some sound a bit
tinny or distant"**. The Edge Australians are **"good"**. The Chatterbox clones
of the same speakers were **"utter shit"**.

### Gaps that are the corpus, not the code

VCTK is 110 speakers and supplies every native accent above. It contains
**exactly two Australians, both male**, and **exactly one Welsh speaker, female**.

- **No Australian female** in VCTK → Edge covers it.
- **No Welsh male** anywhere I could find. Piper ships no `en_AU` model at all,
  and `rhasspy/piper-voices` has only `en_GB` and `en_US` English. Closing this
  needs a fine-tune on accent-tagged Common Voice data, or nothing.

`cy_GB` Piper voices speak the **Welsh language**, not English with a Welsh
accent. Tested: feeding them English produced Welsh gibberish (ASR heard
*"U'n gynill yn ymwandsyn yn gallu srwy"*). Do not try this again.

---

## `cfg_weight` — the accent lever, and the thing I missed all day

`chatterbox/server.py` accepts `cfg_weight` and `exaggeration` per request and
has done since it was written. **Default is 0.5.** Every clip rendered on
2026-07-27 used that default until the very end.

From Resemble's own README, describing the inverse problem:

> *"language transfer outputs may inherit the accent of the reference clip's
> language. To mitigate this, set `cfg_weight` to `0`."*

Read the other way round: **low `cfg_weight` lets the reference's accent through;
high `cfg_weight` lets the model's own American phonetics dominate.** The
default was actively destroying the thing being attempted.

**Measured by ear (Dave, 2026-07-27):** Nano at `cfg_weight=0` is the best
Chatterbox result so far — *"nano cfg 0 is best, but could be better"*. Still
short of the Piper natives for accent fidelity.

Other documented settings, untested here:

- `exaggeration` default `0.5`; `~0.7+` for dramatic delivery, speeds speech up.
- Pair higher `exaggeration` with lower `cfg_weight` for slower pacing.

---

## Model zoo (from Resemble's README, which I should have read first)

| Model | Size | Languages | Notes |
|---|---|---|---|
| Chatterbox-Nano | 110M | **English only** | On-device/CPU, 3× realtime on 8 cores. What we render books with. |
| Chatterbox-Turbo | 350M | **English only** | Built for low-latency voice agents. |
| **Chatterbox-Multilingual V3** | **500M** | 23+ | Headline feature: *"improves voice identity and **accent preservation**"*. **NOT INSTALLED — this is the next thing to try.** |
| Chatterbox (original) | 500M | English | CFG & exaggeration tuning. |

Nano and Turbo are English-only agent models that make **no claim about accent
fidelity**. V3 is the one built for it. That we are chasing accents on Nano is a
consequence of never having read this table.

---

## Failures, 2026-07-27

Recorded because each cost real time and each is repeatable by someone who
doesn't know.

**1. Never read the engine's documentation.** Ran an entire day of accent work
against `cfg_weight=0.5` — the setting Resemble's README says to change for
exactly this problem — and never opened the Model Zoo, which says plainly that
Nano and Turbo are English-only agent models. Dave: *"did you bother to consult
chatterbox docs and repo to actually check?"* No.

**1b. Did not sweep the field.** After four cloning failures I was still
reaching for more cloners instead of asking which models ship *trained* accents.
Dave found MeloTTS, Fish-Speech, Orpheus, Dia2 and VibeVoice in five minutes and
sent them over. MeloTTS — five native English accent variants, exactly the
architecture that works — was the obvious first stop and I had not looked at it.
**When a class of approach fails repeatedly, survey the alternatives instead of
producing another instance of the failing class.**

**2. Re-researched what the repo already contained. Three times.**
The VCTK accent voices were already installed. The Edge Australian voices were
already installed. The `LEADIN` cold-start fix was already in `tada/server.py`.
Each was "discovered" from scratch. **Read the code and the voice list before
researching anything.**

**3. Concluded correctly, then argued myself out of it — twice.** I established
that cloning carries timbre but not phonetics, then hypothesised that better
reference audio would fix it, rebuilt nine voices, and shipped them **without
listening**. Dave: *"you softened the shit out of the voices and made them
american"*. Reverted entirely.

Then did the same shape again with XTTS-v2: pulled an 8 GB image on the strength
of a reputation for accent preservation, without a single clip to back it.
Dave: *"bullshit, americanised crap"*. Reverted, image deleted.

The second one was worth running — XTTS is genuinely different architecture, and
its failure is what made the rule general instead of Chatterbox-specific. But
the honest framing is: **the rule was already visible after attempt one**, and
attempts two through four cost hours to confirm it.

**4. Blamed the model for our own bug.** Reported that TADA "invented a word
that was not in the text". It was `LEADIN = "Right. "`, which we prepend
deliberately and `_trim_leadin()` intermittently fails to cut. The answer was in
our source the whole time.

**5. Invented a measurement.** Claimed the hyphen fix "measurably" removed ~1
second of dead air, from a file-size delta between two generations of different
text on a non-deterministic engine. Not a measurement. Retracted in
`tts_preprocess.py`.

**6. Overstepped a contract on inference.** Spelled bare decades for modern
engines, which the MODERN-ENGINE CONTRACT forbids without an ear test. A
regression guard caught it. The guard was right.

**7. Handed over a URL I never opened.** `/api/sample/ab_tada_cpu` 404'd because
the name was never added to the endpoint allowlist. **Test the link before
sending it.**

**8. Deployed half the stack.** `docker compose up -d --build webapp` leaves
`worker` on old code; they share `app.py`. The stale worker silently reverted a
database field. `/api/health` reports the *webapp's* version, so it looked
current. Use `scripts/deploy.sh`. See OPERATIONS.md.

---

## How the pieces fit

- **Piper** — `piper/voice_to_speaker.yaml` maps voice ids to model + speaker
  index. Speaker indices come from the model's own `speaker_id_map`, **not** the
  VCTK number: `p364` is index `106`. Config and models are bind-mounted
  (`piper/config`, `piper/voices`) because the image keeps both inside `/app`
  where edits are lost on recreate. `scripts/piper_setup.sh` copies the stock
  models out of the image first — the mounts shadow the image directory, so
  skipping that step removes the built-in voices.
- **Chatterbox** — reference WAVs in `chatterbox/voices/` (baked into the image)
  and `CUSTOM_VOICES_DIR` = `data/voices` (overlaid at `/app/voices/custom`, no
  rebuild needed). That directory is owned by the container uid; **write to it
  through the container**, not from the host.
- **Reference clips** — 8–45 s (`REF_MIN_SECONDS`/`REF_MAX_SECONDS`). Continuous
  prose beats disconnected sentences. Quality of the reference changes timbre,
  **not** accent.

---

## Next, in order

1. **Install Chatterbox Multilingual V3** and A/B it against Nano `cfg_weight=0`
   on the same references. It is the only model in the family that claims accent
   preservation, and it is the honest answer to "can I have these accents on a
   good-sounding engine".
2. **Expose `cfg_weight` per voice**, so accented narrators default to `0` and
   ordinary ones stay at `0.5`.
3. **De-tinny the Piper natives.** VCTK was recorded in an anechoic chamber on a
   headset mic and the models inherited that dry close-mic sound — Dave's "tinny
   or distant". Light EQ and a touch of room in post. Does not fight the model,
   unlike the accent.
4. **Welsh male** — fine-tune on accent-tagged Common Voice, or accept the gap.
