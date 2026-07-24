#!/usr/bin/env python3
"""Generate a Kaggle kernel that narrates one chapter with CosyVoice 3.

Kaggle script kernels are a single file with no attachable sources, so the
chapter text is embedded at build time rather than fetched at runtime (a
network fetch inside the kernel is one more way for a 30-minute GPU run to
die). The install half of the kernel is lifted verbatim from
run_cosyvoice3.py so the documented install path stays single-sourced; only
the inference half is swapped.

    python scripts/kaggle/build_chapter_kernel.py

Writes scratch/chapter_kernel/{run_chapter.py,kernel-metadata.json}.
"""
import html
import json
import os
import re
import sys

import ebooklib
from ebooklib import epub

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EPUB = os.path.join(ROOT, "data", "library", "YellowWallpaper.epub")
DRIVER = os.path.join(HERE, "run_cosyvoice3.py")
OUTDIR = os.path.join(ROOT, "scratch", "chapter_kernel")

# Explicit anchors: assert the boundaries instead of trusting index arithmetic,
# so a re-released Gutenberg edition fails loudly rather than narrating the
# licence boilerplate.
FIRST = "It is very seldom that mere ordinary people"
LAST = "so that I had to creep over him every time!"

MIN_CHARS = 220   # below this, zero-shot quality degrades (the model warns when
MAX_CHARS = 600   # tts_text is short relative to the prompt transcript)


def extract_paragraphs():
    book = epub.read_epub(EPUB)
    doc = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))[0]
    raw = doc.get_content().decode("utf-8", "replace")
    paras = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", raw, re.S | re.I):
        t = html.unescape(re.sub(r"<[^>]+>", " ", p))
        t = (t.replace("’", "'").replace("‘", "'")
              .replace("“", '"').replace("”", '"')
              .replace("—", " - ").replace("–", "-")
              .replace("…", "..."))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            paras.append(t)

    starts = [i for i, p in enumerate(paras) if p.startswith(FIRST)]
    ends = [i for i, p in enumerate(paras) if p.endswith(LAST)]
    if not starts or not ends:
        sys.exit("chapter anchors not found - the epub edition changed")
    body = paras[starts[0]:ends[-1] + 1]
    non_ascii = {c for p in body for c in p if ord(c) > 127}
    if non_ascii:
        sys.exit("non-ASCII survived normalisation: %r" % sorted(non_ascii))
    return body


def chunk(paras):
    """Group short paragraphs so each synthesis call carries enough text."""
    chunks, buf = [], []
    for p in paras:
        buf.append(p)
        if sum(len(x) + 1 for x in buf) >= MIN_CHARS:
            chunks.append(buf)
            buf = []
    if buf:
        if chunks:
            chunks[-1].extend(buf)
        else:
            chunks.append(buf)
    # split any group that overshot badly on sentence boundaries
    out = []
    for grp in chunks:
        text = " ".join(grp)
        if len(text) <= MAX_CHARS:
            out.append(text)
            continue
        cur = ""
        for sent in re.split(r"(?<=[.!?\"]) +", text):
            if cur and len(cur) + len(sent) + 1 > MAX_CHARS:
                out.append(cur.strip())
                cur = sent
            else:
                cur = (cur + " " + sent).strip()
        if cur:
            out.append(cur.strip())
    return out


INFER_TEMPLATE = r'''
import sys
sys.path.append('third_party/Matcha-TTS')  # per example.py

import os
import re
import time
import json
import difflib
import urllib.request

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

MODEL_DIR = 'pretrained_models/Fun-CosyVoice3-0.5B'
OUT = '/kaggle/working/out'
REF = '/kaggle/working/out/reference_uk_male_minter.wav'
REF_URL = ('https://github.com/davedavedavenm/epub-to-audiobook/raw/master/'
           'chatterbox/voices/uk_male_minter.wav')

REF_TRANSCRIPT = (
    "No, I know that, snapped Bertram. Not that it would make any difference "
    "if she stayed, pursued the relentless George. She flies higher than the "
    "paper trade, my boy. Hang her, said Bertram. It would make it more "
    "interesting for me, I ventured to observe."
)
PROMPT_TEXT = 'You are a helpful assistant.<|endofprompt|>' + REF_TRANSCRIPT

TITLE = __TITLE__
CHUNKS = json.loads(r"""__CHUNKS__""")
print('chapter: %s, %d chunks, %d words'
      % (TITLE, len(CHUNKS), sum(len(c.split()) for c in CHUNKS)))

os.makedirs(OUT, exist_ok=True)

if not os.path.exists(REF):
    urllib.request.urlretrieve(REF_URL, REF)
info = torchaudio.info(REF)
ref_secs = info.num_frames / info.sample_rate
print('reference: %.2fs @ %dHz' % (ref_secs, info.sample_rate))
if not (3.0 < ref_secs < 40.0):
    raise SystemExit('reference audio looks wrong (%.2fs)' % ref_secs)

print('torch', torch.__version__, 'cuda', torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit('no GPU visible - refusing to run on CPU')
print('gpu:', torch.cuda.get_device_name(0))

t0 = time.time()
cosyvoice = AutoModel(model_dir=MODEL_DIR)
sr = cosyvoice.sample_rate
print('model loaded in %.0fs, sample_rate=%d' % (time.time() - t0, sr))

def norm(s):
    return [w for w in re.sub(r"[^a-z0-9' ]+", ' ', s.lower()).split() if w]


GAP = torch.zeros(1, int(0.45 * sr))
pieces, manifest = [], []
asr = None
t_start = time.time()
for idx, text in enumerate(CHUNKS):
    t1 = time.time()
    chunks = [o['tts_speech'] for o in
              cosyvoice.inference_zero_shot(text, PROMPT_TEXT, REF, stream=False)]
    if not chunks:
        raise SystemExit('no audio for chunk %d' % idx)
    speech = torch.cat(chunks, dim=1)
    secs = speech.shape[1] / sr
    gen = time.time() - t1

    if idx == 0:
        # EARLY GATE. Runs v4-v16 produced confident, well-formed speech that
        # decoded to unrelated languages. Prove chunk 0 reproduces its text
        # before spending ~30 more minutes of GPU on the other 104 chunks.
        import whisper
        asr = whisper.load_model('small')
        torchaudio.save('/tmp/probe.wav', speech, sr)
        pr = asr.transcribe('/tmp/probe.wav', language='en')
        ratio = difflib.SequenceMatcher(None, norm(text), norm(pr['text'])).ratio()
        print('\n=== EARLY GATE: similarity %.3f ===' % ratio)
        print('  REF: ' + text[:220])
        print('  ASR: ' + pr['text'].strip()[:220] + '\n', flush=True)
        if ratio < 0.75:
            raise SystemExit(
                'EARLY GATE FAILED (%.3f) - the engine is not reproducing the '
                'text. Aborting rather than rendering 40 minutes of babble.' % ratio)
    pieces.append(speech)
    pieces.append(GAP)
    manifest.append({'idx': idx, 'text': text, 'secs': round(secs, 2)})
    done = sum(p.shape[1] for p in pieces) / sr
    print('[%3d/%3d] %5.1fs audio in %5.1fs (RTF %.2f) | total %.1f min | elapsed %.1f min'
          % (idx + 1, len(CHUNKS), secs, gen, gen / secs, done / 60,
             (time.time() - t_start) / 60), flush=True)

full = torch.cat(pieces, dim=1)
wav_path = os.path.join(OUT, 'chapter.wav')
torchaudio.save(wav_path, full, sr)
total_min = full.shape[1] / sr / 60
print('\nchapter.wav  %.1f min  (generated in %.1f min)'
      % (total_min, (time.time() - t_start) / 60))
os.system('ffmpeg -y -loglevel error -i %s -b:a 96k %s'
          % (wav_path, os.path.join(OUT, 'chapter.mp3')))

with open(os.path.join(OUT, 'chapter_text.txt'), 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(CHUNKS) + '\n')

# ------------------------------------------------------------ ASR verification
print('\n=== Whisper ASR verification (every chunk) ===')
offset, report = 0.0, []
for m in manifest:
    seg = full[:, int(offset * sr):int((offset + m['secs']) * sr)]
    tmp = '/tmp/seg.wav'
    torchaudio.save(tmp, seg, sr)
    r = asr.transcribe(tmp, language='en')
    hyp = r['text'].strip()
    ratio = difflib.SequenceMatcher(None, norm(m['text']), norm(hyp)).ratio()
    report.append({'idx': m['idx'], 'similarity': round(ratio, 4),
                   'expected': m['text'], 'asr': hyp})
    if ratio < 0.75:
        print('  LOW [%d] %.3f\n    REF: %s\n    ASR: %s'
              % (m['idx'], ratio, m['text'][:150], hyp[:150]))
    offset += m['secs'] + 0.45

with open(os.path.join(OUT, 'asr_verification.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

sims = [r['similarity'] for r in report]
avg = sum(sims) / len(sims)
bad = [r['idx'] for r in report if r['similarity'] < 0.75]
print('\nchunks: %d | mean similarity %.3f | min %.3f | below 0.75: %d %s'
      % (len(sims), avg, min(sims), len(bad), bad[:20]))
print('VERDICT:', 'PASS' if avg > 0.85 and len(bad) <= len(sims) * 0.05
      else 'FAIL - output does not reliably match the text')
'''


def main():
    paras = extract_paragraphs()
    chunks = chunk(paras)
    words = sum(len(c.split()) for c in chunks)
    print("paragraphs: %d -> chunks: %d (%d words, ~%.0f min audio)"
          % (len(paras), len(chunks), words, words / 155))
    print("chunk chars: min %d, max %d"
          % (min(len(c) for c in chunks), max(len(c) for c in chunks)))

    infer = (INFER_TEMPLATE
             .replace("__TITLE__", repr("The Yellow Wallpaper - "
                                        "Charlotte Perkins Gilman"))
             .replace("__CHUNKS__", json.dumps(chunks)))

    with open(DRIVER, encoding="utf-8") as f:
        driver = f.read()
    new, n = re.subn(r"INFER_SRC = r'''.*?'''",
                     lambda _: "INFER_SRC = r'''" + infer + "'''",
                     driver, count=1, flags=re.S)
    if n != 1:
        sys.exit("could not splice INFER_SRC into the driver")

    os.makedirs(OUTDIR, exist_ok=True)
    kernel = os.path.join(OUTDIR, "run_chapter.py")
    with open(kernel, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    meta = {"id": "davedavedavedavenm/cosyvoice3-yellow-wallpaper",
            "title": "cosyvoice3-yellow-wallpaper",
            "code_file": "run_chapter.py", "language": "python",
            "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [],
            "kernel_sources": []}
    with open(os.path.join(OUTDIR, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    compile(new, kernel, "exec")
    compile(infer, "infer", "exec")
    print("wrote", kernel)


if __name__ == "__main__":
    main()
