"""modal_higgs_book.py - render a book with Higgs TTS 3 on Modal L4 GPUs, chapters in parallel.

Why Modal (2026-10-06): Colab lane VMs are removed after ~1 hour and run one at a time (~30 h and
~53 units for Armed Struggle). Modal functions run up to 24 h, scale out, and bill per second
(L4 $0.000222/s = $0.80/h, modal.com/pricing, checked 2026-10-06); the Starter plan includes $30/month.

Design (same pattern as scripts/render_armed_struggle_full_modal.py, which rendered on Modal in
September):
  * the image bakes vllm 0.30.0 + vllm-omni 0.30.0 + the Higgs weights + the Cillian reference;
  * each container starts the vLLM server once (@modal.enter) and renders BATCHES of chunks;
  * the driver keeps every returned chunk wav on local disk immediately, so a crash or a stopped run
    resumes exactly where it was (nothing is regenerated), and enforces a hard spend cap between rounds;
  * chunks are paragraph-sized (default 110 words, 2-5 sentences) and are joined with Dave's chosen
    "V3" join (scripts/higgs_assemble.py); per-chunk gates and seed re-rolls are the Colab runner's.

Usage (driver runs locally; `modal` must be authenticated):
    python scripts/modal_higgs_book.py BOOK.epub --title "Armed Struggle" --start 8 --end 8   # rehearsal
    python scripts/modal_higgs_book.py BOOK.epub --title "Armed Struggle" --budget 26          # whole book
Outputs: scratch/modal_higgs/<book_tag>/{chunks/<slug>/NNNN.wav, chapters/NNN_<title>.mp3, run.json}
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import modal

from higgs_book_plan import L4_USD_PER_S, estimate_usd, load_bundle, plan_batches, spent_usd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "webapp")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MODEL = "bosonai/higgs-audio-v3-tts-4b"
PORT = 8095
SEEDS = (42, 43, 44, 45, 46)

app = modal.App("higgs-book")


def _bake_weights_and_patch():
    """Runs at image build: download the weights into the image and apply the proven L4 patch."""
    import glob
    import pathlib

    from huggingface_hub import snapshot_download
    snapshot_download(MODEL)
    yml = glob.glob("/usr/local/lib/python3.12/site-packages/vllm_omni/deploy/higgs_multimodal_qwen3.yaml")
    if not yml:
        raise SystemExit("vllm-omni deploy yaml for Higgs not found - version drift?")
    p = pathlib.Path(yml[0])
    p.write_text(p.read_text().replace("attention_backend: FLASHINFER", "attention_backend: TRITON_ATTN"))


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install("vllm==0.30.0", "vllm-omni==0.30.0", "huggingface_hub", "soundfile", "numpy", "requests")
    .run_function(_bake_weights_and_patch)
    .env({"FISH_BASE": "/tmp/hr", "VLLM_USE_FLASHINFER_SAMPLER": "0"})
    .add_local_file(str(ROOT / "chatterbox" / "voices" / "cillian_irish.wav"), "/root/ref.wav")
    .add_local_file(str(ROOT / "fixtures" / "fish_ref_texts.json"), "/root/ref_texts.json")
    .add_local_python_source("higgs_colab_runner")
)


@app.cls(image=image, gpu="L4", timeout=3600, scaledown_window=120, max_containers=6)
class Higgs:
    @modal.enter()
    def start(self):
        import base64

        import requests
        self.proc = subprocess.Popen(
            ["vllm", "serve", MODEL, "--host", "127.0.0.1", "--port", str(PORT),
             "--trust-remote-code", "--omni", "--dtype", "bfloat16"],
            stdout=open("/tmp/vllm.log", "ab"), stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < 1200:
            time.sleep(5)
            try:
                if requests.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=5).ok:
                    break
            except Exception:
                if self.proc.poll() is not None:
                    break
        else:
            raise RuntimeError("vLLM server did not start in 20 min")
        if self.proc.poll() is not None:
            raise RuntimeError("vLLM server exited: " + Path("/tmp/vllm.log").read_text()[-1500:])
        self.ref_url = "data:audio/wav;base64," + base64.b64encode(Path("/root/ref.wav").read_bytes()).decode()
        self.ref_text = json.loads(Path("/root/ref_texts.json").read_text(encoding="utf-8"))["ref_full_text"]
        self.ready_s = time.time() - t0

    @modal.method()
    def render(self, job: dict) -> dict:
        """job = {"slug", "items": [{"i", "text", "words"}], "parallel"} ->
        {"items": [...], "wall_s": container seconds spent on this batch}.

        Chunks are sent to vLLM CONCURRENTLY (default 4 at a time): one request at a time leaves the L4
        mostly idle, and vLLM batches concurrent requests, so GPU-seconds per audio-second drop."""
        from concurrent.futures import ThreadPoolExecutor

        t_batch = time.time()
        with ThreadPoolExecutor(max_workers=int(job.get("parallel") or 4)) as pool:
            items = list(pool.map(lambda it: self._one(job["slug"], it), job["items"]))
        return {"items": items, "wall_s": round(time.time() - t_batch, 1)}

    def _one(self, slug: str, it: dict) -> dict:
        import numpy as np
        import requests
        import soundfile as sf

        import higgs_colab_runner as hr
        best, err = None, ""
        for seed in SEEDS:
            try:
                r = requests.post(f"http://127.0.0.1:{PORT}/v1/audio/speech", json={
                    "model": MODEL, "input": it["text"], "response_format": "wav",
                    "ref_audio": self.ref_url, "ref_text": self.ref_text,
                    "max_new_tokens": 4096, "seed": seed}, timeout=900)
                r.raise_for_status()
                w, sr = sf.read(io.BytesIO(r.content), dtype="float32")
                if w.ndim > 1:
                    w = w.mean(axis=1)
            except Exception as e:
                err = str(e)[:200]
                continue
            ok, m = hr.gate_chunk(w, sr, it["words"])
            score = m.get("end", 9) if m.get("why") in (None, "abrupt end") else 99
            if best is None or ok or score < best[2]:
                best = (w, m, score, ok, seed, sr)
            if ok:
                break
        if best is None:
            return {"slug": slug, "i": it["i"], "wav": None, "ok": False, "metrics": {"why": "no audio", "err": err}}
        w, m, _, ok, seed, sr = best
        buf = io.BytesIO()
        sf.write(buf, np.asarray(w, dtype=np.float32), sr, format="WAV", subtype="PCM_16")
        return {"slug": slug, "i": it["i"], "wav": buf.getvalue(), "ok": ok,
                "metrics": {**m, "seed": seed}, "audio_s": round(len(w) / sr, 1)}

    @modal.exit()
    def stop(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


# ----------------------------------------------------------------------------- driver (local)

def _loudness(wav_path: Path) -> tuple:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_path), "-af", "ebur128=peak=sample",
                        "-f", "null", "-"], capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", r.stderr)
    return (float(i[-1]) if i else None), (float(p[-1]) if p else None)


def assemble_chapter(man_ch: dict, payload: dict, chunk_dir: Path, out_dir: Path) -> Path | None:
    import numpy as np
    import soundfile as sf

    import higgs_assemble as ha
    slug, chunks = man_ch["slug"], payload["chunks"]
    files = [chunk_dir / slug / f"{i:04d}.wav" for i in range(1, len(chunks) + 1)]
    if not all(f.exists() for f in files):
        return None
    wavs, sr = [], 24000
    for f in files:
        w, sr = sf.read(str(f), dtype="float32")
        wavs.append(w)
    full = ha.assemble(wavs, chunks, sr)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{slug}_raw.wav"
    sf.write(str(raw), full, sr, subtype="PCM_16")
    gain = ha.loudness_gain_db(*_loudness(raw))
    sf.write(str(raw), (full * (10 ** (gain / 20))).astype(np.float32), sr, subtype="PCM_16")
    title = re.sub(r'[\\/:*?"<>|]', "", str(man_ch.get("title") or slug)).strip()[:80]
    mp3 = out_dir / f"{int(man_ch['index']):03d}_{title}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-codec:a", "libmp3lame",
                    "-b:a", "192k", str(mp3)], check=True)
    raw.unlink()
    return mp3


def main(argv=None) -> int:
    import fish_bundle

    ap = argparse.ArgumentParser(description="Render a book with Higgs TTS 3 on Modal")
    ap.add_argument("epub")
    ap.add_argument("--title", required=True)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--chunk-words", type=int, default=110)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--containers", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=4, help="concurrent chunks per GPU (vLLM batches them)")
    ap.add_argument("--budget", type=float, required=True, help="hard USD cap for THIS run (credit is $30/month)")
    ap.add_argument("--out", default=str(ROOT / "scratch" / "modal_higgs"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    out_root = Path(a.out)
    out_root.mkdir(parents=True, exist_ok=True)
    bundle = out_root / f"{fish_bundle._tagify(a.title)}_bundle.zip"
    man = fish_bundle.build_bundle(a.epub, bundle, title=a.title, start=a.start, end=a.end,
                                   engine="higgs", chunk_max_words=a.chunk_words)
    import book_preflight
    print(book_preflight.format_report(man["preflight"]))
    if not man["preflight"]["ok"]:
        return 3
    man, pay = load_bundle(bundle)
    book_dir = out_root / man["book_tag"]
    chunk_dir, chap_dir = book_dir / "chunks", book_dir / "chapters"
    batches = plan_batches(man, pay, chunk_dir, a.batch)
    for b in batches:
        b["parallel"] = a.parallel
    est = estimate_usd(batches, min(a.containers, max(1, len(batches))))
    print(f"to render: {sum(len(b['items']) for b in batches)} chunks in {len(batches)} batches; "
          f"estimated ${est} (cap ${a.budget})")
    if est > a.budget:
        print("REFUSED: estimate exceeds the cap - raise --budget deliberately or render fewer chapters")
        return 4
    if a.dry_run:
        return 0

    log = (book_dir / "run.log").open("a", encoding="utf-8")
    run = {"gpu_s": 0.0, "audio_s": 0.0, "chunks": 0, "flagged": 0, "failed": 0,
           "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    containers = min(a.containers, len(batches))
    round_size = containers * 3
    with modal.enable_output(), app.run():
        worker = Higgs()
        for r0 in range(0, len(batches), round_size):
            if spent_usd(run["gpu_s"], containers) > a.budget:
                print(f"STOPPED: spend cap ${a.budget} reached (est ${spent_usd(run['gpu_s'], containers)})")
                break
            for res in worker.render.map(batches[r0:r0 + round_size], order_outputs=False, return_exceptions=True):
                if isinstance(res, Exception):
                    print("batch error:", str(res)[:300], file=log, flush=True)
                    continue
                run["gpu_s"] += res["wall_s"]
                for it in res["items"]:
                    run["audio_s"] += it.get("audio_s", 0.0)
                    if it["wav"] is None:
                        run["failed"] += 1
                        continue
                    d = chunk_dir / it["slug"]
                    d.mkdir(parents=True, exist_ok=True)
                    (d / f"{it['i']:04d}.wav").write_bytes(it["wav"])
                    run["chunks"] += 1
                    run["flagged"] += 0 if it["ok"] else 1
                    if not it["ok"]:
                        print(f"flagged {it['slug']}#{it['i']}: {it['metrics']}", file=log, flush=True)
            print(f"{time.strftime('%H:%M:%S')} round {r0 // round_size + 1}: {run['chunks']} chunks, "
                  f"{run['flagged']} flagged, {run['failed']} failed, ~${spent_usd(run['gpu_s'], containers)}, "
                  f"GPU-s per audio-s {run['gpu_s'] / max(run['audio_s'], 1):.2f}", flush=True)

    done = []
    for c in man["chapters"]:
        mp3 = assemble_chapter(c, pay[c["slug"]], chunk_dir, chap_dir)
        if mp3:
            done.append(mp3.name)
    run.update(chapters_done=done, chapters_total=len(man["chapters"]), est_usd=spent_usd(run["gpu_s"], containers),
               gpu_s_per_audio_s=round(run["gpu_s"] / max(run["audio_s"], 1), 2),
               usd_per_audio_hour=round(run["gpu_s"] / max(run["audio_s"], 1) * 3600 * L4_USD_PER_S, 2))
    (book_dir / "run.json").write_text(json.dumps(run, indent=1))
    print(json.dumps(run, indent=1))
    return 0 if len(done) == len(man["chapters"]) else 5


if __name__ == "__main__":
    raise SystemExit(main())
