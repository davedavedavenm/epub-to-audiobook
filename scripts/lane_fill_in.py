"""lane_fill_in.py - render ONLY a Modal book's missing chunks on the Colab lane, without checkpoints.

  stage BUNDLE CHUNK_DIR STAGE   -> STAGE/as_bundle.zip + STAGE/mapping.json
      For every chapter with chunks that are missing or not current (no sidecar whose key matches
      text + sampling), the staged bundle has a fill chapter "chx<NN>" holding just those chunks, in
      order, with the original text (so the chunk keys are identical). mapping.json maps fill index ->
      original index. Run it through the webapp lane loop (fish_lane.render_colab).
  place STAGE CHUNK_DIR
      After the fill chunks were extracted to STAGE/chunks/chx<NN>/ and adopted there
      (chunk_asr_audit.py + voice_audit.py + adopt_lane_chunks.py against STAGE/as_bundle.zip), copy every
      adopted wav + sidecar to its original position. Unadopted ones stay missing for the next round.

Why no checkpoints: restoring a chapter's existing chunks meant uploading them to each Colab VM, and
Colab's upload API failed on them (HTTP 500 on a 90 MB archive, HTTP 503 part-way through 55 x 12 MB,
2026-10-07). A fill chapter needs nothing but the bundle.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def stage(bundle: Path, chunk_dir: Path, out: Path, model: str) -> dict:
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())
    import higgs_colab_runner as hr
    from higgs_book_plan import chunk_is_current, chunk_key, load_bundle
    man, pay = load_bundle(bundle)
    recipe = f"{model} {json.dumps(hr.SAMPLING, sort_keys=True)}"
    out.mkdir(parents=True, exist_ok=True)
    chapters, payloads, mapping = [], {}, {}
    for n, c in enumerate(man["chapters"]):
        slug, chunks = c["slug"], pay[c["slug"]]["chunks"]
        todo = [i for i, ch in enumerate(chunks, 1)
                if not chunk_is_current(chunk_dir, slug, i, chunk_key(ch.get("tagged") or ch["text"], recipe))]
        if not todo:
            continue
        # must still match the runner's checkpoint filter (`ch\w+/NNNN.wav`), or a replacement VM
        # would not restore what the previous one rendered
        x = "chx" + (slug[2:] if slug.startswith("ch") else slug)
        chapters.append({**c, "slug": x, "index": 900 + n, "title": f"fill {slug}"})
        payloads[x] = {**pay[slug], "slug": x, "title": f"fill {slug}", "chunks": [chunks[i - 1] for i in todo]}
        mapping[x] = {"slug": slug, "orig": todo}
    with zipfile.ZipFile(bundle) as z, zipfile.ZipFile(out / "as_bundle.zip", "w", zipfile.ZIP_DEFLATED) as o:
        for name in z.namelist():
            if name == "manifest.json" or name.startswith("payloads/"):
                continue
            o.writestr(name, z.read(name))
        for x, p in payloads.items():
            o.writestr(f"payloads/{x}.json", json.dumps(p, ensure_ascii=False))
        o.writestr("manifest.json", json.dumps({**man, "chapters": chapters}, ensure_ascii=False, indent=1))
    (out / "mapping.json").write_text(json.dumps(mapping, indent=1), encoding="utf-8")
    return {x: {"chapter": m["slug"], "chunks": len(m["orig"]), "first": m["orig"][:12]} for x, m in mapping.items()}


def place(stage_dir: Path, chunk_dir: Path) -> dict:
    mapping = json.loads((stage_dir / "mapping.json").read_text(encoding="utf-8"))
    placed = {}
    for x, m in mapping.items():
        n = 0
        for k, orig in enumerate(m["orig"], 1):
            src = stage_dir / "chunks" / x / f"{k:04d}"
            if src.with_suffix(".json").exists() and src.with_suffix(".wav").exists():   # adopted only
                dst = chunk_dir / m["slug"] / f"{orig:04d}"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src.with_suffix(".wav"), dst.with_suffix(".wav"))
                shutil.copyfile(src.with_suffix(".json"), dst.with_suffix(".json"))
                n += 1
        placed[m["slug"]] = {"placed": n, "of": len(m["orig"])}
    return placed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("bundle")
    s.add_argument("chunk_dir")
    s.add_argument("stage")
    s.add_argument("--model", default="bosonai/higgs-audio-v3-tts-4b")
    p = sub.add_parser("place")
    p.add_argument("stage")
    p.add_argument("chunk_dir")
    a = ap.parse_args()
    if a.cmd == "stage":
        print(json.dumps(stage(Path(a.bundle), Path(a.chunk_dir), Path(a.stage), a.model), indent=1))
    else:
        print(json.dumps(place(Path(a.stage), Path(a.chunk_dir)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
