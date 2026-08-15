#!/usr/bin/env python3
"""Render controlled Chatterbox model and human-reference diagnostics.

This is an evaluation harness, not an app voice-cache path.  Every arm uses
the exact same production-normalized hard passage, seed and server chunker.
The three model arms share Arthur; the accent arms change only the declared
human reference. It refuses to run while a conversion is active or queued and
writes all evidence under ignored ``scratch/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_REF = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
ARTHUR_BYTES = 864_182
TADHG_SHA256 = "5f9190dc1923d4741e889fedf14671642c09171ddcc8ac8145c3b501cf125ea6"
TADHG_BYTES = 864_208
VCTK_P374_SHA256 = "f1db6a7a352526cdf867b27ec7ebfd00538b8f88375953217c1b212756725c73"
VCTK_P374_BYTES = 864_078
ACTIVE_STATUSES = {
    "queued", "preparing", "running", "verifying", "syncing",
    "recovering", "converting", "converting pdf", "converting to audio",
}
SEED = 12_345
OFFICIAL_URL = "https://github.com/resemble-ai/chatterbox"
PYTORCH_REPRO_URL = "https://docs.pytorch.org/docs/2.6/notes/randomness.html"
EXPECTED_INPUT_SHA256 = "9a4b6bd1f48b6f745f53ceb284306b3d57488fe565af9736b9f4d47e3fffe083"
EXPECTED_NORMALIZED_SHA256 = "896a1789614a103df34f29eca27353d3ebe7d969c2880abd43a340dff63c2824"
EXPECTED_CHUNK_SHA256 = (
    "4c8d82e0f8a3150b33216b3486d8dc8c20a52cf23e3b527b774e89e2d0b61872",
    "5f06b4118ad2625465d94e47a3c400517f163205549a9da81617927d4ddab1df",
    "8924022538c7f68a87cb890a8fcec5ab9ea77b2f6553d2712d96029cd45683c6",
    "2730fcd535691b88d3a6633f408128cd822aadcdf0f7735053cbc1ac4b072b87",
)
ARMS = (
    {
        "id": "arthur-turbo",
        "container": "chatterbox-tts",
        "url": "http://127.0.0.1:8004",
        "cfg_weight": 0.5,
        "exaggeration": 0.5,
        "model_repo": "ResembleAI/chatterbox-turbo",
        "model_snapshot": "749d1c1a46eb10492095d68fbcf55691ccf137cd",
        "multilingual_v3": False,
        "voice": "uk_male_minter",
        "reference_sha256": ARTHUR_SHA256,
        "reference_bytes": ARTHUR_BYTES,
        "reference_source": "User-authorized human Arthur narration reference",
        "note": "Turbo's pinned generate() ignores CFG/exaggeration controls",
    },
    {
        "id": "arthur-v3-cfg-0",
        "container": "chatterbox-v3",
        "url": "http://127.0.0.1:8009",
        "cfg_weight": 0.0,
        "exaggeration": 0.5,
        "model_repo": "ResembleAI/chatterbox",
        "model_snapshot": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        "multilingual_v3": True,
        "voice": "uk_male_minter",
        "reference_sha256": ARTHUR_SHA256,
        "reference_bytes": ARTHUR_BYTES,
        "reference_source": "User-authorized human Arthur narration reference",
        "note": "Previously deployed V3 setting; not the same-language official default",
    },
    {
        "id": "arthur-v3-cfg-0.5",
        "container": "chatterbox-v3",
        "url": "http://127.0.0.1:8009",
        "cfg_weight": 0.5,
        "exaggeration": 0.5,
        "model_repo": "ResembleAI/chatterbox",
        "model_snapshot": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        "multilingual_v3": True,
        "voice": "uk_male_minter",
        "reference_sha256": ARTHUR_SHA256,
        "reference_bytes": ARTHUR_BYTES,
        "reference_source": "User-authorized human Arthur narration reference",
        "note": "Official same-language V3 default",
    },
    {
        "id": "irish-tadhg-v3-cfg-0.5",
        "container": "chatterbox-v3",
        "url": "http://127.0.0.1:8009",
        "cfg_weight": 0.5,
        "exaggeration": 0.5,
        "model_repo": "ResembleAI/chatterbox",
        "model_snapshot": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        "multilingual_v3": True,
        "voice": "tadhg_hynes",
        "reference_sha256": TADHG_SHA256,
        "reference_bytes": TADHG_BYTES,
        "reference_source": (
            "Human Irish LibriVox narrator; The Woodlanders. Exact upstream "
            "chapter/offset provenance remains incomplete."
        ),
        "reference_url": "https://librivox.org/the-woodlanders-by-thomas-hardy-2/",
        "note": "Human Irish reference; official same-language V3 default",
    },
    {
        "id": "australian-vctk-p374-v3-cfg-0.5",
        "container": "chatterbox-v3",
        "url": "http://127.0.0.1:8009",
        "cfg_weight": 0.5,
        "exaggeration": 0.5,
        "model_repo": "ResembleAI/chatterbox",
        "model_snapshot": "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        "multilingual_v3": True,
        "voice": "vctk_australian_m_p374",
        "reference_sha256": VCTK_P374_SHA256,
        "reference_bytes": VCTK_P374_BYTES,
        "reference_source": "Human Australian VCTK 0.92 speaker p374; CC BY 4.0",
        "reference_url": "https://datashare.ed.ac.uk/handle/10283/3443",
        "note": "Human Australian reference; official same-language V3 default",
    },
)


def _json_get(url: str, timeout: int = 30):
    with urlopen(url, timeout=timeout) as response:
        return json.load(response)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _docker_text(container: str, *args: str) -> str:
    return subprocess.check_output(
        ["docker", "exec", container, *args], text=True).strip()


def _reference_evidence(arm: dict) -> dict:
    container = arm["container"]
    voice = arm["voice"]
    effective_path = _docker_text(
        container,
        "sh", "-lc",
        f"p=/app/voices/{voice}.wav; "
        f"if [ -f /app/voices/custom/{voice}.wav ]; then "
        f"p=/app/voices/custom/{voice}.wav; fi; "
        "printf '%s\\n' \"$p\"",
    )
    sha, _ = _docker_text(container, "sha256sum", effective_path).split(maxsplit=1)
    size = int(_docker_text(container, "stat", "-c", "%s", effective_path))
    if (sha, size) != (arm["reference_sha256"], arm["reference_bytes"]):
        raise RuntimeError(
            f"{container} {voice} mismatch: sha256={sha}, bytes={size}"
        )
    probe = json.loads(_docker_text(
        container,
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_name,sample_fmt,sample_rate,channels,nb_frames",
        "-of", "json", effective_path,
    ))
    stream = probe["streams"][0]
    expected = {
        "codec_name": "pcm_s16le", "sample_fmt": "s16",
        "sample_rate": "24000", "channels": 1,
    }
    if len(probe["streams"]) != 1 or any(stream.get(k) != v for k, v in expected.items()):
        raise RuntimeError(f"unexpected {voice} format in {container}: {probe}")
    duration = float(probe["format"]["duration"])
    if abs(duration - 18.0) > 0.001:
        raise RuntimeError(f"unexpected {voice} duration in {container}: {duration}")
    return {
        "effective_path": effective_path, "sha256": sha, "bytes": size,
        "duration_seconds": duration, "source": arm["reference_source"],
        "source_url": arm.get("reference_url"), **expected,
    }


def _docker_image_id(container: str) -> str:
    return subprocess.check_output(
        ["docker", "inspect", "--format", "{{.Image}}", container], text=True
    ).strip()


def _package_direct_url(container: str) -> dict:
    raw = _docker_text(
        container,
        "python", "-c",
        "import importlib.metadata as m; "
        "print(m.distribution('chatterbox-tts').read_text('direct_url.json'))",
    )
    evidence = json.loads(raw)
    vcs = evidence.get("vcs_info") or {}
    if vcs.get("commit_id") != APP_REF or vcs.get("requested_revision") != APP_REF:
        raise RuntimeError(f"{container} package source is not pinned to {APP_REF}: {evidence}")
    return evidence


def _model_evidence(container: str, repo_id: str, expected_snapshot: str) -> dict:
    cache_name = "models--" + repo_id.replace("/", "--")
    snapshot_root = f"/data/hf/hub/{cache_name}/snapshots"
    snapshots = _docker_text(
        container,
        "sh", "-lc",
        f"find {snapshot_root} -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' "
        "2>/dev/null | sort -u",
    ).splitlines()
    if expected_snapshot not in snapshots:
        raise RuntimeError(
            f"{container} missing expected {repo_id} snapshot {expected_snapshot}; "
            f"found {snapshots}"
        )
    active_ref = _docker_text(container, "cat", f"/data/hf/hub/{cache_name}/refs/main")
    if active_ref != expected_snapshot:
        raise RuntimeError(
            f"{container} active {repo_id} main ref is {active_ref}, expected {expected_snapshot}"
        )
    files = _docker_text(
        container,
        "sh", "-lc",
        f"find {snapshot_root}/{expected_snapshot} -maxdepth 1 -type l -printf '%f -> %l\\n' "
        "2>/dev/null | sort",
    ).splitlines()
    return {
        "repo_id": repo_id,
        "snapshot": expected_snapshot,
        "active_main_ref": active_ref,
        "snapshot_files": files,
    }


def _active_jobs() -> list[dict]:
    jobs = _json_get("http://127.0.0.1:8881/api/jobs", timeout=60)
    return [
        {"id": job.get("id"), "title": job.get("book_name"), "status": job.get("status")}
        for job in jobs
        if str(job.get("status", "")).lower() in ACTIVE_STATUSES
    ]


def _chunk_evidence(text: str) -> dict:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?”])\s+", normalized)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + 1 + len(sentence) > 280:
            chunks.append(current)
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        chunks.append(current)
    evidence = {
        "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "normalized_chars": len(normalized),
        "chunks": [
            {
                "number": number,
                "chars": len(chunk),
                "words": len(chunk.split()),
                "sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
            }
            for number, chunk in enumerate(chunks, start=1)
        ],
    }
    hashes = tuple(item["sha256"] for item in evidence["chunks"])
    if evidence["normalized_sha256"] != EXPECTED_NORMALIZED_SHA256 or hashes != EXPECTED_CHUNK_SHA256:
        raise RuntimeError(f"server chunk contract drifted: {evidence}")
    return evidence


def _post_audio(url: str, payload: dict, destination: Path) -> float:
    request = Request(
        f"{url}/v1/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=1800) as response:
            content_type = response.headers.get("Content-Type", "")
            if response.status != 200 or "audio" not in content_type:
                raise RuntimeError(
                    f"unexpected response {response.status} {content_type}"
                )
            temp = destination.with_suffix(".tmp")
            with temp.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            temp.replace(destination)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"synthesis request failed: {error}") from error
    return time.monotonic() - started


def _monitor_product(stop: threading.Event, samples: list[dict]) -> None:
    """Sample UI responsiveness and host load while synthesis occupies CPU."""
    while True:
        started = time.monotonic()
        try:
            health = _json_get("http://127.0.0.1:8881/api/health", timeout=10)
            error = None
        except Exception as exc:  # retain transient failure evidence
            health = None
            error = f"{type(exc).__name__}: {exc}"
        samples.append({
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latency_seconds": round(time.monotonic() - started, 4),
            "health": health,
            "error": error,
            "load_average": [round(value, 3) for value in os.getloadavg()],
        })
        if stop.wait(10):
            return


def _validate_audio(path: Path, probe_container: str) -> dict:
    if path.stat().st_size < 100_000:
        raise RuntimeError(f"non-triviality check failed for {path}")
    remote = f"/tmp/{path.name}"
    subprocess.run(
        ["docker", "cp", str(path), f"{probe_container}:{remote}"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        probe = json.loads(_docker_text(
            probe_container,
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_name,sample_rate,channels",
            "-of", "json", remote,
        ))
        subprocess.run(
            ["docker", "exec", probe_container, "ffmpeg", "-v", "error", "-i", remote,
             "-f", "null", "-"],
            check=True,
        )
    finally:
        subprocess.run(
            ["docker", "exec", "--user", "0", probe_container, "rm", "-f", remote],
            check=True,
        )
    duration = float(probe["format"]["duration"])
    if len(probe["streams"]) != 1:
        raise RuntimeError(f"expected one audio stream: {probe}")
    stream = probe["streams"][0]
    codec = stream["codec_name"]
    if duration < 30 or codec != "mp3" or stream.get("sample_rate") != "24000" or stream.get("channels") != 1:
        raise RuntimeError(f"audio validation failed: duration={duration}, codec={codec}")
    return {
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "duration_seconds": duration,
        "codec": codec,
        "sample_rate": int(stream["sample_rate"]),
        "channels": stream["channels"],
        "full_decode": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", default="scratch/chatterbox-control",
        help="Ignored directory in which a timestamped evidence bundle is created",
    )
    parser.add_argument(
        "--arms", nargs="*", choices=[arm["id"] for arm in ARMS],
        help="Optional subset; default renders all three arms",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "webapp"))
    from voice_sample import sample_text_for  # noqa: PLC0415

    queue = _json_get("http://127.0.0.1:8881/api/queue/status")
    active = _active_jobs()
    if queue.get("queued_count") or active:
        raise RuntimeError(f"product queue is not idle: queue={queue}, active={active}")

    chosen = [arm for arm in ARMS if not args.arms or arm["id"] in args.arms]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_dir = (repo / args.output_root / stamp).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    source = sample_text_for("chatterbox")
    source_path = output_dir / "source.txt"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    source_sha = _sha256(source_path)
    if source_sha != EXPECTED_INPUT_SHA256:
        raise RuntimeError(
            f"production-normalized hard passage drifted: {source_sha}"
        )
    chunk_evidence = _chunk_evidence(source)
    common = {
        "created_utc": stamp,
        "repo_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "official_source": OFFICIAL_URL,
        "runtime_source": f"https://github.com/resemble-ai/chatterbox/tree/{APP_REF}",
        "runtime_commit": APP_REF,
        "runtime_license": "MIT",
        "rng_guidance": PYTORCH_REPRO_URL,
        "seed": SEED,
        "source_file": source_path.name,
        "source_sha256": source_sha,
        "source_chars": len(source),
        "source_words": len(source.split()),
        "server_text_contract": chunk_evidence,
        "queue_preflight": queue,
    }

    print(f"Evidence directory: {output_dir}", flush=True)
    print(f"Source: {common['source_words']} words, sha256={source_sha}", flush=True)
    for arm in chosen:
        queue_now = _json_get("http://127.0.0.1:8881/api/queue/status")
        active_now = _active_jobs()
        if queue_now.get("queued_count") or active_now:
            raise RuntimeError(
                f"product queue became busy before {arm['id']}: "
                f"queue={queue_now}, active={active_now}"
            )
        health = _json_get(f"{arm['url']}/health", timeout=30)
        if int(health.get("chunk_chars", -1)) != 280:
            raise RuntimeError(
                f"unexpected effective chunk size for {arm['id']}: {health.get('chunk_chars')}"
            )
        if health.get("device") != "cpu" or health.get("cuda_available"):
            raise RuntimeError(f"this gate is CPU-only, got health={health}")
        if bool(health.get("multilingual_v3")) is not arm["multilingual_v3"]:
            raise RuntimeError(f"wrong model family for {arm['id']}: health={health}")
        reference = _reference_evidence(arm)
        payload = {
            "model": "tts-1",
            "input": source,
            "voice": arm["voice"],
            "response_format": "mp3",
            "seed": SEED,
            "cfg_weight": arm["cfg_weight"],
            "exaggeration": arm["exaggeration"],
        }

        destination = output_dir / f"{arm['id']}.mp3"
        print(f"Rendering {arm['id']} ...", flush=True)
        monitor_stop = threading.Event()
        monitor_samples: list[dict] = []
        monitor = threading.Thread(
            target=_monitor_product, args=(monitor_stop, monitor_samples), daemon=True
        )
        monitor.start()
        try:
            wall_seconds = _post_audio(arm["url"], payload, destination)
        finally:
            monitor_stop.set()
            monitor.join(timeout=15)
        audio = _validate_audio(destination, "epub-to-audiobook-ui")
        manifest = {
            **common,
            "arm": arm["id"],
            "model_family": "Multilingual V3" if health.get("multilingual_v3") else "Turbo",
            "health": health,
            "reference": reference,
            "model": _model_evidence(
                arm["container"], arm["model_repo"], arm["model_snapshot"]
            ),
            "container_image_id": _docker_image_id(arm["container"]),
            "installed_package": _package_direct_url(arm["container"]),
            "request_parameters": {
                key: value for key, value in payload.items() if key not in {"input"}
            },
            "parameter_note": arm["note"],
            "synthesis_wall_seconds": round(wall_seconds, 3),
            "product_monitor": monitor_samples,
            "queue_exclusion_boundary": (
                "Idle was rechecked before this arm; a new job arriving during an "
                "already-running request cannot be excluded without pausing the product queue."
            ),
            "audio": audio,
        }
        (output_dir / f"{arm['id']}.manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"Validated {destination.name}: {audio['duration_seconds']:.3f}s, "
            f"{audio['bytes']} bytes, sha256={audio['sha256']}",
            flush=True,
        )

    print("All requested arms rendered and structurally validated.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
