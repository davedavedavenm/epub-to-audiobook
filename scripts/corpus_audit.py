"""corpus_audit.py - run the automatic book audit over a whole folder of EPUBs (no GPU, no LLM).

This is the regression harness for text extraction. Run it after ANY change to chapter detection,
as_prep, fish_bundle or book_preflight:

    python scripts/corpus_audit.py /path/to/epubs [--out results.json] [--limit N]

On Dave's 187-book library it took the pass rate from 90% (10 refused, 7 crashed) to 100% by finding four
generic classes (file-name titles, imprint pages, books the chapter detector misses, over-eager junk rule).
Pass here = structurally sound text; it does not judge how the audio sounds.
"""
import argparse
import collections
import glob
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp"))

import fish_bundle  # noqa: E402


def audit_folder(folder: str, limit: int | None = None) -> list:
    files = sorted(glob.glob(os.path.join(folder, "*.epub")))[: limit or None]
    results, tmp = [], tempfile.mkdtemp()
    for f in files:
        t0, rec = time.time(), {"file": os.path.basename(f)[:90]}
        try:
            z = os.path.join(tmp, "b.zip")
            m = fish_bundle.build_bundle(f, z, engine="higgs")
            pf = m["preflight"]
            rec.update(ok=pf["ok"], chapters=pf["info"].get("chapters"), words=pf["info"].get("words"),
                       errors=[(e["rule"], e["msg"][:140]) for e in pf["errors"]],
                       warnings=[(w["rule"], w["msg"][:100]) for w in pf["warnings"]],
                       skipped=len(m.get("skipped", [])), stripped=m.get("imprint_sentences_stripped", 0))
            os.remove(z)
        except Exception as e:   # a crash is a finding, not a reason to stop
            rec.update(ok=False, crash=f"{type(e).__name__}: {str(e)[:160]}")
        rec["s"] = round(time.time() - t0, 1)
        results.append(rec)
    return results


def summarise(results: list) -> str:
    n = len(results) or 1
    ok = sum(1 for r in results if r.get("ok"))
    crash = [r for r in results if r.get("crash")]
    refused = [r for r in results if not r.get("ok") and not r.get("crash")]
    rules = collections.Counter(rule for r in results for rule, _ in r.get("errors", []))
    lines = [f"{len(results)} books: PASS {ok} ({100 * ok / n:.1f}%), REFUSED {len(refused)}, CRASHED {len(crash)}"]
    if rules:
        lines.append(f"error rules: {dict(rules)}")
    for r in crash + refused:
        lines.append(f"  {r['file'][:60]} | {(r.get('crash') or str(r.get('errors'))[:110])}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    os.environ["FISH_PREFLIGHT_OVERRIDE"] = "1"
    res = audit_folder(a.folder, a.limit)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
    print(summarise(res))
    return 0 if all(r.get("ok") for r in res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
