# Test Barrage

This repo is a stack project. Most real failures are integration failures (UI -> API -> DB -> docker-run -> TTS -> output).
The goal is fast feedback locally plus a smaller set of high-signal end-to-end checks.

## Fast checks (every change)

- Python compile:
  - `python -m py_compile webapp/app.py`
- Unit/regression tests:
  - `python -m unittest discover -s tests -p "test_*.py" -q`

## API contract checks (against a running stack)

- `/api/library` returns JSON array and includes `modified_ts`:
  - `curl -fsS http://localhost:8881/api/library | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list); print(len(d)); print(sorted(d[0].keys()))"`
- `/api/library/convert` returns JSON (not HTML) on success and failure.

## End-to-end smoke (tiny fixture)

1. Add a tiny EPUB fixture (2 short chapters) into the library folder.
2. Convert from Library.
3. Assert job transitions: `queued -> converting -> completed`.
4. Assert output dir contains `*.mp3`.

## Resilience tests

- Restart `webapp` during conversion; verify `worker` keeps it moving.
- Kill the conversion container; verify job marks failed and Retry works.

## UI tests (Playwright)

- Library convert works for titles containing apostrophes.
- Sorting controls reorder list and persist after reload.

## Transcript verification (optional)

Enable `tts_proxy/` to capture the *exact* chunk text sent to TTS, then compare it to text extracted from the EPUB.

- Set `TTS_PROXY_URL=http://tts-proxy:8882` in the stack env.
- On successful conversion the app writes `_verification/verification.json` into the output folder.

