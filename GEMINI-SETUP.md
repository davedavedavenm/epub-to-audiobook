# Gemini 3.1 Flash TTS setup (free tier only)

This app supports Google's `gemini-3.1-flash-tts-preview` through a deliberately
restricted backend adapter. Achernar has passed the project's long-form human
listening gate. The other 29 official presets are catalogue auditions until
their exact app previews have been cached and heard.

The integration has no Vertex endpoint, Batch route, paid model or paid-tier
fallback. It stops when the Free project reaches its limit. Do not attach Cloud
Billing to the project used here.

## 1. Create the project and key

1. Open [Google AI Studio](https://aistudio.google.com/) and accept its terms.
2. In **Dashboard → Projects**, create a dedicated project for audiobook TTS.
   Do not reuse a project linked to billing.
3. Confirm its Billing Tier says **Free**. A button saying **Set up billing** is
   expected; do not click it for this integration.
4. In **Dashboard → API Keys**, create a key in that project. New AI Studio keys
   are authorization keys by default. This matters because Google says standard
   keys stop working in September 2026.
5. Keep the key server-side. Never commit it, paste it into browser JavaScript,
   or put it in an issue/log. If an older key is marked unrestricted, use AI
   Studio's **Restrict to Gemini API only** action or replace it with an auth key.

Official references, checked 2026-08-15:

- [API-key creation and security](https://ai.google.dev/gemini-api/docs/api-key)
- [Billing tiers and how to verify Free](https://ai.google.dev/gemini-api/docs/billing)
- [Gemini TTS API and all 30 voices](https://ai.google.dev/gemini-api/docs/speech-generation)
- [Current pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 2. Configure the host

Copy `.env.example` to `.env` if this is a new installation, then set:

```dotenv
GEMINI_API_KEY=your_server_side_key
GEMINI_FREE_PROJECT_ID=the_exact_project_id_shown_in_ai_studio
GEMINI_FREE_PROJECT_CONFIRMED=1
ENABLE_GEMINI_PROFILE=1
```

`GEMINI_FREE_PROJECT_CONFIRMED=1` is an operator assertion, not a billing API.
Set it only after checking that exact project in AI Studio. The unbilled project
is the real safety boundary.

Deploy the complete stack:

```bash
./scripts/deploy.sh
```

Do not start just `gemini-tts`: webapp and worker must carry the same app
revision and voice catalogue.

## 3. Verify without consuming speech quota

These reads do not synthesize audio:

```bash
curl -fsS http://127.0.0.1:8881/api/health
curl -fsS http://127.0.0.1:8881/api/engines/health
curl -fsS http://127.0.0.1:8881/api/voices
docker logs --since 10m gemini-tts
```

Expected state: app health is `ok`, `gemini` is `true`, and the Gemini adapter
log contains only `GET /health` and `GET /v1/audio/voices` until someone
explicitly requests a preview or conversion.

## 4. Cache voice previews deliberately

The Voices page only offers presets whose exact MP3 already exists under
`/data/previews`. Play never triggers synthesis.

In **Settings → Gemini**, **Prepare next missing Gemini preview** makes at most
one upstream request. A cache hit makes none. The API also accepts an explicit
bounded batch for an operator who has first checked the remaining allowance:

```bash
curl -fsS -X POST http://127.0.0.1:8881/api/settings/prepare_gemini_preview \
  -H 'Content-Type: application/json' \
  -d '{"limit": 1}'
```

Use `voice_id` to target one preset, for example:

```json
{"voice_id":"gemini_gacrux","limit":1}
```

The local adapter independently records every attempted upstream request and
refuses an eleventh request in one Pacific quota day. Google documents that
rate limits apply per project—not per key—and RPD resets at midnight Pacific.
The local ledger is deliberately conservative: failed upstream attempts remain
counted and are never retried automatically. Check **AI Studio → Dashboard →
Usage** before any catalogue batch because requests made outside this app are
not visible to the local ledger.

## 5. Convert and resume a book

Choose an already-cached Gemini narrator for a book. The worker:

- applies the explicit number/currency profile;
- packs complete paragraphs into at most 2,200 characters per request;
- writes every successful passage to the resume cache;
- makes exactly one attempt per passage;
- stops on 429, 500, timeout or malformed output.

After the next quota window, use the job's manual **Resume** action. Completed
passages are reused, so resuming does not regenerate them. Never enable a paid
fallback to finish a book.

## Data and preview limitations

Google states that Free Tier prompts and outputs may be used to improve its
products. Do not submit private or confidential books unless that term is
acceptable. The TTS model is Preview and may change. A preset's official label
(for example `Warm` or `Mature`) is not proof of gender, nationality, accent or
audiobook quality; only the cached app-path audition and human listening verdict
establish those properties for this project.
