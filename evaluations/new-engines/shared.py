"""Shared corpus, provenance, and structural checks for new-engine auditions."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path("/repo") if Path("/repo/webapp").is_dir() else Path(__file__).resolve().parents[2]
OUTPUT = Path("/output") if Path("/output").is_dir() else Path(__file__).with_name("output")
ARTHUR = REPO_ROOT / "chatterbox" / "voices" / "uk_male_minter.wav"
ARTHUR_SHA256 = "8774082c3acf6c215dc9307a4a9cce5fd50d4242fc9263534ed420675873e252"
BEATRICE = REPO_ROOT / "chatterbox" / "voices" / "uk_female_samuel.wav"
BEATRICE_SHA256 = "24abde8ee35ff4e0be0863675bb6c81311a38c582a99eb237b586a671bbd63bb"
ARTHUR_TRANSCRIPT = (
    '"I know that," snapped Bertram. "Not that it would make any difference if she stayed," '
    'pursued the relentless George. "She flies higher than the paper trade, my boy." '
    '"Hang her!" said Bertram. "It would make it more interesting for me," I ventured to observe.'
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def corpus() -> tuple[str, str]:
    sys.path.insert(0, str(REPO_ROOT / "webapp"))
    from voice_sample import SAMPLE_LEXICON, SAMPLE_TEXT
    from tts_preprocess import HAS_NUM2WORDS, _is_letter_spacing, normalize_text_for_tts

    if not HAS_NUM2WORDS:
        raise RuntimeError("prepared audition text requires num2words")
    safe_lexicon = {
        key: value for key, value in SAMPLE_LEXICON.items() if _is_letter_spacing(key, value)
    }
    prepared = normalize_text_for_tts(
        SAMPLE_TEXT,
        lexicon=safe_lexicon,
        modern=True,
        expand_numbers=True,
    )
    if any(symbol in prepared for symbol in ("$", "£", "%")):
        raise RuntimeError("prepared corpus still contains unexpanded number/currency symbols")
    return SAMPLE_TEXT, prepared


def bounded_chunks(text: str, limit: int = 150) -> list[str]:
    """Prefer sentence/clause boundaries and guarantee the upstream character limit."""
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    chunks: list[str] = []
    for sentence in sentences:
        pending = [sentence]
        while pending:
            item = pending.pop(0).strip()
            if len(item) <= limit:
                chunks.append(item)
                continue
            cut = max(item.rfind(mark, 0, limit + 1) for mark in (", ", "; ", ": ", " — "))
            if cut < limit // 2:
                cut = item.rfind(" ", 0, limit + 1)
            if cut <= 0:
                cut = limit
            else:
                cut += 1
            pending.insert(0, item[cut:].strip())
            pending.insert(0, item[:cut].strip())
    if not chunks or max(map(len, chunks)) > limit:
        raise RuntimeError("failed to construct bounded Audio8 chunks")
    return chunks


def sentence_chunks(text: str) -> list[str]:
    """Split only at terminal punctuation while preserving common abbreviations."""
    protected = text
    marker = "\ue000"
    for abbreviation in ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St."):
        protected = protected.replace(abbreviation, abbreviation[:-1] + marker)
    chunks = [
        item.replace(marker, ".").strip()
        for item in re.split(r"(?<=[.!?])\s+", protected)
        if item.strip()
    ]
    if not chunks or any(chunk[-1] not in ".!?" for chunk in chunks):
        raise RuntimeError("failed to construct complete-sentence chunks")
    return chunks


def verify_reference() -> dict:
    if sha256_file(ARTHUR) != ARTHUR_SHA256:
        raise RuntimeError("Arthur reference is missing, corrupt, or a Git LFS pointer")
    return {
        "reference": "user-authorized public-domain LibriVox Arthur / Andy Minter excerpt",
        "reference_sha256": ARTHUR_SHA256,
        "reference_bytes": ARTHUR.stat().st_size,
        "reference_transcript": ARTHUR_TRANSCRIPT,
    }


def verify_beatrice() -> dict:
    """Beatrice is the repository's shipped default narrator (uk_female_samuel_nano)."""
    if sha256_file(BEATRICE) != BEATRICE_SHA256:
        raise RuntimeError("Beatrice reference is missing, corrupt, or a Git LFS pointer")
    return {
        "reference": "Beatrice — the repository's shipped default narrator voice (uk_female_samuel)",
        "reference_sha256": BEATRICE_SHA256,
        "reference_bytes": BEATRICE.stat().st_size,
        "reference_chosen_by": "Dave, 2026-08-28",
    }


def _probe(path: Path) -> dict:
    if shutil.which("ffprobe") is None:
        import soundfile as sf

        info = sf.info(str(path))
        return {
            "codec": info.subtype.lower(),
            "sample_rate": int(info.samplerate),
            "channels": int(info.channels),
            "duration_seconds": round(float(info.duration), 3),
        }
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels,duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "duration_seconds": round(float(stream["duration"]), 3),
    }


def parse_peak_rss(time_file: Path) -> float | None:
    if not time_file.is_file():
        return None
    match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", time_file.read_text())
    return round(int(match.group(1)) / 1024, 1) if match else None


def finish(
    *,
    stem: str,
    wav: Path,
    input_text: str,
    wall_seconds: float,
    report: dict,
    peak_rss_mib: float | None = None,
    minimum_duration_seconds: float = 10,
) -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not wav.is_file() or wav.stat().st_size < 4096:
        raise RuntimeError(f"missing or implausibly small output: {wav}")
    mp3 = OUTPUT / f"{stem}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3)],
        check=True,
    )
    for candidate in (wav, mp3):
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(candidate), "-f", "null", "-"], check=True)
    probe = _probe(wav)
    if probe["duration_seconds"] < minimum_duration_seconds:
        raise RuntimeError(f"audition is suspiciously short: {probe['duration_seconds']} seconds")
    evidence = {
        **report,
        "input_characters": len(input_text),
        "input_sha256": sha256_bytes(input_text.encode("utf-8")),
        **probe,
        "wall_seconds": round(wall_seconds, 3),
        "rtf": round(wall_seconds / probe["duration_seconds"], 3),
        "peak_rss_mib": peak_rss_mib,
        "wav_bytes": wav.stat().st_size,
        "wav_sha256": sha256_file(wav),
        "mp3_bytes": mp3.stat().st_size,
        "mp3_sha256": sha256_file(mp3),
        "structural_check": "WAV and MP3 fully decoded with ffmpeg; quality requires human listening",
    }
    (OUTPUT / f"{stem}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2), flush=True)
    return evidence
