"""QA Layer 2 — ASR verification (the self-correcting / "learning" layer).

The point: stop needing a human to find TTS bugs by ear. After a chapter is
rendered, transcribe the audio back with a LOCAL Whisper (faster-whisper, CPU),
align the transcript to the source text, and surface where the spoken words
diverge from the text — dropped words/sentences, gross misreads, numbers or
names that came out wrong. High-confidence, clearly-mapped fixes are proposed
as lexicon entries; everything else is written to a per-book QA report.

What this reliably catches (high value):
  * dropped/duplicated words and skipped sentences,
  * gross substitutions (engine said something clearly different),
  * numbers/dates that lost a piece ("1976" heard as "nineteen seventy").
What it does NOT catch: subtle prosody/pacing and fine pronunciation — ASR
normalizes those away. That still needs an ear. We are honest about this in the
report rather than pretending WER==0 means perfect.

Design choices:
  * Local-first: faster-whisper on CPU, small/base model is enough for
    verification (we are checking words, not producing a transcript to keep).
  * Pure-python core (`normalize_words`, `diff_report`, `suggest_lexicon`) is
    unit-tested WITHOUT audio, so the alignment logic is guarded even where the
    Whisper model isn't installed.
  * Degrades gracefully: if faster-whisper isn't installed, transcribe() raises
    a clear, actionable error; callers treat QA as optional.
"""
from __future__ import annotations
import re
import json
import difflib
import logging
from pathlib import Path

try:
    from num2words import num2words
    _HAS_N2W = True
except ImportError:
    _HAS_N2W = False

log = logging.getLogger("qa-asr")

# tokens that are "content words" worth flagging when dropped/changed
_WORD_RE = re.compile(r"[a-z0-9']+")


def _expand_number(tok: str) -> list[str]:
    """Expand a pure-digit token to number-words so '1976' and 'nineteen
    seventy six' compare equal (avoids false divergences from formatting)."""
    if not tok.isdigit() or not _HAS_N2W:
        return [tok]
    try:
        n = int(tok)
        # years read naturally: 1976 -> nineteen seventy-six
        if 1000 <= n <= 2099 and len(tok) == 4:
            words = num2words(n, to='year') if _year_supported() else num2words(n)
        else:
            words = num2words(n)
        return _WORD_RE.findall(words.lower().replace('-', ' '))
    except Exception:
        return [tok]


def _year_supported() -> bool:
    try:
        num2words(1999, to='year')
        return True
    except Exception:
        return False


def normalize_words(text: str) -> list[str]:
    """Lowercase, strip punctuation, expand digits to words. Returns a word
    list suitable for alignment. Numbers are canonicalised so digit vs spelled
    forms don't register as differences."""
    text = (text or "").lower().replace('&', ' and ')
    out: list[str] = []
    for tok in _WORD_RE.findall(text):
        if tok.isdigit():
            out.extend(_expand_number(tok))
        else:
            out.append(tok)
    return out


def diff_report(source_text: str, transcript: str, context: int = 4) -> dict:
    """Align a source text against an ASR transcript and report divergences.

    Returns {wer, n_source, n_heard, n_match, divergences:[...]}. Each
    divergence: {type: drop|extra|sub, source: [...], heard: [...], at: idx,
    context: "..."}. `wer` = (subs+dels+ins)/n_source.
    """
    s = normalize_words(source_text)
    h = normalize_words(transcript)
    sm = difflib.SequenceMatcher(a=s, b=h, autojunk=False)
    subs = dels = ins = 0
    divergences = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            continue
        src_span = s[i1:i2]
        heard_span = h[j1:j2]
        if op == 'replace':
            subs += max(len(src_span), len(heard_span))
            dtype = 'sub'
        elif op == 'delete':
            dels += len(src_span)
            dtype = 'drop'          # in source, missing from audio
        else:  # insert
            ins += len(heard_span)
            dtype = 'extra'         # in audio, not in source
        ctx_lo = max(0, i1 - context)
        ctx = ' '.join(s[ctx_lo:i1]) + ' [[' + ' '.join(src_span) + ']] ' + ' '.join(s[i2:i2 + context])
        divergences.append({
            'type': dtype,
            'source': src_span,
            'heard': heard_span,
            'at': i1,
            'context': ctx.strip(),
        })
    n_source = max(1, len(s))
    return {
        'wer': round((subs + dels + ins) / n_source, 4),
        'n_source': len(s),
        'n_heard': len(h),
        'n_match': sum(b - a for _, a, b, _, _ in
                       ((o, i1, i2, j1, j2) for o, i1, i2, j1, j2 in sm.get_opcodes() if o == 'equal')),
        'divergences': divergences,
    }


def suggest_lexicon(divergences: list[dict], min_len: int = 5) -> dict:
    """From substitution divergences, propose conservative lexicon entries:
    a source word the ASR heard as something clearly different is a candidate
    for a phonetic hint. High-precision only — single-word 1:1 subs on
    non-trivial words (>=5 chars filters common-word ASR noise like cat/bat
    while keeping real names like Huawei). These are SUGGESTIONS; a human or an
    opt-in flag applies them."""
    sugg: dict[str, str] = {}
    for d in divergences:
        if d['type'] != 'sub':
            continue
        src, heard = d['source'], d['heard']
        if len(src) == 1 and len(heard) == 1:
            w, got = src[0], heard[0]
            # skip trivial/short words and near-identical (likely ASR noise)
            if len(w) >= min_len and w != got and not w.isdigit():
                if difflib.SequenceMatcher(a=w, b=got).ratio() < 0.8:
                    sugg[w] = got  # {misread source word: what it sounded like}
    return sugg


def transcribe(audio_path: str | Path, model_size: str = "base", device: str = "cpu") -> str:
    """Transcribe audio to text with a LOCAL faster-whisper model (CPU by
    default). Raises a clear, actionable error if faster-whisper isn't
    installed — QA is optional and callers handle that."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper not installed — QA Layer 2 needs it. "
            "Install locally: pip install faster-whisper") from e
    compute = "int8" if device == "cpu" else "float16"
    model = WhisperModel(model_size, device=device, compute_type=compute)
    segments, _ = model.transcribe(str(audio_path), beam_size=1, vad_filter=True)
    return " ".join(seg.text for seg in segments)


def verify_chapter(audio_path: str | Path, source_text: str,
                   model_size: str = "base", wer_flag: float = 0.08) -> dict:
    """Transcribe one chapter's audio and report divergence vs its source text.
    Returns the diff_report plus 'flagged' (wer over threshold) and
    'lexicon_suggestions'."""
    transcript = transcribe(audio_path, model_size=model_size)
    rep = diff_report(source_text, transcript)
    rep['audio'] = str(audio_path)
    rep['flagged'] = rep['wer'] >= wer_flag
    rep['lexicon_suggestions'] = suggest_lexicon(rep['divergences'])
    return rep


def write_report(report: dict, out_path: str | Path) -> Path:
    """Persist a QA report (JSON) to the canonical output location."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return out_path


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description="QA Layer 2 — ASR-verify rendered audio against source text")
    ap.add_argument('--audio', required=True, help='chapter mp3/wav to verify')
    ap.add_argument('--text', help='source text file (utf-8)')
    ap.add_argument('--text-inline', help='source text as a string (for quick checks)')
    ap.add_argument('--model', default='base', help='whisper model size (tiny/base/small)')
    ap.add_argument('--wer-flag', type=float, default=0.08)
    ap.add_argument('--report', help='write JSON report here')
    a = ap.parse_args()
    src = a.text_inline or (Path(a.text).read_text(encoding='utf-8') if a.text else '')
    if not src:
        raise SystemExit("provide --text or --text-inline")
    rep = verify_chapter(a.audio, src, model_size=a.model, wer_flag=a.wer_flag)
    print(f"WER={rep['wer']}  flagged={rep['flagged']}  "
          f"source_words={rep['n_source']} heard={rep['n_heard']} "
          f"divergences={len(rep['divergences'])}")
    for d in rep['divergences'][:20]:
        print(f"  [{d['type']}] {d['context']}")
    if rep['lexicon_suggestions']:
        print("lexicon suggestions:", rep['lexicon_suggestions'])
    if a.report:
        print("report ->", write_report(rep, a.report))
