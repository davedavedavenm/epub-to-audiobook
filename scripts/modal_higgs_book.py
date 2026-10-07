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


ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "webapp")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MODEL = "bosonai/higgs-audio-v3-tts-4b"
PORT = 8095
SEEDS = (42, 43, 44, 45, 46)
MIN_S_PER_WORD = 0.29   # Cillian/Higgs speaks ~0.37 s/word; faster than this a chunk lost words
# Voice match = cosine similarity of the chunk's speaker embedding to the Cillian reference, using the
# Chatterbox voice encoder (chatterbox-tts 0.1.7, MIT; weights ResembleAI/chatterbox-nano @ VE_REVISION).
# AS Preface at temperature 1.0: normal chunks 0.914-0.967; the two Dave heard as "not Cillian"
# (#20 at 7:41, #26 at 10:23) scored 0.816 and 0.813, #28 0.879.
MIN_VOICE_SIM = 0.90
VE_REPO, VE_REVISION = "ResembleAI/chatterbox-nano", "71ccd1d0081b430592cea481f4307e764e07bc64"
# Per-take completeness check: every take is transcribed and aligned against its own text
# (scripts/chunk_asr_audit.py). The whole-chapter ASR ratio said 98.3 % for a Preface that had lost
# 25 words in one chunk (the model looped on a list of years and skipped a sentence).
ASR_MODEL = "openai/whisper-small.en"

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
    # speaker-embedding scorer: only chatterbox's self-contained voice_encoder package (its top-level
    # __init__ would import the whole TTS stack), plus the encoder weights
    import shutil
    import subprocess as sp
    import zipfile
    from huggingface_hub import hf_hub_download
    sp.run(["pip", "download", "chatterbox-tts==0.1.7", "--no-deps", "-d", "/tmp/cb"], check=True)
    with zipfile.ZipFile(glob.glob("/tmp/cb/chatterbox_tts-0.1.7-*.whl")[0]) as z:
        for n in z.namelist():
            if n.startswith("chatterbox/models/voice_encoder/") and n.endswith(".py"):
                dst = pathlib.Path("/root/ve_pkg") / pathlib.Path(n).name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(z.read(n))
    shutil.copy(hf_hub_download(VE_REPO, "ve.safetensors", revision=VE_REVISION), "/root/ve.safetensors")
    snapshot_download(ASR_MODEL)


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install("vllm==0.30.0", "vllm-omni==0.30.0", "huggingface_hub", "soundfile", "numpy", "requests",
                 "librosa", "safetensors", "num2words")
    .run_function(_bake_weights_and_patch)
    .env({"FISH_BASE": "/tmp/hr", "VLLM_USE_FLASHINFER_SAMPLER": "0"})
    .add_local_file(str(ROOT / "chatterbox" / "voices" / "cillian_irish.wav"), "/root/ref.wav")
    .add_local_file(str(ROOT / "fixtures" / "fish_ref_texts.json"), "/root/ref_texts.json")
    .add_local_python_source("higgs_colab_runner", "higgs_assemble", "chunk_asr_audit", "qa_asr")
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
        self._load_voice_encoder()
        self._load_asr()
        self.ready_s = time.time() - t0

    def _load_voice_encoder(self):
        import sys as _sys
        import threading

        import soundfile as sf
        import torch
        from safetensors.torch import load_file
        _sys.path.insert(0, "/root")
        from ve_pkg.voice_encoder import VoiceEncoder
        torch.set_num_threads(2)
        self.ve = VoiceEncoder()
        self.ve.load_state_dict(load_file("/root/ve.safetensors"))
        self.ve.eval()
        self.ve_lock = threading.Lock()
        w, sr = sf.read("/root/ref.wav", dtype="float32")
        self.ref_emb = self._embed(w.mean(axis=1) if w.ndim > 1 else w, sr)

    def _embed(self, w, sr):
        import librosa
        w16 = librosa.resample(w, orig_sr=sr, target_sr=16000)
        if len(w16) < 16000 * 1.6:
            return None
        with self.ve_lock:
            return self.ve.embeds_from_wavs([w16], sample_rate=16000, as_spk=True)

    def voice_sim(self, w, sr):
        import numpy as np
        e = self._embed(w, sr)
        return None if e is None else round(float(np.dot(self.ref_emb, e)), 3)

    @modal.method()
    def render(self, job: dict) -> dict:
        """job = {"slug", "items": [{"i", "text", "words"}], "parallel"} ->
        {"items": [...], "wall_s": container seconds spent on this batch}.

        Chunks are sent to vLLM CONCURRENTLY (default 4 at a time): one request at a time leaves the L4
        mostly idle, and vLLM batches concurrent requests, so GPU-seconds per audio-second drop."""
        from concurrent.futures import ThreadPoolExecutor

        t_batch = time.time()
        with ThreadPoolExecutor(max_workers=int(job.get("parallel") or 4)) as pool:
            items = list(pool.map(lambda it: self._one(job["slug"], it, job.get("sampling")), job["items"]))
        return {"items": items, "wall_s": round(time.time() - t_batch, 1)}

    def _load_asr(self):
        """Whisper small.en on the same GPU (transformers pipeline, chunk_length_s=30 as in the official
        openai/whisper-small.en model card). Loaded AFTER vLLM has taken its share of GPU memory."""
        import threading

        import torch
        from transformers import pipeline
        self.asr_pipe = pipeline("automatic-speech-recognition", model=ASR_MODEL, chunk_length_s=30,
                                 device="cuda:0", torch_dtype=torch.float16)
        self.asr_lock = threading.Lock()

    def asr_check(self, text: str, w, sr) -> dict:
        import librosa

        import chunk_asr_audit
        w16 = librosa.resample(w, orig_sr=sr, target_sr=16000)
        with self.asr_lock:
            heard = self.asr_pipe({"raw": w16, "sampling_rate": 16000}, batch_size=4)["text"]
        a = chunk_asr_audit.audit_chunk(re.sub(r"<\|[^|]*\|>", "", text), heard)
        return {"asr_cover": a["cover"], "asr_tail": a["tail"], "asr_bad": a["bad"], "asr_drops": a["drops"][:1]}

    def _synth(self, text: str, seed: int, sampling: dict):
        import numpy as np
        import requests
        import soundfile as sf
        r = requests.post(f"http://127.0.0.1:{PORT}/v1/audio/speech", json={
            "model": MODEL, "input": text, "response_format": "wav",
            "ref_audio": self.ref_url, "ref_text": self.ref_text,
            "max_new_tokens": 4096, "seed": seed, "extra_params": sampling}, timeout=900)
        r.raise_for_status()
        w, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        return (w.mean(axis=1) if w.ndim > 1 else np.asarray(w)), sr

    def _judge(self, text: str, words: int, w, sr) -> tuple:
        """All gates on one take -> (penalty, metrics); penalty 0 = accept."""
        import higgs_colab_runner as hr
        _, m = hr.gate_chunk(w, sr, words, min_s_per_word=MIN_S_PER_WORD, min_rolloff_hz=None)
        if not (m.get("why") in hr.HARD_FAILS or str(m.get("why", "")).startswith("duration")):
            if len(w) / sr >= hr.MIN_ROLLOFF_DUR_S:
                roll = hr.rolloff_hz(w, sr)
                if roll is not None:
                    m["roll"] = round(roll)
            m["sim"] = self.voice_sim(w, sr)
            m.update(self.asr_check(text, w, sr))
        pen, why = hr.take_penalty(m, min_voice_sim=MIN_VOICE_SIM)
        m["why"] = why or None
        return pen, m

    def _best_of(self, text: str, words: int, seeds, sampling: dict, log: list):
        best = None
        for seed in seeds:
            try:
                w, sr = self._synth(text, seed, sampling)
            except Exception as e:
                log.append({"seed": seed, "err": str(e)[:120]})
                continue
            pen, m = self._judge(text, words, w, sr)
            log.append({"seed": seed, "pen": pen, "why": m.get("why"), "words": words,
                        "roll": m.get("roll"), "sim": m.get("sim")})
            if best is None or pen < best[0]:
                best = (pen, w, sr, {**m, "seed": seed})
            if pen == 0:
                break
        return best

    def _by_sentence(self, text: str, sampling: dict, log: list):
        """Fallback for a chunk whose words keep going missing (e.g. the AS Preface year list): render
        each sentence on its own and join them with the in-paragraph V3 crossfade."""
        import higgs_assemble as ha
        sents = ha.split_sentences(text)
        if len(sents) < 2:
            return None
        wavs, sr = [], 24000
        for s_ in sents:
            b = self._best_of(s_, len(s_.split()), SEEDS[:3], sampling, log)
            if b is None:
                return None
            wavs.append(b[1])
            sr = b[2]
        return ha.assemble(wavs, [{"para": 0}] * len(wavs), sr), sr

    def _one(self, slug: str, it: dict, sampling: dict | None = None) -> dict:
        import numpy as np
        import soundfile as sf

        import higgs_colab_runner as hr
        sampling = sampling or hr.SAMPLING
        log: list = []
        best = self._best_of(it["text"], it["words"], SEEDS[:3], sampling, log)
        if best is not None and best[0] > 0 and "words" in (best[3].get("why") or ""):
            split = self._by_sentence(it["text"], sampling, log)
            if split is not None:
                pen, m = self._judge(it["text"], it["words"], *split)
                log.append({"split": True, "pen": pen, "why": m.get("why")})
                if pen < best[0]:
                    best = (pen, split[0], split[1], {**m, "split": True})
        # seeds 4-5 only for faults worth paying for; a take that is only muffled keeps the best of 3
        if best is not None and best[0] > 0 and (best[3].get("why") or "") != "muffled":
            more = self._best_of(it["text"], it["words"], SEEDS[3:], sampling, log)
            if more is not None and more[0] < best[0]:
                best = more
        if best is None:
            return {"slug": slug, "i": it["i"], "key": it.get("key"), "wav": None, "ok": False,
                    "metrics": {"why": "no audio", "attempts": log}}
        pen, w, sr, m = best
        buf = io.BytesIO()
        sf.write(buf, np.asarray(w, dtype=np.float32), sr, format="WAV", subtype="PCM_16")
        return {"slug": slug, "i": it["i"], "key": it.get("key"), "wav": buf.getvalue(), "ok": pen == 0,
                "metrics": {**m, "penalty": pen, "attempts": log}, "audio_s": round(len(w) / sr, 1)}

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


def assemble_chapter(man_ch: dict, payload: dict, chunk_dir: Path, out_dir: Path, recipe: str = "") -> Path | None:
    import numpy as np
    import soundfile as sf

    import higgs_assemble as ha
    from higgs_book_plan import chunk_is_current, chunk_key
    slug, chunks = man_ch["slug"], payload["chunks"]
    files = [chunk_dir / slug / f"{i:04d}.wav" for i in range(1, len(chunks) + 1)]
    if not all(chunk_is_current(chunk_dir, slug, i, chunk_key(ch.get("tagged") or ch["text"], recipe))
               for i, ch in enumerate(chunks, 1)):
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
    # driver-only imports: this module is also imported INSIDE the Modal image (image build + containers),
    # where these local helpers are not present
    import fish_bundle
    import higgs_colab_runner as hr
    from higgs_book_plan import (L4_USD_PER_S, OVERHEAD, estimate_usd, load_bundle, metered_usd, plan_batches,
                                 spent_usd)

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
    ap.add_argument("--temperature", type=float, default=None,
                    help="override Boson's documented cloning temperature (0.8) - for listening A/Bs")
    ap.add_argument("--partial-ok", action="store_true",
                    help="start even if the estimate exceeds --budget; the cap still stops the run (resume later)")
    ap.add_argument("--assemble-only", action="store_true",
                    help="no Modal at all: assemble every chapter whose chunks are all present and current ($0)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    sampling = dict(hr.SAMPLING, **({"temperature": a.temperature} if a.temperature is not None else {}))
    # chunk audio is reused only when rendered from the same text with the same model + sampling
    recipe = f"{MODEL} {json.dumps(sampling, sort_keys=True)}"

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
    batches = plan_batches(man, pay, chunk_dir, a.batch, recipe)
    for b in batches:
        b["parallel"], b["sampling"] = a.parallel, sampling
    est = estimate_usd(batches, min(a.containers, max(1, len(batches))))
    print(f"to render: {sum(len(b['items']) for b in batches)} chunks in {len(batches)} batches; "
          f"estimated ${est} (cap ${a.budget})")
    if est > a.budget and not a.partial_ok:
        print("REFUSED: estimate exceeds the cap - raise --budget deliberately or render fewer chapters")
        return 4
    if a.dry_run:
        return 0
    if a.assemble_only:
        done = [mp3.name for c in man["chapters"]
                if (mp3 := assemble_chapter(c, pay[c["slug"]], chunk_dir, chap_dir, recipe))]
        print(f"assembled {len(done)}/{len(man['chapters'])}: {done}")
        return 0 if len(done) == len(man["chapters"]) else 5

    book_dir.mkdir(parents=True, exist_ok=True)
    log = (book_dir / "run.log").open("a", encoding="utf-8")
    run = {"gpu_s": 0.0, "audio_s": 0.0, "chunks": 0, "flagged": 0, "failed": 0,
           "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    containers = max(1, min(a.containers, len(batches)))   # >= 1 even when resuming a finished render
    run_t0 = time.time()

    def render_all(worker, batches) -> bool:
        """Stream ALL batches through one .map; False if the spend cap stopped it.

        Rounds were the cost bug (2026-10-07): each round waited for its slowest batch, the other GPUs
        idled (billed) and, after 2 min idle, shut down - so every round paid fresh ~7 min cold starts.
        Measured $1.91-3.01 per audio hour against the $1.07 the driver claimed. Streaming keeps every
        container busy until the queue is empty. Spend = max(containers x wall clock x rate, Modal's
        metered cost) - the first is what Modal bills at most, the second lags by up to an hour."""
        last_meter, done_b = 0.0, 0
        for res in worker.render.map(batches, order_outputs=False, return_exceptions=True):
            done_b += 1
            if isinstance(res, Exception):
                print("batch error:", str(res)[:300], file=log, flush=True)
            else:
                run["gpu_s"] += res["wall_s"]
                for it in res["items"]:
                    run["audio_s"] += it.get("audio_s", 0.0)
                    if it["wav"] is None:
                        run["failed"] += 1
                        continue
                    d = chunk_dir / it["slug"]
                    d.mkdir(parents=True, exist_ok=True)
                    (d / f"{it['i']:04d}.wav").write_bytes(it["wav"])
                    (d / f"{it['i']:04d}.json").write_text(json.dumps(
                        {"key": it.get("key"), "ok": it["ok"], "metrics": it["metrics"]}), encoding="utf-8")
                    run["chunks"] += 1
                    run["flagged"] += 0 if it["ok"] else 1
                    if not it["ok"]:
                        print(f"flagged {it['slug']}#{it['i']}: {it['metrics']}", file=log, flush=True)
            run["wall_usd"] = round(containers * (time.time() - run_t0) * L4_USD_PER_S * OVERHEAD, 2)
            if time.time() - last_meter > 600:
                metered(run)
                last_meter = time.time()
            spent = max(run["wall_usd"], run.get("metered_usd") or 0.0)
            if done_b % containers == 0 or done_b == len(batches):
                print(f"{time.strftime('%H:%M:%S')} {done_b}/{len(batches)} batches: {run['chunks']} chunks, "
                      f"{run['flagged']} flagged, {run['failed']} failed, spend <= ${spent} "
                      f"(metered ${run.get('metered_usd')}), audio {run['audio_s'] / 3600:.2f} h", flush=True)
            if spent > a.budget:
                print(f"STOPPED: spend cap ${a.budget} reached (${spent}; metered ${run.get('metered_usd')})",
                      flush=True)
                return False
        return True

    def metered(run) -> float:
        """Modal's real metered cost for this app run (GPU + CPU + memory); 0 if the report is unavailable."""
        try:
            import datetime as dt
            end = (dt.date.today() + dt.timedelta(days=2)).isoformat()   # the report needs --start AND --end
            out = subprocess.run(["modal", "billing", "report", "--start", run["started"][:10], "--end", end,
                                  "--json"], capture_output=True, text=True, timeout=120)
            run["metered_usd"] = metered_usd(json.loads(out.stdout), run.get("app_id"))
        except Exception as e:
            print("billing report unavailable:", str(e)[:120], file=log, flush=True)
        return run.get("metered_usd") or 0.0

    with modal.enable_output(), app.run():
        run["app_id"] = app.app_id
        worker = Higgs()
        # passes 2-3 only re-plan chunks that came back with no audio at all; every returned take has
        # already been checked word-by-word (ASR), voice and bandwidth inside the worker
        for pass_no in range(1, 4):
            if pass_no > 1:
                batches = plan_batches(man, pay, chunk_dir, a.batch, recipe)
                for b in batches:
                    b["parallel"], b["sampling"] = a.parallel, sampling
                if not batches:
                    break
                print(f"pass {pass_no}: {sum(len(b['items']) for b in batches)} chunk(s) still missing", flush=True)
            if not render_all(worker, batches):
                break

    done = []
    for c in man["chapters"]:
        mp3 = assemble_chapter(c, pay[c["slug"]], chunk_dir, chap_dir, recipe)
        if mp3:
            done.append(mp3.name)
    metered(run)   # may lag the run by minutes; `modal billing report` gives the final figure
    run.update(chapters_done=done, chapters_total=len(man["chapters"]), est_usd=max(run.get("wall_usd") or 0.0,
                                                                                  spent_usd(run["gpu_s"], containers)),
               gpu_s_per_audio_s=round(run["gpu_s"] / max(run["audio_s"], 1), 2),
               usd_per_audio_hour=round(max(run.get("wall_usd") or 0.0, run.get("metered_usd") or 0.0)
                                        / max(run["audio_s"] / 3600, 1e-6), 2))
    (book_dir / "run.json").write_text(json.dumps(run, indent=1))
    print(json.dumps(run, indent=1))
    return 0 if len(done) == len(man["chapters"]) else 5


if __name__ == "__main__":
    raise SystemExit(main())
