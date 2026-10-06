"""higgs_prep.py - turn prepped sentences into Higgs TTS 3 generation chunks.

Dave's listening verdicts (2026-10-05, DECISIONS "Higgs TTS 3 works on a Colab L4"):
per-sentence generation sounds clipped and strung together; paragraph-sized chunks
(<= ~70 words, Higgs shapes the sentence joins itself) fixed most of it; heading lines
each followed by a 0.5 s gap caused "pause fatigue", so consecutive heading lines are one
chunk. This module is pure (no GPU, no network) so the rules are unit-tested.

Input is the ``sents`` list produced by ``as_prep.prep``:
    [{"text": str, "para": int, "quote": bool}, ...]
Output is a list of chunk dicts:
    {"sents": [indexes], "text": str, "para": int, "words": int,
     "heading": bool, "quote": bool}
The runner generates one request per chunk. ``text`` is plain; an optional emotion tag
(see ``apply_tags``) is prefixed per sentence at generation time.
"""
from __future__ import annotations

import re

MAX_WORDS = 70          # Higgs chunk ceiling that rendered cleanly (tested up to ~73)
HARD_MAX_WORDS = 110    # a single sentence longer than this is split at ; / , boundaries
HEADING_MAX_WORDS = 9

# Emotions Dave heard and liked vs the one he did not ("not the shouty one"). Anything
# not in ALLOWED_EMOTIONS is dropped by apply_tags, so a tagger cannot reintroduce
# shouting. Boson's documented set: affection amusement anger arousal awe bitterness
# confusion contemplation contentment determination disgust elation enthusiasm fear
# helplessness longing pride relief sadness shame surprise.
ALLOWED_EMOTIONS = frozenset({
    "awe", "contemplation", "determination", "pride", "sadness", "longing",
    "bitterness", "fear", "affection", "relief", "contentment", "helplessness",
})
FORBIDDEN_STYLES = frozenset({"shouting", "screaming"})

_TERMINAL = re.compile(r"[.!?…][”’\"')\]]*$")


def _words(text: str) -> int:
    return len(text.split())


def is_heading(text: str) -> bool:
    """A short line with no sentence-final punctuation: chapter number, title, date
    range, epigraph attribution. Real prose sentences end in . ! ? (or a closing quote)."""
    t = text.strip()
    if not t or _words(t) > HEADING_MAX_WORDS:
        return False
    return not _TERMINAL.search(t)


def _split_long(text: str) -> list[str]:
    """Split an over-long sentence into <= MAX_WORDS pieces at ; : then , boundaries."""
    if _words(text) <= HARD_MAX_WORDS:
        return [text]
    parts = [p.strip() for p in re.split(r"(?<=[;:])\s+", text) if p.strip()]
    if len(parts) == 1:
        parts = [p.strip() for p in re.split(r"(?<=,)\s+", text) if p.strip()]
    out, buf = [], ""
    for p in parts:
        cand = f"{buf} {p}".strip()
        if buf and _words(cand) > MAX_WORDS:
            out.append(buf)
            buf = p
        else:
            buf = cand
    if buf:
        out.append(buf)
    return out or [text]


def build_chunks(sents: list[dict], max_words: int = MAX_WORDS) -> list[dict]:
    """Group sentences into generation chunks.

    Rules, in order of precedence:
      1. Consecutive heading lines (see is_heading) form one chunk, joined with ". ".
      2. A chunk never crosses a paragraph boundary.
      3. Within a paragraph, sentences accumulate until adding the next would exceed
         ``max_words`` (a chunk always holds at least one sentence).
      4. A single sentence over HARD_MAX_WORDS is split at ; : , so no request can
         approach the model's context limit.
    """
    chunks: list[dict] = []
    i, n = 0, len(sents)
    while i < n:
        s = sents[i]
        if is_heading(s["text"]):
            j = i
            parts = []
            while j < n and is_heading(sents[j]["text"]):
                parts.append(sents[j]["text"].strip().rstrip(".:"))
                j += 1
            text = ". ".join(parts) + "."
            chunks.append({"sents": list(range(i, j)), "text": text,
                           "para": s["para"], "words": _words(text),
                           "heading": True, "quote": False})
            i = j
            continue

        group = [i]
        total = _words(s["text"])
        j = i + 1
        while (j < n and sents[j]["para"] == s["para"] and not is_heading(sents[j]["text"])
               and total + _words(sents[j]["text"]) <= max_words):
            group.append(j)
            total += _words(sents[j]["text"])
            j += 1

        if len(group) == 1 and _words(s["text"]) > HARD_MAX_WORDS:
            for piece in _split_long(s["text"]):
                chunks.append({"sents": [i], "text": piece, "para": s["para"],
                               "words": _words(piece), "heading": False,
                               "quote": bool(s.get("quote")), "split": True})
        else:
            text = " ".join(sents[k]["text"].strip() for k in group)
            chunks.append({"sents": group, "text": text, "para": s["para"],
                           "words": total, "heading": False,
                           "quote": any(sents[k].get("quote") for k in group)})
        i = j
    return chunks


def apply_tags(sents: list[dict], chunk: dict, tags: dict[int, str] | None) -> str:
    """Chunk text with an optional ``<|emotion:x|>`` prefix on tagged sentences.

    ``tags`` maps sentence index -> emotion. Only emotions in ALLOWED_EMOTIONS are
    emitted (never anger / shouting - Dave's explicit dislike), and a chunk is left
    untagged if it contains no tagged sentence. Per Boson's guide a tag colours only its
    own sentence, one emotion per sentence, so tags are re-applied at each sentence start.
    """
    if not tags or chunk.get("heading") or chunk.get("split"):
        return chunk["text"]
    out = []
    for k in chunk["sents"]:
        text = sents[k]["text"].strip()
        emo = (tags.get(k) or "").strip().lower()
        if emo in ALLOWED_EMOTIONS:
            text = f"<|emotion:{emo}|>{text}"
        out.append(text)
    return " ".join(out)


def gap_after(chunk: dict, next_chunk: dict | None) -> float:
    """Seconds of silence after *chunk* (0.3 within a paragraph, 0.5 across)."""
    if next_chunk is None:
        return 0.0
    if chunk.get("heading") and next_chunk.get("heading"):
        return 0.3
    return 0.5 if chunk["para"] != next_chunk["para"] else 0.3
