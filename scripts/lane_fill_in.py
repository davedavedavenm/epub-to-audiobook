"""lane_fill_in.py - stage a Colab-lane job that renders ONLY the missing chunks of a Modal book.

For every chapter with chunks that are missing or not current (no sidecar whose key matches the text +
sampling), this writes:
  <stage>/as_bundle.zip                 the bundle cut down to those chapters (same chunking/text)
  <stage>/out/ckpt_<slug>_0001-NNNN.tgz  every current chunk of those chapters, as lane checkpoints
The Colab runner restores the checkpoints and renders only the gaps (see higgs_colab_runner
restore_checkpoints). Copy <stage> to khpi5 ~/as-lane/jobs/<tag>/ and drive it with the webapp's
fish_lane.render_colab under that tag. The new chunks then go through chunk_asr_audit.py,
voice_audit.py and adopt_lane_chunks.py like any lane output.

    python scripts/lane_fill_in.py FULL_BUNDLE.zip CHUNK_DIR STAGE_DIR
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    os.environ.setdefault("FISH_BASE", tempfile.mkdtemp())
    import higgs_colab_runner as hr
    from higgs_book_plan import chunk_is_current, chunk_key, load_bundle
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("chunk_dir")
    ap.add_argument("stage")
    ap.add_argument("--model", default="bosonai/higgs-audio-v3-tts-4b")
    a = ap.parse_args()
    man, pay = load_bundle(Path(a.bundle))
    recipe = f"{a.model} {json.dumps(hr.SAMPLING, sort_keys=True)}"
    chunk_dir, stage = Path(a.chunk_dir), Path(a.stage)
    (stage / "out").mkdir(parents=True, exist_ok=True)
    keep, report = [], {}
    for c in man["chapters"]:
        slug, chunks = c["slug"], pay[c["slug"]]["chunks"]
        current = [i for i, ch in enumerate(chunks, 1)
                   if chunk_is_current(chunk_dir, slug, i, chunk_key(ch.get("tagged") or ch["text"], recipe))]
        missing = [i for i in range(1, len(chunks) + 1) if i not in set(current)]
        if not missing:
            continue
        keep.append(slug)
        report[slug] = {"missing": len(missing), "first": missing[:12]}
        # only CURRENT wavs go into the checkpoint: a stale or failed wav must be re-rendered
        tmp = Path(tempfile.mkdtemp()) / slug
        tmp.mkdir(parents=True)
        for i in current:
            (tmp / f"{i:04d}.wav").write_bytes((chunk_dir / slug / f"{i:04d}.wav").read_bytes())
        if current:
            hr.write_checkpoint(slug, 1, len(chunks), tmp, out=stage / "out")
    with zipfile.ZipFile(a.bundle) as z, zipfile.ZipFile(stage / "as_bundle.zip", "w", zipfile.ZIP_DEFLATED) as o:
        m2 = dict(man, chapters=[c for c in man["chapters"] if c["slug"] in keep])
        for n in z.namelist():
            if n == "manifest.json" or (n.startswith("payloads/") and Path(n).stem not in keep):
                continue
            o.writestr(n, z.read(n))
        o.writestr("manifest.json", json.dumps(m2, ensure_ascii=False, indent=1))
    print(json.dumps({"chapters": keep, "missing": report}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
