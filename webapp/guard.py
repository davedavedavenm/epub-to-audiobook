"""Optional LLM guard, layered over the deterministic heuristics.

First job: chapter classification. Each renderable chapter is labelled
front / body / back matter from its title AND opening words — which catches
cases the title-only regex cannot, e.g. a page whose title is the book's own
name but whose text is actually the copyright notice, or trailing ad pages.

Design contract: the guard is ALWAYS optional and ALWAYS safe. Every function
returns None on any problem (no LLM configured, network error, malformed reply,
or a result that fails a sanity check), and callers fall back to the
deterministic heuristic (chapters.body_end_index). The guard can only improve
the default range, never break it.

It talks to the app's existing OpenAI-compatible LLM (local Ollama primary,
cloud fallback) through a caller-supplied `llm_chat(messages) -> str`, so this
module has no dependency on app config or Flask.
"""
import json
import logging
import re

log = logging.getLogger(__name__)

_SYS = (
    "You sort the sections of an ebook so an audiobook only narrates the real "
    "book. For each section you get its number, title, and the first words of "
    "its text. Label each as exactly one of:\n"
    "  body  = content a listener wants narrated (introduction, prologue, "
    "numbered/titled chapters, epilogue)\n"
    "  front = front matter (title page, copyright/publisher page, dedication, "
    "table of contents, epigraph, half-title)\n"
    "  back  = back matter (acknowledgments, notes/endnotes, bibliography, "
    "references, index, about the author, also-by or advertisement pages, "
    "colophon)\n"
    "Judge by the TEXT, not just the title — a section titled with the book's "
    "name whose text is a copyright notice is 'front'. Reply with ONLY a JSON "
    "object mapping each section number (string) to its label. No prose, no "
    "code fence."
)


def classify_chapters(chapters, llm_chat):
    """Return {index:int -> 'body'|'front'|'back'} for the given chapters, or
    None if the guard could not produce a trustworthy classification."""
    if not chapters:
        return None
    lines = [
        f'{c["index"]}. title="{(c.get("title") or "")[:80]}" '
        f'text="{(c.get("snippet") or "")[:220]}"'
        for c in chapters
    ]
    user = ("Sections:\n" + "\n".join(lines) +
            '\n\nReturn JSON like {"1":"front","2":"body","3":"back"}.')
    try:
        raw = llm_chat([{"role": "system", "content": _SYS},
                        {"role": "user", "content": user}])
    except Exception as e:  # not configured, network, timeout — all non-fatal
        log.info("guard: classify call failed: %s", str(e)[:140])
        return None
    return _parse_labels(raw, {c["index"] for c in chapters})


def _parse_labels(raw, valid_indices):
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.S)   # tolerate stray prose / code fences
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    out = {}
    for k, v in data.items():
        try:
            i = int(str(k).strip())
        except (TypeError, ValueError):
            continue
        label = str(v).strip().lower()
        if i in valid_indices and label in ("body", "front", "back"):
            out[i] = label
    # need most sections classified to trust it
    if len(out) < 0.6 * len(valid_indices):
        return None
    return out


def resolve_body_range(chapters, llm_chat, head=6, tail=8):
    """Find (first_body, last_body) by classifying ONLY the boundary chapters.

    The book body is a contiguous middle block; the fuzzy decisions are all at the
    edges (leading front-matter, trailing back-matter). Classifying just the first
    `head` and last `tail` chapters keeps the prompt small enough for a Pi-hosted
    model — the doc's "deterministic where determinable, LLM only for the fuzzy
    remainder" principle. Middle chapters are body by construction.

    Returns (first_body, last_body) or None (caller falls back to the heuristic).
    """
    n = len(chapters)
    if n == 0:
        return None
    edge_idx = {c["index"] for c in chapters[:head]} | {c["index"] for c in chapters[-tail:]}
    candidates = [c for c in chapters if c["index"] in edge_idx]
    labels = classify_chapters(candidates, llm_chat)
    if not labels:
        return None

    first_body = last_body = None
    for c in chapters:                      # scan forward: skip leading non-body
        i = c["index"]
        if i not in labels or labels[i] == "body":
            first_body = i
            break
    for c in reversed(chapters):            # scan backward: skip trailing non-body
        i = c["index"]
        if i not in labels or labels[i] == "body":
            last_body = i
            break
    if first_body is None or last_body is None or first_body > last_body:
        return None
    if (last_body - first_body + 1) < max(1, 0.25 * n):   # body too small — distrust
        return None
    return first_body, last_body


def explain_gate(flags, llm_chat):
    """One or two plain sentences explaining a pre-sync quality hold, phrased from
    the deterministically-detected facts. Non-load-bearing: the hold decision is
    made in code; this only humanises it. Returns None on any failure (the raw
    per-chapter details stand on their own)."""
    if not flags:
        return None
    facts = "; ".join(
        f"chapter {f.get('chapter')} looks {f.get('issue')} ({f.get('detail', '')})"
        for f in flags)
    sys = (
        "You explain an audiobook quality hold to its owner in ONE or TWO plain "
        "sentences. You are given the detected problems as facts — state what is "
        "wrong and recommend re-rendering the affected chapter(s). Do not invent "
        "anything beyond the facts. No preamble, no list, no markdown.")
    try:
        out = llm_chat([{"role": "system", "content": sys},
                        {"role": "user", "content": "Problems: " + facts}])
        out = (out or "").strip()
        return out[:400] or None
    except Exception:
        return None


def body_range(labels, n_chapters):
    """From {index:label}, return (first_body, last_body) for the book body, or
    None if the classification looks unsafe (too little body, or too gappy to be
    a single contiguous run)."""
    body = sorted(i for i, l in labels.items() if l == "body")
    if not body:
        return None
    first, last = body[0], body[-1]
    span = last - first + 1
    if len(body) < 0.5 * span:                       # body run too gappy
        return None
    if len(body) < max(1, 0.25 * n_chapters):        # suspiciously little body
        return None
    return first, last
