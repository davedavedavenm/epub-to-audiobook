"""higgs_book_plan.py - pure planning/cost helpers for scripts/modal_higgs_book.py (no modal import,
so CI can test them)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

L4_USD_PER_S = 0.000222              # modal.com/pricing, checked 2026-10-06 ($0.80/h)
GPU_S_PER_AUDIO_S = 1.5              # measured RTF 1.2-1.9 on an L4, one request at a time (Colab, same runtime)
CONTAINER_START_S = 360              # image pull + vLLM start + weights load, per container (estimate)


def load_bundle(zip_path: Path) -> tuple[dict, dict]:
    with zipfile.ZipFile(zip_path) as z:
        man = json.loads(z.read("manifest.json"))
        pay = {c["slug"]: json.loads(z.read(f"payloads/{c['slug']}.json")) for c in man["chapters"]}
    return man, pay


def plan_batches(man: dict, pay: dict, chunk_dir: Path, batch_size: int = 8) -> list:
    """Batches of chunks that are NOT on disk yet (so a rerun resumes, never regenerates)."""
    batches = []
    for c in man["chapters"]:
        slug, items = c["slug"], []
        for i, ch in enumerate(pay[slug]["chunks"], 1):
            if (chunk_dir / slug / f"{i:04d}.wav").exists():
                continue
            items.append({"i": i, "text": ch.get("tagged") or ch["text"], "words": ch["words"]})
            if len(items) == batch_size:
                batches.append({"slug": slug, "items": items})
                items = []
        if items:
            batches.append({"slug": slug, "items": items})
    return batches


def estimate_usd(batches: list, containers: int) -> float:
    words = sum(it["words"] for b in batches for it in b["items"])
    gpu_s = words / 150 * 60 * GPU_S_PER_AUDIO_S + containers * CONTAINER_START_S
    return round(gpu_s * L4_USD_PER_S, 2)


def spent_usd(gpu_seconds: float, containers_started: int) -> float:
    return round((gpu_seconds + containers_started * CONTAINER_START_S) * L4_USD_PER_S, 2)




def pace_outliers(rows: list, fast: float = 0.85, slow: float = 1.6, min_words: int = 15) -> list:
    """rows = [(chunk_index, words, seconds)] for ONE chapter -> indexes to re-render.

    A chunk spoken much faster than the chapter's own median pace almost always lost words (the model
    stopped early: Armed Struggle Preface chunk 23, 105 words in 29.2 s = 0.278 s/word vs median 0.368,
    18 words missing); much slower usually means babble or a loop. Short chunks are ignored (headings)."""
    import statistics
    paced = [(i, s / w) for i, w, s in rows if w >= min_words and s > 0]
    if len(paced) < 3:
        return []
    med = statistics.median(p for _, p in paced)
    return [i for i, p in paced if p < fast * med or p > slow * med]
