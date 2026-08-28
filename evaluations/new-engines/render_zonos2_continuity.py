"""Corrective ZONOS2 gate using one persistent server and cached Arthur embedding."""

from __future__ import annotations

import base64
import json
import os
import shlex
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

from render_zonos2 import MODEL_REVISION, SOURCE_COMMIT, SOURCE_RELEASE
from shared import ARTHUR, OUTPUT, corpus, finish, parse_peak_rss, sentence_chunks, verify_reference


PORT = int(os.environ.get("ZONOS2_CONTINUITY_PORT", "19192"))
SESSION_ID = "epub-audition-zonos2-continuity"
SERVER_MAX_TOKENS = 2000
SAMPLE_RATE = 44100


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return str(resolved).replace("\\", "/")
    return f"/mnt/{drive}/{str(resolved)[3:].replace(chr(92), '/')}"


def _request(path: str, body: dict | None = None, timeout: int = 600) -> bytes:
    headers = {"X-TTS-Session-ID": SESSION_ID}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=data, headers=headers
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _wait_ready(process: subprocess.Popen, timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"ZONOS2 server exited early with {process.returncode}")
        try:
            if json.loads(_request("/health", timeout=2))["status"] == "ok":
                return
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            time.sleep(0.5)
    raise TimeoutError("ZONOS2 server did not become healthy")


def main() -> None:
    runtime = Path(os.environ["ZONOS2_RUNTIME_DIR"])
    models = Path(os.environ["ZONOS2_MODELS_DIR"])
    server = runtime / "zonos2-server"
    for required in (
        server,
        models / "zonos2-q4_k.gguf",
        models / "dac.gguf",
        models / "spk-encoder.gguf",
    ):
        if not required.is_file():
            raise RuntimeError(f"missing pinned ZONOS2 continuity input: {required}")

    _, prepared = corpus()
    mode = os.environ.get("ZONOS2_CONTINUITY_MODE", "full").strip().lower()
    all_sentences = sentence_chunks(prepared)
    if mode == "full":
        input_text = prepared
        chunks = all_sentences
        stem = "zonos2_arthur_q4_k_sentence_fixed"
        punctuation_adjustment = None
    elif mode == "iphone_split":
        original = next(
            chunk for chunk in all_sentences if chunk.startswith("Today the iPhone")
        )
        left, right = original.split(", and the App Store", 1)
        chunks = [left + ".", "And the App Store" + right]
        input_text = original
        stem = "zonos2_arthur_q4_k_iphone_split"
        punctuation_adjustment = (
            "replace the comma before 'and the App Store' with a sentence boundary; "
            "word content unchanged"
        )
    else:
        raise ValueError("ZONOS2_CONTINUITY_MODE must be full or iphone_split")
    reference = verify_reference()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    timing = OUTPUT / f"{stem}.time.txt"
    server_log = OUTPUT / f"{stem}.server.log"
    command = [
        "taskset",
        "-c",
        "0-3",
        "/usr/bin/time",
        "-v",
        "-o",
        _wsl_path(timing),
        _wsl_path(server),
        _wsl_path(models / "zonos2-q4_k.gguf"),
        "--dac",
        _wsl_path(models / "dac.gguf"),
        "--spk",
        _wsl_path(models / "spk-encoder.gguf"),
        "--cpu",
        "--batch",
        "1",
        "--host",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--max",
        str(SERVER_MAX_TOKENS),
    ]
    wsl_command = " ".join(shlex.quote(item) for item in command)
    started = time.perf_counter()
    with server_log.open("wb") as log:
        process = subprocess.Popen(
            ["wsl.exe", "-e", "bash", "-lc", wsl_command],
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            _wait_ready(process)
            speaker_payload = {
                "label": "Arthur continuity gate",
                "speaker_audio_name": ARTHUR.name,
                "speaker_audio_base64": (
                    "data:audio/wav;base64,"
                    + base64.b64encode(ARTHUR.read_bytes()).decode("ascii")
                ),
            }
            speaker = json.loads(_request("/tts/speakers", speaker_payload, timeout=60))
            speaker_id = speaker["id"]
            pieces: list[np.ndarray] = []
            chunk_durations: list[float] = []
            eos_settings = {
                "temperature": 1.15,
                "topk": 106,
                "top_p": 0.0,
                "min_p": 0.18,
                "repetition_window": 50,
                "repetition_penalty": 1.2,
                "repetition_codebooks": 8,
                "seed": 42,
                "max_tokens": SERVER_MAX_TOKENS,
                "accurate_mode": True,
                "clean_speaker_background": False,
                "stream": False,
                "format": "wav",
                "fade_out_ms": 0.0,
            }
            for index, chunk in enumerate(chunks):
                payload = {
                    "text": chunk,
                    "speaker_embedding_id": speaker_id,
                    **eos_settings,
                }
                wav_bytes = _request("/tts/generate", payload)
                chunk_path = OUTPUT / f"{stem}_chunk_{index + 1:02d}.wav"
                chunk_path.write_bytes(wav_bytes)
                audio, rate = sf.read(chunk_path, dtype="float32")
                if rate != SAMPLE_RATE or audio.ndim != 1 or len(audio) < SAMPLE_RATE // 2:
                    raise RuntimeError(f"invalid ZONOS2 chunk {index + 1}")
                pieces.append(audio)
                chunk_durations.append(round(len(audio) / rate, 3))
            wav = OUTPUT / f"{stem}.wav"
            sf.write(wav, np.concatenate(pieces), SAMPLE_RATE)
        finally:
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=15)

    finish(
        stem=stem,
        wav=wav,
        input_text=input_text,
        wall_seconds=time.perf_counter() - started,
        peak_rss_mib=parse_peak_rss(timing),
        minimum_duration_seconds=5 if mode == "iphone_split" else 10,
        report={
            "engine": "ZONOS2 official native GGUF",
            "arm": "q4_k_sentence_fixed" if mode == "full" else "q4_k_iphone_split",
            "runtime_release": SOURCE_RELEASE,
            "runtime_commit": SOURCE_COMMIT,
            "model_revision": MODEL_REVISION,
            "model_file": "zonos2-q4_k.gguf",
            "execution": "one persistent server; one cached Arthur embedding",
            "settings": eos_settings,
            "server_settings": {
                "backend": "CPU",
                "cpu_cap": 4,
                "batch": 1,
                "max_tokens": SERVER_MAX_TOKENS,
            },
            "chunk_strategy": "exact complete sentences; fixed settings; no added join silence",
            "punctuation_adjustment": punctuation_adjustment,
            "chunks": chunks,
            "chunk_lengths": [len(chunk) for chunk in chunks],
            "chunk_durations_seconds": chunk_durations,
            "join_silence_ms": 0,
            "input_path": "repository explicit preparation; native byte-tokenizer path",
            **reference,
        },
    )


if __name__ == "__main__":
    main()
