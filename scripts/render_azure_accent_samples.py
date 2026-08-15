#!/usr/bin/env python3
"""Render an explicit, tightly bounded Azure regional-voice shortlist on F0.

Authentication is inherited from ``az login``.  The Speech resource key is held
in memory only: it is never printed or written to the evidence manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


OFFICIAL_SOURCES = {
    "azure_cli_login": "https://learn.microsoft.com/cli/azure/authenticate-azure-cli-interactively",
    "speech_quickstart": "https://learn.microsoft.com/azure/ai-services/speech-service/get-started-text-to-speech",
    "speech_rest": "https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech",
    "speech_pricing": "https://azure.microsoft.com/en-gb/pricing/details/speech/",
}
OUTPUT_FORMAT = "audio-24khz-160kbitrate-mono-mp3"


def _az_json(*args: str):
    azure_cli = shutil.which("az") or shutil.which("az.cmd")
    if not azure_cli:
        raise RuntimeError("Azure CLI is not available on PATH")
    completed = subprocess.run(
        [azure_cli, *args, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _az_secret(*args: str) -> str:
    azure_cli = shutil.which("az") or shutil.which("az.cmd")
    if not azure_cli:
        raise RuntimeError("Azure CLI is not available on PATH")
    completed = subprocess.run(
        [azure_cli, *args, "--output", "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if not value:
        raise RuntimeError("Azure CLI returned an empty Speech key")
    return value


def _request(url: str, key: str, *, body: bytes | None = None) -> bytes:
    headers = {"Ocp-Apim-Subscription-Key": key, "User-Agent": "epub-to-audiobook-eval"}
    method = "GET"
    if body is not None:
        method = "POST"
        headers.update({
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
        })
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure Speech HTTP {exc.code}: {detail[:500]}") from exc


def _ssml(text: str, locale: str, voice: str) -> bytes:
    escaped = html.escape(text, quote=False)
    payload = (
        f"<speak version='1.0' xml:lang='{locale}'>"
        f"<voice name='{voice}'>{escaped}</voice></speak>"
    )
    return payload.encode("utf-8")


def _looks_like_mp3(audio: bytes) -> bool:
    return len(audio) >= 50_000 and (audio.startswith(b"ID3") or audio.startswith(b"\xff"))


def _validate_gate(voices: list[str], source: str, max_characters: int) -> tuple[list[str], int]:
    requested = list(dict.fromkeys(voices))
    if len(requested) != len(voices):
        raise RuntimeError("Duplicate --voices entries are not allowed")
    if not 1 <= len(requested) <= 3:
        raise RuntimeError("A focused gate must request between one and three voices")
    estimated = len(source) * len(requested)
    if estimated > max_characters:
        raise RuntimeError(
            f"Refusing estimated {estimated} billable characters; "
            f"--max-characters is {max_characters}"
        )
    return requested, estimated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", default="uksouth")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--voices", nargs="+", required=True,
        help="One to three exact GA ShortName values; there is deliberately no catalogue-wide default",
    )
    parser.add_argument("--max-characters", type=int, default=1_000)
    parser.add_argument("--pace-seconds", type=float, default=3.2)
    args = parser.parse_args()

    account = _az_json(
        "cognitiveservices", "account", "show",
        "--subscription", args.subscription,
        "--resource-group", args.resource_group,
        "--name", args.account,
    )
    sku = account.get("sku", {}).get("name")
    if account.get("kind") != "SpeechServices" or sku != "F0":
        raise RuntimeError(f"Refusing non-F0 Speech resource: kind={account.get('kind')} sku={sku}")
    if str(account.get("location", "")).lower() != args.region.lower():
        raise RuntimeError("Speech resource region does not match --region")

    key = _az_secret(
        "cognitiveservices", "account", "keys", "list",
        "--subscription", args.subscription,
        "--resource-group", args.resource_group,
        "--name", args.account,
        "--query", "key1",
    )
    base = f"https://{args.region}.tts.speech.microsoft.com/cognitiveservices"
    catalogue = json.loads(_request(f"{base}/voices/list", key).decode("utf-8"))
    source = args.source.read_text(encoding="utf-8").strip()
    if not source:
        raise RuntimeError("Source text is empty")
    requested, estimated_billable_chars = _validate_gate(
        args.voices, source, args.max_characters
    )
    requested_set = set(requested)
    wanted = sorted(
        (
            voice for voice in catalogue
            if voice.get("ShortName") in requested_set
            and voice.get("Status") == "GA"
            and voice.get("VoiceType") == "Neural"
        ),
        key=lambda voice: (voice["Locale"], voice["ShortName"]),
    )
    found = {voice["ShortName"] for voice in wanted}
    if found != requested_set:
        raise RuntimeError(f"Requested voices are not all live GA neural voices: missing={sorted(requested_set - found)}")

    args.output.mkdir(parents=True, exist_ok=True)
    existing = sorted(args.output.glob("*.mp3"))
    if existing:
        raise RuntimeError(f"Refusing to repeat synthesis into non-empty output: {existing[0]}")
    print(
        f"Bounded gate: {len(wanted)} voices, {len(source)} source characters each, "
        f"estimated maximum {estimated_billable_chars} billable characters",
        flush=True,
    )
    results = []
    for index, voice in enumerate(wanted):
        if index:
            time.sleep(max(0.0, args.pace_seconds))
        short_name = voice["ShortName"]
        filename = f"{short_name}.mp3"
        audio = _request(
            f"{base}/v1",
            key,
            body=_ssml(source, voice["Locale"], short_name),
        )
        if not _looks_like_mp3(audio):
            raise RuntimeError(f"Invalid or trivial MP3 returned for {short_name}: {len(audio)} bytes")
        (args.output / filename).write_bytes(audio)
        digest = hashlib.sha256(audio).hexdigest()
        print(f"{short_name}: {len(audio)} bytes sha256={digest}", flush=True)
        results.append({
            "locale": voice["Locale"],
            "voice": short_name,
            "gender": voice["Gender"],
            "status": voice["Status"],
            "file": filename,
            "bytes": len(audio),
            "sha256": digest,
        })

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "subscription_id": args.subscription,
        "resource_group": args.resource_group,
        "speech_account": args.account,
        "resource_kind": account["kind"],
        "resource_sku": sku,
        "region": args.region,
        "output_format": OUTPUT_FORMAT,
        "source_file": str(args.source),
        "source_chars": len(source),
        "source_words": len(source.split()),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "estimated_billable_characters": estimated_billable_chars,
        "character_budget": args.max_characters,
        "production_defaults_changed": False,
        "credentials_persisted": False,
        "official_sources": OFFICIAL_SOURCES,
        "voices": results,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Rendered and recorded {len(results)} official GA voices in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
