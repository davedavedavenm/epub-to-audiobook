"""Local ASR screen for gross audition completeness; never a voice-quality rank."""

from __future__ import annotations

import json
import os
import sys

from faster_whisper import WhisperModel

from shared import OUTPUT, REPO_ROOT, corpus, sentence_chunks

sys.path.insert(0, str(REPO_ROOT / "webapp"))
from qa_asr import diff_report  # noqa: E402


def main() -> None:
    raw, prepared = corpus()
    model_name = os.environ.get("AUDITION_ASR_MODEL", "base.en")
    model_root = os.environ.get("WHISPER_MODEL_DIR", str(OUTPUT / ".whisper"))
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=model_root,
    )
    for audio in sorted(OUTPUT.glob("*.mp3")):
        report_path = audio.with_suffix(".asr.json")
        if report_path.is_file():
            print(f"skip existing {report_path.name}", flush=True)
            continue
        if audio.stem == "audio8_arthur_raw":
            source = raw
        elif audio.stem == "zonos2_arthur_q4_k_short":
            source = prepared.split("\n\n", 1)[0]
        elif audio.stem == "zonos2_arthur_q4_k_iphone_split":
            source = next(
                sentence
                for sentence in sentence_chunks(prepared)
                if sentence.startswith("Today the iPhone")
            )
        else:
            source = prepared
        segments, info = model.transcribe(
            str(audio), language="en", beam_size=1, vad_filter=True
        )
        transcript = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        report = diff_report(source, transcript)
        report.update({
            "audio": audio.name,
            "model": model_name,
            "language": getattr(info, "language", None),
            "transcript": transcript,
            "boundary": (
                "ASR detects gross omissions, insertions, repetition or collapse only; "
                "it does not rank voice, accent, pacing, prosody, or pronunciation"
            ),
        })
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            f"{audio.name}: wer={report['wer']} source={report['n_source']} "
            f"heard={report['n_heard']} divergences={len(report['divergences'])}",
            flush=True,
        )


if __name__ == "__main__":
    main()
