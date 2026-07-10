"""Regression guards for the 2026-07-07 incident fixes (see OPERATIONS.md).

These are deliberate tripwires: if someone reverts or refactors away one of
the incident fixes, a test fails naming the incident it re-opens. Structural
assertions on the source are crude but honest — they encode invariants that
full integration tests (docker + DB + engines) can't cheaply cover.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'webapp' / 'app.py').read_text(encoding='utf-8')
CB_SERVER = (ROOT / 'chatterbox' / 'server.py').read_text(encoding='utf-8')
TADA_SERVER = (ROOT / 'tada' / 'server.py').read_text(encoding='utf-8')
COMPOSE = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')


# --- incident 2026-07-07a: retries must actually run ---

def test_retry_clears_container_name():
    """Job d67c50ac: stale container_name aborted every auto-retry.

    Applies to EVERY path that requeues a job (auto-retry, orphan recovery,
    bulk retry-failed): a stale container_name trips the duplicate-start
    guard and silently no-ops the retry.
    """
    blocks = re.findall(r"UPDATE jobs\s+SET status\s?=\s?'queued',.*?WHERE id\s?=\s?\?", APP, re.S)
    assert len(blocks) >= 3, f"expected >=3 requeue UPDATEs, found {len(blocks)}"
    for b in blocks:
        assert re.search(r"container_name\s?=\s?NULL", b), (
            "a requeue path does not clear container_name — re-opens "
            "incident 2026-07-07a:\n" + b[:200])


def test_job_spawns_respect_queue_runner_flag():
    """The webapp must not race the worker (QUEUE_RUNNER_ENABLED=0)."""
    assert 'threading.Thread(target=start_next_queued_job' not in APP, \
        "direct start_next_queued_job spawn bypasses QUEUE_RUNNER_ENABLED"


# --- incident 2026-07-07b: engine OOM death-spiral ---

def test_engine_servers_serialize_generation():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert '_GEN_LOCK' in src and 'with _GEN_LOCK' in src, \
            f"{name} server generation no longer serialized — re-opens OOM incident 2026-07-07b"
        assert 'inference_mode' in src, f"{name} server lost inference_mode"


def test_engine_containers_have_memory_caps():
    for svc in ('chatterbox-tts', 'tada-tts'):
        block = COMPOSE.split(f'{svc}:', 1)[1][:800]
        assert 'mem_limit' in block, \
            f"{svc} lost its mem_limit — kernel OOM kills return (incident 2026-07-07b)"


def test_slow_engine_timeout_floor():
    assert 'SLOW_ENGINE_MIN_TIMEOUT' in APP or 'Timeout floored' in APP, \
        "slow-engine timeout floor removed — full books will time out again"


def test_metrics_only_from_full_books():
    assert 'partial-range jobs pollute' in APP, \
        "conversion metrics gating removed — ETA pollution returns"


# --- GPU images (incident 2026-07-06/07c) ---

def test_engine_images_gpu_capable():
    for eng in ('chatterbox', 'tada'):
        df = (ROOT / eng / 'Dockerfile').read_text(encoding='utf-8')
        assert 'NVIDIA_VISIBLE_DEVICES' in df, f"{eng} image lost NVIDIA env — silent CPU on GPU hosts"
        assert 'download.pytorch.org/whl/cu' in df, f"{eng} image lost explicit CUDA torch"


def test_tada_torch_stack_pinned():
    """Incident 2026-07-08d: tada's `torch --index-url cu124` was UNPINNED, so
    the hume-tada install (torch>=2.7 + unpinned torchaudio/torchvision)
    re-resolved the whole stack from PyPI to the cu130 build, which needs an
    R580+ driver and silently ran CPU on GPU hosts. The torch stack must be
    version-pinned AND include pinned torchaudio+torchvision from the CUDA
    index, so the requirements install can't drag the default build back in."""
    df = (ROOT / 'tada' / 'Dockerfile').read_text(encoding='utf-8')
    assert re.search(r'torch==\d', df), "tada torch is not version-pinned — cu130 drift returns (2026-07-08d)"
    assert re.search(r'torchaudio==\d', df) and re.search(r'torchvision==\d', df), \
        "tada must pin torchaudio+torchvision too, else requirements re-pulls the cu130 stack (2026-07-08d)"
    # cu130 needs R580+ (rare); the pin must target an older, broadly-supported CUDA
    assert '/whl/cu130' not in df, "tada pinned to cu130 — needs R580+ driver, silent-CPU on most hosts"


def test_chatterbox_kaggle_kernel_pins_cuda_torch():
    """The Chatterbox GPU kernel must install a CUDA-pinned torch BEFORE
    chatterbox-tts, or the pip resolver can pull a CPU/mismatched wheel and the
    kernel silently runs on CPU (the TADA silent-CPU class, 2026-07-08d). It
    must also keep the CUDA-availability gate that refuses a CPU run, and pin
    setuptools<81 (perth watermarker imports the removed pkg_resources)."""
    k = (ROOT / 'scripts' / 'kaggle' / 'run_chatterbox.py').read_text(encoding='utf-8')
    assert re.search(r'torch==\d.*cu\d', k, re.S), "chatterbox kernel torch not CUDA-pinned — silent-CPU risk"
    # Order the actual pip-install INVOCATIONS (ignore prose in comments): the
    # CUDA torch install must precede the chatterbox-tts install so pip finds
    # torch satisfied and doesn't re-resolve to a CPU/mismatched wheel.
    lines = k.splitlines()
    torch_line = next((i for i, l in enumerate(lines)
                       if 'pip' in l and '"torch==' in l or ('torch==' in l and 'index-url' in l)), None)
    cbx_line = next((i for i, l in enumerate(lines)
                     if '"chatterbox-tts"' in l), None)
    assert torch_line is not None and cbx_line is not None, "couldn't locate the pip install lines"
    assert torch_line < cbx_line, "CUDA torch must be installed BEFORE chatterbox-tts, else it re-resolves"
    assert 'refusing CPU run' in k or 'cuda_available' in k, "kernel dropped the GPU gate — could run CPU unnoticed"
    assert 'setuptools<81' in k, "perth watermarker needs setuptools<81 (pkg_resources removed in 81+)"


def test_health_reports_cuda():
    for name, src in [('chatterbox', CB_SERVER), ('tada', TADA_SERVER)]:
        assert 'cuda_available' in src, f"{name} /health no longer reports CUDA — GPU issues undiagnosable"


# --- engine health lockdown ---

def test_engine_offline_queue_gate():
    assert 'engine is offline' in APP and 'check_engines_health' in APP, \
        "409 engine-offline gate removed — jobs can queue into dead engines again"


# --- GPU cost safety ---

def test_gpu_render_gate_default_off():
    assert "gpu_render_enabled" in APP and "GPU_RENDER_ENABLED', '0'" in APP.replace('"', "'"), \
        "GPU render gate weakened — paid GPU no longer default-off"


# --- incident 2026-07-08: cross-process recovery race ---

def test_recovery_has_cross_process_lock():
    """Resume API (webapp) and orphan cleanup (worker) raced two recovery
    threads; in-memory guards cannot work across processes."""
    assert 'recovery_lock_' in APP,         "cross-process recovery DB lock removed — re-opens 2026-07-08 recovery race"


# --- audio quality fixes 2026-07-08 ---

def test_dashes_not_forced_to_commas():
    """Dash-heavy prose produced constant pauses when every dash became a comma."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('tp', ROOT / 'webapp' / 'tts_preprocess.py')
    tp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
    out = tp.normalize_text_for_tts("Apple — the company — grew.")
    assert ', the company ,' not in out, "em-dash still forced to comma (pause regression 2026-07-08)"


def test_tada_first_word_leadin_trim():
    assert '_trim_leadin' in TADA_SERVER and 'LEADIN' in TADA_SERVER,         "TADA first-word lead-in trim removed — cold-start garble returns"


def test_qa_layer2_wired():
    """QA Layer 2 (ASR verification — the self-correcting loop) must stay
    reachable: the diff core exists and convert_book exposes --qa."""
    qa = (ROOT / 'webapp' / 'qa_asr.py').read_text(encoding='utf-8')
    assert 'def diff_report' in qa and 'def verify_chapter' in qa, "QA Layer 2 core removed (#7)"
    cb = (ROOT / 'scripts' / 'convert_book.py').read_text(encoding='utf-8')
    assert '--qa' in cb, "convert_book lost the --qa hook — QA Layer 2 unreachable (#7)"


def test_preprocess_reads_engine_from_job_not_unset_local():
    """convert_book's preprocessing runs BEFORE the local `tts_engine` is
    assigned; it must read the engine from the job. Referencing the not-yet-set
    local threw at runtime and silently fell back to raw text — none of the
    modern-contract preprocessing applied (caught on the real worker path,
    2026-07-08)."""
    assert '_modern = tts_engine in' not in APP, \
        "preprocess block references tts_engine before it is assigned (use-before-assign regression)"
    assert 'modern=_modern' in APP, "modern-contract preprocessing no longer wired into convert_book"


def test_preprocessing_llm_provider_chain():
    """#6: the narration profile must degrade through providers to a seed floor,
    never straight to {} (which drops all pronunciation help)."""
    lm = (ROOT / 'webapp' / 'llm_metadata.py').read_text(encoding='utf-8')
    assert '_call_llm_json_chain' in lm and '_fallback_settings' in lm, "LLM provider chain removed (#6)"
    assert 'SEED_RULES' in lm and '_seed_profile' in lm, "seed-rule floor removed (#6)"


def test_recovery_frees_slot_when_container_missing():
    """#14: a 'converting' job whose container is gone after a restart must be
    failed (freeing the single MAX_CONCURRENT slot), not left stuck holding the
    queue. resume_inflight_jobs must have the else-branch that fails it."""
    assert "container missing after worker restart" in APP, \
        "recovery no longer fails zombie jobs — queue-jam regression (#14)"


def test_conversion_engine_failover_wired():
    """#6: a dead engine must be able to fail over to a healthy one instead of
    always hard-stranding a book."""
    assert 'pick_engine_with_fallback' in APP and '_ENGINE_FALLBACK_ORDER' in APP, \
        "conversion engine failover helper removed (#6)"
    assert 'allow_engine_fallback' in APP, "engine failover not wired into the queue gate (#6)"


def _load_tp():
    import importlib.util
    spec = importlib.util.spec_from_file_location('tp2', ROOT / 'webapp' / 'tts_preprocess.py')
    tp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
    return tp


def test_modern_engines_keep_raw_years():
    """Spelling '1976'->'nineteen seventy-six' made TADA pause before the last
    digit, so years sounded like endnote numbers ('1976' heard as '1970...6').
    Modern engines must keep raw years/numbers (incident 2026-07-08)."""
    tp = _load_tp()
    out = tp.normalize_text_for_tts("founded in 1976, returned in 1997.", modern=True)
    assert '1976' in out and '1997' in out and 'seventy-six' not in out,         "modern engine year-spelling regressed — re-opens 2026-07-08 '1970...6' artifact"
    # legacy path still spells (unchanged for Kokoro/Piper)
    leg = tp.normalize_text_for_tts("founded in 1976.", modern=False)
    assert 'seventy-six' in leg, "legacy year spelling broken"


def test_modern_contract_skips_all_plain_number_spelling():
    """MODERN-ENGINE CONTRACT: modern engines read plain numbers/years/decades/
    large integers natively. Every plain-number spelling transform must sit
    under the single `if not modern:` guard so we stop discovering these one
    incident at a time (2026-07-08). Symbol/abbrev expansion still applies."""
    tp = _load_tp()
    cases = {
        "It was the 1990s.":        ('1990s', 'nineties'),   # decade
        "a crowd of 2,905 people":  ('2,905', 'nine hundred'),  # comma-number
        "the figure hit 45000":     ('45000', 'forty-five thousand'),  # large int
    }
    for text, (keep, must_not) in cases.items():
        out = tp.normalize_text_for_tts(text, modern=True)
        assert keep in out and must_not not in out, (
            f"modern engine spelled a plain number ({text!r} -> {out!r}) — "
            "re-opens the mid-number pause artifact class (2026-07-08)")
    # Revised 2026-07-09 (minimal-for-modern): modern KEEPS only acronym
    # letter-spacing (U.S.->U S, which genuinely helps) but SKIPS %/$/1st and
    # word-abbrev expansion — it reads those natively, and blind expansion
    # misfired ("Main St."->"Main Saint", "Coo-per-TEE-no").
    sym = tp.normalize_text_for_tts("the U.S. had 50% and Dr. Lee left on 1st", modern=True)
    assert 'U S' in sym, "modern dropped acronym letter-spacing (U.S.->U S helps)"
    assert 'percent' not in sym and 'Doctor' not in sym and 'first' not in sym, \
        "modern still expanding %/Dr./ordinals — should read them natively (minimal contract)"
    # legacy engines still get the full expansion
    leg = tp.normalize_text_for_tts("about 50% and Dr. Lee", modern=False)
    assert 'percent' in leg and 'Doctor' in leg, "legacy expansion broken"


def test_modern_keeps_acronym_letter_spacing_only():
    """Modern engines misread undotted initialisms ("CEO" heard as "see you",
    2026-07-10) — acronym LETTER-SPACING lexicon rules are the one class that
    must still apply for modern. Phonetic respellings stay banned."""
    tp = _load_tp()
    lex = {"CEO": "C E O", "IPO": "I P O", "Beijing": "Bay-JING"}
    out = tp.normalize_text_for_tts("The CEO priced the IPO in Beijing.", lexicon=lex, modern=True)
    assert 'C E O' in out and 'I P O' in out, "acronym letter-spacing dropped for modern ('see you' regression)"
    assert 'Bay-JING' not in out and 'Beijing' in out, "phonetic respelling leaked into modern"


def test_modern_skips_phonetic_lexicon():
    """Modern engines read Beijing/Cupertino natively; the phonetic respelling
    lexicon ("Bay-JING","Coo-per-TEE-no") makes them read broken syllables
    ("bay...zhing"). Modern must SKIP the lexicon (Dave, 2026-07-09)."""
    tp = _load_tp()
    lex = {"Beijing": "Bay-JING", "Cupertino": "Coo-per-TEE-no", "iPhones": "eye-phones"}
    out = tp.normalize_text_for_tts("Broken iPhones in Beijing near Cupertino.", lexicon=lex, modern=True)
    assert 'Bay-JING' not in out and 'Coo-per-TEE-no' not in out and 'eye-phones' not in out, \
        "modern engine applied phonetic respelling — re-opens the 'bay...zhing' breakage"
    assert 'Beijing' in out and 'Cupertino' in out and 'iPhones' in out
    # legacy engines (Kokoro/Piper) still get the respelling — they need it
    leg = tp.normalize_text_for_tts("We flew to Beijing.", lexicon=lex, modern=False)
    assert 'Bay-JING' in leg, "legacy lexicon respelling broken"
