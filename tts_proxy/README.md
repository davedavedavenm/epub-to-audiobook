# TTS Proxy (Transcript Capture)

Optional reverse proxy between the conversion container and Kokoro.

- Capture the exact text chunks sent to TTS.
- Store them under the stack `data/` volume: `data/transcripts/<job_id>/chunks.jsonl`.

Enable by setting `TTS_PROXY_URL=http://tts-proxy:8882` in the stack environment.
