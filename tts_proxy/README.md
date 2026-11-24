# TTS Proxy (Transcript Capture)

Internal proxy for Kokoro and proxy-routed hosted engines. Direct local
engine routes do not pass through this service.

- Capture the exact text chunks sent to TTS.
- Store them under the stack `data/` volume in `data/transcripts/<job_id>/`.
  The book converter also captures requests for direct engines.

Enable by setting `TTS_PROXY_URL=http://tts-proxy:8882` in the stack environment.
