"""higgs_colab_runner.py - Higgs TTS 3 book render on a GPU lane (headless).

Same lane contract as scripts/fish_colab_runner.py, so webapp/fish_lane.py, the khpi5
lane_ctl.sh control plane, the harvest loop and the gates work unchanged:

  * input   : $FISH_BASE/as_bundle.zip (default /content) built by
              scripts/fish_bundle.py --engine higgs (payloads carry ``chunks``)
  * state   : $FISH_BASE/as_state.json  {"completed": [...], "progress": {slug: n}}
              (n = last banked CHUNK; manifest chapter "sents" is the chunk count)
  * output  : $FISH_BASE/out/<book_tag>_<slug>_<voice_tag>.mp3
  * log     : stdout (lane_launch redirects it to render.log); the markers
              "=== CHAPTER DONE: <slug> ..." and "ALL CHAPTERS COMPLETE" are parsed.

Engine: bosonai/higgs-audio-v3-tts-4b served by vllm 0.30.0 + vllm-omni 0.30.0 in a clean
Python 3.12 venv (Colab's system Python 3.13 cannot be used: torch mismatch - see
DECISIONS "Higgs TTS 3 works on a Colab L4"). The server runs bf16 on an Ampere/Ada GPU.

Quality gates per chunk (each one paid for in the 2026-10-05 listening session):
  health      RMS 0.005-0.5, mean|diff| > 0.001, peak 0.05-0.999 (no clipping)
  duration    0.18 s/word <= dur <= 1.1 s/word + 3 s (catches truncation and loops)
  abrupt end  last 50 ms RMS / body RMS <= 0.25 (the "...even for a moment" defect)
Failing chunks are re-rolled with seeds 43..46; the best attempt is kept and flagged if
none passes. Output is GAIN-ONLY (no EQ, no dynamic loudnorm) until the cause of the
earlier "clipped" mastered MP3s is isolated.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

BASE = Path(os.environ.get("FISH_BASE", "/content"))
OUT = BASE / "out"
OUT.mkdir(parents=True, exist_ok=True)
WAVS = BASE / "wavs"
WAVS.mkdir(exist_ok=True)
STATE_PATH = BASE / "as_state.json"
BUNDLE = BASE / "as_bundle.zip"
VENV = BASE / "h3env"
MODEL = "bosonai/higgs-audio-v3-tts-4b"
PORT = 8095
SEEDS = (42, 43, 44, 45, 46)
# Sampling: temperature 1.0, top_k 50 - Dave's listening pick on 2026-10-07 (AS Preface A/B, "b") over
# Boson's model-card cloning example ("temperature": 0.8, "top_k": 50; bosonai/higgs-audio-v3-tts-4b
# README, read 2026-10-07). 1.0 is also vllm-omni 0.30.0's deploy-profile default
# (higgs_multimodal_qwen3.yaml); the speech endpoint takes temperature/top_p/top_k only through
# ``extra_params`` (serving_speech.py), so it is sent explicitly to make the recipe visible.
SAMPLING = {"temperature": 1.0, "top_k": 50}
# Muffled / "speakerphone" takes: the Cillian reference keeps 95 % of its energy below ~4.7 kHz; about
# half of raw Higgs takes roll off lower. Re-rolling rarely helps - on the first 300 Armed Struggle
# chunks (2026-10-07) 106 first takes were under 2.7 kHz and 100 still were after 3 seeds (it follows the
# passage, not the seed) - and Dave accepted the fixed Preface "B" with takes at 1.6-2.3 kHz in it.
# Only takes below 1.8 kHz are re-rolled now; every take's roll-off stays in the chunk sidecar.
MIN_ROLLOFF_HZ = 1800.0
MIN_ROLLOFF_DUR_S = 3.0          # "NOTE." and other one-word chunks are too short to measure
BUDGET_S = 10 * 3600
BOOK_TAG, VOICE_TAG = "book", "cillian_higgs"
ORDER: list = []


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------
# environment: clean py3.12 venv with vllm + vllm-omni, patched for the L4
# ----------------------------------------------------------------------------

def bootstrap_env():
    if not (VENV / "bin" / "vllm").exists():
        log("=== installing runtime (py3.12 venv, vllm 0.30.0) ===")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=False)
        subprocess.run(["uv", "venv", str(VENV), "--python", "3.12"], check=True)
        subprocess.run(["uv", "pip", "install", "-p", str(VENV / "bin" / "python"), "-q",
                        "vllm==0.30.0", "vllm-omni==0.30.0", "huggingface_hub"], check=True)
    yml = glob.glob(str(VENV / "lib/python3.12/site-packages/vllm_omni/deploy/"
                                 "higgs_multimodal_qwen3.yaml"))
    if not yml:
        raise SystemExit("vllm-omni deploy yaml for Higgs not found - version drift?")
    p = Path(yml[0])
    cfg = p.read_text()
    cfg = (cfg.replace("attention_backend: FLASHINFER", "attention_backend: TRITON_ATTN")
              .replace("max_model_len: 8192", "max_model_len: 4096"))
    p.write_text(cfg)


_SRV = {"proc": None}


def start_server():
    stop_server()
    env = dict(os.environ, VLLM_USE_FLASHINFER_SAMPLER="0")
    _SRV["proc"] = subprocess.Popen(
        [str(VENV / "bin" / "vllm"), "serve", MODEL, "--host", "127.0.0.1", "--port", str(PORT),
         "--trust-remote-code", "--omni", "--dtype", "bfloat16"],
        env=env, stdout=open(BASE / "vllm.log", "ab"), stderr=subprocess.STDOUT)
    import requests
    for _ in range(300):
        time.sleep(10)
        try:
            if requests.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=5).ok:
                log("server ready")
                return
        except Exception:
            if _SRV["proc"].poll() is not None:
                break
    raise RuntimeError("vLLM-Omni server never became ready (see vllm.log)")


def stop_server():
    p = _SRV.get("proc")
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=30)
        except Exception:
            p.kill()
    _SRV["proc"] = None


# ----------------------------------------------------------------------------
# audio gates (pure functions, unit-tested in tests/test_higgs_runner.py)
# ----------------------------------------------------------------------------

def _rms(x):
    import numpy as np
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0


def rolloff_hz(w, sr, frac=0.95):
    """Frequency below which ``frac`` of the speech energy lies (loud frames only)."""
    import numpy as np
    n, hop = 2048, 1024
    if len(w) < n * 2:
        return None
    frames = np.lib.stride_tricks.sliding_window_view(w, n)[::hop] * np.hanning(n)
    spec = np.abs(np.fft.rfft(frames, axis=1)) ** 2
    energy = spec.sum(axis=1)
    p = spec[energy > np.percentile(energy, 40)].mean(axis=0)
    cum = np.cumsum(p) / max(float(p.sum()), 1e-12)
    return float(np.fft.rfftfreq(n, 1 / sr)[min(int(np.searchsorted(cum, frac)), len(cum) - 1)])


def attempt_score(ok, m):
    """Lower is better, for keeping the best of several seeds when none passes."""
    if ok:
        return 0.0
    if m.get("why") == "abrupt end":
        return m.get("end", 9)
    if m.get("why") == "muffled":
        return 10.0 - m.get("roll", 0) / 1000.0
    if m.get("why") == "voice":                     # wrong-sounding speaker: worse than muffled
        return 10.0 + (1.0 - m.get("sim", 0)) * 10.0
    return 99.0


HARD_FAILS = ("too short", "health/clipping")


def take_penalty(m, min_rolloff_hz=MIN_ROLLOFF_HZ, min_voice_sim=0.90, max_end_ratio=0.8):
    """Modal worker's verdict on one take: (penalty, reasons); 0 = accept. Lower is better when every
    seed fails. ``m`` = gate_chunk metrics plus roll (Hz), sim (voice match) and asr_* (per-chunk ASR).

    Ordered by what Dave hears as worst: missing words (AS Preface chunk 20: 25 words never spoken),
    then a voice that is not Cillian, then muffled, then a cut-off last syllable. The end-loudness
    ratio is only a hard fault above 0.8 (stops mid-word): at 0.25 it re-rolled 4 Preface chunks the
    ASR showed were complete, which was most of the 2.6 attempts/chunk measured on 2026-10-07."""
    why = m.get("why") or ""
    if why in HARD_FAILS or why.startswith("duration"):
        return 99.0, why
    p, reasons = 0.0, []
    if m.get("asr_bad"):
        p += 30.0 + m.get("asr_tail", 0) + 20.0 * (1.0 - m.get("asr_cover", 1.0))
        reasons.append("words")
    if m.get("sim") is not None and m["sim"] < min_voice_sim:
        p += 10.0 + (min_voice_sim - m["sim"]) * 50.0
        reasons.append("voice")
    if m.get("roll") is not None and m["roll"] < min_rolloff_hz:
        p += 5.0 + (min_rolloff_hz - m["roll"]) / 1000.0
        reasons.append("muffled")
    if m.get("end", 0) > max_end_ratio:
        p += 3.0 + m["end"]
        reasons.append("cut-off end")
    if m.get("start", 0) > 0.5:
        p += 2.0
        reasons.append("abrupt start")
    return round(p, 3), "+".join(reasons)


def gate_chunk(w, sr, words, min_s_per_word=0.18, min_rolloff_hz=MIN_ROLLOFF_HZ):
    """Return (ok, metrics). ``w`` is mono float32."""
    import numpy as np
    d = len(w) / sr
    m = {"dur": round(d, 2)}
    if d < 0.5:
        return False, {**m, "why": "too short"}
    rms = _rms(w)
    md = float(np.abs(np.diff(w)).mean())
    pk = float(np.abs(w).max())
    m.update(rms=round(rms, 4), md=round(md, 4), peak=round(pk, 3))
    if not (0.005 < rms < 0.5 and md > 0.001 and 0.05 < pk < 0.999):
        return False, {**m, "why": "health/clipping"}
    if not (min_s_per_word * words <= d <= 1.1 * words + 3.0):
        return False, {**m, "why": f"duration {d:.1f}s for {words} words"}
    body = _rms(w[int(0.3 * sr): max(int(0.3 * sr) + 1, len(w) - int(0.3 * sr))]) + 1e-9
    end_ratio = _rms(w[-int(0.05 * sr):]) / body
    start_ratio = _rms(w[:int(0.05 * sr)]) / body
    m.update(end=round(end_ratio, 3), start=round(start_ratio, 3))
    if end_ratio > 0.25:
        return False, {**m, "why": "abrupt end"}
    if start_ratio > 0.5:
        return False, {**m, "why": "abrupt start"}
    if min_rolloff_hz and d >= MIN_ROLLOFF_DUR_S:
        roll = rolloff_hz(w, sr)
        if roll is not None:
            m["roll"] = round(roll)
            if roll < min_rolloff_hz:
                return False, {**m, "why": "muffled"}
    return True, m


# ----------------------------------------------------------------------------
# checkpoints: Colab removes these VMs after ~1 hour (3 of 3 on 2026-10-06), so finished chunk
# audio must leave the VM continuously. The runner packs new chunk wavs into small
# ckpt_<slug>_<lo>-<hi>.tgz files in /content/out; lane_ctl (khpi5) downloads them on every
# progress poll and uploads them to the NEXT VM as /content/ckpt_*.tgz, where
# restore_checkpoints() unpacks them so generation resumes at the first missing chunk.
# ----------------------------------------------------------------------------

CKPT_EVERY_CHUNKS = 10
CKPT_EVERY_S = 120
_CKPT_MEMBER = re.compile(r"ch\w+/\d{4}\.wav")


def restore_checkpoints(base=None, wavs=None) -> int:
    """Unpack uploaded ckpt_*.tgz into the wav bank; returns the number of wavs restored."""
    import tarfile
    n = 0
    for t in sorted(glob.glob(str(Path(base or BASE) / "ckpt_*.tgz"))):
        try:
            with tarfile.open(t) as tf:
                for m in tf.getmembers():
                    if m.isfile() and _CKPT_MEMBER.fullmatch(m.name):   # nothing else is ever extracted
                        tf.extract(m, str(wavs or WAVS))
                        n += 1
        except Exception as e:
            log(f"checkpoint {Path(t).name} unreadable: {str(e)[:100]}")
    return n


def write_checkpoint(slug, lo, hi, wdir, out=None):
    """Pack chunk wavs lo..hi (1-based, inclusive) of a chapter into out/ckpt_<slug>_<lo>-<hi>.tgz.
    Written to a .part file and renamed, so a poller never sees a half-written archive."""
    import tarfile
    out = Path(out or OUT)
    files = [Path(wdir) / f"{i:04d}.wav" for i in range(lo, hi + 1) if (Path(wdir) / f"{i:04d}.wav").exists()]
    if not files:
        return None
    name = f"ckpt_{slug}_{lo:04d}-{hi:04d}.tgz"
    part = out / (name + ".part")
    with tarfile.open(part, "w:gz", compresslevel=1) as tf:
        for f in files:
            tf.add(f, arcname=f"{slug}/{f.name}")
    part.rename(out / name)
    return name


def gap_after(chunk, next_chunk):
    """Silence after a chunk: 0.3 s within a paragraph or between headings, 0.5 s across
    paragraphs (kept in step with scripts/higgs_prep.gap_after; duplicated because this file
    is uploaded to the VM on its own)."""
    if next_chunk is None:
        return 0.0
    if chunk.get("heading") and next_chunk.get("heading"):
        return 0.3
    return 0.5 if chunk["para"] != next_chunk["para"] else 0.3


def trim_and_fade(w, sr, thr_db=-55, pad=0.15, fade_ms=15):
    import numpy as np
    idx = np.where(np.abs(w) > 10 ** (thr_db / 20))[0]
    if len(idx):
        w = w[max(0, idx[0] - int(pad * sr)): min(len(w), idx[-1] + int(pad * sr))]
    f = int(fade_ms / 1000 * sr)
    w = w.copy()
    if len(w) > 2 * f:
        w[:f] *= np.linspace(0, 1, f)
        w[-f:] *= np.linspace(1, 0, f)
    return w


def gain_only(full, sr, wav_path):
    """Scale to ~-20 LUFS integrated with sample peak <= -2 dBFS. No EQ, no compression."""
    import re
    import numpy as np
    import soundfile as sf
    sf.write(str(wav_path), full, sr)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_path),
                        "-af", "ebur128=peak=sample", "-f", "null", "-"],
                       capture_output=True, text=True)
    mi = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r.stderr)
    mp = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", r.stderr)
    gain = -20.0 - float(mi[-1]) if mi else 0.0
    if mp:
        gain = min(gain, -2.0 - float(mp[-1]))
    gain = max(-12.0, min(12.0, gain))
    return (full * (10 ** (gain / 20))).astype(np.float32), gain


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main():
    global BOOK_TAG, VOICE_TAG, ORDER
    if not BUNDLE.exists():
        raise SystemExit(f"as_bundle.zip missing at {BASE}")
    with zipfile.ZipFile(BUNDLE) as zf:
        zf.extractall(BASE)
    mf = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    ORDER = [c["slug"] for c in mf["chapters"]]
    BOOK_TAG = mf.get("book_tag") or BOOK_TAG
    VOICE_TAG = mf.get("voice_tag") or VOICE_TAG
    scope = BASE / "as_chapters.txt"
    if scope.exists():
        wanted = [s.strip() for s in scope.read_text().split(",") if s.strip()]
        ORDER = [s for s in ORDER if s in wanted]

    restored = restore_checkpoints()
    if restored:
        log(f"restored {restored} chunk wav(s) from checkpoints uploaded by the previous VM")
    bootstrap_env()
    import numpy as np
    import soundfile as sf
    start_server()

    import base64
    import requests
    refs = json.loads((BASE / "refs/refs.json").read_text(encoding="utf-8"))
    ref_text = refs["ref_full_text"]
    ref_url = "data:audio/wav;base64," + base64.b64encode(
        (BASE / "refs/cillian_irish.wav").read_bytes()).decode()

    def generate(text, seed):
        for attempt in range(3):
            try:
                if _SRV["proc"] is None or _SRV["proc"].poll() is not None:
                    log("server not running - restarting")
                    start_server()
                r = requests.post(f"http://127.0.0.1:{PORT}/v1/audio/speech", json={
                    "model": MODEL, "input": text, "response_format": "wav",
                    "ref_audio": ref_url, "ref_text": ref_text,
                    "max_new_tokens": 2048, "seed": seed, "extra_params": SAMPLING}, timeout=900)
                r.raise_for_status()
                import io
                w, sr = sf.read(io.BytesIO(r.content), dtype="float32")
                if w.ndim > 1:
                    w = w.mean(axis=1)
                return w, sr
            except requests.exceptions.ConnectionError:
                log("connection error - restarting server")
                start_server()
        raise RuntimeError("server unreachable after restarts")

    def state_load():
        if STATE_PATH.exists():
            return json.loads(STATE_PATH.read_text())
        return {"completed": [], "progress": {}}

    st = state_load()
    t0 = time.time()
    last_save = 0.0
    for slug in ORDER:
        if slug in st["completed"]:
            continue
        payload = json.loads((BASE / "payloads" / f"{slug}.json").read_text(encoding="utf-8"))
        chunks = payload["chunks"]
        wdir = WAVS / slug
        wdir.mkdir(exist_ok=True, parents=True)
        log(f"=== {slug}: {len(chunks)} chunks, resuming at {st['progress'].get(slug, 0)} ===")
        warns = 0
        sr = 24000
        ck_hi = 0                      # last chunk already packed into a checkpoint (or restored)
        while (wdir / f"{ck_hi + 1:04d}.wav").exists():
            ck_hi += 1
        ck_t = time.time()
        for i, ch in enumerate(chunks, 1):
            wp = wdir / f"{i:04d}.wav"
            if wp.exists():
                st["progress"][slug] = i
                continue
            text = ch.get("tagged") or ch["text"]
            best = None
            for seed in SEEDS:
                try:
                    w, sr = generate(text, seed)
                except Exception as e:
                    log(f"  [{slug} {i}] seed {seed} error: {str(e)[:100]}")
                    continue
                ok, m = gate_chunk(w, sr, ch["words"])
                score = attempt_score(ok, m)
                if best is None or ok or score < best[2]:
                    best = (w, m, score, ok, seed)
                if ok:
                    break
            if best is None:
                (wdir / f"{i:04d}.FAIL").write_text("no audio from any seed")
                log(f"  [{slug} {i}] FAILED: no audio")
            else:
                w, m, _, ok, seed = best
                sf.write(str(wp), w, sr)
                if not ok:
                    warns += 1
                    (wdir / f"{i:04d}.WARN").write_text(json.dumps(m))
                    log(f"  [{slug} {i}] WARN kept best attempt: {m}")
            st["progress"][slug] = i
            # the chapter's last chunk always closes a checkpoint: otherwise the final few chunks exist
            # only inside the chapter mp3 (2026-10-07 fill job: 6 chunks, incl. every 1-chunk chapter)
            if i > ck_hi and (i - ck_hi >= CKPT_EVERY_CHUNKS or time.time() - ck_t >= CKPT_EVERY_S
                              or i == len(chunks)):
                name = write_checkpoint(slug, ck_hi + 1, i, wdir)
                if name:
                    st.setdefault("ckpts", []).append(name)
                    STATE_PATH.write_text(json.dumps(st, indent=1))   # publish promptly
                    last_save = time.time()
                ck_hi, ck_t = i, time.time()
            if time.time() - last_save > 60 or i == len(chunks):
                STATE_PATH.write_text(json.dumps(st, indent=1))
                last_save = time.time()
            if i % 10 == 0 or i == len(chunks):
                log(f"  [{slug} {i}/{len(chunks)}] elapsed {(time.time() - t0) / 60:.0f}m")
            if time.time() - t0 > BUDGET_S:
                STATE_PATH.write_text(json.dumps(st, indent=1))
                log("=== 10h budget, exiting clean ===")
                stop_server()
                sys.exit(0)

        pieces = []
        for i, ch in enumerate(chunks, 1):
            wp = wdir / f"{i:04d}.wav"
            if not wp.exists():
                continue
            w, sr = sf.read(str(wp), dtype="float32")
            pieces.append(trim_and_fade(w, sr))
            nxt = chunks[i] if i < len(chunks) else None
            gap = gap_after(ch, nxt)
            if gap:
                pieces.append(np.zeros(int(gap * sr), dtype=np.float32))
        full = np.concatenate(pieces)
        scaled, gain = gain_only(full, sr, BASE / f"{slug}_raw.wav")
        raw = BASE / f"{slug}_raw.wav"
        sf.write(str(raw), scaled, sr)
        mp3 = OUT / f"{BOOK_TAG}_{slug}_{VOICE_TAG}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                        "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
        raw.unlink()
        fails = len(list(wdir.glob("*.FAIL")))
        # Checkpoints are KEPT after the chapter mp3 exists: they used to be deleted here, so the last
        # few chunks of every chapter never reached the lane (a fill job that needs the chunk wavs lost
        # 6, 2026-10-07). lane_ctl only re-uploads checkpoints of unfinished chapters, so this costs nothing.
        st["completed"].append(slug)
        st.setdefault("meta", {})[slug] = {"sec": round(len(full) / sr, 1), "sents": len(chunks),
                                           "fails": fails, "warns": warns, "gain_db": round(gain, 2)}
        STATE_PATH.write_text(json.dumps(st, indent=1))
        log(f"=== CHAPTER DONE: {slug} {len(full) / sr / 60:.1f} min, {fails} failed, "
            f"{warns} flagged chunks, gain {gain:+.1f} dB ===")

    stop_server()
    log("ALL CHAPTERS COMPLETE")


if __name__ == "__main__":
    main()
