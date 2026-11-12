# Shared narrator audition standard

Approved by Dave on 11 November 2026. Every agent evaluating a narrator must use
this standard before any supplementary book, accent or pronunciation test.

## One source, two listening questions

The authoritative text is `webapp/voice_sample.py`, sample ID
`narrator-standard-v1`. Its UTF-8 SHA-256 is
`386e062ef7020b882240cf512ba7c886be75b3d20dede6b60360b5c1bf3d8dc7`.
Do not maintain a second prose literal in a script or notebook. Import
`sample_text_for(engine)`; notebook builders must inject its result and the
sample ID/hash. Changes to the approved passage require a new version and Dave's
agreement; never silently replace an existing version.

The first paragraph is ordinary narration. Judge voice, pacing, fatigue and
naturalness here independently of the following pronunciation challenge.

> The room grew quiet as the visitors took their seats. Outside, rain tapped against the windows, but nobody seemed in a hurry to leave. The speaker paused, looked around the table, and began a story about the people who had helped her understand a changing world.
>
> In 2026, Dr. Helen Carter travelled from the United Kingdom to South Africa, Kenya, Nigeria and China. In Johannesburg, Amina Okafor and David Williams discussed Nelson Mandela, Desmond Tutu and the election of 1994. In Beijing, Wang Wei and Li Na compared reports from Huawei and Xiaomi.
>
> The meeting began at 9:30 a.m. on 12 March. Of the 1,250 people invited, 875 attended. Ticket prices rose by 7.5%, from £24.60 to £26.45. A separate project cost $1.2 million and covered 3.5 kilometres. "Are these the final figures?" Helen asked. "Yes," David replied, "but the next report is due on 21 April."

Irish and Zulu tests remain optional, separately labelled tracks. An Irish-name
failure does not by itself reject a voice for ordinary books. Quotation marks
test phrasing; they do not imply automatic speaker casting.

## Fair input and reproducible settings

- One source passage for every engine, with the **same preprocessing that the
  engine receives for books**. Engine contracts differ: explicit number expansion
  for the CPU narrator adapter and Deepgram, existing modern-engine treatment for
  Chatterbox, and the existing legacy lexicon for Kokoro/Edge. Record the exact
  prepared payload and its hash; do not claim these engine payloads are identical.
- Audition-only Maya2 Native, VoxCPM2 and the Higgs3 native default voice have no
  book route for these voices. Their named helper contracts
  (`sample_text_for('maya2')` / `sample_text_for('voxcpm2')` / `'higgs3'`) return
  the approved source for the native API; each voice declares that preview
  contract explicitly. Record internal engine normalization separately: Maya's
  documented numeric-text recommendation is `normalize=True`; VoxCPM2's current
  native default is `normalize=False`. This is not a fallback for missing
  dependencies or an inferred production preparation policy. Higgs3's default
  audition uses its documented text-only API input; it does not claim parity
  with the separate locked Cillian book pipeline or rerun its book-specific prep.
- Prepare app-normalized payloads with the application dependencies installed,
  then freeze the text and source/prepared hashes before sending to an isolated
  model environment. Missing `num2words` must fail preparation explicitly: the
  legacy normalizer's optional-dependency fallback can silently change the text,
  including for modern engines. Do not recompute inside a lean Modal CLI or
  inference environment and call the different result equivalent.
- Read `DECISIONS.md`, `VOICES.md`, `PREPROCESSING.md`, and the exact upstream
  model/runtime documentation first. `TUNING-AUDIT-2026-11.md` records the current
  evidence, not perpetual permission to skip checking changed versions.
- Record model and runtime revisions, voice/reference identity and hash, seed,
  all overrides, chunking, synthesis time, audio duration, device and transcoding.
  An override being supported does not mean it is optimal. Change one variable
  in a tuning A/B; retain the baseline and disclose regenerated takes.
- Check completeness using independent, unprompted ASR and duration. ASR errors
  on names are not pronunciation verdicts. Only Dave's listening can approve
  naturalness, accent retention or preference.
- Recheck timeouts when changing text length. Render serially with bounded CPU
  threads; protect the live UI. No paid GPU service follows from this standard.

## Cached previews and earlier evidence

Keep existing previews playable while replacing them with verified new samples.
Write `<voice_id>.sample.json` with `preview_manifest.write_manifest` after the
audio is final. It binds the sample ID, source/payload hashes and audio hash.
The UI labels a matching recording **Shared test v1**; files without matching
provenance remain **Earlier audition**. A Play click must never cold-generate.
Verify every promoted ID through `/api/voices` and `/api/preview/<voice_id>`.

Do not relabel old audio, erase listening history, or infer a new Like from an
older recording. Historical hash-pinned reproductions may explicitly request
`legacy-apple-2026`; targeted diagnostics may keep their named micro-test. These
exceptions must not become the default for new narrator comparisons.
