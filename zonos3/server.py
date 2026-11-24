"""Serve the pinned local ZONOS3-Mini Imogen voice over the OpenAI TTS API."""

import io
import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen

VOICE_ID = "zonos3_imogen_audition"
NATIVE_VOICE_ID = "default_b78b28baf5c31a1d"
NATIVE_URL = "http://127.0.0.1:19190"
DECODER = "keep2_plain"
MAX_BODY_BYTES = 32 * 1024
MAX_INPUT_CHARS = 4096
NATIVE_CHARS = 900
NATIVE_WORDS = 150
MAX_SECONDS_PER_CHUNK = 125
NATIVE_AUDIO_BYTES = 12 * 1024 * 1024
REQUEST_TIMEOUT = 360
PCM = (1, 2, 44100)
LOGGER = logging.getLogger(__name__)

WORD = re.compile(r"\S+\s*")
SENTENCE_END = re.compile(r"""(?<=[.!?])["”’)]*\s+""")
ABBREVIATION = re.compile(r"\b(?:dr|mr|mrs|ms|prof|st|sr|jr|vs)\.$|(?:\b[a-z]\.){1,}$", re.I)


def split_text(text: str) -> list[str]:
    """Preserve the input exactly, preferring sentence edges inside native limits."""
    chunks = []
    while len(text) > NATIVE_CHARS or len(text.split()) > NATIVE_WORDS:
        words = list(WORD.finditer(text[:NATIVE_CHARS + 1]))
        ends = [word.end() for word in words[:NATIVE_WORDS]
                if word.end() <= NATIVE_CHARS and text[word.end() - 1].isspace()]
        limit = ends[-1] if ends else NATIVE_CHARS
        sentences = [edge.end() for edge in SENTENCE_END.finditer(text, 0, limit)
                     if edge.end() >= limit // 2 and not ABBREVIATION.search(text[:edge.start()])]
        cut = sentences[-1] if sentences else limit
        chunks.append(text[:cut])
        text = text[cut:]
    if text:
        chunks.append(text)
    return chunks


def _native_json(path: str, timeout: float):
    with urlopen(NATIVE_URL + path, timeout=timeout) as response:
        return json.load(response)


def _native_wav(text: str, timeout: float) -> bytes:
    payload = json.dumps({
        "text": text,
        "speaker_embedding_id": NATIVE_VOICE_ID,
        "speaker_mode": "reference",
        "language": "en_gb",
        "text_normalization": True,
        "decoder": DECODER,
        "stream": False,
        "format": "wav",
        "seed": 42,
    }, ensure_ascii=False).encode("utf-8")
    request = Request(NATIVE_URL + "/v2/generate", data=payload, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if response.headers.get("X-Decoder") != DECODER or response.headers.get("X-Seed") != "42":
            raise ValueError("Unexpected ZONOS3 decoder or seed")
        audio = response.read(NATIVE_AUDIO_BYTES + 1)
    if len(audio) > NATIVE_AUDIO_BYTES:
        raise ValueError("Oversized ZONOS3 audio")
    return audio


def _checked_frames(audio: bytes) -> bytes:
    with wave.open(io.BytesIO(audio), "rb") as wav:
        frames = wav.getnframes()
        if wav.getparams()[:3] != PCM or not 0 < frames < PCM[2] * MAX_SECONDS_PER_CHUNK:
            raise ValueError("Unexpected ZONOS3 audio format or possible truncation")
        samples = wav.readframes(frames)
    if len(samples) != frames * PCM[1]:
        raise ValueError("Truncated ZONOS3 WAV")
    return samples


def _synthesize(text: str) -> bytes:
    started = time.monotonic()
    result = io.BytesIO()
    with wave.open(result, "wb") as output:
        output.setnchannels(PCM[0])
        output.setsampwidth(PCM[1])
        output.setframerate(PCM[2])
        chunks = (chunk for chunk in split_text(text) if chunk.strip())
        for index, chunk in enumerate(chunks):
            remaining = REQUEST_TIMEOUT - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("ZONOS3 request deadline elapsed")
            if index:
                output.writeframes(b"\0\0" * (PCM[2] // 4))
            output.writeframes(_checked_frames(_native_wav(chunk, remaining)))
    return result.getvalue()


def _mp3(wav: bytes) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", "pipe:0",
         "-c:a", "libmp3lame", "-b:a", "128k", "-f", "mp3", "pipe:1"],
        input=wav, capture_output=True, check=True, timeout=30,
    )
    if not result.stdout:
        raise ValueError("Empty ZONOS3 MP3")
    return result.stdout


class SpeechServer(ThreadingHTTPServer):
    def __init__(self, process: subprocess.Popen, address=("0.0.0.0", 8080)):
        super().__init__(address, SpeechHandler)
        self.process = process
        self.synth_slot = threading.Lock()


class SpeechHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def _respond(self, status, media_type, body, *, retry_after=None):
        try:
            self.send_response(status)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(body)))
            if retry_after is not None:
                self.send_header("Retry-After", str(retry_after))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            LOGGER.info("Client disconnected during ZONOS3 response")

    def _json(self, status, body, **headers):
        self._respond(status, "application/json", json.dumps(body).encode("utf-8"), **headers)

    def _error(self, status, message, **headers):
        self._json(status, {"error": {"message": message}}, **headers)

    def do_GET(self):
        if self.path not in ("/health", "/v1/audio/voices"):
            self._error(404, "Unknown route")
        elif self.server.process.poll() is not None:
            self._error(503, "ZONOS3 is unavailable")
        elif self.path == "/health":
            self._json(200, {"status": "ok", "engine": "zonos3", "device": "cpu"})
        else:
            self._json(200, {"voices": [{"id": VOICE_ID}]})

    def do_POST(self):
        if self.path != "/v1/audio/speech":
            self._error(404, "Unknown route")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("Invalid content length")
            body = json.loads(self.rfile.read(length))
        except (ValueError, TimeoutError):
            self._error(400, "A valid JSON request body is required")
            return
        if not isinstance(body, dict) or body.get("voice") != VOICE_ID:
            self._error(400, f"voice must be {VOICE_ID}")
            return
        text = body.get("input")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_INPUT_CHARS:
            self._error(400, f"input must contain 1–{MAX_INPUT_CHARS} characters")
            return
        output_format = body.get("response_format", "mp3")
        if not isinstance(output_format, str) or output_format.lower() not in ("mp3", "wav"):
            self._error(400, "response_format must be mp3 or wav")
            return
        if body.get("speed", 1.0) != 1.0:
            self._error(400, "Only speed=1.0 is supported")
            return
        if self.server.process.poll() is not None:
            self._error(503, "ZONOS3 is unavailable")
            return
        if not self.server.synth_slot.acquire(blocking=False):
            self._error(429, "ZONOS3 is already synthesizing", retry_after=5)
            return
        try:
            wav = _synthesize(text)
            if output_format.lower() == "wav":
                self._respond(200, "audio/wav", wav)
            else:
                self._respond(200, "audio/mpeg", _mp3(wav))
        except TimeoutError:
            LOGGER.exception("ZONOS3 synthesis timed out")
            self.server.process.terminate()
            self._error(504, "ZONOS3 synthesis timed out")
        except (OSError, ValueError, EOFError, wave.Error, subprocess.SubprocessError):
            LOGGER.exception("ZONOS3 synthesis failed")
            self._error(502, "ZONOS3 failed to produce audio")
        finally:
            self.server.synth_slot.release()


def _wait_until_ready(process: subprocess.Popen):
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ZONOS3 exited during startup ({process.returncode})")
        try:
            capabilities = _native_json("/v2/capabilities", 3)
            speakers = _native_json("/v2/speakers", 3)
        except (URLError, TimeoutError):
            time.sleep(.5)
            continue
        if capabilities["decoder"]["id"] != DECODER or capabilities["speaker_mode_default"] != "reference":
            raise RuntimeError("Pinned ZONOS3 decoder or speaker mode unavailable")
        if not any(s["id"] == NATIVE_VOICE_ID and "reference" in s["speaker_modes"] for s in speakers["speakers"]):
            raise RuntimeError("Pinned ZONOS3 Imogen reference preset unavailable")
        _checked_frames(_native_wav("Ready.", 30))
        return
    raise TimeoutError("ZONOS3 did not become ready")


def main():
    logging.basicConfig(level=logging.INFO)
    threads = int(os.environ.get("ZAC_THREADS", "4"))
    if not 1 <= threads <= 8:
        raise ValueError("ZAC_THREADS must be between 1 and 8")
    command = [
        "/opt/zonos3/zonos3-server", "/models/backbone-ptq.gguf", "--cpu", "--zac-cpu",
        "--host", "127.0.0.1", "--port", "19190", "--batch", "1", "--zac-threads", "1",
        "--tts-default-voices-dir", "/models/voices",
    ]
    process = subprocess.Popen(command)
    signal.signal(signal.SIGTERM, lambda *_: process.terminate())
    try:
        _wait_until_ready(process)
        with SpeechServer(process) as service:
            def stop_on_native_exit():
                process.wait()
                service.shutdown()

            threading.Thread(target=stop_on_native_exit, daemon=True).start()
            LOGGER.info("ZONOS3 Imogen ready on port 8080")
            service.serve_forever()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    if process.returncode not in (0, -signal.SIGTERM):
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
